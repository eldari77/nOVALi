from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .bounded_workspace_work import (
    GovernedExecutionFailure,
    load_controller_summary as load_governed_execution_controller_summary,
    load_session_summary as load_governed_execution_session_summary,
    run_governed_workspace_work_controller,
)
from .common import OPERATOR_SESSION_FILE_ENV, OperatorConstraintViolationError
from .policy import (
    EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING,
    GOVERNED_EXECUTION_MODE_MULTI_CYCLE,
    GOVERNED_EXECUTION_MODE_SINGLE_CYCLE,
    load_effective_operator_session_from_file,
    validate_effective_operator_session,
)


GOVERNED_EXECUTION_SESSION_SCHEMA_NAME = "GovernedExecutionSession"
GOVERNED_EXECUTION_SESSION_SCHEMA_VERSION = "governed_execution_session_v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_path(value: Any) -> str:
    if value in {None, ""}:
        return ""
    try:
        return str(Path(str(value)).resolve())
    except OSError:
        return str(value)


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def _session_token(session_id: str) -> str:
    return str(session_id or "governed_execution").replace(":", "_")


def _append_runtime_event(log_path: Path, payload: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _load_runtime_session() -> dict[str, Any]:
    session_path = str(os.environ.get(OPERATOR_SESSION_FILE_ENV, "")).strip()
    if not session_path:
        raise OperatorConstraintViolationError(
            "governed execution requires a frozen operator session file in canonical operator mode",
            constraint_id="operator_session_file",
            enforcement_class="hard_enforced",
        )

    session = load_effective_operator_session_from_file(session_path)
    session_errors = validate_effective_operator_session(
        session,
        operator_root=session.get("operator_policy_root", ""),
        package_root=session.get("package_root", ""),
    )
    if session_errors:
        raise OperatorConstraintViolationError(
            "governed execution requires a valid frozen operator session",
            constraint_id="effective_operator_session",
            enforcement_class="hard_enforced",
        )
    return session


def governed_execution_session_summary_for_workspace(workspace_root: str | Path | None) -> dict[str, Any]:
    return load_governed_execution_session_summary(workspace_root)


def governed_execution_controller_summary_for_workspace(workspace_root: str | Path | None) -> dict[str, Any]:
    return load_governed_execution_controller_summary(workspace_root)


def run_bounded_governed_execution(
    *,
    bootstrap_summary: dict[str, Any],
) -> dict[str, Any]:
    session = _load_runtime_session()
    runtime_constraints = dict(session.get("effective_runtime_constraints", {}))
    constraint_values = dict(runtime_constraints.get("constraints", {}))
    governed_execution_policy = dict(runtime_constraints.get("governed_execution", {}))
    workspace_policy = dict(
        session.get("workspace_policy", runtime_constraints.get("workspace_policy", {}))
    )

    execution_profile = str(
        session.get("execution_profile", runtime_constraints.get("execution_profile", ""))
    ).strip()
    if execution_profile != EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING:
        raise OperatorConstraintViolationError(
            "governed execution requires the bounded_active_workspace_coding execution profile",
            constraint_id="governed_execution_profile",
            enforcement_class="hard_enforced",
        )

    workspace_id = str(workspace_policy.get("workspace_id", "")).strip()
    workspace_root_text = str(workspace_policy.get("workspace_root", "")).strip()
    if not workspace_id or not workspace_root_text:
        raise OperatorConstraintViolationError(
            "governed execution requires an active workspace id and root",
            constraint_id="active_workspace_root",
            enforcement_class="hard_enforced",
        )

    workspace_root = Path(workspace_root_text)
    workspace_root.mkdir(parents=True, exist_ok=True)
    artifacts_root = workspace_root / "artifacts"
    plans_root = workspace_root / "plans"
    artifacts_root.mkdir(parents=True, exist_ok=True)
    plans_root.mkdir(parents=True, exist_ok=True)

    runtime_event_log_path = Path(str(session.get("runtime_event_log_path", "")).strip())
    session_artifact_path = artifacts_root / "governed_execution_session_latest.json"
    session_archive_path = artifacts_root / f"{_session_token(str(session.get('session_id', '')))}.json"
    brief_path = plans_root / "governed_execution_brief.md"
    controller_mode = str(
        governed_execution_policy.get("mode", GOVERNED_EXECUTION_MODE_SINGLE_CYCLE)
    ).strip() or GOVERNED_EXECUTION_MODE_SINGLE_CYCLE
    max_cycles_per_invocation = int(
        governed_execution_policy.get(
            "max_cycles_per_invocation",
            2 if controller_mode == GOVERNED_EXECUTION_MODE_MULTI_CYCLE else 1,
        )
        or 1
    )

    payload = {
        "schema_name": GOVERNED_EXECUTION_SESSION_SCHEMA_NAME,
        "schema_version": GOVERNED_EXECUTION_SESSION_SCHEMA_VERSION,
        "generated_at": _now(),
        "status": "ready_for_bounded_mutable_shell_work",
        "session_id": str(session.get("session_id", "")),
        "launch_kind": str(session.get("launch_kind", "")),
        "directive_id": str(bootstrap_summary.get("directive_id", "")),
        "state_root": str(bootstrap_summary.get("state_root", "")),
        "execution_profile": execution_profile,
        "workspace_id": workspace_id,
        "workspace_root": _normalize_path(workspace_root),
        "working_directory": str(workspace_policy.get("working_directory", "")),
        "generated_output_root": str(workspace_policy.get("generated_output_root", "")),
        "log_root": str(workspace_policy.get("log_root", "")),
        "runtime_event_log_path": str(runtime_event_log_path),
        "governed_execution_policy": {
            "mode": controller_mode,
            "max_cycles_per_invocation": max_cycles_per_invocation,
        },
        "allowed_write_roots": list(constraint_values.get("allowed_write_roots", [])),
        "protected_root_hints": list(workspace_policy.get("protected_root_hints", [])),
        "canonical_authority_file": str(
            dict(bootstrap_summary.get("artifact_paths", {})).get("governance_memory_authority", "")
        ),
        "reason": (
            "canonical bootstrap is complete and the bounded active workspace is attached; "
            "mutable-shell work may proceed only inside the approved workspace and generated/log roots"
        ),
        "work_cycle": {},
    }
    session_artifact_path.write_text(_stable_json(payload), encoding="utf-8")
    session_archive_path.write_text(_stable_json(payload), encoding="utf-8")

    brief_lines = [
        "# Governed Execution Brief",
        "",
        f"Directive ID: `{payload['directive_id']}`",
        f"Execution profile: `{payload['execution_profile']}`",
        f"Workspace: `{payload['workspace_id']} -> {payload['workspace_root']}`",
        f"Working directory: `{payload['working_directory']}`",
        f"Generated output root: `{payload['generated_output_root']}`",
        f"Runtime event log: `{payload['runtime_event_log_path']}`",
        f"Controller mode: `{controller_mode}`",
        f"Max cycles per invocation: `{max_cycles_per_invocation}`",
        "",
        "Writable roots:",
        *[f"- `{item}`" for item in payload["allowed_write_roots"]],
        "",
        "Protected root hints:",
        *[f"- `{item}`" for item in payload["protected_root_hints"]],
        "",
        "Status: ready for bounded mutable-shell work.",
    ]
    brief_path.write_text("\n".join(brief_lines) + "\n", encoding="utf-8")

    if str(runtime_event_log_path):
        _append_runtime_event(
            runtime_event_log_path,
            {
                "event_type": "governed_execution_entered",
                "timestamp": _now(),
                "session_id": str(session.get("session_id", "")),
                "directive_id": payload["directive_id"],
                "execution_profile": execution_profile,
                "workspace_id": workspace_id,
                "workspace_root": payload["workspace_root"],
                "session_artifact_path": str(session_artifact_path),
                "brief_path": str(brief_path),
            },
        )

    work_summary_path = artifacts_root / "bounded_work_summary_latest.json"
    try:
        payload = run_governed_workspace_work_controller(
            bootstrap_summary=bootstrap_summary,
            session=session,
            payload=payload,
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
            controller_mode=controller_mode,
            max_cycles_per_invocation=max_cycles_per_invocation,
        )
    except GovernedExecutionFailure:
        raise
    except Exception as exc:
        failure_reason = f"bounded governed work failed before completion: {exc}"
        failure_summary = {
            "generated_at": _now(),
            "directive_id": str(payload.get("directive_id", "")),
            "workspace_id": workspace_id,
            "workspace_root": str(payload.get("workspace_root", "")),
            "status": "bounded_failure",
            "reason": failure_reason,
            "output_artifact_paths": [],
        }
        work_summary_path.write_text(_stable_json(failure_summary), encoding="utf-8")
        payload["generated_at"] = _now()
        payload["status"] = "bounded_failure"
        payload["reason"] = failure_reason
        payload["work_cycle"] = {
            "work_item_id": "bounded_failure",
            "summary_artifact_path": str(work_summary_path),
            "output_artifact_paths": [str(work_summary_path)],
        }
        session_text = _stable_json(payload)
        session_artifact_path.write_text(session_text, encoding="utf-8")
        session_archive_path.write_text(session_text, encoding="utf-8")
        brief_path.write_text(
            "\n".join(
                [
                    "# Governed Execution Brief",
                    "",
                    "Status: bounded_failure",
                    f"Reason: {failure_reason}",
                    f"Work summary: {work_summary_path}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        if str(runtime_event_log_path):
            _append_runtime_event(
                runtime_event_log_path,
                {
                    "event_type": "bounded_work_failure",
                    "timestamp": _now(),
                    "session_id": str(session.get("session_id", "")),
                    "directive_id": payload.get("directive_id", ""),
                    "execution_profile": execution_profile,
                    "workspace_id": workspace_id,
                    "workspace_root": payload.get("workspace_root", ""),
                    "reason": failure_reason,
                    "summary_artifact_path": str(work_summary_path),
                    "session_artifact_path": str(session_artifact_path),
                },
            )
        raise GovernedExecutionFailure(
            failure_reason,
            session_artifact_path=str(session_artifact_path),
            summary_artifact_path=str(work_summary_path),
        ) from exc

    return {
        **payload,
        "session_artifact_path": str(session_artifact_path),
        "session_archive_path": str(session_archive_path),
        "brief_path": str(brief_path),
        "work_summary_path": str(work_summary_path),
        "controller_artifact_path": str(artifacts_root / "governed_execution_controller_latest.json"),
    }
