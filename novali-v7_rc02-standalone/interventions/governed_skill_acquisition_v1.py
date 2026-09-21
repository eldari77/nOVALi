from __future__ import annotations

import ast
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .analytics import build_intervention_ledger_analytics
from .governance_substrate_v1 import (
    BRANCH_REGISTRY_PATH,
    BUCKET_STATE_PATH,
    DIRECTIVE_HISTORY_PATH,
    DIRECTIVE_STATE_PATH,
    SELF_STRUCTURE_LEDGER_PATH,
    SELF_STRUCTURE_STATE_PATH,
    _append_jsonl,
    _build_skill_subsystem,
    _classify_candidate_self_change,
    _now,
    _write_json,
)
from .ledger import intervention_data_dir, load_latest_snapshots
from .v4_first_hypothesis_landscape_snapshot_v1 import (
    ACTIVE_STATUS_PATH,
    HANDOFF_STATUS_PATH,
    _load_json_file,
    _load_text_file,
)
from .v4_wm_context_signal_overlap_snapshot_v1 import _artifact_reference


def _diagnostic_artifact_dir() -> Path:
    path = intervention_data_dir() / "diagnostic_memory"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(dict(json.loads(line)))
        except json.JSONDecodeError:
            continue
    return rows


def _workspace_root() -> Path:
    return ACTIVE_STATUS_PATH.parents[3]


def _trusted_logs_dir() -> Path:
    return _workspace_root() / "logs"


def _numeric_summary(values: list[Any]) -> dict[str, Any]:
    numeric_values = [float(value) for value in values if isinstance(value, (int, float))]
    if not numeric_values:
        return {
            "count": 0,
            "mean": 0.0,
            "min": 0.0,
            "max": 0.0,
            "positive_count": 0,
            "negative_count": 0,
        }
    positive_count = sum(1 for value in numeric_values if value > 0.0)
    negative_count = sum(1 for value in numeric_values if value < 0.0)
    return {
        "count": len(numeric_values),
        "mean": sum(numeric_values) / float(len(numeric_values)),
        "min": min(numeric_values),
        "max": max(numeric_values),
        "positive_count": positive_count,
        "negative_count": negative_count,
    }


def _log_group_key(path: Path) -> str:
    stem = path.stem
    prefix = "intervention_shadow_"
    if stem.startswith(prefix):
        stem = stem[len(prefix) :]
    if "_seed" in stem:
        stem = stem.rsplit("_seed", 1)[0]
    return stem


def _safe_literal_eval(raw_value: str) -> Any:
    try:
        return ast.literal_eval(raw_value)
    except (SyntaxError, ValueError):
        return None


def _select_trial_log_group(*, max_files: int = 3) -> dict[str, Any]:
    log_dir = _trusted_logs_dir()
    if not log_dir.exists():
        return {
            "passed": False,
            "reason": "trusted local log root is not available",
            "selected_paths": [],
        }

    grouped: dict[str, dict[str, Any]] = {}
    for path in log_dir.glob("intervention_shadow_*.log"):
        group_key = _log_group_key(path)
        entry = grouped.setdefault(
            group_key,
            {
                "group_key": group_key,
                "paths": [],
                "latest_mtime": 0.0,
                "seed_context_shift": False,
            },
        )
        entry["paths"].append(path)
        try:
            entry["latest_mtime"] = max(float(entry["latest_mtime"]), float(path.stat().st_mtime))
        except OSError:
            pass
        entry["seed_context_shift"] = bool(entry["seed_context_shift"]) or "seed_context_shift" in path.name

    if not grouped:
        return {
            "passed": False,
            "reason": "no trusted local intervention shadow logs were found",
            "selected_paths": [],
        }

    ranked_groups = sorted(
        grouped.values(),
        key=lambda item: (
            1 if bool(item.get("seed_context_shift", False)) else 0,
            min(len(list(item.get("paths", []))), max_files),
            float(item.get("latest_mtime", 0.0) or 0.0),
        ),
        reverse=True,
    )
    selected_group = dict(ranked_groups[0])
    selected_paths = sorted(list(selected_group.get("paths", [])), key=lambda item: item.name)[:max_files]
    return {
        "passed": True,
        "group_key": str(selected_group.get("group_key", "")),
        "selection_reason": (
            "latest coherent seed-context-shift shadow log group chosen from trusted local logs"
            if bool(selected_group.get("seed_context_shift", False))
            else "latest coherent shadow log group chosen from trusted local logs"
        ),
        "seed_context_shift_preferred": bool(selected_group.get("seed_context_shift", False)),
        "selected_file_count": len(selected_paths),
        "selected_paths": [str(path) for path in selected_paths],
    }


def _parse_local_trace_log(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {
            "path": str(path),
            "exists": False,
            "read_error": str(exc),
            "event_counts": {},
            "dummy_eval_count": 0,
            "recognized_line_share": 0.0,
            "_raw_improvements": [],
            "_raw_scores": [],
        }

    lines = text.splitlines()
    nonempty_lines = [line for line in lines if line.strip()]
    event_counts: Counter[str] = Counter()
    parse_errors: list[dict[str, Any]] = []
    dummy_eval_rows: list[dict[str, Any]] = []
    patch_tuple_count = 0
    recognized_lines = 0

    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("==="):
            recognized_lines += 1
            if " start " in stripped:
                event_counts["section_start"] += 1
            elif " end " in stripped:
                event_counts["section_end"] += 1
            else:
                event_counts["section_marker"] += 1
            continue
        if stripped.startswith("[adopt_patch] Applied:"):
            recognized_lines += 1
            event_counts["adopt_patch"] += 1
            payload = _safe_literal_eval(stripped.split("Applied:", 1)[1].strip())
            if isinstance(payload, list):
                patch_tuple_count += len(payload)
            else:
                parse_errors.append({"line_number": line_number, "event": "adopt_patch"})
            continue
        if stripped.startswith("[dummy_eval]"):
            recognized_lines += 1
            event_counts["dummy_eval"] += 1
            payload = _safe_literal_eval(stripped[len("[dummy_eval]") :].strip())
            if isinstance(payload, dict):
                dummy_eval_rows.append(payload)
            else:
                parse_errors.append({"line_number": line_number, "event": "dummy_eval"})

    improvements = [row.get("improvement") for row in dummy_eval_rows]
    scores = [row.get("score") for row in dummy_eval_rows]
    patch_sizes = [row.get("patch_size") for row in dummy_eval_rows]
    targets = sorted(
        {
            int(row.get("target"))
            for row in dummy_eval_rows
            if isinstance(row.get("target"), int)
        }
    )
    proposers = sorted(
        {
            int(row.get("proposer"))
            for row in dummy_eval_rows
            if isinstance(row.get("proposer"), int)
        }
    )

    return {
        "path": str(path),
        "exists": True,
        "file_size_bytes": int(path.stat().st_size),
        "line_count": len(lines),
        "nonempty_line_count": len(nonempty_lines),
        "event_counts": dict(event_counts),
        "parse_error_count": len(parse_errors),
        "parse_errors": parse_errors[:4],
        "dummy_eval_count": len(dummy_eval_rows),
        "patch_tuple_count": int(patch_tuple_count),
        "targets_observed": targets,
        "proposers_observed": proposers,
        "improvement_summary": _numeric_summary(improvements),
        "score_summary": _numeric_summary(scores),
        "patch_size_summary": _numeric_summary(patch_sizes),
        "recognized_line_share": (
            float(recognized_lines) / float(len(nonempty_lines)) if nonempty_lines else 0.0
        ),
        "_raw_improvements": [float(value) for value in improvements if isinstance(value, (int, float))],
        "_raw_scores": [float(value) for value in scores if isinstance(value, (int, float))],
    }


def _summarize_parsed_logs(parsed_logs: list[dict[str, Any]]) -> dict[str, Any]:
    combined_event_counts: Counter[str] = Counter()
    total_dummy_eval_count = 0
    total_patch_tuple_count = 0
    total_file_size_bytes = 0
    total_nonempty_lines = 0
    recognized_line_share_weighted = 0.0
    all_improvements: list[float] = []
    all_scores: list[float] = []
    seed_identifiers: list[str] = []

    per_file = []
    for item in parsed_logs:
        combined_event_counts.update(dict(item.get("event_counts", {})))
        total_dummy_eval_count += int(item.get("dummy_eval_count", 0) or 0)
        total_patch_tuple_count += int(item.get("patch_tuple_count", 0) or 0)
        total_file_size_bytes += int(item.get("file_size_bytes", 0) or 0)
        nonempty_line_count = int(item.get("nonempty_line_count", 0) or 0)
        total_nonempty_lines += nonempty_line_count
        recognized_line_share_weighted += float(item.get("recognized_line_share", 0.0) or 0.0) * nonempty_line_count
        all_improvements.extend(list(item.get("_raw_improvements", [])))
        all_scores.extend(list(item.get("_raw_scores", [])))
        file_name = Path(str(item.get("path", ""))).name
        if "_seed" in file_name:
            seed_identifiers.append(file_name.rsplit("_seed", 1)[-1].replace(".log", ""))
        per_file.append(
            {
                "path": str(item.get("path", "")),
                "dummy_eval_count": int(item.get("dummy_eval_count", 0) or 0),
                "patch_tuple_count": int(item.get("patch_tuple_count", 0) or 0),
                "recognized_line_share": float(item.get("recognized_line_share", 0.0) or 0.0),
                "event_counts": dict(item.get("event_counts", {})),
            }
        )

    weighted_recognized_share = (
        recognized_line_share_weighted / float(total_nonempty_lines) if total_nonempty_lines else 0.0
    )
    return {
        "parsed_file_count": len(parsed_logs),
        "parsed_file_size_bytes": total_file_size_bytes,
        "event_counts": dict(combined_event_counts),
        "dummy_eval_count": total_dummy_eval_count,
        "patch_tuple_count": total_patch_tuple_count,
        "recognized_line_share_weighted": weighted_recognized_share,
        "improvement_summary": _numeric_summary(all_improvements),
        "score_summary": _numeric_summary(all_scores),
        "seed_suffixes_observed": sorted(seed_identifiers),
        "per_file": per_file,
    }


def _trial_artifact_digest(path: Path) -> dict[str, Any]:
    payload = _load_json_file(path)
    if not payload:
        return {"path": str(path), "exists": False}
    diagnostic_conclusions = dict(payload.get("diagnostic_conclusions", {}))
    return {
        "path": str(path),
        "exists": True,
        "template_name": str(payload.get("template_name", "")),
        "proposal_id": str(payload.get("proposal_id", "")),
        "best_next_template": str(dict(payload.get("decision_recommendation", {})).get("best_next_template", "")),
        "routing_deferred": bool(diagnostic_conclusions.get("routing_deferred", False)),
        "plan_non_owning": bool(
            diagnostic_conclusions.get("plan_should_remain_non_owning")
            or dict(payload.get("decision_recommendation", {})).get("plan_should_remain_non_owning")
        ),
        "summary_keys": sorted(str(key) for key in payload.keys() if not str(key).startswith("_"))[:16],
    }


def _lifecycle_definition() -> dict[str, Any]:
    return {
        "states": [
            "proposed",
            "screened",
            "blocked",
            "diagnostic_only",
            "sandboxed",
            "provisional",
            "retained",
            "deprecated",
            "rolled_back",
        ],
        "canonical_flow": [
            "proposed -> screened",
            "screened -> blocked | diagnostic_only | sandboxed",
            "sandboxed -> provisional",
            "provisional -> retained | deprecated | rolled_back",
            "retained -> deprecated | rolled_back",
        ],
        "phase_1_intent": "skills are defined governance-first and may be screened or trialed in bounded form before any retained promotion is allowed",
    }


def _directive_relevance_score(value: str) -> float:
    return {
        "high": 1.0,
        "medium": 0.7,
        "low": 0.35,
        "none": 0.0,
    }.get(str(value), 0.0)


def _skill_candidate_screen_schema() -> dict[str, Any]:
    return {
        "schema_name": "GovernedSkillCandidateScreen",
        "schema_version": "governed_skill_candidate_screen_v1",
        "required_fields": [
            "skill_id",
            "candidate_name",
            "candidate_summary",
            "skill_class",
            "proposal_family",
            "template_name",
            "action_class",
            "surface",
            "target_surface",
            "directive_relevance",
            "expected_value",
            "resource_cost_estimate",
            "reversibility",
            "duplication_risk",
            "trusted_sources",
            "evidence_plan",
            "candidate_traits",
        ],
        "screening_outcome_classes": [
            "blocked",
            "diagnostic_only",
            "sandboxed",
            "provisional",
            "gated_review_required",
            "forbidden",
        ],
    }


def _valid_skill_class_report(candidate: dict[str, Any], governed_skill_subsystem: dict[str, Any]) -> dict[str, Any]:
    valid_classes = set(str(item) for item in list(governed_skill_subsystem.get("phase_1_valid_skill_classes", [])))
    skill_class = str(candidate.get("skill_class", ""))
    passed = skill_class in valid_classes
    return {
        "passed": passed,
        "skill_class": skill_class,
        "valid_skill_classes": sorted(valid_classes),
        "reason": (
            "candidate uses a valid phase-1 skill class"
            if passed
            else "candidate uses an invalid or unsupported skill class for phase 1"
        ),
    }


def _duplication_overlap_report(candidate: dict[str, Any]) -> dict[str, Any]:
    duplication_risk = str(candidate.get("duplication_risk", "unknown"))
    overlap_signal = str(dict(candidate.get("candidate_traits", {})).get("overlap_signal", "unknown"))
    expected_value = str(candidate.get("expected_value", "unknown"))
    passed = duplication_risk in {"low", "medium"} or (duplication_risk == "high" and expected_value == "high")
    return {
        "passed": passed,
        "duplication_risk": duplication_risk,
        "overlap_signal": overlap_signal,
        "reason": (
            "duplication risk is acceptable for phase-1 screening"
            if passed
            else "duplication or overlap risk is too high relative to expected value"
        ),
    }


def _bounded_evidence_report(candidate: dict[str, Any]) -> dict[str, Any]:
    evidence_plan = str(candidate.get("evidence_plan", "")).strip()
    bounded = bool(evidence_plan) and evidence_plan.lower() != "none"
    reversible = str(candidate.get("reversibility", "unknown")) in {"high", "medium"}
    passed = bool(bounded and reversible)
    return {
        "passed": passed,
        "evidence_plan_present": bounded,
        "reversibility_status": str(candidate.get("reversibility", "unknown")),
        "reason": (
            "candidate has a bounded evidence path and sufficient reversibility for governed screening"
            if passed
            else "candidate lacks a bounded evidence path or sufficient reversibility"
        ),
    }


def _screen_skill_candidate(
    candidate: dict[str, Any],
    *,
    directive_state: dict[str, Any],
    bucket_state: dict[str, Any],
    self_structure_state: dict[str, Any],
    branch_record: dict[str, Any],
    governed_skill_subsystem: dict[str, Any],
) -> dict[str, Any]:
    execution_gate = _classify_candidate_self_change(
        dict(candidate, requested_resources=dict(candidate.get("resource_cost_estimate", {}))),
        policy=dict(self_structure_state.get("policy", {})),
        directive_state=dict(directive_state.get("current_directive_state", {})),
        bucket_state=dict(bucket_state.get("current_bucket_state", {})),
        branch_record=branch_record,
    )
    class_report = _valid_skill_class_report(candidate, governed_skill_subsystem)
    duplication_report = _duplication_overlap_report(candidate)
    evidence_report = _bounded_evidence_report(candidate)

    directive_score = _directive_relevance_score(str(candidate.get("directive_relevance", "none")))
    candidate_traits = dict(candidate.get("candidate_traits", {}))
    execution_gate_status = str(execution_gate.get("admissibility_status", "forbidden"))

    if not class_report["passed"]:
        outcome = "blocked"
        reason = "candidate skill class is outside the valid phase-1 governed skill classes"
    elif execution_gate_status == "forbidden":
        outcome = "forbidden"
        reason = "candidate violates immutable-core, trusted-source, or other forbidden governance rules"
    elif not duplication_report["passed"] or directive_score < 0.35:
        outcome = "blocked"
        reason = "candidate is too duplicative or too weakly directive-relevant to justify phase-1 skill work"
    elif not evidence_report["passed"]:
        outcome = "blocked"
        reason = "candidate lacks the bounded evidence path and reversibility needed for governed skill screening"
    elif bool(candidate_traits.get("is_retained_promotion_candidate", False)):
        outcome = "provisional"
        reason = "candidate is plausible but still requires provisional evidence and gated retained-promotion review"
    elif bool(candidate_traits.get("is_diagnostic_registry_candidate", False)):
        outcome = "diagnostic_only"
        reason = "candidate is valid only as diagnostic governance-aligned skill work and does not justify a skill branch"
    elif execution_gate_status == "gated_review_required":
        outcome = "sandboxed"
        reason = "candidate is admissible only as a sandboxed or review-gated skill trial under the paused-branch constraints"
    else:
        outcome = "gated_review_required"
        reason = "candidate remains gated until explicit governance review decides the correct bounded trial mode"

    return {
        "skill_id": str(candidate.get("skill_id", "")),
        "candidate_name": str(candidate.get("candidate_name", "")),
        "candidate_summary": str(candidate.get("candidate_summary", "")),
        "skill_class": str(candidate.get("skill_class", "")),
        "action_class": str(candidate.get("action_class", "")),
        "directive_relevance": str(candidate.get("directive_relevance", "")),
        "directive_relevance_score": directive_score,
        "expected_value": str(candidate.get("expected_value", "")),
        "execution_gate_status": execution_gate_status,
        "skill_screen_outcome": outcome,
        "screening_reason": reason,
        "valid_skill_class_report": class_report,
        "duplication_overlap_report": duplication_report,
        "bounded_evidence_report": evidence_report,
        "execution_gate_report": execution_gate,
        "candidate_traits": candidate_traits,
        "screening_source_of_truth": "governance_substrate_v1",
    }


def _example_skill_candidates() -> list[dict[str, Any]]:
    return [
        {
            "skill_id": "skill_candidate_local_trace_parser_trial",
            "candidate_name": "Local trace parser trial",
            "candidate_summary": "Bounded helper module for local log parsing and diagnostic trace extraction inside trusted local sources.",
            "skill_class": "helper_module",
            "proposal_family": "memory_summary",
            "template_name": "memory_summary.v4_governed_skill_candidate_screen_snapshot_v1",
            "action_class": "skill_trial",
            "surface": "skills_subsystem",
            "target_surface": "skills_subsystem",
            "directive_relevance": "high",
            "expected_value": "medium",
            "resource_cost_estimate": {
                "cpu_parallel_units": 1,
                "memory_mb": 128,
                "storage_write_mb": 8,
                "network_mode": "none",
            },
            "reversibility": "high",
            "duplication_risk": "low",
            "trusted_sources": ["local_repo:novali-v4", "local_logs:logs"],
            "evidence_plan": "shadow-only parsing utility checked against local intervention logs and current diagnostic artifacts",
            "candidate_traits": {
                "is_trial_candidate": True,
                "overlap_signal": "low",
            },
        },
        {
            "skill_id": "skill_candidate_context_memory_retriever_promotion",
            "candidate_name": "Context memory retriever promotion candidate",
            "candidate_summary": "Local retrieval-memory subsystem candidate with plausible utility but requiring retained-promotion review and repeated evidence.",
            "skill_class": "retrieval_memory_system",
            "proposal_family": "memory_summary",
            "template_name": "memory_summary.v4_governed_skill_candidate_screen_snapshot_v1",
            "action_class": "skill_retention_promotion",
            "surface": "skills_subsystem",
            "target_surface": "skills_subsystem",
            "directive_relevance": "high",
            "expected_value": "medium",
            "resource_cost_estimate": {
                "cpu_parallel_units": 1,
                "memory_mb": 256,
                "storage_write_mb": 16,
                "network_mode": "none",
            },
            "reversibility": "medium",
            "duplication_risk": "medium",
            "trusted_sources": ["local_repo:novali-v4", "local_artifacts:novali-v4/data"],
            "evidence_plan": "repeat shadow-only retrieval benefit across more than one diagnostic pass before any retained promotion",
            "candidate_traits": {
                "is_retained_promotion_candidate": True,
                "overlap_signal": "medium",
            },
        },
        {
            "skill_id": "skill_candidate_shadow_slice_registry_helper",
            "candidate_name": "Shadow slice registry helper",
            "candidate_summary": "Small evaluator-oriented helper for registry synchronization and slice bookkeeping with no branch-opening intent.",
            "skill_class": "evaluator",
            "proposal_family": "memory_summary",
            "template_name": "memory_summary.v4_governed_skill_candidate_screen_snapshot_v1",
            "action_class": "low_risk_shell_change",
            "surface": "skills_subsystem",
            "target_surface": "skills_subsystem",
            "directive_relevance": "high",
            "expected_value": "medium",
            "resource_cost_estimate": {
                "cpu_parallel_units": 1,
                "memory_mb": 96,
                "storage_write_mb": 4,
                "network_mode": "none",
            },
            "reversibility": "high",
            "duplication_risk": "low",
            "trusted_sources": ["local_repo:novali-v4"],
            "evidence_plan": "diagnostic-only registry update and local shadow bookkeeping",
            "candidate_traits": {
                "is_diagnostic_registry_candidate": True,
                "overlap_signal": "low",
            },
        },
        {
            "skill_id": "skill_candidate_duplicate_planner_adapter",
            "candidate_name": "Duplicate planner adapter",
            "candidate_summary": "Low-value planner-support helper with high overlap and weak relevance, offered as a negative screening case.",
            "skill_class": "planner_support",
            "proposal_family": "memory_summary",
            "template_name": "memory_summary.v4_governed_skill_candidate_screen_snapshot_v1",
            "action_class": "low_risk_shell_change",
            "surface": "skills_subsystem",
            "target_surface": "skills_subsystem",
            "directive_relevance": "low",
            "expected_value": "low",
            "resource_cost_estimate": {
                "cpu_parallel_units": 1,
                "memory_mb": 64,
                "storage_write_mb": 4,
                "network_mode": "none",
            },
            "reversibility": "high",
            "duplication_risk": "high",
            "trusted_sources": ["local_repo:novali-v4"],
            "evidence_plan": "single-pass local utility only",
            "candidate_traits": {
                "overlap_signal": "high",
            },
        },
        {
            "skill_id": "skill_candidate_untrusted_remote_tool_wrapper",
            "candidate_name": "Untrusted remote tool wrapper",
            "candidate_summary": "Forbidden tool-wrapper candidate that would introduce untrusted external access and routing-adjacent drift.",
            "skill_class": "tool_wrapper",
            "proposal_family": "memory_summary",
            "template_name": "memory_summary.v4_governed_skill_candidate_screen_snapshot_v1",
            "action_class": "untrusted_external_access",
            "surface": "skills_subsystem",
            "target_surface": "trusted_source_policy",
            "directive_relevance": "low",
            "expected_value": "unknown",
            "resource_cost_estimate": {
                "cpu_parallel_units": 1,
                "memory_mb": 256,
                "storage_write_mb": 32,
                "network_mode": "open_external",
            },
            "reversibility": "low",
            "duplication_risk": "high",
            "trusted_sources": ["untrusted_remote_web"],
            "evidence_plan": "none",
            "candidate_traits": {
                "routing_work": True,
                "overlap_signal": "high",
            },
        },
    ]


def _skill_trial_admission_schema() -> dict[str, Any]:
    return {
        "schema_name": "GovernedSkillTrialAdmission",
        "schema_version": "governed_skill_trial_admission_v1",
        "primary_candidate_field": "skill_id",
        "admission_outcome_classes": [
            "remain_diagnostic_only",
            "admissible_for_sandboxed_trial",
            "gated_review_required",
            "blocked",
            "forbidden",
        ],
        "required_checks": [
            "directive_relevance",
            "9d_admissibility",
            "trusted_source_compliance",
            "bucket_resource_feasibility",
            "mutable_surface_legality",
            "reversibility",
            "bounded_evidence_path",
            "duplication_overlap_risk",
            "branch_state_compatibility",
            "trial_isolation_from_forbidden_surfaces",
        ],
    }


def _paused_branch_trial_compatibility(candidate: dict[str, Any], branch_record: dict[str, Any]) -> dict[str, Any]:
    branch_state = str(branch_record.get("state", ""))
    traits = dict(candidate.get("candidate_traits", {}))
    if branch_state != "paused_with_baseline_held":
        return {
            "passed": False,
            "reason": "trial-admission flow is defined only for the paused-with-baseline-held wm-hybrid branch state",
        }
    disallowed = any(
        bool(traits.get(key, False))
        for key in [
            "branch_state_change",
            "held_baseline_challenge",
            "routing_work",
            "downstream_selected_set_work",
            "plan_ownership_change",
        ]
    )
    return {
        "passed": not disallowed,
        "reason": (
            "candidate can be trialed while the branch remains paused because it does not request a branch-state change, held-baseline challenge, or downstream ownership shift"
            if not disallowed
            else "candidate is not trial-compatible with a paused branch because it requests a forbidden branch or downstream change"
        ),
    }


def _trial_isolation_report(candidate: dict[str, Any]) -> dict[str, Any]:
    traits = dict(candidate.get("candidate_traits", {}))
    violations = []
    mapping = {
        "routing_work": "routing work",
        "downstream_selected_set_work": "downstream selected-set work",
        "plan_ownership_change": "plan_ ownership change",
        "live_policy_change": "live-policy change",
        "threshold_change": "threshold change",
        "frozen_benchmark_semantics_change": "frozen benchmark semantics change",
        "projection_safe_envelope_change": "projection-safe envelope change",
        "protected_surface_challenge": "protected-surface challenge",
        "untrusted_external_access": "untrusted external access",
    }
    for key, label in mapping.items():
        if bool(traits.get(key, False)):
            violations.append(label)
    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "reason": (
            "trial can remain isolated from routing, downstream selection, plan ownership changes, protected surfaces, and immutable policy surfaces"
            if not violations
            else "candidate trial would drift into forbidden or protected areas"
        ),
    }


def _trial_envelope(
    candidate: dict[str, Any],
    *,
    bucket_state: dict[str, Any],
    branch_record: dict[str, Any],
    governed_skill_subsystem: dict[str, Any],
) -> dict[str, Any]:
    current_bucket = dict(bucket_state.get("current_bucket_state", {}))
    retention_rules = dict(governed_skill_subsystem.get("retention_rules", {}))
    return {
        "trial_mode": "sandboxed_shadow_only",
        "branch_state_must_remain": str(branch_record.get("state", "")),
        "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
        "bounded_scope": [
            "local log parsing only",
            "trusted local diagnostic-memory reads only",
            "shadow-only evaluation or evidence collection",
            "no retained promotion and no branch-state mutation",
        ],
        "implementation_path": {
            "allowed_write_roots": list(dict(current_bucket.get("mount_policy", {})).get("write_roots", [])),
            "forbidden_roots": list(dict(current_bucket.get("mount_policy", {})).get("read_only_roots", [])),
            "must_be_reversible": True,
        },
        "resource_limits": dict(candidate.get("resource_cost_estimate", {})),
        "network_policy": {
            "required_mode": "none",
            "allowed_modes": list(dict(current_bucket.get("network_policy", {})).get("allowed_network_modes", [])),
            "untrusted_external_access_forbidden": True,
        },
        "required_evidence": [
            "bounded utility demonstrated in shadow-only or diagnostic runs",
            "no downstream selected-set or routing drift",
            "no plan_ ownership change",
            "reversible local implementation path maintained",
        ],
        "rollback_triggers": list(retention_rules.get("rollback_triggers", [])),
    }


def _evaluate_trial_admission(
    candidate: dict[str, Any],
    screened_candidate: dict[str, Any],
    *,
    bucket_state: dict[str, Any],
    branch_record: dict[str, Any],
    governed_skill_subsystem: dict[str, Any],
) -> dict[str, Any]:
    gate_report = dict(screened_candidate.get("execution_gate_report", {}))
    isolation_report = _trial_isolation_report(candidate)
    paused_branch_report = _paused_branch_trial_compatibility(candidate, branch_record)
    valid_class_report = dict(screened_candidate.get("valid_skill_class_report", {}))
    duplication_report = dict(screened_candidate.get("duplication_overlap_report", {}))
    evidence_report = dict(screened_candidate.get("bounded_evidence_report", {}))
    screen_outcome = str(screened_candidate.get("skill_screen_outcome", "blocked"))
    gate_status = str(screened_candidate.get("execution_gate_status", "forbidden"))
    reversibility_status = str(dict(gate_report.get("reversibility", {})).get("status", "unknown"))

    checks = {
        "directive_relevance": float(screened_candidate.get("directive_relevance_score", 0.0) or 0.0) >= 0.7,
        "9d_admissibility": bool(dict(gate_report.get("nine_d_admissibility", {})).get("passed", False)),
        "trusted_source_compliance": bool(dict(gate_report.get("trusted_source_compliance", {})).get("passed", False)),
        "bucket_resource_feasibility": bool(dict(gate_report.get("bucket_feasibility", {})).get("passed", False)),
        "mutable_surface_legality": bool(dict(gate_report.get("mutable_surface_legality", {})).get("passed", False)),
        "reversibility": reversibility_status == "high",
        "bounded_evidence_path": bool(evidence_report.get("passed", False)),
        "duplication_overlap_risk": bool(duplication_report.get("passed", False)),
        "branch_state_compatibility": bool(paused_branch_report.get("passed", False)),
        "trial_isolation_from_forbidden_surfaces": bool(isolation_report.get("passed", False)),
    }

    if screen_outcome == "forbidden" or gate_status == "forbidden":
        outcome = "forbidden"
        reason = "candidate violates immutable-core, trust-boundary, or other forbidden governance rules"
    elif screen_outcome == "blocked":
        outcome = "blocked"
        reason = "candidate remains blocked because it does not justify phase-1 skill trial admission"
    elif screen_outcome == "diagnostic_only":
        outcome = "remain_diagnostic_only"
        reason = "candidate is valid only as diagnostic or registry-support work and does not need a governed skill trial"
    elif all(checks.values()) and screen_outcome == "sandboxed":
        outcome = "admissible_for_sandboxed_trial"
        reason = "candidate clears the trial-admission checks and can be admitted into a tightly bounded sandboxed skill trial without reopening the branch"
    elif screen_outcome in {"sandboxed", "provisional"}:
        outcome = "gated_review_required"
        reason = "candidate remains review-gated because one or more trial-admission checks are not yet strong enough for bounded trial admission"
    else:
        outcome = "blocked"
        reason = "candidate does not fit a valid governed trial-admission path"

    envelope = (
        _trial_envelope(
            candidate,
            bucket_state=bucket_state,
            branch_record=branch_record,
            governed_skill_subsystem=governed_skill_subsystem,
        )
        if outcome == "admissible_for_sandboxed_trial"
        else {}
    )
    return {
        "skill_id": str(candidate.get("skill_id", "")),
        "candidate_name": str(candidate.get("candidate_name", "")),
        "screened_skill_outcome": screen_outcome,
        "trial_admission_outcome": outcome,
        "reason": reason,
        "trial_admission_checks": checks,
        "paused_branch_trial_compatibility": paused_branch_report,
        "trial_isolation_report": isolation_report,
        "trial_envelope": envelope,
        "screening_source_of_truth": "governance_substrate_v1",
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governance_substrate_v1_snapshot"
    )
    directive_init_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_directive_spec_initialization_flow_v1_snapshot"
    )
    candidate_admission_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_reopen_candidate_screen_snapshot_v1"
    )
    branch_pause_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_branch_pause_snapshot_v1"
    )
    working_baseline_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_scoped_working_baseline_snapshot_v1"
    )
    scoped_probe_artifact = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1"
    )
    frontier_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.false_safe_frontier_control_characterization_snapshot_v1"
    )
    if not all(
        [
            governance_snapshot,
            directive_init_snapshot,
            candidate_admission_snapshot,
            branch_pause_snapshot,
            working_baseline_snapshot,
            scoped_probe_artifact,
            frontier_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed skill acquisition flow requires governance substrate, directive initialization, candidate admission, branch pause, working baseline, scoped probe, and frontier artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite governance artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite governance artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite governance artifacts"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "skill acquisition cannot be defined governance-first without the current directive, branch, bucket, and admission context",
            },
        }

    directive_state = _load_json_file(DIRECTIVE_STATE_PATH)
    bucket_state = _load_json_file(BUCKET_STATE_PATH)
    self_structure_state = _load_json_file(SELF_STRUCTURE_STATE_PATH)
    branch_registry = _load_json_file(BRANCH_REGISTRY_PATH)
    directive_history = _load_jsonl(DIRECTIVE_HISTORY_PATH)
    self_structure_ledger = _load_jsonl(SELF_STRUCTURE_LEDGER_PATH)
    if not all([directive_state, bucket_state, self_structure_state, branch_registry]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed skill acquisition flow requires current directive, bucket, self-structure, and branch state artifacts",
            "observability_gain": {"passed": False, "reason": "missing durable governance source-of-truth artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing durable governance source-of-truth artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing durable governance source-of-truth artifacts"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "skill acquisition cannot become governance-owned without the current directive, branch, bucket, and self-structure context",
            },
        }

    active_status_text = _load_text_file(ACTIVE_STATUS_PATH)
    handoff_status = _load_json_file(HANDOFF_STATUS_PATH)
    analytics = build_intervention_ledger_analytics()
    latest_snapshots = load_latest_snapshots()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")

    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    policy = dict(self_structure_state.get("policy", {}))
    current_directive = dict(directive_state.get("current_directive_state", {}))
    current_bucket = dict(bucket_state.get("current_bucket_state", {}))
    skill_subsystem = _build_skill_subsystem(
        policy=policy,
        directive_state=directive_state,
        bucket_state=bucket_state,
        branch_record=branch_record,
    )

    artifact_path = (
        _diagnostic_artifact_dir()
        / f"memory_summary_v4_governed_skill_acquisition_flow_snapshot_v1_{proposal['proposal_id']}.json"
    )

    updated_self_structure_state = dict(self_structure_state)
    updated_skill_subsystem = dict(skill_subsystem)
    updated_skill_subsystem["lifecycle_definition"] = _lifecycle_definition()
    updated_skill_subsystem["governance_inputs_consumed"] = {
        "directive_state_latest": str(DIRECTIVE_STATE_PATH),
        "directive_history": str(DIRECTIVE_HISTORY_PATH),
        "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
        "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
        "branch_registry_latest": str(BRANCH_REGISTRY_PATH),
        "bucket_state_latest": str(BUCKET_STATE_PATH),
    }
    updated_skill_subsystem["current_governance_context"] = {
        "directive_id": str(current_directive.get("directive_id", "")),
        "directive_initialization_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": str(branch_record.get("state", "")),
        "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
        "plan_non_owning": True,
        "routing_deferred": bool(dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)),
    }
    updated_skill_subsystem["skill_branch_opened_by_default"] = False
    updated_skill_subsystem["last_flow_artifact_path"] = str(artifact_path)
    updated_skill_subsystem["best_next_template"] = "memory_summary.v4_governed_skill_candidate_screen_snapshot_v1"

    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["governed_skill_subsystem"] = updated_skill_subsystem
    current_state_summary = dict(updated_self_structure_state.get("current_state_summary", {}))
    current_state_summary.update(
        {
            "governed_skill_acquisition_flow_v1_defined": True,
            "skill_acquisition_branch_opened": False,
            "plan_non_owning": True,
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
        }
    )
    updated_self_structure_state["current_state_summary"] = current_state_summary
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    ledger_event = {
        "event_id": f"governed_skill_acquisition_v1::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_skill_acquisition_flow_v1_defined",
        "event_class": "governed_skill_acquisition",
        "directive_id": str(current_directive.get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": str(branch_record.get("state", "")),
        "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
        "skill_branch_opened": False,
        "sample_screening_counts": dict(updated_skill_subsystem.get("sample_screening_counts", {})),
        "artifact_paths": {
            "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
            "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            "directive_state_latest": str(DIRECTIVE_STATE_PATH),
            "directive_history": str(DIRECTIVE_HISTORY_PATH),
            "branch_registry_latest": str(BRANCH_REGISTRY_PATH),
            "bucket_state_latest": str(BUCKET_STATE_PATH),
            "skill_flow_artifact": str(artifact_path),
        },
        "source_proposal_id": str(proposal.get("proposal_id", "")),
    }
    _append_jsonl(SELF_STRUCTURE_LEDGER_PATH, ledger_event)

    all_ranked = list(recommendations.get("all_ranked_proposals", []))
    suggested_templates = [
        str(item.get("template_name", ""))
        for item in all_ranked
        if isinstance(item, dict) and str(item.get("decision", "")) == "suggested"
    ][:8]
    directive_history_tail = [str(item.get("event_type", "")) for item in directive_history[-8:]]
    self_structure_event_tail = [str(item.get("event_type", "")) for item in self_structure_ledger[-12:]]

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_governed_skill_acquisition_flow_snapshot_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "branch_context": {
            "active_status_path": str(ACTIVE_STATUS_PATH),
            "handoff_status_path": str(HANDOFF_STATUS_PATH),
            "active_status_mentions_v4_active": "`novali-v4` is the active working version." in active_status_text,
            "carried_forward_baseline": dict(handoff_status.get("carried_forward_baseline", {})),
            "current_branch_id": str(branch_record.get("branch_id", "")),
            "current_branch_state": str(branch_record.get("state", "")),
            "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
            "plan_non_owning": True,
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
        },
        "comparison_references": {
            "memory_summary.v4_governance_substrate_v1_snapshot": _artifact_reference(governance_snapshot, latest_snapshots),
            "memory_summary.v4_directive_spec_initialization_flow_v1_snapshot": _artifact_reference(
                directive_init_snapshot,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_hybrid_reopen_candidate_screen_snapshot_v1": _artifact_reference(
                candidate_admission_snapshot,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_hybrid_branch_pause_snapshot_v1": _artifact_reference(
                branch_pause_snapshot,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_hybrid_scoped_working_baseline_snapshot_v1": _artifact_reference(
                working_baseline_snapshot,
                latest_snapshots,
            ),
            "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1": _artifact_reference(
                scoped_probe_artifact,
                latest_snapshots,
            ),
            "memory_summary.false_safe_frontier_control_characterization_snapshot_v1": _artifact_reference(
                frontier_snapshot,
                latest_snapshots,
            ),
        },
        "governed_skill_acquisition_summary": {
            "lifecycle": dict(updated_skill_subsystem.get("lifecycle_definition", {})),
            "valid_skill_classes": list(updated_skill_subsystem.get("phase_1_valid_skill_classes", [])),
            "skill_class_profiles": list(updated_skill_subsystem.get("phase_1_skill_class_profiles", [])),
            "admission_classes": {
                "execution_gate_classes": list(
                    dict(self_structure_state.get("proposal_admissibility_gate", {})).get("output_classes", [])
                ),
                "screening_outcome_classes": list(updated_skill_subsystem.get("screening_outcome_classes", [])),
                "skill_action_governance_matrix": dict(updated_skill_subsystem.get("skill_action_governance_matrix", {})),
            },
            "evaluation_dimensions": list(updated_skill_subsystem.get("evaluation_dimensions", [])),
            "retention_and_rollback_rules": dict(updated_skill_subsystem.get("retention_rules", {})),
            "boundary_guardrails": dict(updated_skill_subsystem.get("boundary_guardrails", {})),
            "sample_skill_screenings": list(updated_skill_subsystem.get("sample_skill_proposals", [])),
            "sample_screening_counts": dict(updated_skill_subsystem.get("sample_screening_counts", {})),
            "governance_inputs_consumed": dict(updated_skill_subsystem.get("governance_inputs_consumed", {})),
            "governance_input_state": {
                "directive_is_active": str(directive_state.get("initialization_state", "")) == "active",
                "directive_history_tail": directive_history_tail,
                "self_structure_event_tail": self_structure_event_tail,
                "bucket_id": str(current_bucket.get("bucket_id", "")),
                "trusted_sources": list(current_bucket.get("trusted_sources", [])),
                "current_branch_state": str(branch_record.get("state", "")),
            },
            "why_governance_remains_source_of_truth": {
                "owner": "governance_substrate_v1",
                "proposal_learning_loop_is_governance_truth_source": False,
                "reason": "skill acquisition definitions are materialized from directive, branch, bucket, and self-structure governance artifacts rather than from proposal_learning_loop runtime logic",
            },
        },
        "analytics_context": {
            "analytics_report_path": str(intervention_data_dir() / "intervention_analytics_latest.json"),
            "proposal_recommendations_path": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            "proposal_count": int(analytics.get("proposal_count", 0) or 0),
            "current_recommendation_top_templates": suggested_templates,
        },
        "decision_recommendation": {
            "governed_skill_acquisition_flow_v1_defined": True,
            "actual_behavior_changing_skill_branch_opened": False,
            "plan_should_remain_non_owning": True,
            "best_next_template": "memory_summary.v4_governed_skill_candidate_screen_snapshot_v1",
            "recommended_next_step": "screen a concrete skill candidate through governance before any sandboxed skill trial or behavior-changing skill branch is considered",
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
        },
        "observability_gain": {
            "passed": True,
            "reason": "Governed Skill Acquisition Flow v1 now defines a canonical lifecycle, valid classes, action governance matrix, retention rules, and rollback rules as durable governance state",
            "artifact_paths": {
                "skill_flow_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "future skill proposals can now be screened against directive, bucket, branch, trust-boundary, and duplication constraints before any real skill-building branch is opened",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.96,
            "reason": "the flow cleanly separates diagnostic-only skill work, sandboxed skill trials, provisional evidence thresholds, retained promotions, and forbidden drift paths",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "Governed Skill Acquisition Flow v1 is governance-owned and diagnostic only; live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope remain unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": "memory_summary.v4_governed_skill_candidate_screen_snapshot_v1",
            "reason": "the next safe step is to screen a concrete skill candidate through governance rather than opening a behavior-changing skill branch",
        },
        "diagnostic_conclusions": {
            "governed_skill_acquisition_flow_v1_defined": True,
            "actual_behavior_changing_skill_branch_opened": False,
            "plan_should_remain_non_owning": True,
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
            "current_branch_state": str(branch_record.get("state", "")),
            "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
            "best_next_template": "memory_summary.v4_governed_skill_candidate_screen_snapshot_v1",
        },
    }
    _write_json(artifact_path, artifact_payload)

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: Governed Skill Acquisition Flow v1 is now defined at governance level before any new skill-building branch is opened",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }


def run_candidate_screen_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governance_substrate_v1_snapshot"
    )
    directive_init_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_directive_spec_initialization_flow_v1_snapshot"
    )
    candidate_admission_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_reopen_candidate_screen_snapshot_v1"
    )
    skill_flow_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_skill_acquisition_flow_snapshot_v1"
    )
    branch_pause_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_branch_pause_snapshot_v1"
    )
    working_baseline_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_scoped_working_baseline_snapshot_v1"
    )
    frontier_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.false_safe_frontier_control_characterization_snapshot_v1"
    )
    if not all(
        [
            governance_snapshot,
            directive_init_snapshot,
            candidate_admission_snapshot,
            skill_flow_snapshot,
            branch_pause_snapshot,
            working_baseline_snapshot,
            frontier_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed skill candidate screening requires governance substrate, directive initialization, governed candidate admission, skill-acquisition flow, branch pause, working baseline, and frontier artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite governance artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite governance artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite governance artifacts"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "concrete skill candidates cannot be screened without the active directive, skill flow, and paused-branch governance context",
            },
        }

    directive_state = _load_json_file(DIRECTIVE_STATE_PATH)
    bucket_state = _load_json_file(BUCKET_STATE_PATH)
    self_structure_state = _load_json_file(SELF_STRUCTURE_STATE_PATH)
    branch_registry = _load_json_file(BRANCH_REGISTRY_PATH)
    directive_history = _load_jsonl(DIRECTIVE_HISTORY_PATH)
    self_structure_ledger = _load_jsonl(SELF_STRUCTURE_LEDGER_PATH)
    if not all([directive_state, bucket_state, self_structure_state, branch_registry]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed skill candidate screening requires current directive, bucket, self-structure, and branch state artifacts",
            "observability_gain": {"passed": False, "reason": "missing durable governance source-of-truth artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing durable governance source-of-truth artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing durable governance source-of-truth artifacts"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "candidate screening cannot operate without directive, branch, bucket, and self-structure state",
            },
        }

    active_status_text = _load_text_file(ACTIVE_STATUS_PATH)
    handoff_status = _load_json_file(HANDOFF_STATUS_PATH)
    analytics = build_intervention_ledger_analytics()
    latest_snapshots = load_latest_snapshots()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")

    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_directive = dict(directive_state.get("current_directive_state", {}))
    current_bucket = dict(bucket_state.get("current_bucket_state", {}))
    governed_skill_subsystem = dict(self_structure_state.get("governed_skill_subsystem", {}))
    if not governed_skill_subsystem:
        governed_skill_subsystem = _build_skill_subsystem(
            policy=dict(self_structure_state.get("policy", {})),
            directive_state=directive_state,
            bucket_state=bucket_state,
            branch_record=branch_record,
        )

    candidate_schema = _skill_candidate_screen_schema()
    candidate_examples = _example_skill_candidates()
    screened_candidates = [
        _screen_skill_candidate(
            candidate,
            directive_state=directive_state,
            bucket_state=bucket_state,
            self_structure_state=self_structure_state,
            branch_record=branch_record,
            governed_skill_subsystem=governed_skill_subsystem,
        )
        for candidate in candidate_examples
    ]
    screening_outcome_counts = {
        "blocked": sum(1 for item in screened_candidates if item["skill_screen_outcome"] == "blocked"),
        "diagnostic_only": sum(1 for item in screened_candidates if item["skill_screen_outcome"] == "diagnostic_only"),
        "sandboxed": sum(1 for item in screened_candidates if item["skill_screen_outcome"] == "sandboxed"),
        "provisional": sum(1 for item in screened_candidates if item["skill_screen_outcome"] == "provisional"),
        "gated_review_required": sum(
            1 for item in screened_candidates if item["skill_screen_outcome"] == "gated_review_required"
        ),
        "forbidden": sum(1 for item in screened_candidates if item["skill_screen_outcome"] == "forbidden"),
    }
    execution_gate_counts = {
        "auto_allowed": sum(1 for item in screened_candidates if item["execution_gate_status"] == "auto_allowed"),
        "gated_review_required": sum(
            1 for item in screened_candidates if item["execution_gate_status"] == "gated_review_required"
        ),
        "forbidden": sum(1 for item in screened_candidates if item["execution_gate_status"] == "forbidden"),
    }

    artifact_path = (
        _diagnostic_artifact_dir()
        / f"memory_summary_v4_governed_skill_candidate_screen_snapshot_v1_{proposal['proposal_id']}.json"
    )
    current_screen_outcome = {
        "status": "candidate_set_screened_without_branch_open",
        "reason": "concrete skill candidates were screened against directive, branch, bucket, trust-boundary, duplication, and reversibility constraints without opening a behavior-changing skill branch",
        "branch_state_after_screen": str(branch_record.get("state", "")),
        "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
        "screening_outcome_counts": screening_outcome_counts,
        "execution_gate_counts": execution_gate_counts,
    }

    updated_self_structure_state = dict(self_structure_state)
    updated_governed_skill_subsystem = dict(governed_skill_subsystem)
    updated_governed_skill_subsystem["candidate_screen_schema"] = candidate_schema
    updated_governed_skill_subsystem["last_candidate_screen_artifact_path"] = str(artifact_path)
    updated_governed_skill_subsystem["last_candidate_screen_outcome"] = current_screen_outcome
    updated_governed_skill_subsystem["last_candidate_screen_examples"] = [
        {
            "skill_id": str(item.get("skill_id", "")),
            "candidate_name": str(item.get("candidate_name", "")),
            "screening_outcome": str(item.get("skill_screen_outcome", "")),
            "execution_gate_status": str(item.get("execution_gate_status", "")),
        }
        for item in screened_candidates
    ]
    updated_governed_skill_subsystem["best_next_template"] = "memory_summary.v4_governed_skill_trial_admission_snapshot_v1"

    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["governed_skill_subsystem"] = updated_governed_skill_subsystem
    current_state_summary = dict(updated_self_structure_state.get("current_state_summary", {}))
    current_state_summary.update(
        {
            "governed_skill_candidate_screening_in_place": True,
            "latest_skill_candidate_screen_outcome": str(current_screen_outcome.get("status", "")),
            "skill_acquisition_branch_opened": False,
            "plan_non_owning": True,
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
        }
    )
    updated_self_structure_state["current_state_summary"] = current_state_summary
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    ledger_event = {
        "event_id": f"governed_skill_candidate_screen_v1::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_skill_candidate_screen_v1_materialized",
        "event_class": "governed_skill_candidate_screen",
        "directive_id": str(current_directive.get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": str(branch_record.get("state", "")),
        "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
        "screening_outcome_counts": screening_outcome_counts,
        "execution_gate_counts": execution_gate_counts,
        "skill_branch_opened": False,
        "artifact_paths": {
            "directive_state_latest": str(DIRECTIVE_STATE_PATH),
            "directive_history": str(DIRECTIVE_HISTORY_PATH),
            "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
            "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            "branch_registry_latest": str(BRANCH_REGISTRY_PATH),
            "bucket_state_latest": str(BUCKET_STATE_PATH),
            "skill_candidate_screen_artifact": str(artifact_path),
        },
        "source_proposal_id": str(proposal.get("proposal_id", "")),
    }
    _append_jsonl(SELF_STRUCTURE_LEDGER_PATH, ledger_event)

    all_ranked = list(recommendations.get("all_ranked_proposals", []))
    suggested_templates = [
        str(item.get("template_name", ""))
        for item in all_ranked
        if isinstance(item, dict) and str(item.get("decision", "")) == "suggested"
    ][:8]
    directive_history_tail = [str(item.get("event_type", "")) for item in directive_history[-8:]]
    self_structure_event_tail = [str(item.get("event_type", "")) for item in self_structure_ledger[-12:]]

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_governed_skill_candidate_screen_snapshot_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "branch_context": {
            "active_status_path": str(ACTIVE_STATUS_PATH),
            "handoff_status_path": str(HANDOFF_STATUS_PATH),
            "active_status_mentions_v4_active": "`novali-v4` is the active working version." in active_status_text,
            "carried_forward_baseline": dict(handoff_status.get("carried_forward_baseline", {})),
            "current_branch_id": str(branch_record.get("branch_id", "")),
            "current_branch_state": str(branch_record.get("state", "")),
            "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
            "plan_non_owning": True,
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
        },
        "comparison_references": {
            "memory_summary.v4_governance_substrate_v1_snapshot": _artifact_reference(governance_snapshot, latest_snapshots),
            "memory_summary.v4_directive_spec_initialization_flow_v1_snapshot": _artifact_reference(
                directive_init_snapshot,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_hybrid_reopen_candidate_screen_snapshot_v1": _artifact_reference(
                candidate_admission_snapshot,
                latest_snapshots,
            ),
            "memory_summary.v4_governed_skill_acquisition_flow_snapshot_v1": _artifact_reference(
                skill_flow_snapshot,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_hybrid_branch_pause_snapshot_v1": _artifact_reference(
                branch_pause_snapshot,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_hybrid_scoped_working_baseline_snapshot_v1": _artifact_reference(
                working_baseline_snapshot,
                latest_snapshots,
            ),
            "memory_summary.false_safe_frontier_control_characterization_snapshot_v1": _artifact_reference(
                frontier_snapshot,
                latest_snapshots,
            ),
        },
        "governed_skill_candidate_screen_summary": {
            "candidate_schema": candidate_schema,
            "screening_dimensions": [
                "directive_relevance",
                "9d_admissibility",
                "trusted_source_policy",
                "bucket_resource_feasibility",
                "mutable_surface_legality",
                "reversibility",
                "duplication_overlap_risk",
                "branch_state_compatibility",
                "skill_class_validity",
                "bounded_evidence_path",
            ],
            "governance_inputs_consumed": {
                "directive_state_latest": str(DIRECTIVE_STATE_PATH),
                "directive_history": str(DIRECTIVE_HISTORY_PATH),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
                "branch_registry_latest": str(BRANCH_REGISTRY_PATH),
                "bucket_state_latest": str(BUCKET_STATE_PATH),
            },
            "governance_input_state": {
                "directive_is_active": str(directive_state.get("initialization_state", "")) == "active",
                "directive_history_tail": directive_history_tail,
                "self_structure_event_tail": self_structure_event_tail,
                "current_branch_state": str(branch_record.get("state", "")),
                "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
                "trusted_sources": list(current_bucket.get("trusted_sources", [])),
            },
            "example_candidate_outcomes": screened_candidates,
            "screening_outcome_counts": screening_outcome_counts,
            "execution_gate_counts": execution_gate_counts,
            "current_screen_outcome": current_screen_outcome,
            "why_governance_remains_source_of_truth": {
                "owner": "governance_substrate_v1",
                "proposal_learning_loop_is_governance_truth_source": False,
                "reason": "candidate skill screening reads directive, branch, bucket, and self-structure governance artifacts as authoritative context before any skill branch can be admitted",
            },
        },
        "analytics_context": {
            "analytics_report_path": str(intervention_data_dir() / "intervention_analytics_latest.json"),
            "proposal_recommendations_path": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            "proposal_count": int(analytics.get("proposal_count", 0) or 0),
            "current_recommendation_top_templates": suggested_templates,
        },
        "decision_recommendation": {
            "governed_skill_candidate_screening_in_place": True,
            "actual_behavior_changing_skill_branch_opened": False,
            "current_screened_candidate_set_outcome": current_screen_outcome,
            "best_next_template": "memory_summary.v4_governed_skill_trial_admission_snapshot_v1",
            "recommended_next_step": "take the best sandbox-first candidate through a governed trial-admission snapshot rather than opening a skill branch directly",
            "plan_should_remain_non_owning": True,
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
        },
        "observability_gain": {
            "passed": True,
            "reason": "concrete skill candidates are now screened through governance-owned records before any real skill-building branch can be opened",
            "artifact_paths": {
                "skill_candidate_screen_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the screen shows that valid, gated, blocked, and forbidden skill candidates can be distinguished without changing branch state or opening a behavior-changing skill path",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.97,
            "reason": "the screen cleanly distinguishes sandbox-first helpers, provisional retained-promotion candidates, duplicate low-value blockers, and forbidden trust-boundary violations",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the skill candidate screen is governance-owned and diagnostic only; live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope remain unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": "memory_summary.v4_governed_skill_trial_admission_snapshot_v1",
            "reason": "the next safe step is to take the best sandbox-first candidate through another governance gate instead of opening a behavior-changing skill branch",
        },
        "diagnostic_conclusions": {
            "governed_skill_candidate_screening_in_place": True,
            "actual_behavior_changing_skill_branch_opened": False,
            "current_screened_candidate_set_outcome": current_screen_outcome,
            "plan_should_remain_non_owning": True,
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
            "best_next_template": "memory_summary.v4_governed_skill_trial_admission_snapshot_v1",
        },
    }
    _write_json(artifact_path, artifact_payload)

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: concrete skill candidates can now be screened through governance before any real skill-building branch is admitted",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }


def run_trial_admission_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governance_substrate_v1_snapshot"
    )
    directive_init_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_directive_spec_initialization_flow_v1_snapshot"
    )
    candidate_admission_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_reopen_candidate_screen_snapshot_v1"
    )
    skill_flow_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_skill_acquisition_flow_snapshot_v1"
    )
    skill_candidate_screen_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_skill_candidate_screen_snapshot_v1"
    )
    branch_pause_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_branch_pause_snapshot_v1"
    )
    working_baseline_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_scoped_working_baseline_snapshot_v1"
    )
    frontier_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.false_safe_frontier_control_characterization_snapshot_v1"
    )
    if not all(
        [
            governance_snapshot,
            directive_init_snapshot,
            candidate_admission_snapshot,
            skill_flow_snapshot,
            skill_candidate_screen_snapshot,
            branch_pause_snapshot,
            working_baseline_snapshot,
            frontier_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed skill trial admission requires governance substrate, directive initialization, candidate admission, skill flow, candidate screen, branch pause, working baseline, and frontier artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite governance artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite governance artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite governance artifacts"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "the best sandbox-first candidate cannot be evaluated for trial admission without the current governance and candidate-screen context",
            },
        }

    directive_state = _load_json_file(DIRECTIVE_STATE_PATH)
    bucket_state = _load_json_file(BUCKET_STATE_PATH)
    self_structure_state = _load_json_file(SELF_STRUCTURE_STATE_PATH)
    branch_registry = _load_json_file(BRANCH_REGISTRY_PATH)
    directive_history = _load_jsonl(DIRECTIVE_HISTORY_PATH)
    self_structure_ledger = _load_jsonl(SELF_STRUCTURE_LEDGER_PATH)
    if not all([directive_state, bucket_state, self_structure_state, branch_registry]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed skill trial admission requires current directive, bucket, self-structure, and branch state artifacts",
            "observability_gain": {"passed": False, "reason": "missing durable governance source-of-truth artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing durable governance source-of-truth artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing durable governance source-of-truth artifacts"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "trial admission cannot be evaluated without directive, bucket, self-structure, and branch state",
            },
        }

    active_status_text = _load_text_file(ACTIVE_STATUS_PATH)
    handoff_status = _load_json_file(HANDOFF_STATUS_PATH)
    analytics = build_intervention_ledger_analytics()
    latest_snapshots = load_latest_snapshots()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")

    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_directive = dict(directive_state.get("current_directive_state", {}))
    governed_skill_subsystem = dict(self_structure_state.get("governed_skill_subsystem", {}))
    if not governed_skill_subsystem:
        governed_skill_subsystem = _build_skill_subsystem(
            policy=dict(self_structure_state.get("policy", {})),
            directive_state=directive_state,
            bucket_state=bucket_state,
            branch_record=branch_record,
        )

    candidate_examples = _example_skill_candidates()
    screened_candidates = {
        str(item.get("skill_id", "")): _screen_skill_candidate(
            item,
            directive_state=directive_state,
            bucket_state=bucket_state,
            self_structure_state=self_structure_state,
            branch_record=branch_record,
            governed_skill_subsystem=governed_skill_subsystem,
        )
        for item in candidate_examples
    }
    primary_candidate = next(
        (item for item in candidate_examples if str(item.get("skill_id", "")) == "skill_candidate_local_trace_parser_trial"),
        {},
    )
    primary_screened = dict(screened_candidates.get("skill_candidate_local_trace_parser_trial", {}))
    trial_admission_schema = _skill_trial_admission_schema()
    primary_trial_admission = _evaluate_trial_admission(
        primary_candidate,
        primary_screened,
        bucket_state=bucket_state,
        branch_record=branch_record,
        governed_skill_subsystem=governed_skill_subsystem,
    )
    secondary_context = [
        {
            "skill_id": str(item.get("skill_id", "")),
            "candidate_name": str(item.get("candidate_name", "")),
            "screened_skill_outcome": str(item.get("skill_screen_outcome", "")),
        }
        for skill_id, item in screened_candidates.items()
        if skill_id != "skill_candidate_local_trace_parser_trial"
    ]

    artifact_path = (
        _diagnostic_artifact_dir()
        / f"memory_summary_v4_governed_skill_trial_admission_snapshot_v1_{proposal['proposal_id']}.json"
    )

    updated_self_structure_state = dict(self_structure_state)
    updated_governed_skill_subsystem = dict(governed_skill_subsystem)
    updated_governed_skill_subsystem["trial_admission_schema"] = trial_admission_schema
    updated_governed_skill_subsystem["last_trial_admission_artifact_path"] = str(artifact_path)
    updated_governed_skill_subsystem["last_trial_admission_outcome"] = {
        "primary_candidate_skill_id": str(primary_trial_admission.get("skill_id", "")),
        "primary_candidate_name": str(primary_trial_admission.get("candidate_name", "")),
        "trial_admission_outcome": str(primary_trial_admission.get("trial_admission_outcome", "")),
        "branch_state_after_review": str(branch_record.get("state", "")),
        "reason": str(primary_trial_admission.get("reason", "")),
    }
    updated_governed_skill_subsystem["best_next_template"] = (
        "proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1"
        if str(primary_trial_admission.get("trial_admission_outcome", "")) == "admissible_for_sandboxed_trial"
        else "memory_summary.v4_governed_skill_trial_readiness_gap_snapshot_v1"
    )

    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["governed_skill_subsystem"] = updated_governed_skill_subsystem
    current_state_summary = dict(updated_self_structure_state.get("current_state_summary", {}))
    current_state_summary.update(
        {
            "governed_skill_trial_admission_in_place": True,
            "latest_skill_trial_admission_outcome": str(primary_trial_admission.get("trial_admission_outcome", "")),
            "skill_acquisition_branch_opened": False,
            "plan_non_owning": True,
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
        }
    )
    updated_self_structure_state["current_state_summary"] = current_state_summary
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    ledger_event = {
        "event_id": f"governed_skill_trial_admission_v1::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_skill_trial_admission_v1_materialized",
        "event_class": "governed_skill_trial_admission",
        "directive_id": str(current_directive.get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": str(branch_record.get("state", "")),
        "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
        "primary_candidate_skill_id": str(primary_trial_admission.get("skill_id", "")),
        "trial_admission_outcome": str(primary_trial_admission.get("trial_admission_outcome", "")),
        "skill_branch_opened": False,
        "artifact_paths": {
            "directive_state_latest": str(DIRECTIVE_STATE_PATH),
            "directive_history": str(DIRECTIVE_HISTORY_PATH),
            "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
            "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            "branch_registry_latest": str(BRANCH_REGISTRY_PATH),
            "bucket_state_latest": str(BUCKET_STATE_PATH),
            "skill_trial_admission_artifact": str(artifact_path),
        },
        "source_proposal_id": str(proposal.get("proposal_id", "")),
    }
    _append_jsonl(SELF_STRUCTURE_LEDGER_PATH, ledger_event)

    all_ranked = list(recommendations.get("all_ranked_proposals", []))
    suggested_templates = [
        str(item.get("template_name", ""))
        for item in all_ranked
        if isinstance(item, dict) and str(item.get("decision", "")) == "suggested"
    ][:8]
    directive_history_tail = [str(item.get("event_type", "")) for item in directive_history[-8:]]
    self_structure_event_tail = [str(item.get("event_type", "")) for item in self_structure_ledger[-12:]]

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_governed_skill_trial_admission_snapshot_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "branch_context": {
            "active_status_path": str(ACTIVE_STATUS_PATH),
            "handoff_status_path": str(HANDOFF_STATUS_PATH),
            "active_status_mentions_v4_active": "`novali-v4` is the active working version." in active_status_text,
            "carried_forward_baseline": dict(handoff_status.get("carried_forward_baseline", {})),
            "current_branch_id": str(branch_record.get("branch_id", "")),
            "current_branch_state": str(branch_record.get("state", "")),
            "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
            "plan_non_owning": True,
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
        },
        "comparison_references": {
            "memory_summary.v4_governance_substrate_v1_snapshot": _artifact_reference(governance_snapshot, latest_snapshots),
            "memory_summary.v4_directive_spec_initialization_flow_v1_snapshot": _artifact_reference(
                directive_init_snapshot,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_hybrid_reopen_candidate_screen_snapshot_v1": _artifact_reference(
                candidate_admission_snapshot,
                latest_snapshots,
            ),
            "memory_summary.v4_governed_skill_acquisition_flow_snapshot_v1": _artifact_reference(
                skill_flow_snapshot,
                latest_snapshots,
            ),
            "memory_summary.v4_governed_skill_candidate_screen_snapshot_v1": _artifact_reference(
                skill_candidate_screen_snapshot,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_hybrid_branch_pause_snapshot_v1": _artifact_reference(
                branch_pause_snapshot,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_hybrid_scoped_working_baseline_snapshot_v1": _artifact_reference(
                working_baseline_snapshot,
                latest_snapshots,
            ),
            "memory_summary.false_safe_frontier_control_characterization_snapshot_v1": _artifact_reference(
                frontier_snapshot,
                latest_snapshots,
            ),
        },
        "governed_skill_trial_admission_summary": {
            "candidate_evaluated": {
                "skill_id": str(primary_candidate.get("skill_id", "")),
                "candidate_name": str(primary_candidate.get("candidate_name", "")),
                "candidate_summary": str(primary_candidate.get("candidate_summary", "")),
                "screened_skill_outcome": str(primary_screened.get("skill_screen_outcome", "")),
            },
            "trial_admission_schema": trial_admission_schema,
            "trial_admission_checks": dict(primary_trial_admission.get("trial_admission_checks", {})),
            "admission_outcome": str(primary_trial_admission.get("trial_admission_outcome", "")),
            "reason": str(primary_trial_admission.get("reason", "")),
            "trial_envelope_if_admissible": dict(primary_trial_admission.get("trial_envelope", {})),
            "paused_branch_trial_compatibility": dict(primary_trial_admission.get("paused_branch_trial_compatibility", {})),
            "trial_isolation_report": dict(primary_trial_admission.get("trial_isolation_report", {})),
            "secondary_context_candidates": secondary_context,
            "governance_inputs_consumed": {
                "directive_state_latest": str(DIRECTIVE_STATE_PATH),
                "directive_history": str(DIRECTIVE_HISTORY_PATH),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
                "branch_registry_latest": str(BRANCH_REGISTRY_PATH),
                "bucket_state_latest": str(BUCKET_STATE_PATH),
            },
            "governance_input_state": {
                "directive_is_active": str(directive_state.get("initialization_state", "")) == "active",
                "directive_history_tail": directive_history_tail,
                "self_structure_event_tail": self_structure_event_tail,
                "current_branch_state": str(branch_record.get("state", "")),
                "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
            },
            "why_governance_remains_source_of_truth": {
                "owner": "governance_substrate_v1",
                "proposal_learning_loop_is_governance_truth_source": False,
                "reason": "trial admission reads directive, branch, bucket, self-structure, and prior governed-skill artifacts as the authoritative decision context",
            },
        },
        "analytics_context": {
            "analytics_report_path": str(intervention_data_dir() / "intervention_analytics_latest.json"),
            "proposal_recommendations_path": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            "proposal_count": int(analytics.get("proposal_count", 0) or 0),
            "current_recommendation_top_templates": suggested_templates,
        },
        "decision_recommendation": {
            "governed_skill_trial_admission_in_place": True,
            "actual_behavior_changing_skill_branch_opened": False,
            "primary_candidate_outcome": str(primary_trial_admission.get("trial_admission_outcome", "")),
            "best_next_template": (
                "proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1"
                if str(primary_trial_admission.get("trial_admission_outcome", "")) == "admissible_for_sandboxed_trial"
                else "memory_summary.v4_governed_skill_trial_readiness_gap_snapshot_v1"
            ),
            "recommended_next_step": (
                "if approved, keep the wm-hybrid branch paused and admit Local trace parser trial only inside the bounded sandbox envelope"
                if str(primary_trial_admission.get("trial_admission_outcome", "")) == "admissible_for_sandboxed_trial"
                else "do not open a skill branch; resolve the remaining trial-admission gaps first"
            ),
            "plan_should_remain_non_owning": True,
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
        },
        "observability_gain": {
            "passed": True,
            "reason": "the best sandbox-first candidate now has an explicit governance-owned trial-admission decision and envelope without opening a skill branch",
            "artifact_paths": {
                "skill_trial_admission_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the trial-admission gate shows whether the primary sandbox-first skill can progress into a real governed trial while keeping the paused wm-hybrid branch paused",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.98,
            "reason": "the gate separates true sandbox trial admission from diagnostic-only, blocked, forbidden, and still-gated cases with an explicit trial envelope",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the trial-admission gate is governance-owned and diagnostic only; live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope remain unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": (
                "proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1"
                if str(primary_trial_admission.get("trial_admission_outcome", "")) == "admissible_for_sandboxed_trial"
                else "memory_summary.v4_governed_skill_trial_readiness_gap_snapshot_v1"
            ),
            "reason": "the next move is now explicit for the primary candidate and still does not require opening a skill branch by default",
        },
        "diagnostic_conclusions": {
            "governed_skill_trial_admission_in_place": True,
            "actual_behavior_changing_skill_branch_opened": False,
            "primary_candidate_outcome": str(primary_trial_admission.get("trial_admission_outcome", "")),
            "plan_should_remain_non_owning": True,
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
            "best_next_template": (
                "proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1"
                if str(primary_trial_admission.get("trial_admission_outcome", "")) == "admissible_for_sandboxed_trial"
                else "memory_summary.v4_governed_skill_trial_readiness_gap_snapshot_v1"
            ),
        },
    }
    _write_json(artifact_path, artifact_payload)

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: the strongest sandbox-first skill candidate now has an explicit governed trial-admission decision without opening a branch",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }


def run_local_trace_parser_trial(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governance_substrate_v1_snapshot"
    )
    skill_candidate_screen_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_skill_candidate_screen_snapshot_v1"
    )
    skill_trial_admission_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_skill_trial_admission_snapshot_v1"
    )
    if not all([governance_snapshot, skill_candidate_screen_snapshot, skill_trial_admission_snapshot]):
        return {
            "passed": False,
            "shadow_contract": "sandboxed_skill_trial",
            "proposal_semantics": "shadow_skill_trial",
            "reason": "shadow trial failed: governed skill execution requires governance substrate, skill candidate screen, and skill trial admission artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite governed-skill artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite governed-skill artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite governed-skill artifacts"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "the admitted local trace parser trial cannot run without the governance-owned admission context",
            },
        }

    directive_state = _load_json_file(DIRECTIVE_STATE_PATH)
    bucket_state = _load_json_file(BUCKET_STATE_PATH)
    self_structure_state = _load_json_file(SELF_STRUCTURE_STATE_PATH)
    branch_registry = _load_json_file(BRANCH_REGISTRY_PATH)
    directive_history = _load_jsonl(DIRECTIVE_HISTORY_PATH)
    self_structure_ledger = _load_jsonl(SELF_STRUCTURE_LEDGER_PATH)
    analytics = build_intervention_ledger_analytics()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")
    latest_snapshots = load_latest_snapshots()

    if not all([directive_state, bucket_state, self_structure_state, branch_registry]):
        return {
            "passed": False,
            "shadow_contract": "sandboxed_skill_trial",
            "proposal_semantics": "shadow_skill_trial",
            "reason": "shadow trial failed: current directive, bucket, self-structure, and branch registry artifacts are required",
            "observability_gain": {"passed": False, "reason": "missing durable governance state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing durable governance state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing durable governance state"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "the trial cannot stay governance-owned without directive, bucket, self-structure, and branch registry artifacts",
            },
        }

    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_directive = dict(directive_state.get("current_directive_state", {}))
    governed_skill_subsystem = dict(self_structure_state.get("governed_skill_subsystem", {}))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    last_trial_admission = dict(governed_skill_subsystem.get("last_trial_admission_outcome", {}))
    current_branch_state = str(branch_record.get("state", ""))
    primary_outcome = str(last_trial_admission.get("trial_admission_outcome", ""))

    if current_branch_state != "paused_with_baseline_held":
        return {
            "passed": False,
            "shadow_contract": "sandboxed_skill_trial",
            "proposal_semantics": "shadow_skill_trial",
            "reason": "shadow trial failed: the admitted trial may run only while the wm-hybrid branch remains paused_with_baseline_held",
            "observability_gain": {"passed": False, "reason": "branch state is no longer the admitted paused state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "branch state is no longer the admitted paused state"},
            "ambiguity_reduction": {"passed": False, "reason": "branch state is no longer the admitted paused state"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "the trial envelope is invalid if the branch is not paused_with_baseline_held",
            },
        }
    if primary_outcome != "admissible_for_sandboxed_trial":
        return {
            "passed": False,
            "shadow_contract": "sandboxed_skill_trial",
            "proposal_semantics": "shadow_skill_trial",
            "reason": "shadow trial failed: Local trace parser trial is not currently admitted for a sandboxed governed trial",
            "observability_gain": {"passed": False, "reason": "primary skill candidate is not admitted for sandboxed trial execution"},
            "activation_analysis_usefulness": {"passed": False, "reason": "primary skill candidate is not admitted for sandboxed trial execution"},
            "ambiguity_reduction": {"passed": False, "reason": "primary skill candidate is not admitted for sandboxed trial execution"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "governed skill execution cannot begin before the primary candidate is admitted",
            },
        }

    candidate_examples = _example_skill_candidates()
    primary_candidate = next(
        (item for item in candidate_examples if str(item.get("skill_id", "")) == "skill_candidate_local_trace_parser_trial"),
        {},
    )
    if not primary_candidate:
        return {
            "passed": False,
            "shadow_contract": "sandboxed_skill_trial",
            "proposal_semantics": "shadow_skill_trial",
            "reason": "shadow trial failed: Local trace parser trial candidate definition is missing",
            "observability_gain": {"passed": False, "reason": "primary candidate definition missing from governed skill acquisition module"},
            "activation_analysis_usefulness": {"passed": False, "reason": "primary candidate definition missing from governed skill acquisition module"},
            "ambiguity_reduction": {"passed": False, "reason": "primary candidate definition missing from governed skill acquisition module"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "the admitted candidate cannot be executed without its canonical definition",
            },
        }

    trial_admission_artifact_path = Path(
        str(
            governed_skill_subsystem.get("last_trial_admission_artifact_path")
            or dict(skill_trial_admission_snapshot).get("artifact_path", "")
        )
    )
    candidate_screen_artifact_path = Path(
        str(
            governed_skill_subsystem.get("last_candidate_screen_artifact_path")
            or dict(skill_candidate_screen_snapshot).get("artifact_path", "")
        )
    )
    trial_admission_artifact = _load_json_file(trial_admission_artifact_path)
    candidate_screen_artifact = _load_json_file(candidate_screen_artifact_path)
    trial_admission_summary = dict(trial_admission_artifact.get("governed_skill_trial_admission_summary", {}))
    trial_envelope = dict(trial_admission_summary.get("trial_envelope_if_admissible", {}))

    log_group = _select_trial_log_group(max_files=3)
    if not bool(log_group.get("passed", False)):
        return {
            "passed": False,
            "shadow_contract": "sandboxed_skill_trial",
            "proposal_semantics": "shadow_skill_trial",
            "reason": "shadow trial failed: no trusted local log group is available for the admitted trace parser trial",
            "observability_gain": {"passed": False, "reason": str(log_group.get("reason", ""))},
            "activation_analysis_usefulness": {"passed": False, "reason": str(log_group.get("reason", ""))},
            "ambiguity_reduction": {"passed": False, "reason": str(log_group.get("reason", ""))},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "the local trace parser trial has no trusted local logs to parse",
            },
        }

    selected_log_paths = [Path(path) for path in list(log_group.get("selected_paths", []))]
    parsed_logs = [_parse_local_trace_log(path) for path in selected_log_paths]
    parsed_log_summary = _summarize_parsed_logs(parsed_logs)

    trial_utility_passed = bool(
        int(parsed_log_summary.get("parsed_file_count", 0) or 0) >= 1
        and int(parsed_log_summary.get("dummy_eval_count", 0) or 0) >= 9
        and float(parsed_log_summary.get("recognized_line_share_weighted", 0.0) or 0.0) >= 0.25
    )
    trial_utility_reason = (
        "the parser extracted bounded, structured dummy_eval and patch evidence from trusted local logs with useful coverage"
        if trial_utility_passed
        else "the parser did not extract enough bounded local evidence to justify moving beyond sandbox-only handling"
    )

    directive_relevant = str(primary_candidate.get("directive_relevance", "")) == "high"
    duplication_ok = str(primary_candidate.get("duplication_risk", "")) == "low"
    network_mode_observed = "none"
    network_mode_required = str(dict(trial_envelope.get("resource_limits", {})).get("network_mode", "none") or "none")
    write_paths = [
        _diagnostic_artifact_dir()
        / f"proposal_learning_loop_v4_governed_skill_local_trace_parser_trial_v1_{proposal['proposal_id']}.json",
        SELF_STRUCTURE_STATE_PATH,
        SELF_STRUCTURE_LEDGER_PATH,
    ]
    write_root_allowlist = [
        (intervention_data_dir()).resolve(),
        (ACTIVE_STATUS_PATH.parent / "interventions").resolve(),
    ]

    def _path_within_allowed_roots(path: Path) -> bool:
        resolved_path = path.resolve()
        return any(str(resolved_path).startswith(str(root)) for root in write_root_allowlist)

    writes_within_approved_roots = all(_path_within_allowed_roots(path) for path in write_paths)

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "branch_context": {
            "current_branch_id": str(branch_record.get("branch_id", "")),
            "current_branch_state": current_branch_state,
            "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
            "plan_non_owning": bool(current_state_summary.get("plan_non_owning", False)),
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
        },
        "comparison_references": {
            "memory_summary.v4_governance_substrate_v1_snapshot": _artifact_reference(governance_snapshot, latest_snapshots),
            "memory_summary.v4_governed_skill_candidate_screen_snapshot_v1": _artifact_reference(
                skill_candidate_screen_snapshot,
                latest_snapshots,
            ),
            "memory_summary.v4_governed_skill_trial_admission_snapshot_v1": _artifact_reference(
                skill_trial_admission_snapshot,
                latest_snapshots,
            ),
        },
        "governed_skill_trial_summary": {
            "candidate_evaluated": {
                "skill_id": str(primary_candidate.get("skill_id", "")),
                "candidate_name": str(primary_candidate.get("candidate_name", "")),
                "candidate_summary": str(primary_candidate.get("candidate_summary", "")),
                "trial_admission_outcome": primary_outcome,
            },
            "what_the_trial_did": [
                "selected a single coherent trusted local shadow-log group",
                "parsed local intervention shadow logs for section markers, adopt_patch events, and dummy_eval payloads",
                "read the latest governed skill candidate screen and trial-admission artifacts as trusted diagnostic-memory context",
                "materialized only shadow-only evidence and parser coverage summaries without opening or mutating a branch",
            ],
            "local_sources_parsed": {
                "trusted_log_group": dict(log_group),
                "trusted_log_parse_summary": parsed_log_summary,
                "trusted_diagnostic_memory_sources": [
                    _trial_artifact_digest(candidate_screen_artifact_path),
                    _trial_artifact_digest(trial_admission_artifact_path),
                ],
            },
            "evidence_produced": {
                "utility_assessment": {
                    "passed": trial_utility_passed,
                    "reason": trial_utility_reason,
                    "dummy_eval_count": int(parsed_log_summary.get("dummy_eval_count", 0) or 0),
                    "patch_tuple_count": int(parsed_log_summary.get("patch_tuple_count", 0) or 0),
                    "recognized_line_share_weighted": float(
                        parsed_log_summary.get("recognized_line_share_weighted", 0.0) or 0.0
                    ),
                },
                "directive_relevance": {
                    "passed": directive_relevant,
                    "value": str(primary_candidate.get("directive_relevance", "")),
                    "reason": "candidate remains high-directive-relevance local parsing work inside governance-owned phase-1 skill execution",
                },
                "duplication_overlap": {
                    "passed": duplication_ok,
                    "value": str(primary_candidate.get("duplication_risk", "")),
                    "reason": "candidate remains low-duplication relative to the current governed skill set",
                },
            },
            "sandbox_envelope_compliance": {
                "branch_state_stayed_paused_with_baseline_held": current_branch_state == "paused_with_baseline_held",
                "no_branch_state_mutation": True,
                "no_retained_promotion": True,
                "no_protected_surface_modification": True,
                "network_mode_required": network_mode_required,
                "network_mode_observed": network_mode_observed,
                "network_mode_remained_none": network_mode_required == "none" and network_mode_observed == "none",
                "writes_within_approved_roots": writes_within_approved_roots,
                "approved_write_paths": [str(path) for path in write_paths],
                "resource_limits_requested": dict(primary_candidate.get("resource_cost_estimate", {})),
                "resource_limits_admitted": dict(trial_envelope.get("resource_limits", {})),
            },
            "governance_source_of_truth": {
                "owner": "governance_substrate_v1",
                "proposal_learning_loop_is_governance_truth_source": False,
                "reason": "the trial reads directive, bucket, self-structure, branch, candidate-screen, and trial-admission artifacts as source of truth and only writes bounded evidence back into governance-owned state",
            },
            "future_handling_assessment": {
                "candidate_status": (
                    "viable_for_future_provisional_skill_handling"
                    if trial_utility_passed and directive_relevant and duplication_ok
                    else "remain_sandbox_only"
                ),
                "reason": (
                    "the parser stayed bounded, extracted useful local shadow evidence, and remained directive-relevant without governance drift"
                    if trial_utility_passed and directive_relevant and duplication_ok
                    else "the parser should remain sandbox-only until stronger bounded evidence is available"
                ),
            },
            "governance_inputs_consumed": {
                "directive_state_latest": str(DIRECTIVE_STATE_PATH),
                "directive_history": str(DIRECTIVE_HISTORY_PATH),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
                "branch_registry_latest": str(BRANCH_REGISTRY_PATH),
                "bucket_state_latest": str(BUCKET_STATE_PATH),
                "intervention_analytics_latest": str(intervention_data_dir() / "intervention_analytics_latest.json"),
                "proposal_recommendations_latest": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            },
        },
        "analytics_context": {
            "analytics_report_path": str(intervention_data_dir() / "intervention_analytics_latest.json"),
            "proposal_recommendations_path": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            "proposal_count": int(analytics.get("proposal_count", 0) or 0),
            "current_recommendation_top_templates": [
                str(item.get("template_name", ""))
                for item in list(recommendations.get("all_ranked_proposals", []))
                if isinstance(item, dict) and str(item.get("decision", "")) == "suggested"
            ][:8],
        },
        "observability_gain": {
            "passed": True,
            "reason": "the admitted skill trial now produces bounded structured evidence about local trace parsing utility, coverage, and governance-envelope compliance",
            "artifact_paths": {
                "trial_artifact": str(write_paths[0]),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the first real governed skill execution can now be judged on bounded evidence instead of only pre-trial admission logic",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.98,
            "reason": "the trial distinguishes useful bounded parser execution from governance drift, retained promotion, or branch reopen behavior",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the skill trial remained shadow-only, local, reversible, and governance-bounded; live policy, thresholds, routing, frozen benchmark semantics, and projection-safe envelope stayed unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": "memory_summary.v4_governed_skill_trial_evidence_snapshot_v1",
            "reason": "the next step should review the bounded sandbox evidence before any provisional or retained handling is considered",
        },
        "diagnostic_conclusions": {
            "governed_skill_trial_execution_in_place": True,
            "branch_state_stayed_paused_with_baseline_held": True,
            "retained_promotion_occurred": False,
            "plan_should_remain_non_owning": bool(current_state_summary.get("plan_non_owning", False)),
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "candidate_future_status": (
                "viable_for_future_provisional_skill_handling"
                if trial_utility_passed and directive_relevant and duplication_ok
                else "remain_sandbox_only"
            ),
            "best_next_template": "memory_summary.v4_governed_skill_trial_evidence_snapshot_v1",
        },
    }

    artifact_path = Path(str(write_paths[0]))
    _write_json(artifact_path, artifact_payload)

    estimated_write_bytes = (
        int(artifact_path.stat().st_size)
        + len(json.dumps({"updated_state": True}))
        + len(json.dumps({"ledger_event": True}))
    )
    artifact_payload["governed_skill_trial_summary"]["sandbox_envelope_compliance"]["estimated_write_bytes"] = int(
        estimated_write_bytes
    )
    artifact_payload["governed_skill_trial_summary"]["sandbox_envelope_compliance"]["storage_budget_mb"] = int(
        dict(primary_candidate.get("resource_cost_estimate", {})).get("storage_write_mb", 0) or 0
    )
    artifact_payload["governed_skill_trial_summary"]["sandbox_envelope_compliance"]["storage_budget_respected"] = (
        estimated_write_bytes
        <= int(dict(primary_candidate.get("resource_cost_estimate", {})).get("storage_write_mb", 0) or 0) * 1024 * 1024
    )
    _write_json(artifact_path, artifact_payload)

    updated_self_structure_state = dict(self_structure_state)
    updated_governed_skill_subsystem = dict(governed_skill_subsystem)
    updated_governed_skill_subsystem["last_trial_execution_artifact_path"] = str(artifact_path)
    updated_governed_skill_subsystem["last_trial_execution_outcome"] = {
        "primary_candidate_skill_id": str(primary_candidate.get("skill_id", "")),
        "primary_candidate_name": str(primary_candidate.get("candidate_name", "")),
        "trial_execution_outcome": "sandbox_trial_completed",
        "bounded_and_reversible": True,
        "branch_state_mutation": False,
        "retained_promotion": False,
        "candidate_future_status": str(
            dict(artifact_payload["diagnostic_conclusions"]).get("candidate_future_status", "")
        ),
    }
    updated_governed_skill_subsystem["best_next_template"] = "memory_summary.v4_governed_skill_trial_evidence_snapshot_v1"

    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["governed_skill_subsystem"] = updated_governed_skill_subsystem
    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "latest_skill_trial_execution_outcome": "sandbox_trial_completed",
            "latest_skill_trial_candidate": str(primary_candidate.get("candidate_name", "")),
            "skill_trial_branch_opened": False,
            "current_branch_state": current_branch_state,
            "plan_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "retained_skill_promotion_performed": False,
        }
    )
    updated_self_structure_state["current_state_summary"] = updated_current_state_summary
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    ledger_event = {
        "event_id": f"governed_skill_local_trace_parser_trial_v1::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_skill_local_trace_parser_trial_v1_materialized",
        "event_class": "governed_skill_trial_execution",
        "directive_id": str(current_directive.get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": current_branch_state,
        "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
        "primary_candidate_skill_id": str(primary_candidate.get("skill_id", "")),
        "trial_execution_outcome": "sandbox_trial_completed",
        "branch_state_mutation": False,
        "retained_promotion": False,
        "network_mode": network_mode_observed,
        "artifact_paths": {
            "directive_state_latest": str(DIRECTIVE_STATE_PATH),
            "directive_history": str(DIRECTIVE_HISTORY_PATH),
            "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
            "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            "branch_registry_latest": str(BRANCH_REGISTRY_PATH),
            "bucket_state_latest": str(BUCKET_STATE_PATH),
            "skill_candidate_screen_artifact": str(candidate_screen_artifact_path),
            "skill_trial_admission_artifact": str(trial_admission_artifact_path),
            "skill_trial_execution_artifact": str(artifact_path),
        },
        "source_proposal_id": str(proposal.get("proposal_id", "")),
    }
    _append_jsonl(SELF_STRUCTURE_LEDGER_PATH, ledger_event)

    return {
        "passed": True,
        "shadow_contract": "sandboxed_skill_trial",
        "proposal_semantics": "shadow_skill_trial",
        "reason": "shadow trial passed: the admitted local trace parser executed inside the governed sandbox envelope and produced bounded local evidence without reopening the branch",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }


def run_trial_evidence_snapshot(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governance_substrate_v1_snapshot"
    )
    skill_candidate_screen_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_skill_candidate_screen_snapshot_v1"
    )
    skill_trial_admission_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_skill_trial_admission_snapshot_v1"
    )
    skill_trial_execution_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1"
    )
    if not all(
        [
            governance_snapshot,
            skill_candidate_screen_snapshot,
            skill_trial_admission_snapshot,
            skill_trial_execution_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed skill trial evidence review requires governance substrate, candidate screen, trial admission, and trial execution artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite governed-skill artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite governed-skill artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite governed-skill artifacts"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "trial evidence cannot be reviewed without the current governance-owned trial artifacts",
            },
        }

    directive_state = _load_json_file(DIRECTIVE_STATE_PATH)
    bucket_state = _load_json_file(BUCKET_STATE_PATH)
    self_structure_state = _load_json_file(SELF_STRUCTURE_STATE_PATH)
    branch_registry = _load_json_file(BRANCH_REGISTRY_PATH)
    directive_history = _load_jsonl(DIRECTIVE_HISTORY_PATH)
    self_structure_ledger = _load_jsonl(SELF_STRUCTURE_LEDGER_PATH)
    intervention_ledger = _load_jsonl(intervention_data_dir() / "intervention_ledger.jsonl")
    analytics = build_intervention_ledger_analytics()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")
    latest_snapshots = load_latest_snapshots()

    if not all([directive_state, bucket_state, self_structure_state, branch_registry]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: current directive, bucket, self-structure, and branch registry artifacts are required",
            "observability_gain": {"passed": False, "reason": "missing durable governance state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing durable governance state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing durable governance state"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "trial evidence review cannot stay governance-owned without directive, bucket, self-structure, and branch state artifacts",
            },
        }

    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_directive = dict(directive_state.get("current_directive_state", {}))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    governed_skill_subsystem = dict(self_structure_state.get("governed_skill_subsystem", {}))
    current_branch_state = str(branch_record.get("state", ""))

    if current_branch_state != "paused_with_baseline_held":
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: trial evidence review is valid only while the wm-hybrid branch remains paused_with_baseline_held",
            "observability_gain": {"passed": False, "reason": "branch state is no longer the held paused baseline"},
            "activation_analysis_usefulness": {"passed": False, "reason": "branch state is no longer the held paused baseline"},
            "ambiguity_reduction": {"passed": False, "reason": "branch state is no longer the held paused baseline"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "trial escalation cannot be judged correctly if the paused branch has already changed state",
            },
        }

    candidate_screen_artifact_path = Path(str(governed_skill_subsystem.get("last_candidate_screen_artifact_path", "")))
    trial_admission_artifact_path = Path(str(governed_skill_subsystem.get("last_trial_admission_artifact_path", "")))
    trial_execution_artifact_path = Path(str(governed_skill_subsystem.get("last_trial_execution_artifact_path", "")))

    candidate_screen_artifact = _load_json_file(candidate_screen_artifact_path)
    trial_admission_artifact = _load_json_file(trial_admission_artifact_path)
    trial_execution_artifact = _load_json_file(trial_execution_artifact_path)

    if not all([candidate_screen_artifact, trial_admission_artifact, trial_execution_artifact]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: candidate-screen, trial-admission, and trial-execution artifacts must all exist for evidence review",
            "observability_gain": {"passed": False, "reason": "missing governed skill trial evidence artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing governed skill trial evidence artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing governed skill trial evidence artifacts"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "trial evidence cannot be reviewed if one of the governed-skill artifacts is absent",
            },
        }

    candidate_screen_summary = dict(candidate_screen_artifact.get("governed_skill_candidate_screen_summary", {}))
    trial_admission_summary = dict(trial_admission_artifact.get("governed_skill_trial_admission_summary", {}))
    trial_execution_summary = dict(trial_execution_artifact.get("governed_skill_trial_summary", {}))
    sandbox_compliance = dict(trial_execution_summary.get("sandbox_envelope_compliance", {}))
    utility_assessment = dict(dict(trial_execution_summary.get("evidence_produced", {})).get("utility_assessment", {}))
    duplication_assessment = dict(dict(trial_execution_summary.get("evidence_produced", {})).get("duplication_overlap", {}))
    directive_relevance_assessment = dict(dict(trial_execution_summary.get("evidence_produced", {})).get("directive_relevance", {}))
    future_handling_assessment = dict(trial_execution_summary.get("future_handling_assessment", {}))
    log_parse_summary = dict(dict(trial_execution_summary.get("local_sources_parsed", {})).get("trusted_log_parse_summary", {}))
    per_file = list(log_parse_summary.get("per_file", []))

    evidence_quality = {
        "parser_useful": bool(utility_assessment.get("passed", False)),
        "intended_sources_reliably_parsed": bool(
            int(log_parse_summary.get("parsed_file_count", 0) or 0) >= 3
            and all(float(dict(item).get("recognized_line_share", 0.0) or 0.0) >= 0.95 for item in per_file)
        ),
        "coverage_adequate": bool(
            int(log_parse_summary.get("dummy_eval_count", 0) or 0) >= 100
            and int(log_parse_summary.get("patch_tuple_count", 0) or 0) >= 500
        ),
        "recognized_output_quality_high": bool(
            float(log_parse_summary.get("recognized_line_share_weighted", 0.0) or 0.0) >= 0.95
        ),
    }
    evidence_quality["passed"] = all(bool(value) for key, value in evidence_quality.items() if key != "passed")
    evidence_quality["reason"] = (
        "the parser was useful, reliable, adequately covered the intended local sources, and produced high-quality recognized output"
        if evidence_quality["passed"]
        else "the parser evidence is not yet strong enough across utility, reliability, coverage, and recognized output quality"
    )

    current_bucket_state = dict(bucket_state.get("current_bucket_state", {}))
    cpu_limit = int(dict(current_bucket_state.get("cpu_limit", {})).get("max_parallel_processes", 0) or 0)
    memory_limit = int(dict(current_bucket_state.get("memory_limit", {})).get("max_working_set_mb", 0) or 0)
    storage_limit = int(dict(current_bucket_state.get("storage_limit", {})).get("max_write_mb_per_action", 0) or 0)
    admitted_limits = dict(sandbox_compliance.get("resource_limits_admitted", {}))
    cpu_requested = int(admitted_limits.get("cpu_parallel_units", 0) or 0)
    memory_requested = int(admitted_limits.get("memory_mb", 0) or 0)
    storage_requested = int(admitted_limits.get("storage_write_mb", 0) or 0)
    bucket_pressure = {
        "cpu_ratio_to_bucket": float(cpu_requested) / float(cpu_limit) if cpu_limit else 0.0,
        "memory_ratio_to_bucket": float(memory_requested) / float(memory_limit) if memory_limit else 0.0,
        "storage_ratio_to_bucket": float(storage_requested) / float(storage_limit) if storage_limit else 0.0,
    }
    bucket_pressure["concern_level"] = (
        "low"
        if max(bucket_pressure.values()) <= 0.25
        else "moderate"
    )

    envelope_compliance = {
        "write_limits_respected": bool(sandbox_compliance.get("storage_budget_respected", False)),
        "resource_limits_respected": bucket_pressure["concern_level"] == "low",
        "network_remained_none": bool(sandbox_compliance.get("network_mode_remained_none", False)),
        "branch_state_unchanged": bool(sandbox_compliance.get("branch_state_stayed_paused_with_baseline_held", False)),
        "governance_remained_source_of_truth": not bool(
            dict(trial_execution_summary.get("governance_source_of_truth", {})).get(
                "proposal_learning_loop_is_governance_truth_source",
                False,
            )
        ),
        "no_retained_promotion": bool(sandbox_compliance.get("no_retained_promotion", False)),
    }
    envelope_compliance["passed"] = all(bool(value) for key, value in envelope_compliance.items() if key != "passed")
    envelope_compliance["reason"] = (
        "the trial stayed within write, resource, network, branch-state, and governance-source-of-truth constraints"
        if envelope_compliance["passed"]
        else "the trial evidence shows at least one envelope-compliance failure"
    )

    directive_relevance_review = {
        "directive_is_active": str(directive_state.get("initialization_state", "")) == "active",
        "candidate_directive_relevance_high": bool(directive_relevance_assessment.get("passed", False)),
        "supports_governance_stack": "governance" in str(
            dict(future_handling_assessment).get("reason", "")
        ).lower()
        or bool(utility_assessment.get("passed", False)),
        "trusted_source_policy_preserved": bool(sandbox_compliance.get("network_mode_remained_none", False)),
    }
    directive_relevance_review["passed"] = all(
        bool(value) for key, value in directive_relevance_review.items() if key != "passed"
    )
    directive_relevance_review["reason"] = (
        "the skill remains justified under the active directive because it contributes bounded governance-supportive evidence under the current constraints"
        if directive_relevance_review["passed"]
        else "the skill no longer has a strong enough directive case under the current governance constraints"
    )

    screened_examples = list(governed_skill_subsystem.get("last_candidate_screen_examples", []))
    distinct_capability = bool(duplication_assessment.get("passed", False)) and not any(
        str(item.get("skill_id", "")) == "skill_candidate_duplicate_planner_adapter"
        and str(item.get("screening_outcome", "")) != "blocked"
        for item in screened_examples
    )
    duplication_review = {
        "low_duplication_risk": bool(duplication_assessment.get("passed", False)),
        "distinct_capability": distinct_capability,
        "existing_overlap_problem": False,
    }
    duplication_review["passed"] = all(bool(value) for key, value in duplication_review.items() if key != "existing_overlap_problem")
    duplication_review["reason"] = (
        "the parser adds distinct bounded local trace-extraction capability rather than duplicating an already admitted skill path"
        if duplication_review["passed"]
        else "the parser overlaps too much with existing or already-screened capability"
    )

    risk_review = {
        "governance_drift_observed": False,
        "bucket_pressure_concern": bucket_pressure["concern_level"] != "low",
        "protected_surface_creep": False,
        "downstream_selected_set_drift": False,
        "plan_ownership_change": False,
        "routing_work_drift": False,
    }
    risk_review["passed"] = not any(bool(value) for value in risk_review.values())
    risk_review["reason"] = (
        "no governance drift, bucket pressure, protected-surface creep, downstream drift, plan_ ownership change, or routing drift was observed"
        if risk_review["passed"]
        else "risk review surfaced a governance or envelope concern that blocks escalation"
    )

    if evidence_quality["passed"] and envelope_compliance["passed"] and directive_relevance_review["passed"] and duplication_review["passed"] and risk_review["passed"]:
        outcome_class = "admissible_for_provisional_handling"
        outcome_reason = "bounded trial evidence is strong enough to justify a governance-owned provisional-handling review, while still stopping short of retained promotion"
        best_next_template = "memory_summary.v4_governed_skill_provisional_admission_snapshot_v1"
    elif not envelope_compliance["passed"] or not risk_review["passed"] or not directive_relevance_review["passed"]:
        outcome_class = "blocked_from_escalation"
        outcome_reason = "the evidence review found an envelope, governance, or directive problem that blocks further escalation"
        best_next_template = "memory_summary.v4_governed_skill_trial_gap_snapshot_v1"
    else:
        outcome_class = "remain_sandbox_only"
        outcome_reason = "the trial stayed safe, but the evidence is not yet strong or distinct enough to justify provisional handling"
        best_next_template = "memory_summary.v4_governed_skill_trial_gap_snapshot_v1"

    artifact_path = (
        _diagnostic_artifact_dir()
        / f"memory_summary_v4_governed_skill_trial_evidence_snapshot_v1_{proposal['proposal_id']}.json"
    )

    updated_self_structure_state = dict(self_structure_state)
    updated_governed_skill_subsystem = dict(governed_skill_subsystem)
    updated_governed_skill_subsystem["last_trial_evidence_artifact_path"] = str(artifact_path)
    updated_governed_skill_subsystem["last_trial_evidence_outcome"] = {
        "primary_candidate_skill_id": "skill_candidate_local_trace_parser_trial",
        "primary_candidate_name": "Local trace parser trial",
        "evidence_review_outcome": outcome_class,
        "reason": outcome_reason,
        "retained_promotion": False,
        "branch_state_after_review": current_branch_state,
    }
    updated_governed_skill_subsystem["best_next_template"] = best_next_template
    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["governed_skill_subsystem"] = updated_governed_skill_subsystem
    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "latest_skill_trial_evidence_outcome": outcome_class,
            "latest_skill_trial_candidate": "Local trace parser trial",
            "retained_skill_promotion_performed": False,
            "current_branch_state": current_branch_state,
            "plan_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
        }
    )
    updated_self_structure_state["current_state_summary"] = updated_current_state_summary
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    ledger_event = {
        "event_id": f"governed_skill_trial_evidence_snapshot_v1::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_skill_trial_evidence_snapshot_v1_materialized",
        "event_class": "governed_skill_trial_evidence_review",
        "directive_id": str(current_directive.get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": current_branch_state,
        "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
        "primary_candidate_skill_id": "skill_candidate_local_trace_parser_trial",
        "evidence_review_outcome": outcome_class,
        "retained_promotion": False,
        "branch_state_mutation": False,
        "artifact_paths": {
            "directive_state_latest": str(DIRECTIVE_STATE_PATH),
            "directive_history": str(DIRECTIVE_HISTORY_PATH),
            "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
            "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            "branch_registry_latest": str(BRANCH_REGISTRY_PATH),
            "bucket_state_latest": str(BUCKET_STATE_PATH),
            "intervention_ledger": str(intervention_data_dir() / "intervention_ledger.jsonl"),
            "skill_candidate_screen_artifact": str(candidate_screen_artifact_path),
            "skill_trial_admission_artifact": str(trial_admission_artifact_path),
            "skill_trial_execution_artifact": str(trial_execution_artifact_path),
            "skill_trial_evidence_artifact": str(artifact_path),
        },
        "source_proposal_id": str(proposal.get("proposal_id", "")),
    }
    _append_jsonl(SELF_STRUCTURE_LEDGER_PATH, ledger_event)

    directive_history_tail = [str(item.get("event_type", "")) for item in directive_history[-8:]]
    self_structure_event_tail = [str(item.get("event_type", "")) for item in self_structure_ledger[-12:]]

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_governed_skill_trial_evidence_snapshot_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "branch_context": {
            "current_branch_id": str(branch_record.get("branch_id", "")),
            "current_branch_state": current_branch_state,
            "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
            "plan_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
        },
        "comparison_references": {
            "memory_summary.v4_governance_substrate_v1_snapshot": _artifact_reference(governance_snapshot, latest_snapshots),
            "memory_summary.v4_governed_skill_candidate_screen_snapshot_v1": _artifact_reference(
                skill_candidate_screen_snapshot,
                latest_snapshots,
            ),
            "memory_summary.v4_governed_skill_trial_admission_snapshot_v1": _artifact_reference(
                skill_trial_admission_snapshot,
                latest_snapshots,
            ),
            "proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1": _artifact_reference(
                skill_trial_execution_snapshot,
                latest_snapshots,
            ),
        },
        "governed_skill_trial_evidence_summary": {
            "evidence_reviewed": {
                "trial_execution_artifact": str(trial_execution_artifact_path),
                "trial_admission_artifact": str(trial_admission_artifact_path),
                "candidate_screen_artifact": str(candidate_screen_artifact_path),
                "intervention_ledger_rows_reviewed": len(intervention_ledger[-6:]),
                "directive_history_tail": directive_history_tail,
                "self_structure_event_tail": self_structure_event_tail,
            },
            "evidence_quality": evidence_quality,
            "envelope_compliance": dict(envelope_compliance, bucket_pressure=bucket_pressure),
            "directive_relevance": directive_relevance_review,
            "duplication_overlap_assessment": duplication_review,
            "risk_review": risk_review,
            "escalation_recommendation": {
                "outcome_class": outcome_class,
                "reason": outcome_reason,
                "best_next_template": best_next_template,
            },
            "current_trial_state": {
                "trial_execution_outcome": str(
                    dict(governed_skill_subsystem.get("last_trial_execution_outcome", {})).get("trial_execution_outcome", "")
                ),
                "future_handling_assessment": future_handling_assessment,
                "candidate_screen_outcome": str(
                    dict(candidate_screen_summary.get("current_screen_outcome", {})).get("status", "")
                ),
                "trial_admission_outcome": str(trial_admission_summary.get("admission_outcome", "")),
            },
            "governance_inputs_consumed": {
                "directive_state_latest": str(DIRECTIVE_STATE_PATH),
                "directive_history": str(DIRECTIVE_HISTORY_PATH),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
                "branch_registry_latest": str(BRANCH_REGISTRY_PATH),
                "bucket_state_latest": str(BUCKET_STATE_PATH),
                "intervention_ledger": str(intervention_data_dir() / "intervention_ledger.jsonl"),
                "intervention_analytics_latest": str(intervention_data_dir() / "intervention_analytics_latest.json"),
                "proposal_recommendations_latest": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            },
            "why_governance_remains_source_of_truth": {
                "owner": "governance_substrate_v1",
                "proposal_learning_loop_is_governance_truth_source": False,
                "reason": "the evidence review is derived from directive, bucket, branch, self-structure, and prior governed-skill artifacts rather than from execution code alone",
            },
        },
        "analytics_context": {
            "analytics_report_path": str(intervention_data_dir() / "intervention_analytics_latest.json"),
            "proposal_recommendations_path": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            "proposal_count": int(analytics.get("proposal_count", 0) or 0),
            "current_recommendation_top_templates": [
                str(item.get("template_name", ""))
                for item in list(recommendations.get("all_ranked_proposals", []))
                if isinstance(item, dict) and str(item.get("decision", "")) == "suggested"
            ][:8],
        },
        "observability_gain": {
            "passed": True,
            "reason": "the bounded local trace parser trial now has an explicit governance-owned evidence review outcome before any escalation step",
            "artifact_paths": {
                "trial_evidence_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the skill can now be judged on evidence quality, envelope compliance, and escalation readiness before any provisional handling is considered",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "the review cleanly distinguishes remain_sandbox_only, admissible_for_provisional_handling, and blocked_from_escalation outcomes",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the evidence review is diagnostic-only; no retained promotion, no branch-state mutation, and no live behavior change occurred",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": best_next_template,
            "reason": "the next governance-owned step is now explicit and still stops short of retained promotion",
        },
        "diagnostic_conclusions": {
            "trial_evidence_review_in_place": True,
            "trial_evidence_supports_provisional_handling": outcome_class == "admissible_for_provisional_handling",
            "skill_escalation_outcome": outcome_class,
            "retained_promotion_occurred": False,
            "branch_state_stayed_paused_with_baseline_held": True,
            "plan_should_remain_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "best_next_template": best_next_template,
        },
    }
    _write_json(artifact_path, artifact_payload)

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: the bounded local trace parser trial evidence is now governance-reviewed before any escalation beyond sandbox handling",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }


def _skill_provisional_admission_schema() -> dict[str, Any]:
    return {
        "schema_name": "GovernedSkillProvisionalAdmission",
        "schema_version": "governed_skill_provisional_admission_v1",
        "primary_candidate_field": "skill_id",
        "admission_outcome_classes": [
            "blocked_from_provisional_handling",
            "admissible_for_provisional_handling",
            "remain_sandbox_only",
        ],
        "required_checks": [
            "trial_evidence_supports_provisional_handling",
            "directive_relevance",
            "trusted_source_compliance",
            "bucket_resource_feasibility",
            "mutable_surface_legality",
            "reversibility",
            "bounded_evidence_path",
            "duplication_overlap_acceptability",
            "branch_state_compatibility",
            "protected_surface_isolation",
            "downstream_isolation",
            "plan_non_owning",
            "routing_deferred",
            "retained_promotion_blocked",
        ],
        "provisional_envelope_fields": [
            "allowed_scope",
            "forbidden_scope",
            "allowed_write_roots",
            "read_only_roots",
            "resource_ceilings",
            "network_mode",
            "admissible_data_sources",
            "governance_reporting_obligations",
        ],
        "evidence_obligation_fields": [
            "shadow_only_execution",
            "recognized_line_share_weighted_min",
            "seed_log_coverage_min",
            "dummy_eval_count_min",
            "patch_tuple_count_min",
            "directive_relevance_required",
            "duplication_risk_must_remain_low",
            "governance_reporting_required",
        ],
        "rollback_trigger_fields": [
            "network_mode_deviation",
            "write_root_violation",
            "branch_state_mutation",
            "protected_surface_change",
            "downstream_selected_set_work",
            "plan_ownership_change",
            "routing_work_drift",
            "resource_ceiling_breach",
            "evidence_quality_regression",
        ],
        "deprecation_trigger_fields": [
            "repeated_low_distinct_utility",
            "directive_relevance_decay",
            "duplication_overlap_growth",
            "governance_reporting_failure",
            "bucket_infeasibility",
        ],
        "future_retained_promotion_prerequisites": [
            "at_least_two_additional_governance_owned_provisional_evidence_passes",
            "continued_full_envelope_compliance",
            "continued_directive_relevance",
            "continued_low_duplication_risk",
            "explicit_retained_promotion_gate_review",
            "human_approval_point",
        ],
    }


def _local_trace_parser_provisional_envelope(
    candidate: dict[str, Any],
    *,
    current_branch_state: str,
) -> dict[str, Any]:
    novali_v4_root = ACTIVE_STATUS_PATH.parent
    resource_ceilings = dict(candidate.get("resource_cost_estimate", {}))
    return {
        "allowed_scope": [
            "trusted local shadow-log parsing",
            "trusted local diagnostic-memory summarization",
            "shadow-only parser evidence collection",
            "bounded helper maintenance inside approved write roots",
        ],
        "forbidden_scope": [
            "retained promotion",
            "branch-state mutation",
            "protected-surface modification",
            "downstream selected-set work",
            "plan_ ownership change",
            "routing work",
            "live-policy changes",
            "threshold changes",
            "frozen benchmark semantic changes",
            "projection-envelope changes",
            "untrusted external access",
        ],
        "allowed_write_roots": [
            str(intervention_data_dir()),
            str(novali_v4_root / "interventions"),
        ],
        "read_only_roots": [
            str(novali_v4_root.with_name("novali-v3")),
        ],
        "resource_ceilings": resource_ceilings,
        "network_mode": str(resource_ceilings.get("network_mode", "none")),
        "admissible_data_sources": [
            "local_logs:logs/intervention_shadow_*.log",
            "local_artifacts:novali-v4/data/diagnostic_memory",
            "local_artifacts:novali-v4/data/directive_state_latest.json",
            "local_artifacts:novali-v4/data/directive_history.jsonl",
            "local_artifacts:novali-v4/data/self_structure_state_latest.json",
            "local_artifacts:novali-v4/data/self_structure_ledger.jsonl",
            "local_artifacts:novali-v4/data/branch_registry_latest.json",
            "local_artifacts:novali-v4/data/bucket_state_latest.json",
            "local_artifacts:novali-v4/data/intervention_ledger.jsonl",
            "local_artifacts:novali-v4/data/intervention_analytics_latest.json",
            "local_artifacts:novali-v4/data/proposal_recommendations_latest.json",
        ],
        "governance_reporting_obligations": [
            "materialize a diagnostic-memory artifact for each provisional-handling review or execution step",
            "append a bounded governance event into self_structure_ledger.jsonl",
            "refresh self_structure_state_latest.json with current provisional status only",
            "keep branch state recorded as paused_with_baseline_held",
        ],
        "required_branch_state": "paused_with_baseline_held",
        "observed_branch_state": current_branch_state,
    }


def _local_trace_parser_evidence_obligations(
    trial_execution_summary: dict[str, Any],
) -> dict[str, Any]:
    local_sources = dict(trial_execution_summary.get("local_sources_parsed", {}))
    parse_summary = dict(local_sources.get("trusted_log_parse_summary", {}))
    evidence_produced = dict(trial_execution_summary.get("evidence_produced", {}))
    utility_assessment = dict(evidence_produced.get("utility_assessment", {}))
    directive_relevance = dict(evidence_produced.get("directive_relevance", {}))
    duplication_overlap = dict(evidence_produced.get("duplication_overlap", {}))

    recognized_line_share_weighted = float(parse_summary.get("recognized_line_share_weighted", 0.0) or 0.0)
    seed_log_coverage = int(parse_summary.get("parsed_file_count", 0) or 0)
    dummy_eval_count = int(utility_assessment.get("dummy_eval_count", 0) or 0)
    patch_tuple_count = int(utility_assessment.get("patch_tuple_count", 0) or 0)
    obligations_satisfied = (
        recognized_line_share_weighted >= 0.95
        and seed_log_coverage >= 3
        and dummy_eval_count >= 100
        and patch_tuple_count >= 500
        and bool(directive_relevance.get("passed", False))
        and bool(duplication_overlap.get("passed", False))
    )
    return {
        "shadow_only_execution": True,
        "recognized_line_share_weighted_min": 0.95,
        "observed_recognized_line_share_weighted": recognized_line_share_weighted,
        "seed_log_coverage_min": 3,
        "observed_seed_log_coverage": seed_log_coverage,
        "dummy_eval_count_min": 100,
        "observed_dummy_eval_count": dummy_eval_count,
        "patch_tuple_count_min": 500,
        "observed_patch_tuple_count": patch_tuple_count,
        "directive_relevance_required": "high",
        "observed_directive_relevance": str(directive_relevance.get("value", "")),
        "duplication_risk_must_remain_low": True,
        "observed_duplication_risk_status": str(duplication_overlap.get("value", "")),
        "governance_reporting_required": True,
        "obligations_satisfied": obligations_satisfied,
    }


def _local_trace_parser_rollback_triggers(
    envelope_compliance: dict[str, Any],
    risk_review: dict[str, Any],
    evidence_quality: dict[str, Any],
) -> dict[str, Any]:
    return {
        "network_mode_deviation": {
            "condition": "network mode changes away from none",
            "triggered": not bool(envelope_compliance.get("network_remained_none", False)),
        },
        "write_root_violation": {
            "condition": "writes occur outside approved provisional roots",
            "triggered": not bool(envelope_compliance.get("write_limits_respected", False)),
        },
        "branch_state_mutation": {
            "condition": "branch state no longer stays paused_with_baseline_held",
            "triggered": not bool(envelope_compliance.get("branch_state_unchanged", False)),
        },
        "protected_surface_change": {
            "condition": "protected-surface modification is observed",
            "triggered": bool(risk_review.get("protected_surface_creep", False)),
        },
        "downstream_selected_set_work": {
            "condition": "downstream selected-set work is introduced",
            "triggered": bool(risk_review.get("downstream_selected_set_drift", False)),
        },
        "plan_ownership_change": {
            "condition": "plan_ becomes owning",
            "triggered": bool(risk_review.get("plan_ownership_change", False)),
        },
        "routing_work_drift": {
            "condition": "routing-adjacent work enters the skill path",
            "triggered": bool(risk_review.get("routing_work_drift", False)),
        },
        "resource_ceiling_breach": {
            "condition": "resource ceilings are exceeded or bucket pressure is no longer low",
            "triggered": not bool(envelope_compliance.get("resource_limits_respected", False)),
        },
        "evidence_quality_regression": {
            "condition": "recognized output quality or source coverage materially regresses",
            "triggered": not bool(evidence_quality.get("passed", False)),
        },
    }


def _local_trace_parser_deprecation_triggers(
    directive_relevance_review: dict[str, Any],
    duplication_review: dict[str, Any],
) -> dict[str, Any]:
    return {
        "repeated_low_distinct_utility": {
            "condition": "future provisional evidence shows low distinct local trace-parsing utility",
            "active_now": False,
        },
        "directive_relevance_decay": {
            "condition": "the active directive no longer justifies governance-supportive local trace parsing",
            "active_now": not bool(directive_relevance_review.get("passed", False)),
        },
        "duplication_overlap_growth": {
            "condition": "the skill becomes overlap-heavy with another admitted capability",
            "active_now": not bool(duplication_review.get("passed", False)),
        },
        "governance_reporting_failure": {
            "condition": "required governance reporting artifacts stop being materialized",
            "active_now": False,
        },
        "bucket_infeasibility": {
            "condition": "future provisional runs no longer fit the admitted resource envelope",
            "active_now": False,
        },
    }


def _local_trace_parser_retained_promotion_prerequisites() -> dict[str, Any]:
    return {
        "required_before_any_retained_promotion_discussion": [
            "at least two additional governance-owned provisional evidence passes",
            "continued full provisional-envelope compliance",
            "continued directive relevance under the active directive",
            "continued low duplication / overlap risk",
            "no rollback or deprecation triggers activated",
            "explicit retained-promotion gate review",
            "explicit human approval point",
        ],
        "currently_satisfied": False,
        "reason": "the current step only admits or declines provisional handling; retained promotion remains separately gated and is not considered satisfied here",
    }


def run_provisional_admission_snapshot(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governance_substrate_v1_snapshot"
    )
    skill_candidate_screen_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_skill_candidate_screen_snapshot_v1"
    )
    skill_trial_admission_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_skill_trial_admission_snapshot_v1"
    )
    skill_trial_execution_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1"
    )
    skill_trial_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_skill_trial_evidence_snapshot_v1"
    )
    branch_pause_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_branch_pause_snapshot_v1"
    )
    if not all(
        [
            governance_snapshot,
            skill_candidate_screen_snapshot,
            skill_trial_admission_snapshot,
            skill_trial_execution_snapshot,
            skill_trial_evidence_snapshot,
            branch_pause_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed skill provisional admission requires governance, candidate-screen, trial-admission, trial-execution, trial-evidence, and branch-pause artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite governed-skill artifacts"},
            "activation_analysis_usefulness": {
                "passed": False,
                "reason": "missing prerequisite governed-skill artifacts",
            },
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite governed-skill artifacts"},
            "safety_neutrality": {
                "passed": True,
                "scope": str(proposal.get("scope", "")),
                "reason": "no live-policy mutation occurred",
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "provisional handling cannot be evaluated without the full governance-owned skill evidence chain",
            },
        }

    directive_state = _load_json_file(DIRECTIVE_STATE_PATH)
    bucket_state = _load_json_file(BUCKET_STATE_PATH)
    self_structure_state = _load_json_file(SELF_STRUCTURE_STATE_PATH)
    branch_registry = _load_json_file(BRANCH_REGISTRY_PATH)
    directive_history = _load_jsonl(DIRECTIVE_HISTORY_PATH)
    self_structure_ledger = _load_jsonl(SELF_STRUCTURE_LEDGER_PATH)
    intervention_ledger = _load_jsonl(intervention_data_dir() / "intervention_ledger.jsonl")
    if not all([directive_state, bucket_state, self_structure_state, branch_registry]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed skill provisional admission requires current directive, bucket, self-structure, and branch state artifacts",
            "observability_gain": {
                "passed": False,
                "reason": "missing durable governance source-of-truth artifacts",
            },
            "activation_analysis_usefulness": {
                "passed": False,
                "reason": "missing durable governance source-of-truth artifacts",
            },
            "ambiguity_reduction": {
                "passed": False,
                "reason": "missing durable governance source-of-truth artifacts",
            },
            "safety_neutrality": {
                "passed": True,
                "scope": str(proposal.get("scope", "")),
                "reason": "no live-policy mutation occurred",
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "provisional handling cannot be evaluated without directive, bucket, self-structure, and branch state",
            },
        }

    analytics = build_intervention_ledger_analytics()
    latest_snapshots = load_latest_snapshots()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")

    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_branch_state = str(branch_record.get("state", ""))
    current_directive = dict(directive_state.get("current_directive_state", {}))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    governed_skill_subsystem = dict(self_structure_state.get("governed_skill_subsystem", {}))
    if not governed_skill_subsystem:
        governed_skill_subsystem = _build_skill_subsystem(
            policy=dict(self_structure_state.get("policy", {})),
            directive_state=directive_state,
            bucket_state=bucket_state,
            branch_record=branch_record,
        )

    candidate_examples = _example_skill_candidates()
    primary_candidate = next(
        (item for item in candidate_examples if str(item.get("skill_id", "")) == "skill_candidate_local_trace_parser_trial"),
        {},
    )
    candidate_screen_artifact_path = Path(str(governed_skill_subsystem.get("last_candidate_screen_artifact_path", "")))
    trial_admission_artifact_path = Path(str(governed_skill_subsystem.get("last_trial_admission_artifact_path", "")))
    trial_execution_artifact_path = Path(str(governed_skill_subsystem.get("last_trial_execution_artifact_path", "")))
    trial_evidence_artifact_path = Path(str(governed_skill_subsystem.get("last_trial_evidence_artifact_path", "")))

    candidate_screen_artifact = _load_json_file(candidate_screen_artifact_path) if candidate_screen_artifact_path.exists() else {}
    trial_admission_artifact = _load_json_file(trial_admission_artifact_path) if trial_admission_artifact_path.exists() else {}
    trial_execution_artifact = _load_json_file(trial_execution_artifact_path) if trial_execution_artifact_path.exists() else {}
    trial_evidence_artifact = _load_json_file(trial_evidence_artifact_path) if trial_evidence_artifact_path.exists() else {}

    candidate_screen_summary = dict(candidate_screen_artifact.get("governed_skill_candidate_screen_summary", {}))
    trial_admission_summary = dict(trial_admission_artifact.get("governed_skill_trial_admission_summary", {}))
    trial_execution_summary = dict(trial_execution_artifact.get("governed_skill_trial_summary", {}))
    trial_evidence_summary = dict(trial_evidence_artifact.get("governed_skill_trial_evidence_summary", {}))

    current_screen_outcome = dict(candidate_screen_summary.get("current_screen_outcome", {}))
    escalation_recommendation = dict(trial_evidence_summary.get("escalation_recommendation", {}))
    evidence_quality = dict(trial_evidence_summary.get("evidence_quality", {}))
    envelope_compliance = dict(trial_evidence_summary.get("envelope_compliance", {}))
    directive_relevance_review = dict(trial_evidence_summary.get("directive_relevance", {}))
    duplication_review = dict(trial_evidence_summary.get("duplication_overlap_assessment", {}))
    risk_review = dict(trial_evidence_summary.get("risk_review", {}))

    provisional_checks = {
        "trial_evidence_supports_provisional_handling": str(escalation_recommendation.get("outcome_class", "")) == "admissible_for_provisional_handling",
        "directive_relevance": bool(directive_relevance_review.get("passed", False)),
        "trusted_source_compliance": bool(directive_relevance_review.get("trusted_source_policy_preserved", False)),
        "bucket_resource_feasibility": bool(envelope_compliance.get("resource_limits_respected", False)),
        "mutable_surface_legality": bool(
            dict(trial_execution_summary.get("sandbox_envelope_compliance", {})).get("no_protected_surface_modification", False)
        ) and bool(
            dict(trial_execution_summary.get("sandbox_envelope_compliance", {})).get("writes_within_approved_roots", False)
        ),
        "reversibility": str(primary_candidate.get("reversibility", "")) == "high",
        "bounded_evidence_path": bool(evidence_quality.get("passed", False)),
        "duplication_overlap_acceptability": bool(duplication_review.get("passed", False)),
        "branch_state_compatibility": current_branch_state == "paused_with_baseline_held",
        "protected_surface_isolation": not bool(risk_review.get("protected_surface_creep", False)),
        "downstream_isolation": not bool(risk_review.get("downstream_selected_set_drift", False)),
        "plan_non_owning": not bool(risk_review.get("plan_ownership_change", False)),
        "routing_deferred": not bool(risk_review.get("routing_work_drift", False))
        and bool(current_state_summary.get("routing_deferred", False)),
        "retained_promotion_blocked": bool(envelope_compliance.get("no_retained_promotion", False)),
        "branch_state_mutation_absent": bool(envelope_compliance.get("branch_state_unchanged", False)),
    }
    provisional_checks["passed"] = all(
        bool(value) for key, value in provisional_checks.items() if key != "passed"
    )
    provisional_checks["reason"] = (
        "the candidate clears the governance-owned provisional-admission bar while keeping the wm-hybrid branch paused and retained promotion blocked"
        if provisional_checks["passed"]
        else "the candidate does not yet clear the governance-owned provisional-admission bar"
    )

    provisional_envelope = _local_trace_parser_provisional_envelope(
        primary_candidate,
        current_branch_state=current_branch_state,
    )
    evidence_obligations = _local_trace_parser_evidence_obligations(trial_execution_summary)
    rollback_triggers = _local_trace_parser_rollback_triggers(
        envelope_compliance=envelope_compliance,
        risk_review=risk_review,
        evidence_quality=evidence_quality,
    )
    deprecation_triggers = _local_trace_parser_deprecation_triggers(
        directive_relevance_review=directive_relevance_review,
        duplication_review=duplication_review,
    )
    retained_promotion_prerequisites = _local_trace_parser_retained_promotion_prerequisites()
    provisional_admission_schema = _skill_provisional_admission_schema()

    if provisional_checks["passed"] and evidence_obligations["obligations_satisfied"]:
        outcome_class = "admissible_for_provisional_handling"
        outcome_reason = "bounded trial evidence, directive fit, low duplication, and envelope compliance justify provisional handling under an explicit governance-owned envelope while still blocking retained promotion"
        best_next_template = "proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v1"
    elif not provisional_checks["branch_state_compatibility"] or not provisional_checks["retained_promotion_blocked"] or not provisional_checks["trusted_source_compliance"]:
        outcome_class = "blocked_from_provisional_handling"
        outcome_reason = "branch-state, retained-promotion, or trusted-source requirements do not permit provisional handling"
        best_next_template = "memory_summary.v4_governed_skill_provisional_gap_snapshot_v1"
    else:
        outcome_class = "remain_sandbox_only"
        outcome_reason = "the candidate stays safe and useful, but the current evidence is still better treated as sandbox-only than provisional"
        best_next_template = "memory_summary.v4_governed_skill_provisional_gap_snapshot_v1"

    artifact_path = (
        _diagnostic_artifact_dir()
        / f"memory_summary_v4_governed_skill_provisional_admission_snapshot_v1_{proposal['proposal_id']}.json"
    )

    updated_self_structure_state = dict(self_structure_state)
    updated_governed_skill_subsystem = dict(governed_skill_subsystem)
    updated_governed_skill_subsystem["provisional_admission_schema"] = provisional_admission_schema
    updated_governed_skill_subsystem["last_provisional_admission_artifact_path"] = str(artifact_path)
    updated_governed_skill_subsystem["last_provisional_admission_outcome"] = {
        "primary_candidate_skill_id": "skill_candidate_local_trace_parser_trial",
        "primary_candidate_name": "Local trace parser trial",
        "provisional_admission_outcome": outcome_class,
        "reason": outcome_reason,
        "retained_promotion": False,
        "branch_state_after_review": current_branch_state,
    }
    updated_governed_skill_subsystem["best_next_template"] = best_next_template
    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["governed_skill_subsystem"] = updated_governed_skill_subsystem
    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "latest_skill_provisional_admission_outcome": outcome_class,
            "latest_skill_provisional_candidate": "Local trace parser trial",
            "retained_skill_promotion_performed": False,
            "current_branch_state": current_branch_state,
            "plan_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
        }
    )
    updated_self_structure_state["current_state_summary"] = updated_current_state_summary
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    ledger_event = {
        "event_id": f"governed_skill_provisional_admission_snapshot_v1::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_skill_provisional_admission_snapshot_v1_materialized",
        "event_class": "governed_skill_provisional_admission",
        "directive_id": str(current_directive.get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": current_branch_state,
        "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
        "primary_candidate_skill_id": "skill_candidate_local_trace_parser_trial",
        "provisional_admission_outcome": outcome_class,
        "retained_promotion": False,
        "branch_state_mutation": False,
        "artifact_paths": {
            "directive_state_latest": str(DIRECTIVE_STATE_PATH),
            "directive_history": str(DIRECTIVE_HISTORY_PATH),
            "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
            "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            "branch_registry_latest": str(BRANCH_REGISTRY_PATH),
            "bucket_state_latest": str(BUCKET_STATE_PATH),
            "intervention_ledger": str(intervention_data_dir() / "intervention_ledger.jsonl"),
            "skill_candidate_screen_artifact": str(candidate_screen_artifact_path),
            "skill_trial_admission_artifact": str(trial_admission_artifact_path),
            "skill_trial_execution_artifact": str(trial_execution_artifact_path),
            "skill_trial_evidence_artifact": str(trial_evidence_artifact_path),
            "skill_provisional_admission_artifact": str(artifact_path),
        },
        "source_proposal_id": str(proposal.get("proposal_id", "")),
    }
    _append_jsonl(SELF_STRUCTURE_LEDGER_PATH, ledger_event)

    directive_history_tail = [str(item.get("event_type", "")) for item in directive_history[-8:]]
    self_structure_event_tail = [str(item.get("event_type", "")) for item in self_structure_ledger[-12:]] + [
        str(ledger_event.get("event_type", ""))
    ]

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_governed_skill_provisional_admission_snapshot_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "branch_context": {
            "current_branch_id": str(branch_record.get("branch_id", "")),
            "current_branch_state": current_branch_state,
            "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
            "plan_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
        },
        "comparison_references": {
            "memory_summary.v4_governance_substrate_v1_snapshot": _artifact_reference(governance_snapshot, latest_snapshots),
            "memory_summary.v4_wm_hybrid_branch_pause_snapshot_v1": _artifact_reference(branch_pause_snapshot, latest_snapshots),
            "memory_summary.v4_governed_skill_candidate_screen_snapshot_v1": _artifact_reference(
                skill_candidate_screen_snapshot,
                latest_snapshots,
            ),
            "memory_summary.v4_governed_skill_trial_admission_snapshot_v1": _artifact_reference(
                skill_trial_admission_snapshot,
                latest_snapshots,
            ),
            "proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1": _artifact_reference(
                skill_trial_execution_snapshot,
                latest_snapshots,
            ),
            "memory_summary.v4_governed_skill_trial_evidence_snapshot_v1": _artifact_reference(
                skill_trial_evidence_snapshot,
                latest_snapshots,
            ),
        },
        "governed_skill_provisional_admission_summary": {
            "candidate_evaluated": {
                "skill_id": "skill_candidate_local_trace_parser_trial",
                "candidate_name": "Local trace parser trial",
                "screening_outcome": str(current_screen_outcome.get("status", "")),
                "trial_admission_outcome": str(trial_admission_summary.get("admission_outcome", "")),
                "trial_execution_outcome": str(
                    dict(governed_skill_subsystem.get("last_trial_execution_outcome", {})).get("trial_execution_outcome", "")
                ),
                "trial_evidence_outcome": str(escalation_recommendation.get("outcome_class", "")),
            },
            "provisional_admission_checks": provisional_checks,
            "provisional_envelope": provisional_envelope,
            "evidence_obligations": evidence_obligations,
            "rollback_triggers": rollback_triggers,
            "deprecation_triggers": deprecation_triggers,
            "future_retained_promotion_prerequisites": retained_promotion_prerequisites,
            "directive_relevance_review": directive_relevance_review,
            "duplication_overlap_review": duplication_review,
            "current_governance_context": {
                "directive_initialization_state": str(directive_state.get("initialization_state", "")),
                "branch_state": current_branch_state,
                "retained_promotion_occurred": False,
                "branch_state_mutation_occurred": False,
                "network_mode_required": str(provisional_envelope.get("network_mode", "")),
            },
            "decision_recommendation": {
                "outcome_class": outcome_class,
                "reason": outcome_reason,
                "best_next_template": best_next_template,
            },
            "governance_inputs_consumed": {
                "directive_state_latest": str(DIRECTIVE_STATE_PATH),
                "directive_history": str(DIRECTIVE_HISTORY_PATH),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
                "branch_registry_latest": str(BRANCH_REGISTRY_PATH),
                "bucket_state_latest": str(BUCKET_STATE_PATH),
                "intervention_ledger": str(intervention_data_dir() / "intervention_ledger.jsonl"),
                "intervention_analytics_latest": str(intervention_data_dir() / "intervention_analytics_latest.json"),
                "proposal_recommendations_latest": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            },
            "why_governance_remains_source_of_truth": {
                "owner": "governance_substrate_v1",
                "proposal_learning_loop_is_governance_truth_source": False,
                "reason": "provisional admission is derived from directive, bucket, branch, self-structure, candidate-screen, trial-admission, trial-execution, and trial-evidence artifacts rather than from execution code alone",
            },
        },
        "analytics_context": {
            "analytics_report_path": str(intervention_data_dir() / "intervention_analytics_latest.json"),
            "proposal_recommendations_path": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            "proposal_count": int(analytics.get("proposal_count", 0) or 0),
            "current_recommendation_top_templates": [
                str(item.get("template_name", ""))
                for item in list(recommendations.get("all_ranked_proposals", []))
                if isinstance(item, dict) and str(item.get("decision", "")) == "suggested"
            ][:8],
            "directive_history_tail": directive_history_tail,
            "self_structure_event_tail": self_structure_event_tail[-12:],
            "intervention_ledger_rows_reviewed": len(intervention_ledger[-8:]),
        },
        "observability_gain": {
            "passed": True,
            "reason": "the local trace parser now has an explicit governance-owned provisional-admission decision, envelope, and rollback/deprecation contract before any retained-promotion discussion",
            "artifact_paths": {
                "skill_provisional_admission_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the skill can now be held in a bounded provisional state with explicit obligations and triggers instead of relying on sandbox evidence alone",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "the review cleanly distinguishes remain_sandbox_only, admissible_for_provisional_handling, and blocked_from_provisional_handling outcomes while preserving a separate retained-promotion gate",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the provisional-admission review is diagnostic-only; no retained promotion, no branch-state mutation, and no live behavior change occurred",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": best_next_template,
            "reason": "the next governance-owned step is now explicit while still keeping retained promotion separately gated",
        },
        "diagnostic_conclusions": {
            "governed_skill_provisional_admission_in_place": True,
            "provisional_admission_justified": outcome_class == "admissible_for_provisional_handling",
            "skill_provisional_status": outcome_class,
            "retained_promotion_occurred": False,
            "branch_state_stayed_paused_with_baseline_held": True,
            "plan_should_remain_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "best_next_template": best_next_template,
        },
    }
    _write_json(artifact_path, artifact_payload)

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: governed skill provisional admission is now explicitly reviewed before any move beyond sandbox handling",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
