from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from typing import Any


WORK_SUMMARY_SCHEMA_NAME = "GovernedExecutionWorkSummary"
WORK_SUMMARY_SCHEMA_VERSION = "governed_execution_work_summary_v1"
FILE_PLAN_SCHEMA_NAME = "GovernedExecutionFilePlan"
FILE_PLAN_SCHEMA_VERSION = "governed_execution_file_plan_v1"
IMPLEMENTATION_BUNDLE_SCHEMA_NAME = "GovernedExecutionImplementationBundleSummary"
IMPLEMENTATION_BUNDLE_SCHEMA_VERSION = "governed_execution_implementation_bundle_summary_v1"
WORKSPACE_ARTIFACT_INDEX_SCHEMA_NAME = "GovernedExecutionWorkspaceArtifactIndex"
WORKSPACE_ARTIFACT_INDEX_SCHEMA_VERSION = "governed_execution_workspace_artifact_index_v1"
CONTROLLER_SUMMARY_SCHEMA_NAME = "GovernedExecutionControllerSummary"
CONTROLLER_SUMMARY_SCHEMA_VERSION = "governed_execution_controller_summary_v1"
CYCLE_EXECUTION_MODEL = "single_cycle_per_governed_execution_invocation"
MULTI_CYCLE_EXECUTION_MODEL = "multi_cycle_bounded_governed_execution"
STOP_REASON_COMPLETED = "completed_by_directive_stop_condition"
STOP_REASON_NO_WORK = "no_admissible_bounded_work"
STOP_REASON_BLOCKED = "blocked_by_policy"
STOP_REASON_FAILURE = "bounded_failure"
STOP_REASON_MAX_CAP = "max_cycle_cap_reached"
STOP_REASON_SINGLE_CYCLE = "single_cycle_invocation_completed"
SUPPORTED_FIRST_WORK_ACTION_CLASSES = {
    "low_risk_shell_change",
    "diagnostic_schema_materialization",
    "append_only_ledger_write",
}
WORKSPACE_ARTIFACT_CATEGORIES = ("plans", "docs", "src", "tests", "artifacts")


class GovernedExecutionFailure(RuntimeError):
    def __init__(self, message: str, *, session_artifact_path: str = "", summary_artifact_path: str = "") -> None:
        self.session_artifact_path = str(session_artifact_path)
        self.summary_artifact_path = str(summary_artifact_path)
        super().__init__(message)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dump(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def session_artifact_path(workspace_root: str | Path) -> Path:
    return Path(workspace_root) / "artifacts" / "governed_execution_session_latest.json"


def load_session_summary(workspace_root: str | Path | None) -> dict[str, Any]:
    if not workspace_root:
        return {}
    return load_json(session_artifact_path(workspace_root))


def controller_artifact_path(workspace_root: str | Path) -> Path:
    return Path(workspace_root) / "artifacts" / "governed_execution_controller_latest.json"


def load_controller_summary(workspace_root: str | Path | None) -> dict[str, Any]:
    if not workspace_root:
        return {}
    return load_json(controller_artifact_path(workspace_root))


def _append_event(log_path: Path, payload: dict[str, Any]) -> None:
    if str(log_path) in {"", "."}:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _event(
    log_path: Path,
    *,
    event_type: str,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
    workspace_root: str,
    **extra: Any,
) -> None:
    _append_event(
        log_path,
        {
            "event_type": event_type,
            "timestamp": _now(),
            "session_id": session_id,
            "directive_id": directive_id,
            "execution_profile": execution_profile,
            "workspace_id": workspace_id,
            "workspace_root": workspace_root,
            **dict(extra),
        },
    )


def _write_text(
    path: Path,
    text: str,
    *,
    log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
    workspace_root: str,
    work_item_id: str,
    artifact_kind: str,
) -> None:
    _event(
        log_path,
        event_type="file_write_planned",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=workspace_root,
        work_item_id=work_item_id,
        artifact_kind=artifact_kind,
        path=str(path),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _event(
        log_path,
        event_type="file_write_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=workspace_root,
        work_item_id=work_item_id,
        artifact_kind=artifact_kind,
        path=str(path),
        bytes_written=len(text.encode("utf-8")),
    )


def _write_json(path: Path, payload: dict[str, Any], **kwargs: Any) -> None:
    _write_text(path, _dump(payload), **kwargs)


def _relative_to_workspace(workspace_root: Path, path: Path) -> str:
    return path.relative_to(workspace_root).as_posix()


def _classify_workspace_artifact(relative_path: str) -> str:
    parts = [part for part in Path(relative_path).parts if part not in {"."}]
    if not parts:
        return "other"
    root = parts[0]
    return root if root in WORKSPACE_ARTIFACT_CATEGORIES else "other"


def _build_workspace_artifact_index_payload(workspace_root: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    category_counts: dict[str, int] = {}
    for path in sorted(workspace_root.rglob("*")):
        if not path.is_file():
            continue
        relative_path = _relative_to_workspace(workspace_root, path)
        category = _classify_workspace_artifact(relative_path)
        category_counts[category] = category_counts.get(category, 0) + 1
        records.append(
            {
                "relative_path": relative_path,
                "category": category,
                "size_bytes": int(path.stat().st_size),
            }
        )
    next_recommended_cycle = "materialize_workspace_local_implementation"
    has_python_source = any(
        item["category"] == "src" and str(item["relative_path"]).endswith(".py")
        for item in records
    )
    has_python_tests = any(
        item["category"] == "tests" and str(item["relative_path"]).endswith(".py")
        for item in records
    )
    if has_python_source and has_python_tests:
        next_recommended_cycle = "review_and_expand_workspace_local_implementation"
    elif has_python_source:
        next_recommended_cycle = "add_workspace_local_tests"
    return {
        "schema_name": WORKSPACE_ARTIFACT_INDEX_SCHEMA_NAME,
        "schema_version": WORKSPACE_ARTIFACT_INDEX_SCHEMA_VERSION,
        "generated_at": _now(),
        "workspace_root": str(workspace_root),
        "artifact_count": len(records),
        "category_counts": category_counts,
        "artifacts": records,
        "next_recommended_cycle": next_recommended_cycle,
    }


def _workspace_paths(workspace_root: Path) -> dict[str, Path]:
    return {
        "docs_root": workspace_root / "docs",
        "src_root": workspace_root / "src",
        "tests_root": workspace_root / "tests",
        "artifacts_root": workspace_root / "artifacts",
        "cycles_root": workspace_root / "artifacts" / "cycles",
        "plans_root": workspace_root / "plans",
        "plan_path": workspace_root / "plans" / "bounded_work_cycle_plan.md",
        "design_path": workspace_root / "docs" / "mutable_shell_successor_design_note.md",
        "src_readme_path": workspace_root / "src" / "README.md",
        "tests_readme_path": workspace_root / "tests" / "README.md",
        "file_plan_path": workspace_root / "artifacts" / "bounded_work_file_plan.json",
        "summary_path": workspace_root / "artifacts" / "bounded_work_summary_latest.json",
        "implementation_summary_path": workspace_root / "artifacts" / "implementation_bundle_summary_latest.json",
        "workspace_artifact_index_path": workspace_root / "artifacts" / "workspace_artifact_index_latest.json",
        "controller_summary_path": workspace_root / "artifacts" / "governed_execution_controller_latest.json",
        "implementation_note_path": workspace_root / "docs" / "successor_shell_iteration_notes.md",
        "implementation_package_root": workspace_root / "src" / "successor_shell",
        "implementation_init_path": workspace_root / "src" / "successor_shell" / "__init__.py",
        "implementation_module_path": workspace_root / "src" / "successor_shell" / "workspace_contract.py",
        "implementation_test_path": workspace_root / "tests" / "test_workspace_contract.py",
    }


def _workspace_baseline(workspace_root: Path) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    baseline_paths = [
        paths["plan_path"],
        paths["design_path"],
        paths["file_plan_path"],
        paths["summary_path"],
        paths["src_readme_path"],
        paths["tests_readme_path"],
    ]
    planning_summary = load_json(paths["summary_path"])
    return {
        **paths,
        "baseline_artifact_paths": [str(path) for path in baseline_paths if path.exists()],
        "has_planning_baseline": all(path.exists() for path in baseline_paths),
        "planning_summary": planning_summary,
        "implementation_materialized": all(
            path.exists()
            for path in (
                paths["implementation_init_path"],
                paths["implementation_module_path"],
                paths["implementation_test_path"],
                paths["implementation_note_path"],
                paths["implementation_summary_path"],
            )
        ),
    }


def _invocation_model_for_mode(controller_mode: str) -> str:
    return (
        MULTI_CYCLE_EXECUTION_MODEL
        if str(controller_mode).strip() == "multi_cycle"
        else CYCLE_EXECUTION_MODEL
    )


def _cycle_summary_archive_path(workspace_root: Path, cycle_index: int) -> Path:
    return _workspace_paths(workspace_root)["cycles_root"] / f"cycle_{int(cycle_index):03d}_summary.json"


def _directive_completion_evaluation(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    latest_cycle_summary: dict[str, Any],
) -> dict[str, Any]:
    baseline = _workspace_baseline(workspace_root)
    text_blob = " ".join(
        [
            str(current_directive.get("directive_text", "")).strip(),
            str(current_directive.get("clarified_intent_summary", "")).strip(),
            *[str(item).strip() for item in list(current_directive.get("success_criteria", []))],
            *[
                str(dict(item).get("completion_signal", "")).strip()
                for item in list(current_directive.get("milestone_model", []))
            ],
        ]
    ).lower()
    requires_design = any(token in text_blob for token in ("design", "architecture"))
    requires_implementation = any(token in text_blob for token in ("implement", "implementation"))
    requires_tests = "test" in text_blob
    requires_documentation = any(token in text_blob for token in ("document", "documentation"))

    deliverable_checks = [
        {
            "deliverable_id": "planning_bundle",
            "required": True,
            "completed": bool(baseline.get("has_planning_baseline", False)),
            "evidence_paths": list(baseline.get("baseline_artifact_paths", [])),
        },
        {
            "deliverable_id": "design_note",
            "required": requires_design,
            "completed": bool(baseline["design_path"].exists()),
            "evidence_paths": [str(baseline["design_path"])] if baseline["design_path"].exists() else [],
        },
        {
            "deliverable_id": "implementation_module",
            "required": requires_implementation,
            "completed": bool(baseline["implementation_module_path"].exists()),
            "evidence_paths": [str(baseline["implementation_module_path"])]
            if baseline["implementation_module_path"].exists()
            else [],
        },
        {
            "deliverable_id": "test_module",
            "required": requires_tests,
            "completed": bool(baseline["implementation_test_path"].exists()),
            "evidence_paths": [str(baseline["implementation_test_path"])]
            if baseline["implementation_test_path"].exists()
            else [],
        },
        {
            "deliverable_id": "documentation_note",
            "required": requires_documentation,
            "completed": bool(baseline["implementation_note_path"].exists()),
            "evidence_paths": [str(baseline["implementation_note_path"])]
            if baseline["implementation_note_path"].exists()
            else [],
        },
    ]
    required_checks = [item for item in deliverable_checks if bool(item.get("required", False))]
    explicit_directive_completion = bool(required_checks) and all(
        bool(item.get("completed", False))
        for item in required_checks
    )
    fallback_used = False
    if not required_checks:
        fallback_used = True
        explicit_directive_completion = bool(baseline.get("implementation_materialized", False))

    latest_cycle_kind = str(latest_cycle_summary.get("cycle_kind", "")).strip()
    if (
        explicit_directive_completion
        and latest_cycle_kind == "planning_only"
        and not bool(baseline.get("implementation_materialized", False))
    ):
        explicit_directive_completion = False
    completion_reason = (
        "required directive deliverables are present inside the bounded active workspace"
        if explicit_directive_completion
        else (
            "planning baseline exists, but implementation-bearing deliverables are still absent"
            if latest_cycle_kind == "planning_only" and not bool(baseline.get("implementation_materialized", False))
            else
            "no explicit directive completion deliverables could be derived safely; conservative fallback remains incomplete"
            if fallback_used
            else "directive-derived bounded deliverables are not all present yet"
        )
    )
    return {
        "directive_completion_possible": bool(required_checks) or fallback_used,
        "fallback_used": fallback_used,
        "completed": explicit_directive_completion,
        "latest_cycle_kind": latest_cycle_kind,
        "reason": completion_reason,
        "required_deliverable_count": len(required_checks),
        "deliverable_checks": deliverable_checks,
        "recommended_stop": explicit_directive_completion,
    }


def _augment_cycle_payloads(
    *,
    payload: dict[str, Any],
    workspace_root: Path,
    cycle_index: int,
    controller_mode: str,
    latest_cycle_summary: dict[str, Any],
    completion_evaluation: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], str]:
    invocation_model = _invocation_model_for_mode(controller_mode)
    summary_artifact_path = str(
        dict(payload.get("work_cycle", {})).get("summary_artifact_path", "")
    ).strip() or str(_workspace_paths(workspace_root)["summary_path"])
    cycle_archive_path = _cycle_summary_archive_path(workspace_root, cycle_index)
    augmented_summary = {
        **dict(latest_cycle_summary),
        "cycle_index": int(cycle_index),
        "invocation_model": invocation_model,
        "controller_mode": str(controller_mode),
        "cycle_summary_archive_path": str(cycle_archive_path),
        "directive_completion_evaluation": completion_evaluation,
    }
    cycle_archive_path.parent.mkdir(parents=True, exist_ok=True)
    Path(summary_artifact_path).write_text(_dump(augmented_summary), encoding="utf-8")
    cycle_archive_path.write_text(_dump(augmented_summary), encoding="utf-8")

    work_cycle = {
        **dict(payload.get("work_cycle", {})),
        "cycle_index": int(cycle_index),
        "invocation_model": invocation_model,
        "controller_mode": str(controller_mode),
        "cycle_summary_archive_path": str(cycle_archive_path),
        "directive_completion_evaluation": completion_evaluation,
    }
    updated_payload = {
        **dict(payload),
        "work_cycle": work_cycle,
    }
    return updated_payload, augmented_summary, str(cycle_archive_path)


def _implementation_module_source(*, directive_id: str) -> str:
    return (
        dedent(
            f'''
            """Workspace-local helper for bounded successor review.

            Generated during a governed implementation-bearing cycle for
            `{directive_id}`.
            """

            from __future__ import annotations

            from dataclasses import asdict, dataclass
            from pathlib import Path
            from typing import Iterable


            KNOWN_WORKSPACE_CATEGORIES = ("plans", "docs", "src", "tests", "artifacts", "other")


            @dataclass(frozen=True)
            class WorkspaceArtifactRecord:
                relative_path: str
                category: str
                size_bytes: int


            def classify_workspace_artifact(relative_path: str) -> str:
                parts = [part for part in Path(relative_path).parts if part not in {{'.'}}]
                if not parts:
                    return "other"
                root = parts[0]
                if root in KNOWN_WORKSPACE_CATEGORIES[:-1]:
                    return root
                return "other"


            def iter_workspace_artifact_records(workspace_root: str | Path) -> list[WorkspaceArtifactRecord]:
                root = Path(workspace_root)
                if not root.exists():
                    return []
                records: list[WorkspaceArtifactRecord] = []
                for path in sorted(root.rglob("*")):
                    if not path.is_file():
                        continue
                    relative_path = path.relative_to(root).as_posix()
                    records.append(
                        WorkspaceArtifactRecord(
                            relative_path=relative_path,
                            category=classify_workspace_artifact(relative_path),
                            size_bytes=path.stat().st_size,
                        )
                    )
                return records


            def recommend_next_cycle(records: Iterable[WorkspaceArtifactRecord]) -> str:
                record_list = list(records)
                has_python_source = any(
                    record.category == "src" and record.relative_path.endswith(".py")
                    for record in record_list
                )
                has_python_tests = any(
                    record.category == "tests" and record.relative_path.endswith(".py")
                    for record in record_list
                )
                if has_python_source and has_python_tests:
                    return "review_and_expand_workspace_local_implementation"
                if has_python_source:
                    return "add_workspace_local_tests"
                return "materialize_workspace_local_implementation"


            def build_workspace_artifact_index(workspace_root: str | Path) -> dict[str, object]:
                records = iter_workspace_artifact_records(workspace_root)
                category_counts: dict[str, int] = {{}}
                for record in records:
                    category_counts[record.category] = category_counts.get(record.category, 0) + 1
                return {{
                    "workspace_root": str(Path(workspace_root)),
                    "artifact_count": len(records),
                    "category_counts": category_counts,
                    "artifacts": [asdict(record) for record in records],
                    "next_recommended_cycle": recommend_next_cycle(records),
                }}


            def render_workspace_artifact_report(workspace_root: str | Path) -> str:
                index = build_workspace_artifact_index(workspace_root)
                lines = [
                    "Workspace Artifact Index",
                    "",
                    f"Workspace root: {{index['workspace_root']}}",
                    f"Artifact count: {{index['artifact_count']}}",
                    f"Next recommended cycle: {{index['next_recommended_cycle']}}",
                    "",
                    "Categories:",
                ]
                for category, count in sorted(dict(index["category_counts"]).items()):
                    lines.append(f"- {{category}}: {{count}}")
                return "\\n".join(lines)
            '''
        ).strip()
        + "\n"
    )


def _implementation_init_source() -> str:
    return (
        dedent(
            """
            \"\"\"Workspace-local successor shell helpers.\"\"\"

            from .workspace_contract import (
                build_workspace_artifact_index,
                classify_workspace_artifact,
                recommend_next_cycle,
                render_workspace_artifact_report,
            )

            __all__ = [
                "build_workspace_artifact_index",
                "classify_workspace_artifact",
                "recommend_next_cycle",
                "render_workspace_artifact_report",
            ]
            """
        ).strip()
        + "\n"
    )


def _implementation_test_source() -> str:
    return (
        dedent(
            """
            from __future__ import annotations

            import importlib.util
            import sys
            import tempfile
            import unittest
            from pathlib import Path


            def _load_workspace_contract_module():
                module_path = Path(__file__).resolve().parents[1] / "src" / "successor_shell" / "workspace_contract.py"
                spec = importlib.util.spec_from_file_location("workspace_contract", module_path)
                if spec is None or spec.loader is None:
                    raise RuntimeError(f"Unable to load workspace contract module from {module_path}")
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)
                return module


            class WorkspaceContractTests(unittest.TestCase):
                def test_build_workspace_artifact_index_groups_workspace_outputs(self) -> None:
                    module = _load_workspace_contract_module()
                    with tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        (root / "plans").mkdir(parents=True, exist_ok=True)
                        (root / "src").mkdir(parents=True, exist_ok=True)
                        (root / "tests").mkdir(parents=True, exist_ok=True)
                        (root / "plans" / "bounded_work_cycle_plan.md").write_text("plan", encoding="utf-8")
                        (root / "src" / "module.py").write_text("print('ok')\\n", encoding="utf-8")
                        (root / "tests" / "test_module.py").write_text("assert True\\n", encoding="utf-8")

                        index = module.build_workspace_artifact_index(root)

                        self.assertEqual(index["category_counts"]["plans"], 1)
                        self.assertEqual(index["category_counts"]["src"], 1)
                        self.assertEqual(index["category_counts"]["tests"], 1)
                        self.assertEqual(
                            index["next_recommended_cycle"],
                            "review_and_expand_workspace_local_implementation",
                        )

                def test_render_workspace_artifact_report_mentions_workspace_root(self) -> None:
                    module = _load_workspace_contract_module()
                    with tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        (root / "artifacts").mkdir(parents=True, exist_ok=True)
                        (root / "artifacts" / "summary.json").write_text("{}", encoding="utf-8")

                        report = module.render_workspace_artifact_report(root)

                        self.assertIn("Workspace Artifact Index", report)
                        self.assertIn(str(root), report)


            if __name__ == "__main__":
                unittest.main()
            """
        ).strip()
        + "\n"
    )


def _implementation_note_text(
    *,
    directive_id: str,
    workspace_id: str,
    implementation_bundle_kind: str,
    deferred_items: list[dict[str, str]],
) -> str:
    return (
        "\n".join(
            [
                "# Successor Shell Iteration Notes",
                "",
                f"Directive ID: `{directive_id}`",
                f"Workspace: `{workspace_id}`",
                f"Implementation bundle: `{implementation_bundle_kind}`",
                "",
                "This cycle advances the workspace from planning-only artifacts into a small real implementation bundle.",
                "",
                "Implemented now:",
                "- a workspace-local Python package export under `src/successor_shell/`",
                "- a real artifact-index and review helper module under `src/successor_shell/workspace_contract.py`",
                "- an executable regression module under `tests/test_workspace_contract.py`",
                "- operator-readable JSON summaries for the implementation bundle and workspace artifact index",
                "",
                "Still deferred:",
                *[f"- {item['item']}: {item['reason']}" for item in deferred_items],
                "",
            ]
        )
        + "\n"
    )


def _select_planning_work_item(current_directive: dict[str, Any]) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    skipped = [
        {
            "work_item_id": "protected_surface_rewrite_candidate",
            "reason": "protected-surface and immutable-kernel mutation remain excluded by default",
        }
    ]
    allowed = {
        str(item).strip()
        for item in list(current_directive.get("allowed_action_classes", []))
        if str(item).strip()
    }
    admissible = sorted(allowed & SUPPORTED_FIRST_WORK_ACTION_CLASSES)
    text = str(current_directive.get("directive_text", "")).strip()
    clarified = str(current_directive.get("clarified_intent_summary", "")).strip()
    if not text and not clarified:
        skipped.append(
            {
                "work_item_id": "bounded_successor_workspace_bundle",
                "reason": "directive text and clarified intent summary are missing",
            }
        )
        return None, skipped
    if not admissible:
        skipped.append(
            {
                "work_item_id": "bounded_successor_workspace_bundle",
                "reason": "no admissible first-cycle action classes are enabled",
            }
        )
        return None, skipped
    return (
        {
            "work_item_id": "bounded_successor_workspace_bundle",
            "title": "Produce a bounded successor-planning bundle inside the active workspace.",
            "selected_action_classes": admissible,
            "rationale": "start with workspace-local planning, design, and scaffold outputs only",
            "cycle_kind": "planning_only",
        },
        skipped,
    )


def _select_implementation_work_item(
    current_directive: dict[str, Any],
    *,
    baseline: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    skipped = [
        {
            "work_item_id": "protected_surface_rewrite_candidate",
            "reason": "protected-surface and immutable-kernel mutation remain excluded by default",
        }
    ]
    allowed = {
        str(item).strip()
        for item in list(current_directive.get("allowed_action_classes", []))
        if str(item).strip()
    }
    admissible = sorted(allowed & SUPPORTED_FIRST_WORK_ACTION_CLASSES)
    if not baseline.get("has_planning_baseline", False):
        skipped.append(
            {
                "work_item_id": "implementation_bundle_workspace_contract",
                "reason": "planning baseline artifacts are missing from the active workspace",
            }
        )
        return None, skipped
    if not admissible:
        skipped.append(
            {
                "work_item_id": "implementation_bundle_workspace_contract",
                "reason": "no admissible implementation-cycle action classes are enabled",
            }
        )
        return None, skipped
    if baseline.get("implementation_materialized", False):
        skipped.append(
            {
                "work_item_id": "implementation_bundle_workspace_contract",
                "reason": "the first implementation bundle already exists; further implementation is deferred to a later reviewed cycle",
            }
        )
        return None, skipped
    return (
        {
            "work_item_id": "implementation_bundle_workspace_contract",
            "title": "Materialize a workspace-local artifact contract and review helper bundle.",
            "selected_action_classes": admissible,
            "rationale": "build a small real code/test bundle directly from the existing planning baseline",
            "implementation_bundle_kind": "workspace_artifact_contract",
            "cycle_kind": "implementation_bearing",
        },
        skipped,
    )


def _finalize_session_artifacts(
    *,
    payload: dict[str, Any],
    session_artifact_path: Path,
    session_archive_path: Path,
    brief_path: Path,
    brief_lines: list[str],
) -> None:
    session_text = _dump(payload)
    session_artifact_path.write_text(session_text, encoding="utf-8")
    session_archive_path.write_text(session_text, encoding="utf-8")
    brief_path.write_text("\n".join(brief_lines).strip() + "\n", encoding="utf-8")


def _complete_no_admissible_work(
    *,
    payload: dict[str, Any],
    workspace_root: Path,
    plans_root: Path,
    summary_path: Path,
    session_artifact_path: Path,
    session_archive_path: Path,
    brief_path: Path,
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
    skipped: list[dict[str, str]],
    reason: str,
    include_implementation_deferred_event: bool = False,
) -> dict[str, Any]:
    explanation_path = plans_root / "no_admissible_bounded_work.md"
    _write_text(
        explanation_path,
        "# No Admissible Bounded Work\n\n- " + "\n- ".join(item["reason"] for item in skipped) + "\n",
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id="no_admissible_bounded_work",
        artifact_kind="no_work_explanation_markdown",
    )
    work_summary = {
        "schema_name": WORK_SUMMARY_SCHEMA_NAME,
        "schema_version": WORK_SUMMARY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "status": "no_admissible_bounded_work",
        "cycle_kind": "no_admissible_bounded_work",
        "invocation_model": CYCLE_EXECUTION_MODEL,
        "reason": reason,
        "selected_work_item": {},
        "skipped_work_items": skipped,
        "output_artifact_paths": [str(explanation_path), str(summary_path)],
        "newly_created_paths": [str(explanation_path)],
        "deferred_items": skipped,
        "next_recommended_cycle": "operator_review_required",
    }
    _write_json(
        summary_path,
        work_summary,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id="no_admissible_bounded_work",
        artifact_kind="bounded_work_summary_json",
    )
    payload.update(
        {
            "generated_at": _now(),
            "directive_id": directive_id,
            "status": "no_admissible_bounded_work",
            "reason": reason,
            "work_cycle": {
                "work_item_id": "no_admissible_bounded_work",
                "cycle_kind": "no_admissible_bounded_work",
                "invocation_model": CYCLE_EXECUTION_MODEL,
                "summary_artifact_path": str(summary_path),
                "output_artifact_paths": list(work_summary["output_artifact_paths"]),
                "newly_created_paths": [str(explanation_path)],
                "skipped_work_items": skipped,
                "next_recommended_cycle": "operator_review_required",
            },
        }
    )
    _finalize_session_artifacts(
        payload=payload,
        session_artifact_path=session_artifact_path,
        session_archive_path=session_archive_path,
        brief_path=brief_path,
        brief_lines=[
            "# Governed Execution Brief",
            "",
            "Status: no_admissible_bounded_work",
            f"Reason: {reason}",
            f"Explanation: {explanation_path}",
        ],
    )
    if include_implementation_deferred_event:
        _event(
            runtime_event_log_path,
            event_type="implementation_bundle_deferred",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            reason=reason,
            explanation_path=str(explanation_path),
        )
    _event(
        runtime_event_log_path,
        event_type="no_admissible_bounded_work",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        explanation_path=str(explanation_path),
        summary_artifact_path=str(summary_path),
    )
    _event(
        runtime_event_log_path,
        event_type="work_loop_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        status="no_admissible_bounded_work",
        output_artifact_paths=list(work_summary["output_artifact_paths"]),
    )
    return payload


def _run_planning_cycle(
    *,
    payload: dict[str, Any],
    current_directive: dict[str, Any],
    workspace_root: Path,
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
    session_artifact_path: Path,
    session_archive_path: Path,
    brief_path: Path,
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    selected, skipped = _select_planning_work_item(current_directive)
    for item in skipped:
        _event(
            runtime_event_log_path,
            event_type="work_item_skipped",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=str(item.get("work_item_id", "")),
            reason=str(item.get("reason", "")),
        )

    if not selected:
        return _complete_no_admissible_work(
            payload=payload,
            workspace_root=workspace_root,
            plans_root=paths["plans_root"],
            summary_path=paths["summary_path"],
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            skipped=skipped,
            reason="no admissible bounded first work item was available under the current directive and action-class constraints",
        )

    _event(
        runtime_event_log_path,
        event_type="work_item_selected",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        title=str(selected.get("title", "")),
        rationale=str(selected.get("rationale", "")),
        selected_action_classes=list(selected.get("selected_action_classes", [])),
    )
    directive_text = str(current_directive.get("directive_text", "")).strip()
    clarified = str(current_directive.get("clarified_intent_summary", "")).strip()
    constraints = [str(item) for item in list(current_directive.get("constraints", []))]
    trusted_sources = [str(item) for item in list(current_directive.get("trusted_sources", []))]
    success_criteria = [str(item) for item in list(current_directive.get("success_criteria", []))]
    deferred_items = [
        {
            "item": "workspace_local_implementation_bundle",
            "reason": "this first cycle is intentionally planning-only so the next cycle can implement from an explicit baseline",
        },
        {
            "item": "protected_surface_mutation",
            "reason": "protected-surface and immutable-kernel mutation remain excluded by default",
        },
    ]

    _write_text(
        paths["plan_path"],
        "\n".join(
            [
                "# Bounded Work Cycle Plan",
                "",
                f"Directive ID: `{directive_id}`",
                f"Workspace: `{workspace_id} -> {workspace_root}`",
                "",
                directive_text or clarified,
                "",
                "Writable roots:",
                *[f"- `{item}`" for item in list(payload.get("allowed_write_roots", []))],
                "",
                "Protected roots:",
                *[f"- `{item}`" for item in list(payload.get("protected_root_hints", []))],
                "",
                "Selected outputs:",
                "- `plans/bounded_work_cycle_plan.md`",
                "- `docs/mutable_shell_successor_design_note.md`",
                "- `src/README.md`",
                "- `tests/README.md`",
                "- `artifacts/bounded_work_file_plan.json`",
                "- `artifacts/bounded_work_summary_latest.json`",
                "",
            ]
        )
        + "\n",
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="work_plan_markdown",
    )
    _write_text(
        paths["design_path"],
        "\n".join(
            [
                "# Mutable-Shell Successor Design Note",
                "",
                clarified or directive_text,
                "",
                "Binding constraints:",
                *[f"- {item}" for item in constraints],
                "",
                "Trusted sources in scope:",
                *[f"- `{item}`" for item in trusted_sources],
                "",
                "Success criteria carried forward:",
                *[f"- {item}" for item in success_criteria],
                "",
            ]
        )
        + "\n",
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="design_note_markdown",
    )
    _write_text(
        paths["src_readme_path"],
        "# Workspace Source Scaffold\n\nThis area is reserved for bounded mutable-shell implementation work only.\n",
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="src_scaffold_readme",
    )
    _write_text(
        paths["tests_readme_path"],
        "# Workspace Test Scaffold\n\nThis area is reserved for bounded workspace-local regression coverage only.\n",
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="tests_scaffold_readme",
    )
    file_plan = {
        "schema_name": FILE_PLAN_SCHEMA_NAME,
        "schema_version": FILE_PLAN_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "planned_files": [
            {
                "relative_path": "src/successor_shell/__init__.py",
                "purpose": "workspace-local package export for successor shell helpers",
                "status": "proposed_not_created",
            },
            {
                "relative_path": "src/successor_shell/workspace_contract.py",
                "purpose": "workspace-local artifact index and review helper",
                "status": "proposed_not_created",
            },
            {
                "relative_path": "tests/test_workspace_contract.py",
                "purpose": "workspace-local regression coverage for the artifact contract helper",
                "status": "proposed_not_created",
            },
            {
                "relative_path": "docs/successor_shell_iteration_notes.md",
                "purpose": "implementation-bearing cycle note and deferred-item summary",
                "status": "proposed_not_created",
            },
        ],
        "protected_surfaces_excluded_by_default": [
            "main.py",
            "theory/nined_core.py",
            "routing logic",
            "thresholds",
            "live policy",
            "benchmark semantics",
        ],
    }
    _write_json(
        paths["file_plan_path"],
        file_plan,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="file_plan_json",
    )

    output_paths = [
        str(paths["plan_path"]),
        str(paths["design_path"]),
        str(paths["src_readme_path"]),
        str(paths["tests_readme_path"]),
        str(paths["file_plan_path"]),
        str(paths["summary_path"]),
    ]
    work_summary = {
        "schema_name": WORK_SUMMARY_SCHEMA_NAME,
        "schema_version": WORK_SUMMARY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "status": "work_completed",
        "cycle_kind": "planning_only",
        "invocation_model": CYCLE_EXECUTION_MODEL,
        "reason": "completed one bounded successor-planning work cycle inside the active workspace",
        "selected_work_item": selected,
        "skipped_work_items": skipped,
        "output_artifact_paths": output_paths,
        "newly_created_paths": [
            str(paths["plan_path"]),
            str(paths["design_path"]),
            str(paths["src_readme_path"]),
            str(paths["tests_readme_path"]),
            str(paths["file_plan_path"]),
        ],
        "deferred_items": deferred_items,
        "next_recommended_cycle": "materialize_workspace_local_implementation",
    }
    _write_json(
        paths["summary_path"],
        work_summary,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="bounded_work_summary_json",
    )
    payload.update(
        {
            "generated_at": _now(),
            "directive_id": directive_id,
            "status": "work_completed",
            "reason": work_summary["reason"],
            "work_cycle": {
                "work_item_id": str(selected.get("work_item_id", "")),
                "title": str(selected.get("title", "")),
                "cycle_kind": "planning_only",
                "invocation_model": CYCLE_EXECUTION_MODEL,
                "summary_artifact_path": str(paths["summary_path"]),
                "output_artifact_paths": output_paths,
                "newly_created_paths": work_summary["newly_created_paths"],
                "skipped_work_items": skipped,
                "next_recommended_cycle": "materialize_workspace_local_implementation",
            },
        }
    )
    _finalize_session_artifacts(
        payload=payload,
        session_artifact_path=session_artifact_path,
        session_archive_path=session_archive_path,
        brief_path=brief_path,
        brief_lines=[
            "# Governed Execution Brief",
            "",
            f"Status: {payload['status']}",
            f"Directive ID: `{directive_id}`",
            f"Workspace: `{workspace_id} -> {workspace_root}`",
            "",
            "Outputs:",
            *[f"- `{item}`" for item in output_paths],
        ],
    )
    _event(
        runtime_event_log_path,
        event_type="work_loop_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        status="work_completed",
        cycle_kind="planning_only",
        work_item_id=str(selected.get("work_item_id", "")),
        output_artifact_paths=output_paths,
        summary_artifact_path=str(paths["summary_path"]),
    )
    return payload


def _run_implementation_cycle(
    *,
    payload: dict[str, Any],
    current_directive: dict[str, Any],
    workspace_root: Path,
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
    session_artifact_path: Path,
    session_archive_path: Path,
    brief_path: Path,
) -> dict[str, Any]:
    baseline = _workspace_baseline(workspace_root)
    _event(
        runtime_event_log_path,
        event_type="implementation_planning_started",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        baseline_artifact_paths=list(baseline.get("baseline_artifact_paths", [])),
    )
    selected, skipped = _select_implementation_work_item(current_directive, baseline=baseline)
    for item in skipped:
        _event(
            runtime_event_log_path,
            event_type="work_item_skipped",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=str(item.get("work_item_id", "")),
            reason=str(item.get("reason", "")),
        )

    if not selected:
        return _complete_no_admissible_work(
            payload=payload,
            workspace_root=workspace_root,
            plans_root=baseline["plans_root"],
            summary_path=baseline["summary_path"],
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            skipped=skipped,
            reason="no admissible implementation-bearing work item was available under the current directive, baseline, and action-class constraints",
            include_implementation_deferred_event=True,
        )

    _event(
        runtime_event_log_path,
        event_type="implementation_item_selected",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        title=str(selected.get("title", "")),
        rationale=str(selected.get("rationale", "")),
        implementation_bundle_kind=str(selected.get("implementation_bundle_kind", "")),
        baseline_artifact_paths=list(baseline.get("baseline_artifact_paths", [])),
    )

    baseline["implementation_package_root"].mkdir(parents=True, exist_ok=True)
    deferred_items = [
        {
            "item": "protected_surface_mutation",
            "reason": "protected-surface and immutable-kernel mutation remain excluded by default",
        },
        {
            "item": "live_trusted_source_network_queries",
            "reason": "trusted-source live network expansion remains deferred in this cycle",
        },
        {
            "item": "repo_wide_mutation",
            "reason": "this bundle remains bounded to the active workspace and generated/log roots only",
        },
    ]

    _write_text(
        baseline["implementation_init_path"],
        _implementation_init_source(),
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="implementation_package_init",
    )
    _write_text(
        baseline["implementation_module_path"],
        _implementation_module_source(directive_id=directive_id),
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="implementation_module_python",
    )
    _write_text(
        baseline["implementation_test_path"],
        _implementation_test_source(),
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="implementation_test_python",
    )
    _event(
        runtime_event_log_path,
        event_type="test_scaffold_created",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        path=str(baseline["implementation_test_path"]),
        work_item_id=str(selected.get("work_item_id", "")),
    )
    _write_text(
        baseline["implementation_note_path"],
        _implementation_note_text(
            directive_id=directive_id,
            workspace_id=workspace_id,
            implementation_bundle_kind=str(selected.get("implementation_bundle_kind", "")),
            deferred_items=deferred_items,
        ),
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="implementation_iteration_note_markdown",
    )

    file_plan = load_json(baseline["file_plan_path"])
    planned_files = list(file_plan.get("planned_files", []))
    updated_file_statuses = {
        "src/successor_shell/__init__.py": "created",
        "src/successor_shell/workspace_contract.py": "created",
        "tests/test_workspace_contract.py": "created",
        "docs/successor_shell_iteration_notes.md": "created",
    }
    if not planned_files:
        planned_files = [
            {
                "relative_path": relative_path,
                "purpose": "materialized during the first implementation-bearing workspace cycle",
                "status": status,
            }
            for relative_path, status in updated_file_statuses.items()
        ]
    else:
        seen_paths: set[str] = set()
        for item in planned_files:
            relative_path = str(item.get("relative_path", "")).strip()
            if not relative_path:
                continue
            seen_paths.add(relative_path)
            if relative_path in updated_file_statuses:
                item["status"] = updated_file_statuses[relative_path]
        for relative_path, status in updated_file_statuses.items():
            if relative_path in seen_paths:
                continue
            planned_files.append(
                {
                    "relative_path": relative_path,
                    "purpose": "materialized during the first implementation-bearing workspace cycle",
                    "status": status,
                }
            )
    file_plan["schema_name"] = FILE_PLAN_SCHEMA_NAME
    file_plan["schema_version"] = FILE_PLAN_SCHEMA_VERSION
    file_plan["generated_at"] = _now()
    file_plan["directive_id"] = directive_id
    file_plan["workspace_id"] = workspace_id
    file_plan["planned_files"] = planned_files
    file_plan["protected_surfaces_excluded_by_default"] = file_plan.get(
        "protected_surfaces_excluded_by_default",
        [
            "main.py",
            "theory/nined_core.py",
            "routing logic",
            "thresholds",
            "live policy",
            "benchmark semantics",
        ],
    )
    _write_json(
        baseline["file_plan_path"],
        file_plan,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="file_plan_json",
    )

    workspace_artifact_index = _build_workspace_artifact_index_payload(workspace_root)
    _write_json(
        baseline["workspace_artifact_index_path"],
        workspace_artifact_index,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="workspace_artifact_index_json",
    )

    created_files = [
        str(baseline["implementation_init_path"]),
        str(baseline["implementation_module_path"]),
        str(baseline["implementation_test_path"]),
        str(baseline["implementation_note_path"]),
        str(baseline["workspace_artifact_index_path"]),
    ]
    implementation_summary = {
        "schema_name": IMPLEMENTATION_BUNDLE_SCHEMA_NAME,
        "schema_version": IMPLEMENTATION_BUNDLE_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "cycle_kind": "implementation_bearing",
        "invocation_model": CYCLE_EXECUTION_MODEL,
        "implementation_bundle_kind": str(selected.get("implementation_bundle_kind", "")),
        "baseline_artifact_paths": list(baseline.get("baseline_artifact_paths", [])),
        "created_files": created_files,
        "deferred_items": deferred_items,
        "next_recommended_cycle": "review_and_expand_workspace_local_implementation",
        "implementation_summary": (
            "Materialized a workspace-local artifact contract helper, executable test module, "
            "iteration note, and artifact index summary without touching protected repo surfaces."
        ),
    }
    _write_json(
        baseline["implementation_summary_path"],
        implementation_summary,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="implementation_bundle_summary_json",
    )
    created_files.append(str(baseline["implementation_summary_path"]))

    output_paths = [
        str(baseline["implementation_init_path"]),
        str(baseline["implementation_module_path"]),
        str(baseline["implementation_test_path"]),
        str(baseline["implementation_note_path"]),
        str(baseline["file_plan_path"]),
        str(baseline["workspace_artifact_index_path"]),
        str(baseline["implementation_summary_path"]),
        str(baseline["summary_path"]),
    ]
    work_summary = {
        "schema_name": WORK_SUMMARY_SCHEMA_NAME,
        "schema_version": WORK_SUMMARY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "status": "work_completed",
        "cycle_kind": "implementation_bearing",
        "invocation_model": CYCLE_EXECUTION_MODEL,
        "implementation_bundle_kind": str(selected.get("implementation_bundle_kind", "")),
        "reason": "completed one bounded implementation-bearing workspace cycle inside the active workspace",
        "selected_work_item": selected,
        "skipped_work_items": skipped,
        "baseline_artifact_paths": list(baseline.get("baseline_artifact_paths", [])),
        "output_artifact_paths": output_paths,
        "newly_created_paths": created_files,
        "deferred_items": deferred_items,
        "next_recommended_cycle": "review_and_expand_workspace_local_implementation",
    }
    _write_json(
        baseline["summary_path"],
        work_summary,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="bounded_work_summary_json",
    )

    payload.update(
        {
            "generated_at": _now(),
            "directive_id": directive_id,
            "status": "work_completed",
            "reason": work_summary["reason"],
            "work_cycle": {
                "work_item_id": str(selected.get("work_item_id", "")),
                "title": str(selected.get("title", "")),
                "cycle_kind": "implementation_bearing",
                "invocation_model": CYCLE_EXECUTION_MODEL,
                "implementation_bundle_kind": str(selected.get("implementation_bundle_kind", "")),
                "summary_artifact_path": str(baseline["summary_path"]),
                "output_artifact_paths": output_paths,
                "newly_created_paths": created_files,
                "skipped_work_items": skipped,
                "deferred_items": deferred_items,
                "next_recommended_cycle": "review_and_expand_workspace_local_implementation",
            },
        }
    )
    _finalize_session_artifacts(
        payload=payload,
        session_artifact_path=session_artifact_path,
        session_archive_path=session_archive_path,
        brief_path=brief_path,
        brief_lines=[
            "# Governed Execution Brief",
            "",
            f"Status: {payload['status']}",
            f"Directive ID: `{directive_id}`",
            f"Workspace: `{workspace_id} -> {workspace_root}`",
            "Cycle kind: implementation_bearing",
            f"Implementation bundle: `{selected.get('implementation_bundle_kind', '')}`",
            "",
            "Outputs:",
            *[f"- `{item}`" for item in output_paths],
        ],
    )
    _event(
        runtime_event_log_path,
        event_type="implementation_bundle_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        implementation_bundle_kind=str(selected.get("implementation_bundle_kind", "")),
        created_files=created_files,
        summary_artifact_path=str(baseline["summary_path"]),
    )
    _event(
        runtime_event_log_path,
        event_type="work_loop_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        status="work_completed",
        cycle_kind="implementation_bearing",
        work_item_id=str(selected.get("work_item_id", "")),
        output_artifact_paths=output_paths,
        summary_artifact_path=str(baseline["summary_path"]),
    )
    return payload


def run_initial_bounded_workspace_work(
    *,
    bootstrap_summary: dict[str, Any],
    session: dict[str, Any],
    payload: dict[str, Any],
    session_artifact_path: Path,
    session_archive_path: Path,
    brief_path: Path,
) -> dict[str, Any]:
    workspace_root = Path(str(payload.get("workspace_root", "")))
    paths = _workspace_paths(workspace_root)
    for root in (
        paths["docs_root"],
        paths["src_root"],
        paths["tests_root"],
        paths["artifacts_root"],
        paths["plans_root"],
    ):
        root.mkdir(parents=True, exist_ok=True)

    runtime_event_log_path = Path(str(payload.get("runtime_event_log_path", "")).strip())
    directive_state_path = Path(str(dict(bootstrap_summary.get("artifact_paths", {})).get("directive_state", "")).strip())
    current_directive = dict(load_json(directive_state_path).get("current_directive_state", {}))
    directive_id = str(current_directive.get("directive_id", payload.get("directive_id", ""))).strip() or str(payload.get("directive_id", ""))
    execution_profile = str(payload.get("execution_profile", "")).strip()
    workspace_id = str(payload.get("workspace_id", "")).strip()
    session_id = str(session.get("session_id", ""))

    _event(
        runtime_event_log_path,
        event_type="governed_execution_planning_started",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        directive_state_path=str(directive_state_path),
    )

    baseline = _workspace_baseline(workspace_root)
    if baseline.get("has_planning_baseline", False):
        return _run_implementation_cycle(
            payload=payload,
            current_directive=current_directive,
            workspace_root=workspace_root,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
        )
    return _run_planning_cycle(
        payload=payload,
        current_directive=current_directive,
        workspace_root=workspace_root,
        runtime_event_log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        session_artifact_path=session_artifact_path,
        session_archive_path=session_archive_path,
        brief_path=brief_path,
    )


def run_governed_workspace_work_controller(
    *,
    bootstrap_summary: dict[str, Any],
    session: dict[str, Any],
    payload: dict[str, Any],
    session_artifact_path: Path,
    session_archive_path: Path,
    brief_path: Path,
    controller_mode: str,
    max_cycles_per_invocation: int,
) -> dict[str, Any]:
    workspace_root = Path(str(payload.get("workspace_root", "")))
    paths = _workspace_paths(workspace_root)
    for root in (
        paths["docs_root"],
        paths["src_root"],
        paths["tests_root"],
        paths["artifacts_root"],
        paths["plans_root"],
        paths["cycles_root"],
    ):
        root.mkdir(parents=True, exist_ok=True)

    runtime_event_log_path = Path(str(payload.get("runtime_event_log_path", "")).strip())
    directive_state_path = Path(
        str(dict(bootstrap_summary.get("artifact_paths", {})).get("directive_state", "")).strip()
    )
    current_directive = dict(load_json(directive_state_path).get("current_directive_state", {}))
    directive_id = (
        str(current_directive.get("directive_id", payload.get("directive_id", ""))).strip()
        or str(payload.get("directive_id", ""))
    )
    execution_profile = str(payload.get("execution_profile", "")).strip()
    workspace_id = str(payload.get("workspace_id", "")).strip()
    session_id = str(session.get("session_id", ""))
    invocation_model = _invocation_model_for_mode(controller_mode)
    controller_summary_path = paths["controller_summary_path"]

    _event(
        runtime_event_log_path,
        event_type="governed_execution_controller_started",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        controller_mode=str(controller_mode),
        invocation_model=invocation_model,
        max_cycles_per_invocation=int(max_cycles_per_invocation),
    )

    cycle_rows: list[dict[str, Any]] = []
    stop_reason = ""
    stop_detail = ""
    latest_summary_artifact_path = ""
    latest_cycle_summary_archive_path = ""
    latest_completion_evaluation: dict[str, Any] = {}

    current_payload = dict(payload)
    for cycle_index in range(1, int(max_cycles_per_invocation) + 1):
        _event(
            runtime_event_log_path,
            event_type="governed_execution_cycle_started",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            cycle_index=int(cycle_index),
            controller_mode=str(controller_mode),
            invocation_model=invocation_model,
        )
        current_payload = run_initial_bounded_workspace_work(
            bootstrap_summary=bootstrap_summary,
            session=session,
            payload=current_payload,
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
        )
        work_cycle = dict(current_payload.get("work_cycle", {}))
        latest_summary_artifact_path = (
            str(work_cycle.get("summary_artifact_path", "")).strip() or str(paths["summary_path"])
        )
        latest_cycle_summary = load_json(Path(latest_summary_artifact_path))
        latest_completion_evaluation = _directive_completion_evaluation(
            current_directive=current_directive,
            workspace_root=workspace_root,
            latest_cycle_summary=latest_cycle_summary,
        )
        current_payload, augmented_summary, latest_cycle_summary_archive_path = _augment_cycle_payloads(
            payload=current_payload,
            workspace_root=workspace_root,
            cycle_index=int(cycle_index),
            controller_mode=controller_mode,
            latest_cycle_summary=latest_cycle_summary,
            completion_evaluation=latest_completion_evaluation,
        )

        cycle_status = str(current_payload.get("status", "")).strip()
        cycle_kind = str(dict(current_payload.get("work_cycle", {})).get("cycle_kind", "")).strip()
        cycle_row = {
            "cycle_index": int(cycle_index),
            "cycle_kind": cycle_kind,
            "status": cycle_status,
            "summary_artifact_path": latest_summary_artifact_path,
            "cycle_summary_archive_path": latest_cycle_summary_archive_path,
            "next_recommended_cycle": str(
                dict(current_payload.get("work_cycle", {})).get("next_recommended_cycle", "")
            ).strip(),
            "output_artifact_paths": list(dict(current_payload.get("work_cycle", {})).get("output_artifact_paths", [])),
            "newly_created_paths": list(dict(current_payload.get("work_cycle", {})).get("newly_created_paths", [])),
        }
        cycle_rows.append(cycle_row)

        _event(
            runtime_event_log_path,
            event_type="directive_stop_condition_evaluated",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            cycle_index=int(cycle_index),
            completed=bool(latest_completion_evaluation.get("completed", False)),
            reason=str(latest_completion_evaluation.get("reason", "")),
            fallback_used=bool(latest_completion_evaluation.get("fallback_used", False)),
        )
        _event(
            runtime_event_log_path,
            event_type="governed_execution_cycle_completed",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            cycle_index=int(cycle_index),
            cycle_kind=cycle_kind,
            status=cycle_status,
            summary_artifact_path=latest_summary_artifact_path,
            cycle_summary_archive_path=latest_cycle_summary_archive_path,
        )

        if cycle_status == STOP_REASON_FAILURE:
            stop_reason = STOP_REASON_FAILURE
            stop_detail = str(current_payload.get("reason", "")).strip()
            break
        if cycle_status == STOP_REASON_NO_WORK:
            stop_reason = STOP_REASON_NO_WORK
            stop_detail = str(current_payload.get("reason", "")).strip()
            break
        if bool(latest_completion_evaluation.get("completed", False)):
            stop_reason = STOP_REASON_COMPLETED
            stop_detail = str(latest_completion_evaluation.get("reason", "")).strip()
            break
        if str(controller_mode).strip() == "single_cycle":
            stop_reason = STOP_REASON_SINGLE_CYCLE
            stop_detail = "single-cycle mode stops after one bounded cycle and returns control to the operator"
            break

    if not stop_reason:
        stop_reason = STOP_REASON_MAX_CAP
        stop_detail = (
            f"bounded governed execution reached the operator-selected cycle cap of {int(max_cycles_per_invocation)}"
        )

    latest_cycle_index = int(cycle_rows[-1]["cycle_index"]) if cycle_rows else 0
    latest_cycle_kind = str(cycle_rows[-1].get("cycle_kind", "")) if cycle_rows else ""
    latest_next_recommended_cycle = str(cycle_rows[-1].get("next_recommended_cycle", "")) if cycle_rows else ""
    controller_summary = {
        "schema_name": CONTROLLER_SUMMARY_SCHEMA_NAME,
        "schema_version": CONTROLLER_SUMMARY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "controller_mode": str(controller_mode),
        "invocation_model": invocation_model,
        "max_cycles_per_invocation": int(max_cycles_per_invocation),
        "cycles_completed": len(cycle_rows),
        "latest_cycle_index": latest_cycle_index,
        "latest_cycle_kind": latest_cycle_kind,
        "latest_summary_artifact_path": latest_summary_artifact_path,
        "latest_cycle_summary_archive_path": latest_cycle_summary_archive_path,
        "stop_reason": stop_reason,
        "stop_detail": stop_detail,
        "directive_completion_evaluation": latest_completion_evaluation,
        "next_recommended_cycle": latest_next_recommended_cycle,
        "cycle_rows": cycle_rows,
    }
    controller_summary_path.write_text(_dump(controller_summary), encoding="utf-8")

    if paths["workspace_artifact_index_path"].exists():
        workspace_artifact_index = _build_workspace_artifact_index_payload(workspace_root)
        _write_json(
            paths["workspace_artifact_index_path"],
            workspace_artifact_index,
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id="governed_execution_controller",
            artifact_kind="workspace_artifact_index_json",
        )

    final_reason = str(current_payload.get("reason", "")).strip()
    if stop_reason == STOP_REASON_COMPLETED:
        final_reason = (
            "completed bounded governed execution by directive-derived stop condition after "
            f"{len(cycle_rows)} cycle(s)"
        )
    elif stop_reason == STOP_REASON_MAX_CAP:
        final_reason = stop_detail
    elif stop_reason == STOP_REASON_SINGLE_CYCLE:
        final_reason = stop_detail
    elif not final_reason:
        final_reason = stop_detail

    current_payload["generated_at"] = _now()
    current_payload["reason"] = final_reason
    current_payload["governed_execution_controller"] = controller_summary
    current_payload["controller_artifact_path"] = str(controller_summary_path)

    brief_lines = [
        "# Governed Execution Brief",
        "",
        f"Status: {current_payload.get('status', '')}",
        f"Directive ID: `{directive_id}`",
        f"Workspace: `{workspace_id} -> {workspace_root}`",
        f"Controller mode: `{controller_mode}`",
        f"Invocation model: `{invocation_model}`",
        f"Cycles completed: `{len(cycle_rows)}`",
        f"Stop reason: `{stop_reason}`",
        f"Latest cycle kind: `{latest_cycle_kind or '<none>'}`",
        f"Latest summary artifact: `{latest_summary_artifact_path or '<none>'}`",
        f"Controller summary: `{controller_summary_path}`",
    ]
    _finalize_session_artifacts(
        payload=current_payload,
        session_artifact_path=session_artifact_path,
        session_archive_path=session_archive_path,
        brief_path=brief_path,
        brief_lines=brief_lines,
    )
    _event(
        runtime_event_log_path,
        event_type="governed_execution_controller_stopped",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        controller_mode=str(controller_mode),
        invocation_model=invocation_model,
        cycles_completed=len(cycle_rows),
        latest_cycle_index=latest_cycle_index,
        stop_reason=stop_reason,
        stop_detail=stop_detail,
        controller_artifact_path=str(controller_summary_path),
        latest_summary_artifact_path=latest_summary_artifact_path,
    )
    return current_payload
