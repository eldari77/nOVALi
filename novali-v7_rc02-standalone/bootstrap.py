from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from operator_shell.common import OperatorConstraintViolationError
from operator_shell.runtime_guard import install_runtime_guard_from_environment

_OPERATOR_GUARD_INSTALL_ERROR: OperatorConstraintViolationError | None = None
try:
    install_runtime_guard_from_environment()
except OperatorConstraintViolationError as exc:
    _OPERATOR_GUARD_INSTALL_ERROR = exc

DIRECTIVE_FILE_SCHEMA_NAME = "NOVALIDirectiveBootstrapFile"
DIRECTIVE_FILE_SCHEMA_VERSION = "novali_directive_bootstrap_file_v1"
DIRECTIVE_SPEC_SCHEMA_NAME = "DirectiveSpec"
DIRECTIVE_SPEC_SCHEMA_VERSION = "directive_spec_v1"
INITIALIZATION_FLOW_SCHEMA_NAME = "DirectiveSpecInitializationFlow"
INITIALIZATION_FLOW_SCHEMA_VERSION = "directive_spec_initialization_flow_v1"
READ_CONTRACT_SCHEMA_VERSION = "governance_memory_read_contract_v1"
BINDING_PROMOTED_AUTHORITY = "binding_promoted_authority"

REQUIRED_DIRECTIVE_FIELDS = [
    "directive_id",
    "directive_text",
    "clarified_intent_summary",
    "success_criteria",
    "milestone_model",
    "human_approval_points",
    "constraints",
    "trusted_sources",
    "bucket_spec",
    "allowed_action_classes",
    "stop_conditions",
    "drift_budget_for_context_exploration",
]

REQUIRED_BOOTSTRAP_CONTEXT_FIELDS = [
    "active_branch",
    "completed_reference_branch",
    "reference_operator_surface_branch",
    "frozen_fallback_reference_version",
    "branch_name",
    "branch_state",
    "current_operating_stance",
    "held_baseline_template",
    "routing_status",
    "branch_transition_reason",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("", encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _build_policy_representation() -> dict[str, Any]:
    return {
        "policy_version": "governance_substrate_v1",
        "immutable_core": {
            "boundary_model": "layered_immutable_core",
            "surfaces": [
                "live_policy",
                "thresholds",
                "routing_policy",
                "frozen_benchmark_semantics",
                "projection_safe_envelope",
                "immutable_9d_core",
                "proposal_admissibility_governance",
                "trusted_source_policy",
            ],
            "admissibility_owner": "immutable_9d_core",
        },
        "mutable_shell": {
            "surfaces": [
                "diagnostic_memory",
                "governance_state_artifacts",
                "documentation",
                "observability_tracing",
                "local_low_risk_shell_work",
            ]
        },
        "conditionally_mutable": {
            "surfaces": [
                "branch_registry",
                "directive_state",
                "bucket_state",
                "self_structure_snapshot",
                "skills_subsystem",
                "proposal_learning_loop_upstream_context",
            ]
        },
        "gated_actions": [
            "retained_structural_promotion",
            "branch_state_change",
            "protected_surface_challenge",
            "resource_expansion_request",
            "skill_trial",
            "skill_retention_promotion",
        ],
        "forbidden_actions": [
            "live_policy_change",
            "threshold_change",
            "routing_policy_change",
            "frozen_benchmark_semantics_change",
            "projection_safe_envelope_change",
            "untrusted_external_access",
        ],
    }

KNOWN_ACTION_CLASSES = {
    "low_risk_shell_change",
    "diagnostic_schema_materialization",
    "append_only_ledger_write",
    "local_governance_registry_update",
    "retained_structural_promotion",
    "branch_state_change",
    "protected_surface_challenge",
    "resource_expansion_request",
    "skill_trial",
    "skill_retention_promotion",
}

AMBIGUOUS_STRING_SENTINELS = {
    "?",
    "ambiguous",
    "clarify",
    "placeholder",
    "tbd",
    "todo",
    "unknown",
}

CLARIFICATION_PROMPTS = {
    "clarified_intent_summary": "What exact clarified intent summary should govern activation beyond the raw directive text?",
    "success_criteria": "What concrete success criteria should decide whether this directive has been initialized correctly?",
    "milestone_model": "What milestone model should structure initialization and early governed operation?",
    "human_approval_points": "Which human approval points must remain explicitly gated under this directive?",
    "stop_conditions": "Which stop conditions must terminate initialization or later execution?",
    "drift_budget_for_context_exploration": "What tagged, budgeted drift allowance is permitted for contextual exploration?",
}


class DirectiveBootstrapError(RuntimeError):
    pass


class DirectiveFileValidationError(DirectiveBootstrapError):
    def __init__(self, message: str, *, errors: list[str] | None = None) -> None:
        self.errors = list(errors or [])
        super().__init__(message)


class ClarificationRequiredError(DirectiveBootstrapError):
    def __init__(
        self,
        message: str,
        *,
        questions: list[dict[str, Any]],
        partially_resolved_spec: dict[str, Any],
    ) -> None:
        self.questions = copy.deepcopy(list(questions))
        self.partially_resolved_spec = copy.deepcopy(dict(partially_resolved_spec))
        super().__init__(message)


class CanonicalStateConsistencyError(DirectiveBootstrapError):
    def __init__(self, message: str, *, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__(message)


@dataclass(frozen=True)
class BootstrapPaths:
    package_root: Path
    data_dir: Path
    directive_state_path: Path
    directive_history_path: Path
    bucket_state_path: Path
    branch_registry_path: Path
    governance_memory_authority_path: Path
    self_structure_state_path: Path
    self_structure_ledger_path: Path
    branch_transition_status_path: Path
    version_handoff_status_path: Path


def _default_package_root() -> Path:
    return Path(__file__).resolve().parent


def _build_paths(*, state_root: str | Path | None = None) -> BootstrapPaths:
    package_root = _default_package_root()
    data_dir = Path(state_root) if state_root is not None else package_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return BootstrapPaths(
        package_root=package_root,
        data_dir=data_dir,
        directive_state_path=data_dir / "directive_state_latest.json",
        directive_history_path=data_dir / "directive_history.jsonl",
        bucket_state_path=data_dir / "bucket_state_latest.json",
        branch_registry_path=data_dir / "branch_registry_latest.json",
        governance_memory_authority_path=data_dir / "governance_memory_authority_latest.json",
        self_structure_state_path=data_dir / "self_structure_state_latest.json",
        self_structure_ledger_path=data_dir / "self_structure_ledger.jsonl",
        branch_transition_status_path=data_dir / "branch_transition_status.json",
        version_handoff_status_path=data_dir / "version_handoff_status.json",
    )


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        raise DirectiveBootstrapError(f"invalid JSON in {path}: {exc}") from exc


def _deep_merge(existing: Any, update: Any) -> Any:
    if not isinstance(existing, dict) or not isinstance(update, dict):
        return copy.deepcopy(update)
    merged = copy.deepcopy(existing)
    for key, value in update.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    return False


def _is_ambiguous(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in AMBIGUOUS_STRING_SENTINELS
    return False


def _normalized_path_string(value: Any) -> str:
    if _is_missing(value):
        return ""
    try:
        return str(Path(str(value)).resolve()).casefold()
    except OSError:
        return str(value).replace("/", "\\").casefold()


def _load_directive_file(path: Path) -> dict[str, Any]:
    if path.suffix.lower() != ".json":
        raise DirectiveFileValidationError(
            "formal directive files must be JSON and use the NOVALIDirectiveBootstrapFile schema"
        )
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise DirectiveFileValidationError("directive file must decode to a JSON object")
    errors: list[str] = []
    if str(payload.get("schema_name", "")) != DIRECTIVE_FILE_SCHEMA_NAME:
        errors.append(f"schema_name must be {DIRECTIVE_FILE_SCHEMA_NAME}")
    if str(payload.get("schema_version", "")) != DIRECTIVE_FILE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {DIRECTIVE_FILE_SCHEMA_VERSION}")
    if not isinstance(payload.get("directive_spec"), dict):
        errors.append("directive_spec object is required")
    if not isinstance(payload.get("bootstrap_context"), dict):
        errors.append("bootstrap_context object is required")
    if errors:
        raise DirectiveFileValidationError("invalid formal directive file", errors=errors)
    return payload


def _load_clarification_file(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise DirectiveFileValidationError("clarification file must decode to a JSON object")
    if isinstance(payload.get("clarification_responses"), dict):
        return dict(payload.get("clarification_responses", {}))
    return payload


def _validate_bootstrap_context(bootstrap_context: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_BOOTSTRAP_CONTEXT_FIELDS if _is_missing(bootstrap_context.get(field))]
    if missing:
        raise DirectiveFileValidationError(
            "bootstrap_context is missing required fields",
            errors=[f"missing bootstrap_context fields: {', '.join(missing)}"],
        )


def _build_clarification_questions(directive_spec: dict[str, Any]) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    for field_name in REQUIRED_DIRECTIVE_FIELDS:
        value = directive_spec.get(field_name)
        if _is_missing(value):
            questions.append(
                {
                    "question_id": f"clarify_{field_name}",
                    "field": field_name,
                    "issue_type": "missing_required_field",
                    "question": CLARIFICATION_PROMPTS.get(
                        field_name,
                        f"What clarification is required to supply `{field_name}`?",
                    ),
                    "reason": "required DirectiveSpec field is missing",
                }
            )
            continue
        if _is_ambiguous(value):
            questions.append(
                {
                    "question_id": f"clarify_{field_name}",
                    "field": field_name,
                    "issue_type": "ambiguous_field",
                    "question": CLARIFICATION_PROMPTS.get(
                        field_name,
                        f"What clarification is required to disambiguate `{field_name}`?",
                    ),
                    "reason": "DirectiveSpec field is present but ambiguous",
                }
            )
    return questions


def _run_clarification_loop(
    directive_spec: dict[str, Any],
    *,
    clarification_responses: Mapping[str, Any] | None = None,
    answers_provider: Callable[[dict[str, Any]], Any | None] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    working = copy.deepcopy(dict(directive_spec))
    questions = _build_clarification_questions(working)
    history: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    response_map = dict(clarification_responses or {})

    for question in questions:
        field_name = str(question.get("field", ""))
        response = response_map.get(field_name)
        if _is_missing(response) and answers_provider is not None:
            response = answers_provider(question)
        if _is_missing(response) or _is_ambiguous(response):
            unresolved.append(question)
            continue
        working[field_name] = copy.deepcopy(response)
        history.append(
            {
                "question_id": str(question.get("question_id", "")),
                "field": field_name,
                "resolution_source": (
                    "external_clarification_file"
                    if field_name in response_map
                    else "interactive_clarification_provider"
                ),
                "resolution_summary": copy.deepcopy(response),
            }
        )
    return working, questions, history, unresolved


def _normalize_directive_spec(
    directive_spec: dict[str, Any],
    *,
    bootstrap_context: dict[str, Any],
    clarification_questions: list[dict[str, Any]],
    clarification_history: list[dict[str, Any]],
) -> dict[str, Any]:
    current_bucket_id = str(dict(directive_spec.get("bucket_spec", {})).get("bucket_id", ""))
    current_bucket_model = str(dict(directive_spec.get("bucket_spec", {})).get("bucket_model", ""))
    held_baseline = dict(bootstrap_context.get("held_baseline", {}))
    if _is_missing(held_baseline.get("template")):
        held_baseline["template"] = str(bootstrap_context.get("held_baseline_template", ""))
    normalized = copy.deepcopy(dict(directive_spec))
    normalized["directive_id"] = str(normalized.get("directive_id", ""))
    normalized["directive_text"] = str(normalized.get("directive_text", ""))
    normalized["clarified_intent_summary"] = str(normalized.get("clarified_intent_summary", ""))
    normalized["trusted_sources"] = [str(item) for item in list(normalized.get("trusted_sources", []))]
    normalized["allowed_action_classes"] = [
        str(item) for item in list(normalized.get("allowed_action_classes", []))
    ]
    normalized["branch_context"] = {
        "branch_id": str(
            bootstrap_context.get(
                "branch_id",
                f"{bootstrap_context.get('active_branch', '')}:{bootstrap_context.get('branch_name', '')}",
            )
        ),
        "branch_name": str(bootstrap_context.get("branch_name", "")),
        "branch_state": str(bootstrap_context.get("branch_state", "")),
        "held_baseline": held_baseline,
        "policy_version": "governance_substrate_v1",
    }
    normalized["bucket_runtime_context"] = {
        "bucket_id": current_bucket_id,
        "bucket_model": current_bucket_model,
        "resource_accounting_mode": "tracked_budget_v1",
        "network_mode": "deny_external_except_trusted_sources",
    }
    normalized["clarification_questions"] = copy.deepcopy(clarification_questions)
    normalized["clarification_history"] = copy.deepcopy(clarification_history)
    return normalized


def _validate_directive_spec(
    directive_spec: dict[str, Any],
    *,
    bootstrap_context: dict[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    missing = [field for field in REQUIRED_DIRECTIVE_FIELDS if _is_missing(directive_spec.get(field))]
    if missing:
        errors.append(f"missing required DirectiveSpec fields: {', '.join(missing)}")

    ambiguous = [
        field for field in REQUIRED_DIRECTIVE_FIELDS if _is_ambiguous(directive_spec.get(field))
    ]
    if ambiguous:
        errors.append(f"ambiguous DirectiveSpec fields remain unresolved: {', '.join(ambiguous)}")

    bucket_spec = dict(directive_spec.get("bucket_spec", {}))
    bucket_id_passed = not _is_missing(bucket_spec.get("bucket_id"))
    bucket_model_passed = not _is_missing(bucket_spec.get("bucket_model"))
    if not bucket_id_passed or not bucket_model_passed:
        errors.append("bucket_spec must include bucket_id and bucket_model")

    trusted_sources = [str(item) for item in list(directive_spec.get("trusted_sources", []))]
    trusted_sources_passed = len(trusted_sources) > 0
    if not trusted_sources_passed:
        errors.append("trusted_sources must not be empty")

    allowed_action_classes = [str(item) for item in list(directive_spec.get("allowed_action_classes", []))]
    unknown_action_classes = sorted(set(allowed_action_classes) - KNOWN_ACTION_CLASSES)
    allowed_actions_passed = len(allowed_action_classes) > 0 and not unknown_action_classes
    if not allowed_actions_passed:
        errors.append("allowed_action_classes must be non-empty and use recognized governance action classes")

    stop_conditions = list(directive_spec.get("stop_conditions", []))
    if len(stop_conditions) == 0:
        errors.append("stop_conditions must not be empty")

    drift_budget = dict(directive_spec.get("drift_budget_for_context_exploration", {}))
    required_drift_keys = {
        "allowed",
        "tag_required",
        "max_budgeted_support_reads",
        "max_budgeted_external_fetches",
    }
    if not required_drift_keys.issubset(set(drift_budget.keys())):
        errors.append("drift_budget_for_context_exploration is incomplete")

    if str(bootstrap_context.get("routing_status", "")) != "routing_deferred":
        errors.append("bootstrap_context.routing_status must remain routing_deferred")
    if str(bootstrap_context.get("branch_state", "")) != "paused_with_baseline_held":
        errors.append("bootstrap_context.branch_state must remain paused_with_baseline_held")
    if str(bootstrap_context.get("current_operating_stance", "")) != "hold_and_consolidate":
        errors.append("bootstrap_context.current_operating_stance must remain hold_and_consolidate")

    validation_report = {
        "required_field_completeness": {
            "passed": len(missing) == 0,
            "missing_fields": missing,
        },
        "ambiguity_resolution": {
            "passed": len(ambiguous) == 0,
            "ambiguous_fields": ambiguous,
        },
        "bucket_spec": {
            "passed": bucket_id_passed and bucket_model_passed,
            "bucket_spec": bucket_spec,
        },
        "trusted_sources": {
            "passed": trusted_sources_passed,
            "trusted_sources": trusted_sources,
        },
        "allowed_action_classes": {
            "passed": allowed_actions_passed,
            "unknown_action_classes": unknown_action_classes,
        },
        "posture_invariants": {
            "passed": (
                str(bootstrap_context.get("routing_status", "")) == "routing_deferred"
                and str(bootstrap_context.get("branch_state", "")) == "paused_with_baseline_held"
                and str(bootstrap_context.get("current_operating_stance", "")) == "hold_and_consolidate"
            ),
            "branch_state": str(bootstrap_context.get("branch_state", "")),
            "current_operating_stance": str(bootstrap_context.get("current_operating_stance", "")),
            "routing_status": str(bootstrap_context.get("routing_status", "")),
        },
    }
    return errors, validation_report


def _normalize_additional_reference_versions(bootstrap_context: dict[str, Any]) -> list[str]:
    versions = [str(item) for item in list(bootstrap_context.get("additional_reference_versions", []))]
    older_reference = str(bootstrap_context.get("older_reference_version", "")).strip()
    if older_reference:
        versions.append(older_reference)
    unique: list[str] = []
    seen = set()
    for item in versions:
        if not item or item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def _build_bucket_state(
    *,
    now: str,
    directive_spec: dict[str, Any],
    bootstrap_context: dict[str, Any],
) -> dict[str, Any]:
    active_branch = str(bootstrap_context.get("active_branch", "novali-v5"))
    reference_branch = str(bootstrap_context.get("completed_reference_branch", "novali-v4"))
    fallback_branch = str(bootstrap_context.get("frozen_fallback_reference_version", "novali-v3"))
    additional_refs = _normalize_additional_reference_versions(bootstrap_context)
    read_only_roots = [reference_branch, fallback_branch] + additional_refs
    read_only_roots = [item for item in dict.fromkeys(read_only_roots) if item and item != active_branch]
    return {
        "schema_version": "bucket_state_v1",
        "generated_at": now,
        "bucket_schema": {
            "schema_name": "ContainerizedBucketSpec",
            "schema_version": "bucket_spec_v1",
            "required_fields": [
                "bucket_id",
                "cpu_limit",
                "memory_limit",
                "storage_limit",
                "network_policy",
                "trusted_sources",
                "mount_policy",
                "subprocess_policy",
                "resource_accounting_mode",
            ],
        },
        "current_bucket_state": {
            "bucket_id": str(dict(directive_spec.get("bucket_spec", {})).get("bucket_id", "")),
            "bucket_model": str(dict(directive_spec.get("bucket_spec", {})).get("bucket_model", "")),
            "cpu_limit": {
                "max_parallel_processes": 4,
                "cpu_seconds_per_action": 180,
            },
            "memory_limit": {
                "max_working_set_mb": 2048,
            },
            "storage_limit": {
                "max_write_mb_per_action": 128,
                "max_retained_governance_artifacts_mb": 64,
            },
            "network_policy": {
                "mode": "deny_external_except_trusted_sources",
                "allowed_network_modes": ["none", "trusted_local_only"],
                "external_access_introduced": False,
            },
            "trusted_sources": [str(item) for item in list(directive_spec.get("trusted_sources", []))],
            "mount_policy": {
                "read_roots": [active_branch, reference_branch, "logs"],
                "write_roots": [f"{active_branch}/data", f"{active_branch}/interventions"],
                "read_only_roots": read_only_roots,
                "external_mounts_forbidden": True,
            },
            "subprocess_policy": {
                "auto_allowed_classes": [
                    "read_only_inspection",
                    "py_compile",
                    "shadow_diagnostic_runner",
                ],
                "gated_classes": [
                    "retained_structural_promotion",
                    "branch_state_change",
                    "protected_surface_challenge",
                    "resource_expansion_request",
                    "skill_trial",
                    "skill_retention_promotion",
                ],
                "forbidden_classes": [
                    "live_policy_change",
                    "threshold_change",
                    "routing_policy_change",
                    "frozen_benchmark_semantics_change",
                    "projection_safe_envelope_change",
                    "untrusted_external_access",
                ],
            },
            "resource_accounting_mode": "tracked_budget_v1",
        },
    }


def _build_branch_registry(
    *,
    now: str,
    bootstrap_context: dict[str, Any],
    existing_registry: dict[str, Any],
) -> dict[str, Any]:
    active_branch = str(bootstrap_context.get("active_branch", "novali-v5"))
    reference_branch = str(bootstrap_context.get("completed_reference_branch", "novali-v4"))
    branch_name = str(bootstrap_context.get("branch_name", "directive_bootstrap"))
    active_branch_id = str(
        bootstrap_context.get("branch_id", existing_registry.get("current_branch_id", f"{active_branch}:{branch_name}"))
    )
    reference_branch_id = str(bootstrap_context.get("reference_branch_id", f"{reference_branch}:{branch_name}"))
    transition_timestamp = str(bootstrap_context.get("branch_transition_timestamp", now))
    transition_status = str(
        bootstrap_context.get(
            "branch_transition_status",
            f"{reference_branch}_completed_reference_{active_branch}_active".replace("-", "_"),
        )
    )
    transition_reason = str(bootstrap_context.get("branch_transition_reason", "directive bootstrap opened the next active branch"))
    held_baseline = dict(bootstrap_context.get("held_baseline", {}))
    if _is_missing(held_baseline.get("template")):
        held_baseline["template"] = str(bootstrap_context.get("held_baseline_template", ""))
    active_record = {
        "branch_id": active_branch_id,
        "branch_name": branch_name,
        "branch_role": "active_development_target",
        "reference_base_branch": reference_branch,
        "reference_operator_surface_branch": str(
            bootstrap_context.get("reference_operator_surface_branch", reference_branch)
        ),
        "state": str(bootstrap_context.get("branch_state", "paused_with_baseline_held")),
        "held_baseline": held_baseline,
        "promotion_rationale": str(
            bootstrap_context.get(
                "promotion_rationale",
                "the carried-forward baseline remains the current narrow standard to beat",
            )
        ),
        "pause_rationale": str(
            bootstrap_context.get(
                "pause_rationale",
                "hold the current narrow baseline while future work remains governed and routing stays deferred",
            )
        ),
        "reopen_triggers": [str(item) for item in list(bootstrap_context.get("reopen_triggers", []))],
        "closed_next_steps": [str(item) for item in list(bootstrap_context.get("closed_next_steps", []))],
        "last_evidence_artifact": str(bootstrap_context.get("last_evidence_artifact", "")),
        "supporting_artifacts": [str(item) for item in list(bootstrap_context.get("supporting_artifacts", []))],
        "transition_reason": transition_reason,
        "transition_status": transition_status,
        "transition_timestamp": transition_timestamp,
    }
    reference_record = {
        "branch_id": reference_branch_id,
        "branch_name": branch_name,
        "branch_role": "completed_reference_branch",
        "reference_surface_status": "frozen_reference_operator_surface",
        "state": "closed",
        "held_baseline": copy.deepcopy(held_baseline),
        "promotion_rationale": str(active_record.get("promotion_rationale", "")),
        "pause_rationale": str(active_record.get("pause_rationale", "")),
        "reopen_triggers": copy.deepcopy(active_record.get("reopen_triggers", [])),
        "closed_next_steps": copy.deepcopy(active_record.get("closed_next_steps", [])),
        "last_evidence_artifact": str(active_record.get("last_evidence_artifact", "")),
        "supporting_artifacts": copy.deepcopy(active_record.get("supporting_artifacts", [])),
        "transition_reason": transition_reason,
        "transition_status": transition_status,
        "transition_timestamp": transition_timestamp,
    }
    built_ids = {active_branch_id, reference_branch_id}
    extra_records = [
        copy.deepcopy(item)
        for item in list(existing_registry.get("branches", []))
        if isinstance(item, dict) and str(item.get("branch_id", "")) not in built_ids
    ]
    return {
        "schema_version": "branch_registry_v1",
        "generated_at": now,
        "supported_states": [
            "active",
            "paused_with_baseline_held",
            "held_baseline",
            "reopen_candidate",
            "deprecated",
            "closed",
        ],
        "current_branch_id": active_branch_id,
        "branches": [active_record, reference_record] + extra_records,
    }


def _build_directive_state(
    *,
    now: str,
    directive_spec: dict[str, Any],
    clarification_questions: list[dict[str, Any]],
    clarification_history: list[dict[str, Any]],
    directive_file: Path,
    validation_report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "directive_state_v1",
        "generated_at": now,
        "directive_spec_schema": {
            "schema_name": DIRECTIVE_SPEC_SCHEMA_NAME,
            "schema_version": DIRECTIVE_SPEC_SCHEMA_VERSION,
            "required_fields": list(REQUIRED_DIRECTIVE_FIELDS),
        },
        "initialization_flow_schema": {
            "schema_name": INITIALIZATION_FLOW_SCHEMA_NAME,
            "schema_version": INITIALIZATION_FLOW_SCHEMA_VERSION,
            "states": [
                "draft_received",
                "clarification_required",
                "clarified",
                "validated",
                "active",
            ],
        },
        "partial_directive_intake": {
            "directive_file_path": str(directive_file),
            "directive_id": str(directive_spec.get("directive_id", "")),
            "directive_text": str(directive_spec.get("directive_text", "")),
        },
        "clarification_questions": copy.deepcopy(clarification_questions),
        "clarification_history": copy.deepcopy(clarification_history),
        "validation_report": copy.deepcopy(validation_report),
        "current_directive_state": copy.deepcopy(directive_spec),
        "validated_at": now,
        "activated_at": now,
        "initialization_state": "active",
        "execution_activation_guard": {
            "source_of_truth": "directive_bootstrap_v1",
            "validation_required_before_activation": True,
            "blocked_states": [
                "draft_received",
                "clarification_required",
                "clarified",
            ],
            "release_state": "validated",
            "current_state": "active",
            "current_activation_allowed": True,
            "activation_sequence_correct": True,
            "autonomous_self_directed_execution_blocked_before_validation": True,
        },
        "governance_source_of_truth": {
            "owner": "directive_bootstrap_v1",
            "directive_history_path": "",
            "proposal_learning_loop_is_governance_truth_source": False,
            "raw_freeform_initialization_is_authority_path": False,
            "formal_directive_file_path": str(directive_file),
        },
    }


def _build_binding_decisions(
    *,
    bootstrap_context: dict[str, Any],
    paths: BootstrapPaths,
) -> list[dict[str, Any]]:
    return [
        {
            "decision_id": "branch_posture",
            "decision_class": "binding_decision",
            "status": str(bootstrap_context.get("branch_state", "")),
            "reason": str(bootstrap_context.get("pause_rationale", "")),
            "authority_source": str(paths.branch_registry_path),
        },
        {
            "decision_id": "held_baseline",
            "decision_class": "binding_decision",
            "status": "baseline_held",
            "baseline_template": str(bootstrap_context.get("held_baseline_template", "")),
            "authority_source": str(paths.branch_registry_path),
        },
        {
            "decision_id": "routing_status",
            "decision_class": "binding_decision",
            "status": str(bootstrap_context.get("routing_status", "")),
            "reason": "routing remains deferred under the carried-forward governance posture",
            "authority_source": str(paths.governance_memory_authority_path),
        },
        {
            "decision_id": "directive_activation",
            "decision_class": "binding_decision",
            "status": "formal_directive_active",
            "reason": "the current runtime must initialize from a formal DirectiveSpec before governed execution",
            "authority_source": str(paths.directive_state_path),
        },
        {
            "decision_id": "reference_surface",
            "decision_class": "binding_decision",
            "status": str(bootstrap_context.get("completed_reference_branch", "")),
            "reason": "the completed reference/operator surface remains read-only while novali-v5 is the active edit target",
            "authority_source": str(paths.branch_registry_path),
        },
        {
            "decision_id": "selector_frontier",
            "decision_class": "binding_decision",
            "status": str(bootstrap_context.get("selector_frontier_read", "serial_budget_then_ordering")),
            "reason": "the selector-frontier conclusion is carried forward and remains directly queryable",
            "authority_source": str(paths.governance_memory_authority_path),
        },
    ]


def _build_capability_boundary_state(
    *,
    directive_spec: dict[str, Any],
    bootstrap_context: dict[str, Any],
) -> dict[str, Any]:
    return {
        "formal_directive_required_for_activation": True,
        "trusted_source_only_boundaries": True,
        "bounded_bucket_required": True,
        "routing_deferred": str(bootstrap_context.get("routing_status", "")) == "routing_deferred",
        "plan_non_owning": bool(bootstrap_context.get("plan_non_owning", True)),
        "projection_safety_primary": bool(bootstrap_context.get("projection_safety_primary", True)),
        "allowed_action_classes": [str(item) for item in list(directive_spec.get("allowed_action_classes", []))],
        "new_skill_admission_separate_path": True,
        "reopen_path_separate_from_direct_work": True,
        "capability_use_separate_from_directive_work": True,
        "runtime_loop_code_is_authority": False,
    }


def _build_selector_frontier_memory(bootstrap_context: dict[str, Any]) -> dict[str, Any]:
    selector_frontier_memory = dict(bootstrap_context.get("selector_frontier_memory", {}))
    if selector_frontier_memory:
        return selector_frontier_memory
    return {
        "final_selection_split_assessment": str(
            bootstrap_context.get("selector_frontier_read", "serial_budget_then_ordering")
        ),
        "dominant_blocker": str(
            bootstrap_context.get("selector_frontier_dominant_blocker", "selection_budget_hold_for_drift_control")
        ),
        "first_gate": str(bootstrap_context.get("selector_frontier_first_gate", "budget_eligibility_under_frozen_cap")),
        "second_gate": str(
            bootstrap_context.get("selector_frontier_second_gate", "within_cap_ordering_and_tiebreak")
        ),
        "blocked_residuals": copy.deepcopy(dict(bootstrap_context.get("blocked_residuals", {}))),
    }


def _build_swap_c_status(bootstrap_context: dict[str, Any]) -> dict[str, Any]:
    swap_c = bootstrap_context.get("carried_forward_safe_trio_reference", {})
    if isinstance(swap_c, dict):
        normalized = copy.deepcopy(swap_c)
        normalized.setdefault("baseline_name", "swap_C")
        return normalized
    return {
        "baseline_name": "swap_C",
        "reference_text": str(swap_c),
    }


def _build_bootstrap_read_contract(paths: BootstrapPaths) -> dict[str, Any]:
    return {
        "schema_name": "BootstrapCanonicalReadContract",
        "schema_version": "bootstrap_canonical_read_contract_v1",
        "canonical_authority_file": str(paths.governance_memory_authority_path),
        "directive_state_file": str(paths.directive_state_path),
        "bucket_state_file": str(paths.bucket_state_path),
        "branch_registry_file": str(paths.branch_registry_path),
        "self_structure_state_file": str(paths.self_structure_state_path),
        "read_order": [
            "governance_memory_authority_latest",
            "self_structure_state_latest",
            "branch_registry_latest",
            "directive_state_latest",
            "bucket_state_latest",
        ],
    }


def _build_governance_memory_authority(
    *,
    now: str,
    directive_spec: dict[str, Any],
    bootstrap_context: dict[str, Any],
    paths: BootstrapPaths,
) -> dict[str, Any]:
    additional_reference_versions = _normalize_additional_reference_versions(bootstrap_context)
    authority_file_summary = {
        "schema_name": "GovernanceMemoryAuthority",
        "schema_version": "governance_memory_authority_v1",
        "active_branch": str(bootstrap_context.get("active_branch", "")),
        "default_edit_target_branch": str(bootstrap_context.get("active_branch", "")),
        "next_active_development_branch": str(bootstrap_context.get("active_branch", "")),
        "completed_reference_branch": str(bootstrap_context.get("completed_reference_branch", "")),
        "reference_operator_surface_branch": str(
            bootstrap_context.get("reference_operator_surface_branch", "")
        ),
        "frozen_fallback_reference_version": str(
            bootstrap_context.get("frozen_fallback_reference_version", "")
        ),
        "additional_reference_versions": additional_reference_versions,
        "current_branch_state": str(bootstrap_context.get("branch_state", "")),
        "held_baseline_template": str(bootstrap_context.get("held_baseline_template", "")),
        "current_operating_stance": str(bootstrap_context.get("current_operating_stance", "")),
        "routing_status": str(bootstrap_context.get("routing_status", "")),
        "governed_work_loop_status": str(
            bootstrap_context.get("governed_work_loop_status", "hold_position_closed_out_v1")
        ),
        "plan_non_owning": bool(bootstrap_context.get("plan_non_owning", True)),
        "projection_safety_primary": bool(bootstrap_context.get("projection_safety_primary", True)),
        "reopen_eligibility": copy.deepcopy(
            dict(
                bootstrap_context.get(
                    "reopen_eligibility",
                    {
                        "branch_reopen_candidate_status": "requires_new_evidence",
                        "governed_work_loop_reentry_status": "reentry_requires_new_evidence",
                        "benchmark_controlled_reopen_supported": False,
                    },
                )
            )
        ),
        "branch_transition_id": str(
            bootstrap_context.get(
                "branch_transition_id",
                f"branch_transition::{bootstrap_context.get('completed_reference_branch', '')}_to_{bootstrap_context.get('active_branch', '')}",
            )
        ),
        "branch_transition_status": str(
            bootstrap_context.get("branch_transition_status", "active_branch_opened_from_completed_reference")
        ),
        "branch_transition_reason": str(bootstrap_context.get("branch_transition_reason", "")),
        "branch_transition_timestamp": str(bootstrap_context.get("branch_transition_timestamp", now)),
        "read_contract_version": READ_CONTRACT_SCHEMA_VERSION,
        "selector_frontier_memory": _build_selector_frontier_memory(bootstrap_context),
        "swap_c_status": _build_swap_c_status(bootstrap_context),
    }
    capability_boundary_state = _build_capability_boundary_state(
        directive_spec=directive_spec,
        bootstrap_context=bootstrap_context,
    )
    binding_decisions = _build_binding_decisions(
        bootstrap_context=bootstrap_context,
        paths=paths,
    )
    return {
        "generated_at": now,
        "authority_mutation_stage": BINDING_PROMOTED_AUTHORITY,
        "authority_contract": _build_bootstrap_read_contract(paths),
        "authority_surface": {
            "runtime_loop_code_is_authority": False,
            "canonical_artifacts_are_authority": True,
            "formal_directive_bootstrap_required": True,
            "activation_guard_enforced": True,
        },
        "authority_file_summary": authority_file_summary,
        "binding_decision_register": binding_decisions,
        "capability_boundary_state": capability_boundary_state,
        "selector_frontier_memory": copy.deepcopy(authority_file_summary.get("selector_frontier_memory", {})),
        "swap_c_status": copy.deepcopy(authority_file_summary.get("swap_c_status", {})),
        "authority_candidate_record": {},
        "authority_promotion_record": {},
    }


def _build_current_state_summary(
    *,
    directive_spec: dict[str, Any],
    bootstrap_context: dict[str, Any],
    paths: BootstrapPaths,
) -> dict[str, Any]:
    return {
        "active_directive_id": str(directive_spec.get("directive_id", "")),
        "directive_initialization_state": "active",
        "directive_activation_guarded_by_validation": True,
        "active_working_version": str(bootstrap_context.get("active_branch", "")),
        "default_edit_target_version": str(bootstrap_context.get("active_branch", "")),
        "next_active_development_target": str(bootstrap_context.get("active_branch", "")),
        "completed_reference_working_version": str(bootstrap_context.get("completed_reference_branch", "")),
        "reference_operator_surface_version": str(
            bootstrap_context.get("reference_operator_surface_branch", "")
        ),
        "frozen_fallback_reference_version": str(
            bootstrap_context.get("frozen_fallback_reference_version", "")
        ),
        "current_branch_id": str(
            bootstrap_context.get(
                "branch_id",
                f"{bootstrap_context.get('active_branch', '')}:{bootstrap_context.get('branch_name', '')}",
            )
        ),
        "current_branch_state": str(bootstrap_context.get("branch_state", "")),
        "held_baseline_template": str(bootstrap_context.get("held_baseline_template", "")),
        "latest_current_operating_stance": str(bootstrap_context.get("current_operating_stance", "")),
        "routing_deferred": str(bootstrap_context.get("routing_status", "")) == "routing_deferred",
        "plan_non_owning": bool(bootstrap_context.get("plan_non_owning", True)),
        "governance_substrate_in_place": True,
        "governance_memory_authority_v1_in_place": True,
        "directive_bootstrap_entrypoint_in_place": True,
        "latest_architecture_truth_surface": "governance_memory_authority_v1",
        "latest_governance_memory_authority_file_path": str(paths.governance_memory_authority_path),
        "latest_governance_memory_read_contract_version": READ_CONTRACT_SCHEMA_VERSION,
        "latest_governance_memory_resolution_mode": "authority_then_supporting_then_audit",
    }


def _build_self_structure_state(
    *,
    now: str,
    directive_spec: dict[str, Any],
    bootstrap_context: dict[str, Any],
    paths: BootstrapPaths,
    governance_memory_authority: dict[str, Any],
    existing_self_structure_state: dict[str, Any],
) -> dict[str, Any]:
    policy = _build_policy_representation()
    current_state_summary = _deep_merge(
        dict(existing_self_structure_state.get("current_state_summary", {})),
        _build_current_state_summary(
            directive_spec=directive_spec,
            bootstrap_context=bootstrap_context,
            paths=paths,
        ),
    )
    update = {
        "generated_at": now,
        "directive_state_path": str(paths.directive_state_path),
        "directive_history_path": str(paths.directive_history_path),
        "bucket_state_path": str(paths.bucket_state_path),
        "branch_registry_path": str(paths.branch_registry_path),
        "self_structure_ledger_path": str(paths.self_structure_ledger_path),
        "directive_initialization_flow": {
            "schema_version": INITIALIZATION_FLOW_SCHEMA_VERSION,
            "states": [
                "draft_received",
                "clarification_required",
                "clarified",
                "validated",
                "active",
            ],
            "current_state": "active",
            "validation_required_before_activation": True,
            "autonomous_self_directed_execution_blocked_before_validation": True,
            "directive_history_path": str(paths.directive_history_path),
        },
        "governance_memory_authority": copy.deepcopy(dict(governance_memory_authority.get("authority_file_summary", {}))),
        "governance_memory_authority_promotion_record": copy.deepcopy(
            dict(governance_memory_authority.get("authority_promotion_record", {}))
        ),
        "policy": policy,
        "current_state_summary": current_state_summary,
    }
    return _deep_merge(existing_self_structure_state, update)


def _build_branch_transition_status(
    *,
    now: str,
    bootstrap_context: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_name": "BranchTransitionStatus",
        "schema_version": "branch_transition_status_v1",
        "branch_transition_id": str(
            bootstrap_context.get(
                "branch_transition_id",
                f"branch_transition::{bootstrap_context.get('completed_reference_branch', '')}_to_{bootstrap_context.get('active_branch', '')}",
            )
        ),
        "transition_status": str(
            bootstrap_context.get("branch_transition_status", "active_branch_opened_from_completed_reference")
        ),
        "transition_timestamp": str(bootstrap_context.get("branch_transition_timestamp", now)),
        "reason": str(bootstrap_context.get("branch_transition_reason", "")),
        "completed_reference_branch": str(bootstrap_context.get("completed_reference_branch", "")),
        "reference_operator_surface_branch": str(
            bootstrap_context.get("reference_operator_surface_branch", "")
        ),
        "next_active_development_branch": str(bootstrap_context.get("active_branch", "")),
        "default_edit_target_branch": str(bootstrap_context.get("active_branch", "")),
        "frozen_fallback_reference_version": str(
            bootstrap_context.get("frozen_fallback_reference_version", "")
        ),
        "older_preserved_reference_version": str(bootstrap_context.get("older_reference_version", "")),
        "current_branch_state": str(bootstrap_context.get("branch_state", "")),
        "current_operating_stance": str(bootstrap_context.get("current_operating_stance", "")),
        "held_baseline_template": str(bootstrap_context.get("held_baseline_template", "")),
        "carried_forward_safe_trio_reference": copy.deepcopy(
            bootstrap_context.get("carried_forward_safe_trio_reference", {})
        ),
        "routing_status": str(bootstrap_context.get("routing_status", "")),
        "invariants_preserved": {
            "live_policy": "unchanged",
            "thresholds": "unchanged",
            "routing_policy": "deferred_unchanged",
            "frozen_benchmark_semantics": "unchanged",
        },
    }


def _build_version_handoff_status(
    *,
    now: str,
    bootstrap_context: dict[str, Any],
) -> dict[str, Any]:
    return {
        "active_working_version": str(bootstrap_context.get("active_branch", "")),
        "completed_reference_version": str(bootstrap_context.get("completed_reference_branch", "")),
        "reference_operator_surface_version": str(
            bootstrap_context.get("reference_operator_surface_branch", "")
        ),
        "frozen_fallback_reference_version": str(
            bootstrap_context.get("frozen_fallback_reference_version", "")
        ),
        "older_preserved_reference_version": str(bootstrap_context.get("older_reference_version", "")),
        "branch_transition_id": str(
            bootstrap_context.get(
                "branch_transition_id",
                f"branch_transition::{bootstrap_context.get('completed_reference_branch', '')}_to_{bootstrap_context.get('active_branch', '')}",
            )
        ),
        "branch_transition_timestamp": str(bootstrap_context.get("branch_transition_timestamp", now)),
        "branch_transition_reason": str(bootstrap_context.get("branch_transition_reason", "")),
        "version_transition_status": str(
            bootstrap_context.get("branch_transition_status", "active_branch_opened_from_completed_reference")
        ),
        "carried_forward_baseline": copy.deepcopy(
            bootstrap_context.get("carried_forward_safe_trio_reference", {})
        ),
        "working_rules_for_novali_v5": {
            "use_carried_forward_baseline": True,
            "treat_novali_v4_as_frozen_reference_operator_surface": True,
            "do_not_edit_novali_v4_by_default": True,
            "live_policy_status": "unchanged",
            "threshold_status": "unchanged",
            "routing_status": str(bootstrap_context.get("routing_status", "")),
            "frozen_benchmark_semantics_status": "unchanged",
            "projection_safe_envelope_status": "unchanged",
        },
    }


def _load_existing_payloads(paths: BootstrapPaths) -> dict[str, dict[str, Any]]:
    return {
        "directive_state": _load_json(paths.directive_state_path),
        "bucket_state": _load_json(paths.bucket_state_path),
        "branch_registry": _load_json(paths.branch_registry_path),
        "governance_memory_authority": _load_json(paths.governance_memory_authority_path),
        "self_structure_state": _load_json(paths.self_structure_state_path),
        "branch_transition_status": _load_json(paths.branch_transition_status_path),
        "version_handoff_status": _load_json(paths.version_handoff_status_path),
    }


def _canonical_posture_snapshot(
    *,
    directive_state: dict[str, Any],
    branch_registry: dict[str, Any],
    governance_memory_authority: dict[str, Any],
    self_structure_state: dict[str, Any],
) -> dict[str, Any]:
    current_directive = dict(directive_state.get("current_directive_state", {}))
    branches = list(branch_registry.get("branches", []))
    current_branch_id = str(branch_registry.get("current_branch_id", ""))
    active_branch_record = next(
        (dict(item) for item in branches if isinstance(item, dict) and str(item.get("branch_id", "")) == current_branch_id),
        dict(branches[0]) if branches else {},
    )
    authority_summary = dict(governance_memory_authority.get("authority_file_summary", {}))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    return {
        "directive_id": str(current_directive.get("directive_id", "")),
        "active_branch": str(authority_summary.get("active_branch", "")),
        "current_branch_id": current_branch_id,
        "current_branch_state": str(authority_summary.get("current_branch_state", "")),
        "current_operating_stance": str(authority_summary.get("current_operating_stance", "")),
        "held_baseline_template": str(authority_summary.get("held_baseline_template", "")),
        "routing_status": str(authority_summary.get("routing_status", "")),
        "reference_operator_surface_branch": str(authority_summary.get("reference_operator_surface_branch", "")),
        "completed_reference_branch": str(authority_summary.get("completed_reference_branch", "")),
        "frozen_fallback_reference_version": str(authority_summary.get("frozen_fallback_reference_version", "")),
        "default_edit_target_branch": str(authority_summary.get("default_edit_target_branch", "")),
        "branch_role": str(active_branch_record.get("branch_role", "")),
        "directive_initialization_state": str(directive_state.get("initialization_state", "")),
        "self_structure_active_working_version": str(current_state_summary.get("active_working_version", "")),
    }


def _consistency_errors(
    *,
    directive_state: dict[str, Any],
    bucket_state: dict[str, Any],
    branch_registry: dict[str, Any],
    governance_memory_authority: dict[str, Any],
    self_structure_state: dict[str, Any],
    paths: BootstrapPaths,
) -> list[str]:
    errors: list[str] = []
    if not directive_state:
        errors.append("directive_state is missing")
    if not bucket_state:
        errors.append("bucket_state is missing")
    if not branch_registry:
        errors.append("branch_registry is missing")
    if not governance_memory_authority:
        errors.append("governance_memory_authority is missing")
    if not self_structure_state:
        errors.append("self_structure_state is missing")
    if errors:
        return errors

    current_directive = dict(directive_state.get("current_directive_state", {}))
    current_bucket = dict(bucket_state.get("current_bucket_state", {}))
    authority_summary = dict(governance_memory_authority.get("authority_file_summary", {}))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    branches = list(branch_registry.get("branches", []))
    current_branch_id = str(branch_registry.get("current_branch_id", ""))
    active_branch_record = next(
        (dict(item) for item in branches if isinstance(item, dict) and str(item.get("branch_id", "")) == current_branch_id),
        {},
    )

    if str(directive_state.get("initialization_state", "")) != "active":
        errors.append("directive_state.initialization_state must be active")
    activation_guard = dict(directive_state.get("execution_activation_guard", {}))
    if not bool(activation_guard.get("current_activation_allowed", False)):
        errors.append("directive_state.execution_activation_guard.current_activation_allowed must be true")

    directive_bucket_spec = dict(current_directive.get("bucket_spec", {}))
    if str(directive_bucket_spec.get("bucket_id", "")) != str(current_bucket.get("bucket_id", "")):
        errors.append("directive bucket_id does not match bucket_state current bucket_id")
    if str(directive_bucket_spec.get("bucket_model", "")) != str(current_bucket.get("bucket_model", "")):
        errors.append("directive bucket_model does not match bucket_state current bucket_model")

    trusted_sources = set(str(item) for item in list(current_directive.get("trusted_sources", [])))
    bucket_sources = set(str(item) for item in list(current_bucket.get("trusted_sources", [])))
    if not trusted_sources.issubset(bucket_sources):
        errors.append("directive trusted_sources must be a subset of bucket_state trusted_sources")

    if not current_branch_id:
        errors.append("branch_registry.current_branch_id must not be empty")
    if not active_branch_record:
        errors.append("branch_registry.current_branch_id must resolve to a branch record")

    if str(authority_summary.get("active_branch", "")) != str(current_state_summary.get("active_working_version", "")):
        errors.append("authority active_branch must match self_structure active_working_version")
    if str(authority_summary.get("default_edit_target_branch", "")) != str(
        current_state_summary.get("default_edit_target_version", "")
    ):
        errors.append("authority default_edit_target_branch must match self_structure default_edit_target_version")
    if str(authority_summary.get("current_branch_state", "")) != str(active_branch_record.get("state", "")):
        errors.append("authority current_branch_state must match branch_registry active state")
    if str(authority_summary.get("held_baseline_template", "")) != str(
        dict(active_branch_record.get("held_baseline", {})).get("template", "")
    ):
        errors.append("authority held_baseline_template must match branch_registry held baseline template")
    if str(current_directive.get("directive_id", "")) != str(current_state_summary.get("active_directive_id", "")):
        errors.append("self_structure active_directive_id must match directive_state directive_id")

    if bool(current_state_summary.get("routing_deferred", False)) != (
        str(authority_summary.get("routing_status", "")) == "routing_deferred"
    ):
        errors.append("self_structure routing_deferred must match authority routing_status")

    if _normalized_path_string(self_structure_state.get("directive_state_path", "")) != _normalized_path_string(
        paths.directive_state_path
    ):
        errors.append("self_structure directive_state_path must point at the canonical local directive_state path")
    if _normalized_path_string(self_structure_state.get("bucket_state_path", "")) != _normalized_path_string(
        paths.bucket_state_path
    ):
        errors.append("self_structure bucket_state_path must point at the canonical local bucket_state path")
    if _normalized_path_string(self_structure_state.get("branch_registry_path", "")) != _normalized_path_string(
        paths.branch_registry_path
    ):
        errors.append("self_structure branch_registry_path must point at the canonical local branch_registry path")

    authority_surface = dict(governance_memory_authority.get("authority_surface", {}))
    if bool(authority_surface.get("runtime_loop_code_is_authority", True)):
        errors.append("governance_memory_authority must explicitly record runtime_loop_code_is_authority as false")

    return errors


def _build_execution_handoff(
    *,
    directive_state: dict[str, Any],
    governance_memory_authority: dict[str, Any],
    paths: BootstrapPaths,
) -> dict[str, Any]:
    current_directive = dict(directive_state.get("current_directive_state", {}))
    authority_summary = dict(governance_memory_authority.get("authority_file_summary", {}))
    return {
        "ready_for_governed_execution": True,
        "directive_id": str(current_directive.get("directive_id", "")),
        "canonical_authority_file": str(paths.governance_memory_authority_path),
        "canonical_posture": {
            "active_branch": str(authority_summary.get("active_branch", "")),
            "current_branch_state": str(authority_summary.get("current_branch_state", "")),
            "current_operating_stance": str(authority_summary.get("current_operating_stance", "")),
            "held_baseline_template": str(authority_summary.get("held_baseline_template", "")),
            "routing_status": str(authority_summary.get("routing_status", "")),
        },
        "execution_gate_owner": "governance_memory_execution_gate_v1",
        "allowed_next_surfaces": [
            "governed_execution",
            "proposal_analytics",
            "proposal_recommend",
            "benchmark_only",
            "proposal_runner",
            "training_loop",
            "compare_live_ab",
        ],
        "startup_authority_rule": "load canonical artifacts first, then defer all runtime permission decisions to governance_memory_execution_gate_v1",
    }


def _write_bootstrap_artifacts(
    *,
    payloads: dict[str, dict[str, Any]],
    paths: BootstrapPaths,
    directive_file: Path,
    bootstrap_mode: str,
) -> None:
    _write_json(paths.directive_state_path, payloads["directive_state"])
    _write_json(paths.bucket_state_path, payloads["bucket_state"])
    _write_json(paths.branch_registry_path, payloads["branch_registry"])
    _write_json(paths.governance_memory_authority_path, payloads["governance_memory_authority"])
    _write_json(paths.self_structure_state_path, payloads["self_structure_state"])
    _write_json(paths.branch_transition_status_path, payloads["branch_transition_status"])
    _write_json(paths.version_handoff_status_path, payloads["version_handoff_status"])

    directive_history_row = {
        "event_id": f"{payloads['directive_state']['current_directive_state'].get('directive_id', '')}:bootstrap:{payloads['directive_state'].get('activated_at', '')}",
        "event_type": "directive_bootstrap_activation",
        "event_timestamp": payloads["directive_state"].get("activated_at", ""),
        "directive_id": str(payloads["directive_state"]["current_directive_state"].get("directive_id", "")),
        "bootstrap_mode": bootstrap_mode,
        "directive_file_path": str(directive_file),
        "directive_state_path": str(paths.directive_state_path),
    }
    _append_jsonl(paths.directive_history_path, directive_history_row)
    _append_jsonl(
        paths.self_structure_ledger_path,
        {
            "event_type": "directive_bootstrap_activation",
            "event_timestamp": payloads["directive_state"].get("activated_at", ""),
            "directive_id": str(payloads["directive_state"]["current_directive_state"].get("directive_id", "")),
            "self_structure_state_path": str(paths.self_structure_state_path),
            "current_state_summary": copy.deepcopy(payloads["self_structure_state"].get("current_state_summary", {})),
        },
    )


def _bootstrap_summary(
    *,
    bootstrap_mode: str,
    directive_file: Path | None,
    paths: BootstrapPaths,
    directive_state: dict[str, Any],
    bucket_state: dict[str, Any],
    branch_registry: dict[str, Any],
    governance_memory_authority: dict[str, Any],
    self_structure_state: dict[str, Any],
    consistency_errors: list[str],
) -> dict[str, Any]:
    posture = _canonical_posture_snapshot(
        directive_state=directive_state,
        branch_registry=branch_registry,
        governance_memory_authority=governance_memory_authority,
        self_structure_state=self_structure_state,
    )
    branches = list(branch_registry.get("branches", []))
    return {
        "bootstrap_mode": bootstrap_mode,
        "directive_file_path": "" if directive_file is None else str(directive_file),
        "state_root": str(paths.data_dir),
        "directive_id": str(directive_state.get("current_directive_state", {}).get("directive_id", "")),
        "initialization_state": str(directive_state.get("initialization_state", "")),
        "canonical_posture": posture,
        "artifact_paths": {
            "directive_state": str(paths.directive_state_path),
            "bucket_state": str(paths.bucket_state_path),
            "branch_registry": str(paths.branch_registry_path),
            "governance_memory_authority": str(paths.governance_memory_authority_path),
            "self_structure_state": str(paths.self_structure_state_path),
            "directive_history": str(paths.directive_history_path),
            "self_structure_ledger": str(paths.self_structure_ledger_path),
        },
        "consistency_report": {
            "passed": len(consistency_errors) == 0,
            "error_count": int(len(consistency_errors)),
            "errors": list(consistency_errors),
        },
        "branch_count": int(len(branches)),
        "trusted_source_count": int(
            len(list(dict(bucket_state.get("current_bucket_state", {})).get("trusted_sources", [])))
        ),
        "execution_handoff": _build_execution_handoff(
            directive_state=directive_state,
            governance_memory_authority=governance_memory_authority,
            paths=paths,
        ),
        "recommended_next_step": (
            "continue through the existing governed execution entrypoints using the canonical artifacts as authority"
            if len(consistency_errors) == 0
            else "stop and repair canonical governance state before any governed execution"
        ),
    }


def bootstrap_runtime(
    *,
    directive_file: str | Path | None = None,
    clarification_file: str | Path | None = None,
    state_root: str | Path | None = None,
    answers_provider: Callable[[dict[str, Any]], Any | None] | None = None,
) -> dict[str, Any]:
    paths = _build_paths(state_root=state_root)

    if directive_file is None:
        existing = _load_existing_payloads(paths)
        consistency = _consistency_errors(
            directive_state=existing["directive_state"],
            bucket_state=existing["bucket_state"],
            branch_registry=existing["branch_registry"],
            governance_memory_authority=existing["governance_memory_authority"],
            self_structure_state=existing["self_structure_state"],
            paths=paths,
        )
        if consistency:
            raise CanonicalStateConsistencyError(
                "canonical governance artifacts are missing or inconsistent; a formal directive bootstrap is required before activation",
                errors=consistency,
            )
        return _bootstrap_summary(
            bootstrap_mode="restart_from_persisted_state",
            directive_file=None,
            paths=paths,
            directive_state=existing["directive_state"],
            bucket_state=existing["bucket_state"],
            branch_registry=existing["branch_registry"],
            governance_memory_authority=existing["governance_memory_authority"],
            self_structure_state=existing["self_structure_state"],
            consistency_errors=[],
        )

    directive_path = Path(directive_file)
    directive_payload = _load_directive_file(directive_path)
    bootstrap_context = copy.deepcopy(dict(directive_payload.get("bootstrap_context", {})))
    _validate_bootstrap_context(bootstrap_context)
    clarification_payload = _load_clarification_file(
        None if clarification_file is None else Path(clarification_file)
    )
    file_clarifications = dict(directive_payload.get("clarification_responses", {}))
    merged_clarifications = {**file_clarifications, **clarification_payload}

    directive_spec = copy.deepcopy(dict(directive_payload.get("directive_spec", {})))
    clarified_spec, clarification_questions, clarification_history, unresolved = _run_clarification_loop(
        directive_spec,
        clarification_responses=merged_clarifications,
        answers_provider=answers_provider,
    )
    if unresolved:
        raise ClarificationRequiredError(
            "formal DirectiveSpec still requires clarification before activation",
            questions=unresolved,
            partially_resolved_spec=clarified_spec,
        )

    normalized_spec = _normalize_directive_spec(
        clarified_spec,
        bootstrap_context=bootstrap_context,
        clarification_questions=clarification_questions,
        clarification_history=clarification_history,
    )
    validation_errors, validation_report = _validate_directive_spec(
        normalized_spec,
        bootstrap_context=bootstrap_context,
    )
    if validation_errors:
        raise DirectiveFileValidationError(
            "formal DirectiveSpec failed validation",
            errors=validation_errors,
        )

    now = _now()
    existing = _load_existing_payloads(paths)
    bucket_state = _deep_merge(
        existing["bucket_state"],
        _build_bucket_state(now=now, directive_spec=normalized_spec, bootstrap_context=bootstrap_context),
    )
    branch_registry = _build_branch_registry(
        now=now,
        bootstrap_context=bootstrap_context,
        existing_registry=existing["branch_registry"],
    )
    directive_state = _deep_merge(
        existing["directive_state"],
        _build_directive_state(
            now=now,
            directive_spec=normalized_spec,
            clarification_questions=clarification_questions,
            clarification_history=clarification_history,
            directive_file=directive_path,
            validation_report=validation_report,
        ),
    )
    directive_state["governance_source_of_truth"]["directive_history_path"] = str(paths.directive_history_path)

    governance_memory_authority = _deep_merge(
        existing["governance_memory_authority"],
        _build_governance_memory_authority(
            now=now,
            directive_spec=normalized_spec,
            bootstrap_context=bootstrap_context,
            paths=paths,
        ),
    )
    self_structure_state = _build_self_structure_state(
        now=now,
        directive_spec=normalized_spec,
        bootstrap_context=bootstrap_context,
        paths=paths,
        governance_memory_authority=governance_memory_authority,
        existing_self_structure_state=existing["self_structure_state"],
    )
    branch_transition_status = _deep_merge(
        existing["branch_transition_status"],
        _build_branch_transition_status(now=now, bootstrap_context=bootstrap_context),
    )
    version_handoff_status = _deep_merge(
        existing["version_handoff_status"],
        _build_version_handoff_status(now=now, bootstrap_context=bootstrap_context),
    )

    consistency = _consistency_errors(
        directive_state=directive_state,
        bucket_state=bucket_state,
        branch_registry=branch_registry,
        governance_memory_authority=governance_memory_authority,
        self_structure_state=self_structure_state,
        paths=paths,
    )
    if consistency:
        raise CanonicalStateConsistencyError(
            "canonical governance state could not be established from the formal directive",
            errors=consistency,
        )

    payloads = {
        "directive_state": directive_state,
        "bucket_state": bucket_state,
        "branch_registry": branch_registry,
        "governance_memory_authority": governance_memory_authority,
        "self_structure_state": self_structure_state,
        "branch_transition_status": branch_transition_status,
        "version_handoff_status": version_handoff_status,
    }
    _write_bootstrap_artifacts(
        payloads=payloads,
        paths=paths,
        directive_file=directive_path,
        bootstrap_mode="fresh_bootstrap_from_directive_file",
    )

    reloaded = _load_existing_payloads(paths)
    reload_consistency = _consistency_errors(
        directive_state=reloaded["directive_state"],
        bucket_state=reloaded["bucket_state"],
        branch_registry=reloaded["branch_registry"],
        governance_memory_authority=reloaded["governance_memory_authority"],
        self_structure_state=reloaded["self_structure_state"],
        paths=paths,
    )
    if reload_consistency:
        raise CanonicalStateConsistencyError(
            "canonical governance artifacts were written but failed deterministic readback validation",
            errors=reload_consistency,
        )

    return _bootstrap_summary(
        bootstrap_mode="fresh_bootstrap_from_directive_file",
        directive_file=directive_path,
        paths=paths,
        directive_state=reloaded["directive_state"],
        bucket_state=reloaded["bucket_state"],
        branch_registry=reloaded["branch_registry"],
        governance_memory_authority=reloaded["governance_memory_authority"],
        self_structure_state=reloaded["self_structure_state"],
        consistency_errors=[],
    )


def _print_bootstrap_summary(summary: dict[str, Any]) -> None:
    posture = dict(summary.get("canonical_posture", {}))
    consistency = dict(summary.get("consistency_report", {}))
    execution_handoff = dict(summary.get("execution_handoff", {}))
    print("\n=== NOVALI Bootstrap Summary ===")
    print(f"Mode            : {summary.get('bootstrap_mode')}")
    print(f"Directive ID    : {summary.get('directive_id')}")
    print(f"Directive File  : {summary.get('directive_file_path') or 'persisted-state restart'}")
    print(f"State Root      : {summary.get('state_root')}")
    print(f"Init State      : {summary.get('initialization_state')}")
    print(f"Active Branch   : {posture.get('active_branch')}")
    print(f"Branch State    : {posture.get('current_branch_state')}")
    print(f"Operating Stance: {posture.get('current_operating_stance')}")
    print(f"Held Baseline   : {posture.get('held_baseline_template')}")
    print(f"Routing Status  : {posture.get('routing_status')}")
    print(f"Reference Branch: {posture.get('completed_reference_branch')}")
    print(f"Consistency     : passed={consistency.get('passed')} errors={consistency.get('error_count')}")
    if consistency.get("errors"):
        for item in list(consistency.get("errors", [])):
            print(f"  - {item}")
    print(f"Exec Ready      : {execution_handoff.get('ready_for_governed_execution')}")
    print(f"Next Step       : {summary.get('recommended_next_step')}")


def main() -> None:
    if _OPERATOR_GUARD_INSTALL_ERROR is not None:
        raise _OPERATOR_GUARD_INSTALL_ERROR

    parser = argparse.ArgumentParser(
        description="Non-canonical developer/test bootstrap entrypoint for novali-v5. Canonical human-facing local launch is the operator shell."
    )
    parser.add_argument(
        "--directive-file",
        required=True,
        help="Path to the formal NOVALIDirectiveBootstrapFile JSON document.",
    )
    parser.add_argument(
        "--clarification-file",
        default="",
        help="Optional JSON mapping of clarification responses for missing or ambiguous DirectiveSpec fields.",
    )
    parser.add_argument(
        "--state-root",
        default="",
        help="Optional alternate data directory for bootstrap/testing. Defaults to novali-v5/data.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the bootstrap result as JSON instead of a human-readable summary.",
    )
    args = parser.parse_args()

    try:
        summary = bootstrap_runtime(
            directive_file=str(args.directive_file),
            clarification_file=str(args.clarification_file) or None,
            state_root=str(args.state_root) or None,
        )
    except ClarificationRequiredError as exc:
        payload = {
            "status": "clarification_required",
            "message": str(exc),
            "question_count": len(exc.questions),
            "questions": exc.questions,
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print("\nDirective Clarification Required")
            print(f"Reason          : {exc}")
            for question in exc.questions:
                print(f"  - {question.get('field')}: {question.get('question')}")
        raise SystemExit(2)
    except (DirectiveFileValidationError, CanonicalStateConsistencyError, DirectiveBootstrapError) as exc:
        errors = getattr(exc, "errors", [])
        payload = {
            "status": "bootstrap_failed",
            "message": str(exc),
            "errors": list(errors),
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print("\nNOVALI Bootstrap Failed")
            print(f"Reason          : {exc}")
            for item in list(errors):
                print(f"  - {item}")
        raise SystemExit(2)

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return
    _print_bootstrap_summary(summary)


if __name__ == "__main__":
    try:
        main()
    except OperatorConstraintViolationError as exc:
        print("\nOperator Constraint Blocked")
        print(f"Reason          : {exc}")
        print(f"Constraint ID   : {exc.constraint_id}")
        print(f"Enforcement     : {exc.enforcement_class}")
        raise SystemExit(2)
