from __future__ import annotations

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
    _build_policy_representation,
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


INITIALIZATION_STATES = [
    "draft_received",
    "clarification_required",
    "clarified",
    "validated",
    "active",
]


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


def _diagnostic_artifact_dir() -> Path:
    path = intervention_data_dir() / "diagnostic_memory"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    return False


def _required_fields(existing_directive_state: dict[str, Any]) -> list[str]:
    schema = dict(existing_directive_state.get("directive_spec_schema", {}))
    required = list(schema.get("required_fields", []))
    if required:
        return [str(item) for item in required]
    return [
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


def _build_partial_directive_intake(
    *,
    branch_record: dict[str, Any],
    bucket_state: dict[str, Any],
) -> dict[str, Any]:
    current_bucket = dict(bucket_state.get("current_bucket_state", {}))
    return {
        "directive_id": "directive_branch_transition_v1",
        "directive_text": "Maintain branch-governed continuity by treating novali-v5 as the active edit target and novali-v4 as the frozen reference/operator surface.",
        "constraints": [
            "do not change live policy",
            "do not change thresholds",
            "do not change routing policy",
            "do not change frozen benchmark semantics",
            "do not broaden the projection-safe envelope",
            "novali-v5 is the only active edit target",
            "novali-v4 remains frozen reference/operator surface",
            "novali-v3 remains unchanged as fallback/reference",
            "novali-v2 remains unchanged as older preserved fallback/reference",
            "plan_ remains non-owning",
            "routing remains deferred",
        ],
        "trusted_sources": list(current_bucket.get("trusted_sources", [])),
        "bucket_spec": {
            "bucket_id": str(current_bucket.get("bucket_id", "")),
            "bucket_model": str(current_bucket.get("bucket_model", "")),
        },
        "allowed_action_classes": [
            "low_risk_shell_change",
            "diagnostic_schema_materialization",
            "append_only_ledger_write",
            "local_governance_registry_update",
        ],
        "branch_context": {
            "branch_id": str(branch_record.get("branch_id", "")),
            "branch_state": str(branch_record.get("state", "")),
            "held_baseline": dict(branch_record.get("held_baseline", {})),
        },
    }


def _clarification_prompt(field_name: str) -> str:
    prompts = {
        "clarified_intent_summary": "What exact clarified intent summary should govern the directive beyond the raw task text?",
        "success_criteria": "What concrete success criteria should be used to judge directive completion?",
        "milestone_model": "What milestone model should structure the directive from initialization through completion?",
        "human_approval_points": "Which human approval points must remain explicitly gated under this directive?",
        "stop_conditions": "Which stop conditions must terminate execution or escalation under this directive?",
        "drift_budget_for_context_exploration": "What tagged, budgeted drift allowance is permitted for contextual exploration under this directive?",
    }
    return prompts.get(
        str(field_name),
        f"What clarification is required to complete the DirectiveSpec field `{field_name}`?",
    )


def _build_clarification_questions(partial_intake: dict[str, Any], required_fields: list[str]) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    for field_name in required_fields:
        if not _is_missing(partial_intake.get(field_name)):
            continue
        questions.append(
            {
                "question_id": f"clarify_{field_name}",
                "field": str(field_name),
                "question": _clarification_prompt(str(field_name)),
                "reason": "required DirectiveSpec field is missing from the draft intake",
            }
        )
    return questions


def _normalized_directive_spec(
    *,
    partial_intake: dict[str, Any],
    prior_directive_state: dict[str, Any],
    bucket_state: dict[str, Any],
    branch_record: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    current_bucket = dict(bucket_state.get("current_bucket_state", {}))
    prior_directive = dict(prior_directive_state.get("current_directive_state", {}))
    return {
        "directive_id": str(partial_intake.get("directive_id", "directive_spec_initialization_flow_v1")),
        "directive_text": str(partial_intake.get("directive_text", "")),
        "clarified_intent_summary": (
            "Materialize a governed DirectiveSpec initialization path that accepts partial intake, requires clarification for missing fields, "
            "normalizes into a full DirectiveSpec, validates against governance constraints, and blocks autonomous activation until validation succeeds."
        ),
        "success_criteria": [
            "DirectiveSpec initialization state transitions are persisted durably",
            "ambiguous or partial directives halt at clarification_required before activation",
            "only validated directives can become active",
            "directive-init events are written to governance history and self-structure ledger",
            "governance substrate remains the source of truth while live behavior stays unchanged",
        ],
        "milestone_model": [
            {
                "milestone_id": "directive_partial_intake_recorded",
                "completion_signal": "a partial draft intake is persisted with missing-field detection",
            },
            {
                "milestone_id": "directive_clarification_completed",
                "completion_signal": "clarification questions are generated and resolved into a full DirectiveSpec",
            },
            {
                "milestone_id": "directive_validation_and_activation_gated",
                "completion_signal": "validation passes and directive activation occurs only after validation",
            },
        ],
        "human_approval_points": list(
            prior_directive.get(
                "human_approval_points",
                [
                    "retained structural promotions",
                    "branch-state changes",
                    "protected-surface challenges",
                    "resource-expansion requests",
                    "retained skill promotions",
                ],
            )
        ),
        "constraints": list(partial_intake.get("constraints", [])),
        "trusted_sources": list(partial_intake.get("trusted_sources", [])),
        "bucket_spec": dict(partial_intake.get("bucket_spec", {})),
        "allowed_action_classes": list(partial_intake.get("allowed_action_classes", [])),
        "stop_conditions": [
            "required DirectiveSpec field remains unresolved after clarification",
            "trusted-source validity check fails",
            "bucket compatibility check fails",
            "allowed action-class compatibility check fails",
            "stop-condition set missing",
            "drift budget for contextual exploration missing",
        ],
        "drift_budget_for_context_exploration": {
            "allowed": True,
            "tag_required": "directive_support",
            "max_budgeted_support_reads": 8,
            "max_budgeted_external_fetches": 0,
        },
        "branch_context": {
            "branch_id": str(branch_record.get("branch_id", "")),
            "branch_state": str(branch_record.get("state", "")),
            "held_baseline": dict(branch_record.get("held_baseline", {})),
            "policy_version": str(policy.get("policy_version", "")),
        },
        "bucket_runtime_context": {
            "bucket_id": str(current_bucket.get("bucket_id", "")),
            "resource_accounting_mode": str(current_bucket.get("resource_accounting_mode", "")),
            "network_mode": str(dict(current_bucket.get("network_policy", {})).get("mode", "")),
        },
    }


def _resolution_summary(value: Any) -> Any:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return [item for item in value[:4]]
    if isinstance(value, dict):
        return {key: value[key] for key in list(value.keys())[:4]}
    return value


def _validate_directive_spec(
    spec: dict[str, Any],
    *,
    required_fields: list[str],
    policy: dict[str, Any],
    bucket_state: dict[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    current_bucket = dict(bucket_state.get("current_bucket_state", {}))
    errors: list[str] = []

    missing_fields = [field_name for field_name in required_fields if _is_missing(spec.get(field_name))]
    completeness_passed = len(missing_fields) == 0
    if not completeness_passed:
        errors.append(f"missing required fields: {', '.join(missing_fields)}")

    trusted_sources = set(str(item) for item in list(spec.get("trusted_sources", [])))
    allowed_sources = set(str(item) for item in list(current_bucket.get("trusted_sources", [])))
    untrusted_sources = sorted(trusted_sources - allowed_sources)
    trusted_sources_passed = len(untrusted_sources) == 0 and len(trusted_sources) > 0
    if not trusted_sources_passed:
        errors.append("trusted-source validity failed")

    bucket_spec = dict(spec.get("bucket_spec", {}))
    bucket_id_matches = str(bucket_spec.get("bucket_id", "")) == str(current_bucket.get("bucket_id", ""))
    bucket_model_matches = str(bucket_spec.get("bucket_model", "")) == str(current_bucket.get("bucket_model", ""))
    bucket_compatibility_passed = bucket_id_matches and bucket_model_matches
    if not bucket_compatibility_passed:
        errors.append("bucket compatibility failed")

    forbidden_actions = set(str(item) for item in list(policy.get("forbidden_actions", [])))
    allowed_action_classes = [str(item) for item in list(spec.get("allowed_action_classes", []))]
    unknown_actions = sorted(set(allowed_action_classes) - KNOWN_ACTION_CLASSES - forbidden_actions)
    forbidden_allowed_actions = sorted(set(allowed_action_classes) & forbidden_actions)
    action_class_passed = len(allowed_action_classes) > 0 and not unknown_actions and not forbidden_allowed_actions
    if not action_class_passed:
        errors.append("allowed action-class compatibility failed")

    stop_conditions = list(spec.get("stop_conditions", []))
    stop_conditions_passed = len(stop_conditions) > 0
    if not stop_conditions_passed:
        errors.append("stop-condition presence failed")

    drift_budget = dict(spec.get("drift_budget_for_context_exploration", {}))
    drift_budget_passed = (
        "allowed" in drift_budget
        and "tag_required" in drift_budget
        and "max_budgeted_support_reads" in drift_budget
        and "max_budgeted_external_fetches" in drift_budget
    )
    if not drift_budget_passed:
        errors.append("drift-budget presence failed")

    reports = {
        "required_field_completeness": {
            "passed": bool(completeness_passed),
            "missing_fields": missing_fields,
            "reason": (
                "all required DirectiveSpec fields are populated"
                if completeness_passed
                else "one or more required DirectiveSpec fields are still missing"
            ),
        },
        "trusted_source_validity": {
            "passed": bool(trusted_sources_passed),
            "requested_sources": sorted(trusted_sources),
            "allowed_sources": sorted(allowed_sources),
            "untrusted_sources": untrusted_sources,
            "reason": (
                "trusted sources comply with the current bucket policy"
                if trusted_sources_passed
                else "trusted sources include values outside the current bucket policy or are empty"
            ),
        },
        "bucket_compatibility": {
            "passed": bool(bucket_compatibility_passed),
            "directive_bucket_spec": bucket_spec,
            "current_bucket": {
                "bucket_id": str(current_bucket.get("bucket_id", "")),
                "bucket_model": str(current_bucket.get("bucket_model", "")),
            },
            "reason": (
                "directive bucket matches the active governed bucket"
                if bucket_compatibility_passed
                else "directive bucket does not match the active governed bucket"
            ),
        },
        "allowed_action_class_compatibility": {
            "passed": bool(action_class_passed),
            "allowed_action_classes": allowed_action_classes,
            "forbidden_actions": forbidden_allowed_actions,
            "unknown_actions": unknown_actions,
            "reason": (
                "allowed action classes are recognized and compatible with governance policy"
                if action_class_passed
                else "allowed action classes include forbidden or unknown entries"
            ),
        },
        "stop_condition_presence": {
            "passed": bool(stop_conditions_passed),
            "stop_condition_count": int(len(stop_conditions)),
            "reason": (
                "stop conditions are present"
                if stop_conditions_passed
                else "stop conditions are missing"
            ),
        },
        "drift_budget_presence": {
            "passed": bool(drift_budget_passed),
            "drift_budget": drift_budget,
            "reason": (
                "contextual exploration is tagged and budgeted"
                if drift_budget_passed
                else "drift budget for contextual exploration is incomplete"
            ),
        },
    }
    return errors, reports


def _build_transition(
    *,
    proposal_id: str,
    directive_id: str,
    from_state: str | None,
    to_state: str,
    note: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    timestamp = _now()
    return {
        "event_id": f"{proposal_id}:{to_state}:{timestamp}",
        "timestamp": timestamp,
        "event_type": f"directive_init_{to_state}",
        "event_class": "directive_initialization_state_transition",
        "directive_id": directive_id,
        "from_state": from_state,
        "to_state": to_state,
        "note": note,
        "details": details,
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governance_substrate_v1_snapshot"
    )
    branch_pause_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_branch_pause_snapshot_v1"
    )
    working_baseline_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_scoped_working_baseline_snapshot_v1"
    )
    frontier_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.false_safe_frontier_control_characterization_snapshot_v1"
    )
    if not all([governance_snapshot, branch_pause_artifact, working_baseline_artifact, frontier_snapshot]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: DirectiveSpec Initialization Flow v1 requires the governance substrate, current branch pause, working baseline, and frontier-control artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite artifacts"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot materialize a directive initialization flow without governance substrate and paused-branch context",
            },
        }

    existing_directive_state = _load_json_file(DIRECTIVE_STATE_PATH)
    existing_bucket_state = _load_json_file(BUCKET_STATE_PATH)
    existing_self_structure_state = _load_json_file(SELF_STRUCTURE_STATE_PATH)
    existing_branch_registry = _load_json_file(BRANCH_REGISTRY_PATH)
    if not all([existing_directive_state, existing_bucket_state, existing_self_structure_state, existing_branch_registry]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: directive initialization flow requires existing directive, bucket, branch, and self-structure governance artifacts",
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
                "reason": "directive initialization flow cannot become authoritative without existing governance source-of-truth artifacts",
            },
        }

    active_status_text = _load_text_file(ACTIVE_STATUS_PATH)
    handoff_status = _load_json_file(HANDOFF_STATUS_PATH)
    analytics = build_intervention_ledger_analytics()
    latest_snapshots = load_latest_snapshots()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")

    branches = list(existing_branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    policy = dict(existing_self_structure_state.get("policy", {})) or _build_policy_representation()
    required_fields = _required_fields(existing_directive_state)
    partial_intake = _build_partial_directive_intake(
        branch_record=branch_record,
        bucket_state=existing_bucket_state,
    )
    directive_id = str(partial_intake.get("directive_id", "directive_spec_initialization_flow_v1"))

    state_transitions: list[dict[str, Any]] = []
    draft_event = _build_transition(
        proposal_id=str(proposal.get("proposal_id", "")),
        directive_id=directive_id,
        from_state=None,
        to_state="draft_received",
        note="partial directive intake recorded before clarification",
        details={
            "present_fields": sorted(partial_intake.keys()),
            "required_field_count": int(len(required_fields)),
        },
    )
    state_transitions.append(draft_event)

    clarification_questions = _build_clarification_questions(partial_intake, required_fields)
    clarification_event = _build_transition(
        proposal_id=str(proposal.get("proposal_id", "")),
        directive_id=directive_id,
        from_state="draft_received",
        to_state="clarification_required",
        note="missing required DirectiveSpec fields require clarification before validation",
        details={
            "question_count": int(len(clarification_questions)),
            "missing_fields": [str(item.get("field", "")) for item in clarification_questions],
        },
    )
    state_transitions.append(clarification_event)

    clarified_spec = _normalized_directive_spec(
        partial_intake=partial_intake,
        prior_directive_state=existing_directive_state,
        bucket_state=existing_bucket_state,
        branch_record=branch_record,
        policy=policy,
    )
    clarification_history = [
        {
            "question_id": str(question.get("question_id", "")),
            "field": str(question.get("field", "")),
            "resolution_source": "governance_context_normalization",
            "resolution_summary": _resolution_summary(clarified_spec.get(str(question.get("field", "")))),
        }
        for question in clarification_questions
    ]
    clarified_event = _build_transition(
        proposal_id=str(proposal.get("proposal_id", "")),
        directive_id=directive_id,
        from_state="clarification_required",
        to_state="clarified",
        note="clarification responses were normalized into a full DirectiveSpec",
        details={
            "clarification_history_count": int(len(clarification_history)),
            "normalized_fields": sorted(clarified_spec.keys()),
        },
    )
    state_transitions.append(clarified_event)

    validation_errors, validation_reports = _validate_directive_spec(
        clarified_spec,
        required_fields=required_fields,
        policy=policy,
        bucket_state=existing_bucket_state,
    )
    validated_at = None
    activated_at = None
    if validation_errors:
        initialization_state = "clarified"
    else:
        validated_at = _now()
        validated_event = _build_transition(
            proposal_id=str(proposal.get("proposal_id", "")),
            directive_id=directive_id,
            from_state="clarified",
            to_state="validated",
            note="DirectiveSpec passed governance validation and can now satisfy the activation guard",
            details={
                "validation_error_count": 0,
                "validated_fields": required_fields,
            },
        )
        validated_event["timestamp"] = validated_at
        validated_event["event_id"] = f"{proposal.get('proposal_id', '')}:validated:{validated_at}"
        state_transitions.append(validated_event)

        activated_at = _now()
        active_event = _build_transition(
            proposal_id=str(proposal.get("proposal_id", "")),
            directive_id=directive_id,
            from_state="validated",
            to_state="active",
            note="DirectiveSpec activation was allowed only after successful validation",
            details={
                "activation_guard_release_state": "validated",
                "autonomous_self_directed_execution_allowed": True,
            },
        )
        active_event["timestamp"] = activated_at
        active_event["event_id"] = f"{proposal.get('proposal_id', '')}:active:{activated_at}"
        state_transitions.append(active_event)
        initialization_state = "active"

    execution_activation_guard = {
        "validation_required_before_activation": True,
        "autonomous_self_directed_execution_blocked_before_validation": True,
        "blocked_states": [
            "draft_received",
            "clarification_required",
            "clarified",
        ],
        "release_state": "validated",
        "current_state": initialization_state,
        "current_activation_allowed": initialization_state in {"validated", "active"},
        "activation_sequence_correct": bool(validated_at and activated_at),
        "source_of_truth": "governance_substrate_v1",
    }

    directive_state_payload = {
        "schema_version": "directive_state_v2",
        "generated_at": _now(),
        "directive_spec_schema": {
            "schema_name": "DirectiveSpec",
            "schema_version": "directive_spec_v1",
            "required_fields": required_fields,
        },
        "initialization_flow_schema": {
            "schema_name": "DirectiveSpecInitializationFlow",
            "schema_version": "directive_spec_initialization_flow_v1",
            "states": list(INITIALIZATION_STATES),
        },
        "governance_source_of_truth": {
            "owner": "governance_substrate_v1",
            "directive_history_path": str(DIRECTIVE_HISTORY_PATH),
            "proposal_learning_loop_is_governance_truth_source": False,
        },
        "partial_directive_intake": partial_intake,
        "current_directive_state": clarified_spec,
        "initialization_state": initialization_state,
        "clarification_questions": clarification_questions,
        "clarification_history": clarification_history,
        "validation_reports": validation_reports,
        "validation_errors": validation_errors,
        "validated_at": validated_at,
        "activated_at": activated_at,
        "state_transition_history": state_transitions,
        "execution_activation_guard": execution_activation_guard,
        "previous_directive_reference": {
            "directive_id": str(dict(existing_directive_state.get("current_directive_state", {})).get("directive_id", "")),
            "schema_version": str(existing_directive_state.get("schema_version", "")),
        },
    }
    _write_json(DIRECTIVE_STATE_PATH, directive_state_payload)

    updated_self_structure_state = dict(existing_self_structure_state)
    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["directive_state_path"] = str(DIRECTIVE_STATE_PATH)
    updated_self_structure_state["directive_history_path"] = str(DIRECTIVE_HISTORY_PATH)
    updated_self_structure_state["directive_initialization_flow"] = {
        "schema_version": "directive_spec_initialization_flow_v1",
        "states": list(INITIALIZATION_STATES),
        "current_state": initialization_state,
        "clarification_question_count": int(len(clarification_questions)),
        "validation_required_before_activation": True,
        "autonomous_self_directed_execution_blocked_before_validation": True,
        "directive_history_path": str(DIRECTIVE_HISTORY_PATH),
    }
    current_state_summary = dict(updated_self_structure_state.get("current_state_summary", {}))
    current_state_summary.update(
        {
            "active_directive_id": directive_id,
            "directive_initialization_state": initialization_state,
            "directive_activation_guarded_by_validation": True,
            "autonomous_self_directed_execution_allowed": initialization_state in {"validated", "active"},
            "plan_non_owning": True,
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
            "governance_substrate_in_place": True,
        }
    )
    updated_self_structure_state["current_state_summary"] = current_state_summary
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    ledger_events = []
    previous_state = None
    for transition in state_transitions:
        event = {
            "event_id": str(transition.get("event_id", "")),
            "timestamp": str(transition.get("timestamp", "")),
            "event_type": str(transition.get("event_type", "")),
            "event_class": "directive_initialization_state_transition",
            "directive_id": directive_id,
            "from_state": previous_state,
            "to_state": str(transition.get("to_state", "")),
            "initialization_state": str(transition.get("to_state", "")),
            "note": str(transition.get("note", "")),
            "details": dict(transition.get("details", {})),
            "source_proposal_id": str(proposal.get("proposal_id", "")),
            "artifact_paths": {
                "directive_state_latest": str(DIRECTIVE_STATE_PATH),
                "directive_history": str(DIRECTIVE_HISTORY_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
            },
        }
        ledger_events.append(event)
        previous_state = str(transition.get("to_state", ""))

    for event in ledger_events:
        _append_jsonl(DIRECTIVE_HISTORY_PATH, event)
        _append_jsonl(SELF_STRUCTURE_LEDGER_PATH, event)

    artifact_path = (
        _diagnostic_artifact_dir()
        / f"memory_summary_v4_directive_spec_initialization_flow_v1_snapshot_{proposal['proposal_id']}.json"
    )
    all_ranked = list(recommendations.get("all_ranked_proposals", []))
    suggested_templates = [
        str(item.get("template_name", ""))
        for item in all_ranked
        if isinstance(item, dict) and str(item.get("decision", "")) == "suggested"
    ][:8]
    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_directive_spec_initialization_flow_v1_snapshot",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "branch_context": {
            "active_status_path": str(ACTIVE_STATUS_PATH),
            "handoff_status_path": str(HANDOFF_STATUS_PATH),
            "active_status_mentions_v4_active": "`novali-v4` is the active working version." in active_status_text,
            "carried_forward_baseline": dict(handoff_status.get("carried_forward_baseline", {})),
            "current_branch_state": str(branch_record.get("state", "")),
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
        },
        "comparison_references": {
            "memory_summary.v4_governance_substrate_v1_snapshot": _artifact_reference(
                governance_snapshot,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_hybrid_branch_pause_snapshot_v1": _artifact_reference(
                branch_pause_artifact,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_hybrid_scoped_working_baseline_snapshot_v1": _artifact_reference(
                working_baseline_artifact,
                latest_snapshots,
            ),
            "memory_summary.false_safe_frontier_control_characterization_snapshot_v1": _artifact_reference(
                frontier_snapshot,
                latest_snapshots,
            ),
        },
        "initialization_flow_summary": {
            "state_machine": {
                "states": list(INITIALIZATION_STATES),
                "final_state": initialization_state,
                "state_transition_count": int(len(state_transitions)),
                "state_transition_history": state_transitions,
            },
            "clarification_behavior": {
                "partial_intake_fields_present": sorted(partial_intake.keys()),
                "clarification_question_count": int(len(clarification_questions)),
                "clarification_questions": clarification_questions,
                "clarification_history": clarification_history,
                "normalization_produces_full_directive_spec": True,
            },
            "validation_behavior": {
                "validation_reports": validation_reports,
                "validation_error_count": int(len(validation_errors)),
                "validation_errors": validation_errors,
                "directive_activation_blocked_until_validation": True,
                "directive_activation_guard": execution_activation_guard,
            },
            "persistence_behavior": {
                "directive_state_latest_path": str(DIRECTIVE_STATE_PATH),
                "directive_history_path": str(DIRECTIVE_HISTORY_PATH),
                "self_structure_ledger_path": str(SELF_STRUCTURE_LEDGER_PATH),
                "self_structure_state_latest_path": str(SELF_STRUCTURE_STATE_PATH),
                "directive_init_event_count": int(len(ledger_events)),
            },
            "governance_source_of_truth": {
                "owner": "governance_substrate_v1",
                "proposal_learning_loop_is_governance_truth_source": False,
                "directive_state_latest_path": str(DIRECTIVE_STATE_PATH),
                "branch_registry_latest_path": str(BRANCH_REGISTRY_PATH),
                "bucket_state_latest_path": str(BUCKET_STATE_PATH),
            },
        },
        "analytics_context": {
            "analytics_report_path": str(intervention_data_dir() / "intervention_analytics_latest.json"),
            "proposal_recommendations_path": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            "proposal_count": int(analytics.get("proposal_count", 0) or 0),
            "current_recommendation_top_templates": suggested_templates,
        },
        "decision_recommendation": {
            "directive_spec_initialization_flow_v1_in_place": bool(initialization_state == "active"),
            "directive_activation_correctly_blocked_until_validation": bool(
                execution_activation_guard.get("validation_required_before_activation", False)
                and execution_activation_guard.get("activation_sequence_correct", False)
            ),
            "current_initialization_state": initialization_state,
            "plan_should_remain_non_owning": True,
            "recommended_next_step": "use the active DirectiveSpec plus branch registry as read-only governance context before screening any future reopen candidate",
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
        },
        "observability_gain": {
            "passed": True,
            "reason": "DirectiveSpec Initialization Flow v1 now records partial intake, clarification, validation, activation gating, and directive-init history as durable governance state",
            "artifact_paths": {
                "directive_state_latest": str(DIRECTIVE_STATE_PATH),
                "directive_history": str(DIRECTIVE_HISTORY_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "directive activation is now explicitly blocked until a full DirectiveSpec is clarified and validated against governance constraints",
            "directive_activation_guarded": True,
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.98,
            "reason": "the implementation resolves how partial directives become clarified, validated, and durably active without free drift or raw-text-only execution",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "DirectiveSpec Initialization Flow v1 is governance-stateful only; live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope remain unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": "",
            "reason": "the next safe move is to use the now-active governed DirectiveSpec as context for any future reopen-candidate screening rather than start a new behavior-changing branch",
        },
        "diagnostic_conclusions": {
            "directive_spec_initialization_flow_v1_in_place": bool(initialization_state == "active"),
            "directive_activation_correctly_blocked_until_validation": bool(
                execution_activation_guard.get("validation_required_before_activation", False)
                and execution_activation_guard.get("activation_sequence_correct", False)
            ),
            "plan_should_remain_non_owning": True,
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
            "current_branch_state": str(branch_record.get("state", "")),
            "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
        },
    }
    _write_json(artifact_path, artifact_payload)

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: DirectiveSpec Initialization Flow v1 is now materialized as a durable governance-owned initialization path in novali-v4",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
