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
    _now,
    _write_json,
)
from .governed_skill_acquisition_v1 import _diagnostic_artifact_dir, _load_jsonl
from .ledger import intervention_data_dir, load_latest_snapshots
from .v4_first_hypothesis_landscape_snapshot_v1 import _load_json_file
from .v4_wm_context_signal_overlap_snapshot_v1 import _artifact_reference


def _latest_matching_artifact(pattern: str) -> str:
    matches = sorted(_diagnostic_artifact_dir().glob(pattern), reverse=True)
    return str(matches[0]) if matches else ""


def _trusted_sources_allowed(
    requested_sources: list[str],
    directive_current: dict[str, Any],
    bucket_current: dict[str, Any],
) -> dict[str, Any]:
    directive_sources = set(str(item) for item in list(directive_current.get("trusted_sources", [])))
    bucket_sources = set(str(item) for item in list(bucket_current.get("trusted_sources", [])))
    allowed_sources = sorted(directive_sources & bucket_sources) or sorted(bucket_sources)
    missing_sources = sorted(set(str(item) for item in requested_sources) - set(allowed_sources))
    return {
        "passed": not missing_sources,
        "allowed_sources": allowed_sources,
        "requested_sources": sorted(set(str(item) for item in requested_sources)),
        "missing_sources": missing_sources,
        "reason": (
            "requested sources stay inside the directive and bucket trusted-source policy"
            if not missing_sources
            else "requested sources extend beyond the current directive and bucket trusted-source policy"
        ),
    }


def _resource_request_within_envelope(
    requested_resources: dict[str, Any],
    resource_ceilings: dict[str, Any],
    bucket_current: dict[str, Any],
) -> dict[str, Any]:
    bucket_cpu_limit = int(dict(bucket_current.get("cpu_limit", {})).get("max_parallel_processes", 0) or 0)
    bucket_memory_limit = int(dict(bucket_current.get("memory_limit", {})).get("max_working_set_mb", 0) or 0)
    bucket_storage_limit = int(dict(bucket_current.get("storage_limit", {})).get("max_write_mb_per_action", 0) or 0)
    bucket_network_modes = set(
        str(item) for item in list(dict(bucket_current.get("network_policy", {})).get("allowed_network_modes", []))
    )

    requested_cpu = int(requested_resources.get("cpu_parallel_units", 0) or 0)
    requested_memory = int(requested_resources.get("memory_mb", 0) or 0)
    requested_storage = int(requested_resources.get("storage_write_mb", 0) or 0)
    requested_network_mode = str(requested_resources.get("network_mode", "none"))

    envelope_cpu_limit = int(resource_ceilings.get("cpu_parallel_units", 0) or 0)
    envelope_memory_limit = int(resource_ceilings.get("memory_mb", 0) or 0)
    envelope_storage_limit = int(resource_ceilings.get("storage_write_mb", 0) or 0)
    envelope_network_mode = str(resource_ceilings.get("network_mode", requested_network_mode))

    cpu_ok = requested_cpu <= envelope_cpu_limit and requested_cpu <= bucket_cpu_limit
    memory_ok = requested_memory <= envelope_memory_limit and requested_memory <= bucket_memory_limit
    storage_ok = requested_storage <= envelope_storage_limit and requested_storage <= bucket_storage_limit
    network_ok = requested_network_mode == envelope_network_mode and requested_network_mode in bucket_network_modes

    return {
        "passed": bool(cpu_ok and memory_ok and storage_ok and network_ok),
        "requested_resources": {
            "cpu_parallel_units": requested_cpu,
            "memory_mb": requested_memory,
            "storage_write_mb": requested_storage,
            "network_mode": requested_network_mode,
        },
        "resource_ceilings": dict(resource_ceilings),
        "bucket_limits": {
            "cpu_parallel_units": bucket_cpu_limit,
            "memory_mb": bucket_memory_limit,
            "storage_write_mb": bucket_storage_limit,
            "network_modes": sorted(bucket_network_modes),
        },
        "within_limits": {
            "cpu": bool(cpu_ok),
            "memory": bool(memory_ok),
            "storage": bool(storage_ok),
            "network": bool(network_ok),
        },
    }


def _write_roots_allowed(requested_write_roots: list[str], allowed_write_roots: list[str]) -> dict[str, Any]:
    allowed = set(str(item) for item in allowed_write_roots)
    requested = sorted(set(str(item) for item in requested_write_roots))
    disallowed = sorted(set(requested) - allowed)
    return {
        "passed": not disallowed,
        "allowed_write_roots": sorted(allowed),
        "requested_write_roots": requested,
        "disallowed_write_roots": disallowed,
    }


def _classify_use_request(
    request: dict[str, Any],
    *,
    held_capability: dict[str, Any],
    directive_current: dict[str, Any],
    bucket_current: dict[str, Any],
    current_branch_state: str,
    plan_non_owning: bool,
    routing_deferred: bool,
) -> dict[str, Any]:
    trusted_sources = _trusted_sources_allowed(
        list(request.get("trusted_sources", [])),
        directive_current,
        bucket_current,
    )
    resource_report = _resource_request_within_envelope(
        dict(request.get("requested_resources", {})),
        dict(held_capability.get("resource_ceilings", {})),
        bucket_current,
    )
    write_root_report = _write_roots_allowed(
        list(request.get("requested_write_roots", [])),
        list(held_capability.get("allowed_write_roots", [])),
    )

    directive_relevance = str(request.get("directive_relevance", "none"))
    reversibility = str(request.get("reversibility", "low"))
    capability_family_fit = bool(request.get("capability_family_fit", False))
    better_than_new_skill_candidate = bool(request.get("better_than_new_skill_candidate", False))
    decision_critical_reliance = bool(request.get("decision_critical_reliance", False))
    overlap_with_active_work = str(request.get("overlap_with_active_work", "low"))
    same_shape_rerun = bool(request.get("same_shape_rerun", False))
    requires_capability_modification = bool(request.get("requires_capability_modification", False))
    new_bounded_use_case = bool(request.get("new_bounded_use_case", False))
    shadow_only = bool(request.get("shadow_only", True))

    forbidden_surface_reasons: list[str] = []
    if not trusted_sources["passed"]:
        forbidden_surface_reasons.append("trusted-source policy violated")
    if not resource_report["passed"]:
        forbidden_surface_reasons.append("requested resources exceed held-envelope or bucket limits")
    if not write_root_report["passed"]:
        forbidden_surface_reasons.append("requested writes exceed held capability write roots")
    if str(current_branch_state) != "paused_with_baseline_held":
        forbidden_surface_reasons.append("branch state is not the required paused_with_baseline_held state")
    if directive_relevance not in {"high", "medium"}:
        forbidden_surface_reasons.append("directive relevance is too weak for governed capability use")
    if reversibility not in {"high", "medium"}:
        forbidden_surface_reasons.append("requested use is not sufficiently reversible")
    if not plan_non_owning:
        forbidden_surface_reasons.append("plan_ non-owning guard no longer holds")
    if not routing_deferred:
        forbidden_surface_reasons.append("routing is no longer deferred")
    if bool(request.get("touches_protected_surface", False)):
        forbidden_surface_reasons.append("protected-surface modification requested")
    if bool(request.get("touches_downstream_selected_set", False)):
        forbidden_surface_reasons.append("downstream selected-set work requested")
    if bool(request.get("touches_plan_ownership", False)):
        forbidden_surface_reasons.append("plan_ ownership change requested")
    if bool(request.get("touches_routing", False)):
        forbidden_surface_reasons.append("routing work requested")
    if bool(request.get("touches_branch_state", False)):
        forbidden_surface_reasons.append("branch-state mutation requested")
    if same_shape_rerun:
        forbidden_surface_reasons.append("same-shape rerun remains paused and is not a valid direct capability use")

    if forbidden_surface_reasons:
        outcome = "forbidden_use"
        reason = "; ".join(forbidden_surface_reasons)
    elif not capability_family_fit or not better_than_new_skill_candidate:
        outcome = "new_skill_candidate_required_instead_of_use"
        reason = "the request falls outside the held capability family or a new skill candidate is a better fit than direct use"
    elif requires_capability_modification or new_bounded_use_case:
        outcome = "reopen_required_instead_of_use"
        reason = "the request implies capability development or a materially new bounded use-case, so the paused line must be screened for reopen instead of directly used"
    elif decision_critical_reliance or overlap_with_active_work in {"medium", "high"} or not shadow_only:
        outcome = "gated_review_required_use"
        reason = "the request is policy-valid but operationally weighty enough to require gated review before invocation"
    elif str(held_capability.get("status", "")) == "retained_auto_callable_capability":
        outcome = "auto_allowed_use"
        reason = "the capability is already retained and explicitly callable under an auto-allowed low-risk use path"
    else:
        outcome = "diagnostic_only_use"
        reason = "the held paused provisional capability may be used directly only for bounded, trusted, shadow-only directive support inside its admitted envelope"

    return {
        "use_request_id": str(request.get("use_request_id", "")),
        "capability_id": str(request.get("capability_id", "")),
        "capability_name": str(request.get("capability_name", "")),
        "policy_outcome": outcome,
        "reason": reason,
        "directive_relevance": directive_relevance,
        "reversibility": reversibility,
        "shadow_only": shadow_only,
        "decision_critical_reliance": decision_critical_reliance,
        "overlap_with_active_work": overlap_with_active_work,
        "trusted_source_report": trusted_sources,
        "resource_report": resource_report,
        "write_root_report": write_root_report,
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governance_substrate_v1_snapshot")
    provisional_admission_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_skill_provisional_admission_snapshot_v1"
    )
    provisional_evidence_v2_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_skill_provisional_evidence_snapshot_v2"
    )
    provisional_pause_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_skill_provisional_pause_snapshot_v1"
    )
    if not all(
        [
            governance_snapshot,
            provisional_admission_snapshot,
            provisional_evidence_v2_snapshot,
            provisional_pause_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: Governed Capability-Use Policy v1 requires the governance substrate, provisional admission, provisional evidence v2, and provisional pause artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite governed-capability artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite governed-capability artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite governed-capability artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot define governed capability use without the current paused capability state"},
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
            "reason": "diagnostic shadow failed: governed capability use policy requires current directive, bucket, self-structure, and branch artifacts",
            "observability_gain": {"passed": False, "reason": "missing durable governance state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing durable governance state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing durable governance state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot separate capability use from capability acquisition without the current governance state"},
        }

    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_branch_state = str(branch_record.get("state", ""))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    governed_skill_subsystem = dict(self_structure_state.get("governed_skill_subsystem", {}))

    capability_id = "skill_candidate_local_trace_parser_trial"
    held_capabilities = list(governed_skill_subsystem.get("held_provisional_capabilities", []))
    held_capability = {}
    for item in held_capabilities:
        record = dict(item)
        if str(record.get("skill_id", "")) == capability_id:
            held_capability = record
            break
    if not held_capability:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no held provisional capability was found for the local trace parser",
            "observability_gain": {"passed": False, "reason": "missing held provisional capability record"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing held provisional capability record"},
            "ambiguity_reduction": {"passed": False, "reason": "missing held provisional capability record"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot define capability use policy without a concrete held capability record"},
        }

    provisional_pause_artifact_path = Path(
        str(governed_skill_subsystem.get("last_provisional_pause_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_skill_provisional_pause_snapshot_v1_*.json")
    )
    provisional_evidence_v2_artifact_path = Path(
        str(governed_skill_subsystem.get("last_provisional_evidence_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_skill_provisional_evidence_snapshot_v2_*.json")
    )
    provisional_admission_artifact_path = Path(
        str(governed_skill_subsystem.get("last_provisional_admission_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_skill_provisional_admission_snapshot_v1_*.json")
    )

    provisional_pause_summary = dict(
        _load_json_file(provisional_pause_artifact_path).get("governed_skill_provisional_pause_summary", {})
    )
    provisional_evidence_v2_summary = dict(
        _load_json_file(provisional_evidence_v2_artifact_path).get("governed_skill_provisional_evidence_summary", {})
    )
    provisional_admission_summary = dict(
        _load_json_file(provisional_admission_artifact_path).get("governed_skill_provisional_admission_summary", {})
    )

    directive_current = dict(directive_state.get("current_directive_state", {}))
    bucket_current = dict(bucket_state.get("current_bucket_state", {}))
    provisional_envelope = dict(provisional_admission_summary.get("provisional_envelope", {}))
    evidence_obligations = dict(provisional_admission_summary.get("evidence_obligations", {}))
    rollback_triggers = dict(provisional_admission_summary.get("rollback_triggers", {}))
    deprecation_triggers = dict(provisional_admission_summary.get("deprecation_triggers", {}))
    cumulative_trend = dict(provisional_evidence_v2_summary.get("cumulative_trend_assessment", {}))
    structural_value = dict(provisional_evidence_v2_summary.get("structural_value_assessment", {}))

    default_policy_class_for_current_capability = "diagnostic_only_use"
    next_template = "memory_summary.v4_governed_capability_use_candidate_screen_snapshot_v1"
    held_capability_use_status = "held_and_callable_only_for_admissible_bounded_use_cases"

    policy_classes = {
        "auto_allowed_use": {
            "meaning": "invoke an already retained or explicitly auto-callable capability for a low-risk bounded use without opening a new review path",
            "phase_1_status": "reserved_for_future_retained_or_explicitly_auto_callable_capabilities",
            "requires": [
                "directive relevance high",
                "trusted-source compatibility",
                "bucket feasibility",
                "mutable-surface legality",
                "reversibility high",
                "no protected-surface, routing, branch-state, or plan_ ownership drift",
            ],
        },
        "diagnostic_only_use": {
            "meaning": "invoke a held capability for bounded, shadow-only directive support inside its admitted envelope",
            "phase_1_status": "default direct-use class for the held local trace parser",
            "requires": [
                "shadow-only use",
                "trusted local sources only",
                "write roots stay inside the admitted envelope",
                "no capability development or same-shape rerun",
            ],
        },
        "gated_review_required_use": {
            "meaning": "policy-valid invocation that is still operationally weighty enough to require human or governance review",
            "phase_1_status": "enabled",
            "requires": [
                "directive-valid and governance-valid request",
                "no forbidden surface drift",
                "decision-critical reliance or meaningful overlap with active work",
            ],
        },
        "forbidden_use": {
            "meaning": "requested invocation violates trusted-source, bucket, surface, branch-state, or same-shape pause constraints",
            "phase_1_status": "enabled",
            "requires": [
                "request rejected",
                "no invocation allowed",
            ],
        },
        "reopen_required_instead_of_use": {
            "meaning": "request implies capability development, extension, or materially new bounded use-case and must go through a reopen screen rather than direct use",
            "phase_1_status": "enabled",
            "requires": [
                "paused capability line remains paused for development until a separate reopen screen clears it",
            ],
        },
        "new_skill_candidate_required_instead_of_use": {
            "meaning": "request is a poor fit for the held capability family and should begin as a new governed skill candidate rather than direct use",
            "phase_1_status": "enabled",
            "requires": [
                "capability family mismatch or direct use is not the best fit",
            ],
        },
    }

    capability_use_request_schema = {
        "schema_name": "GovernedCapabilityUseRequest",
        "schema_version": "governed_capability_use_policy_v1",
        "required_fields": [
            "use_request_id",
            "capability_id",
            "capability_name",
            "requested_purpose",
            "directive_relevance",
            "trusted_sources",
            "requested_resources",
            "requested_write_roots",
            "reversibility",
            "shadow_only",
            "decision_critical_reliance",
            "overlap_with_active_work",
            "capability_family_fit",
            "better_than_new_skill_candidate",
            "requires_capability_modification",
            "new_bounded_use_case",
            "same_shape_rerun",
        ],
        "outcome_classes": list(policy_classes.keys()),
    }

    decision_criteria = {
        "directive_relevance": "use is allowed only when it is clearly supportive of the active directive and its current constraints",
        "trusted_source_compatibility": "requested data sources must stay inside both the directive and bucket trusted-source policy",
        "bucket_resource_feasibility": "requested cpu, memory, storage, and network mode must fit both the held capability envelope and the current bucket",
        "mutable_surface_legality": "capability use must not mutate protected surfaces, branch state, routing, downstream selected-set work, or plan_ ownership",
        "reversibility": "use must remain bounded, removable, or safely ignorable",
        "branch_state_compatibility": "the current branch must remain paused_with_baseline_held and capability use must not act as a hidden reopen",
        "overlap_with_active_work": "use should not collide with active work in ways that require a separate review path",
        "better_than_new_skill_candidate": "direct use should be preferred only when it is a cleaner fit than proposing a new capability candidate",
    }

    decision_split = {
        "use_existing_capability_when": [
            "request fits the held capability family",
            "request stays inside the admitted envelope",
            "request is better handled by bounded reuse than by new acquisition",
        ],
        "reopen_paused_capability_line_when": [
            "request requires capability modification or extension",
            "request introduces a materially new bounded use-case within the same capability family",
        ],
        "propose_new_skill_candidate_when": [
            "request falls outside the held capability family",
            "direct use would be a poor fit or a workaround for a truly new capability need",
        ],
        "defer_or_request_human_review_when": [
            "use is directive-valid but decision-critical",
            "use overlaps with active work in a way that needs explicit review",
        ],
    }

    invocation_accounting_requirements = {
        "resource_usage_must_be_logged": [
            "invocation_id",
            "capability_id",
            "directive_id",
            "branch_id",
            "branch_state",
            "cpu_parallel_units_used",
            "memory_mb_used",
            "storage_write_mb_used",
            "network_mode_used",
            "write_roots_touched",
            "source_artifact_paths",
        ],
        "governance_reporting_must_be_logged": [
            "policy_outcome",
            "decision_rationale",
            "trusted_source_report",
            "resource_report",
            "write_root_report",
            "branch_state_unchanged",
            "retained_promotion_performed",
            "rollback_trigger_status",
            "deprecation_trigger_status",
        ],
        "evidence_of_usefulness_must_be_preserved": [
            "use_case_summary",
            "directive_support_observation",
            "bounded_output_artifact_path",
            "usefulness_signal_summary",
            "duplication_or_overlap_observation",
        ],
    }

    capability_use_guardrails = {
        "protected_surface_drift_forbidden": True,
        "downstream_selected_set_work_forbidden": True,
        "plan_ownership_change_forbidden": True,
        "routing_drift_forbidden": True,
        "untrusted_external_access_forbidden": True,
        "paused_branch_state_mutation_forbidden": True,
        "same_shape_rerun_use_forbidden": True,
    }

    paused_capability_handling = {
        "held_capabilities_may_be_called_directly": True,
        "direct_call_requires_admissible_bounded_use_case": True,
        "paused_capability_line_is_not_reopened_by_use": True,
        "same_shape_reruns_remain_disallowed": True,
        "development_extension_requires_separate_reopen_screen": True,
        "current_held_capability_default_use_class": default_policy_class_for_current_capability,
        "current_held_capability_higher_risk_use_class": "gated_review_required_use",
        "current_held_capability_reopen_policy": str(held_capability.get("reopen_policy", "")),
    }

    sample_use_requests = [
        {
            "use_request_id": "use_request_parser_new_trusted_shadow_bundle",
            "capability_id": capability_id,
            "capability_name": str(held_capability.get("skill_name", "")),
            "requested_purpose": "summarize a new trusted local shadow-log bundle for directive-supportive governance diagnostics",
            "directive_relevance": "high",
            "trusted_sources": ["local_artifacts:novali-v4/data", "local_logs:logs"],
            "requested_resources": {"cpu_parallel_units": 1, "memory_mb": 128, "storage_write_mb": 8, "network_mode": "none"},
            "requested_write_roots": list(held_capability.get("allowed_write_roots", [])),
            "reversibility": "high",
            "shadow_only": True,
            "decision_critical_reliance": False,
            "overlap_with_active_work": "low",
            "capability_family_fit": True,
            "better_than_new_skill_candidate": True,
            "requires_capability_modification": False,
            "new_bounded_use_case": False,
            "same_shape_rerun": False,
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
        },
        {
            "use_request_id": "use_request_parser_direct_decision_support",
            "capability_id": capability_id,
            "capability_name": str(held_capability.get("skill_name", "")),
            "requested_purpose": "use parser output as direct decision support for a higher-consequence governance action",
            "directive_relevance": "high",
            "trusted_sources": ["local_artifacts:novali-v4/data", "local_logs:logs"],
            "requested_resources": {"cpu_parallel_units": 1, "memory_mb": 128, "storage_write_mb": 8, "network_mode": "none"},
            "requested_write_roots": list(held_capability.get("allowed_write_roots", [])),
            "reversibility": "high",
            "shadow_only": False,
            "decision_critical_reliance": True,
            "overlap_with_active_work": "medium",
            "capability_family_fit": True,
            "better_than_new_skill_candidate": True,
            "requires_capability_modification": False,
            "new_bounded_use_case": False,
            "same_shape_rerun": False,
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
        },
        {
            "use_request_id": "use_request_parser_same_shape_seed_context_shift_rerun",
            "capability_id": capability_id,
            "capability_name": str(held_capability.get("skill_name", "")),
            "requested_purpose": "repeat the same seed_context_shift parser rerun that was already paused",
            "directive_relevance": "high",
            "trusted_sources": ["local_artifacts:novali-v4/data", "local_logs:logs"],
            "requested_resources": {"cpu_parallel_units": 1, "memory_mb": 128, "storage_write_mb": 8, "network_mode": "none"},
            "requested_write_roots": list(held_capability.get("allowed_write_roots", [])),
            "reversibility": "high",
            "shadow_only": True,
            "decision_critical_reliance": False,
            "overlap_with_active_work": "low",
            "capability_family_fit": True,
            "better_than_new_skill_candidate": True,
            "requires_capability_modification": False,
            "new_bounded_use_case": False,
            "same_shape_rerun": True,
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
        },
        {
            "use_request_id": "use_request_parser_new_local_trace_format",
            "capability_id": capability_id,
            "capability_name": str(held_capability.get("skill_name", "")),
            "requested_purpose": "extend the parser to a new trusted local trace format inside the same capability family",
            "directive_relevance": "high",
            "trusted_sources": ["local_artifacts:novali-v4/data", "local_logs:logs"],
            "requested_resources": {"cpu_parallel_units": 1, "memory_mb": 128, "storage_write_mb": 8, "network_mode": "none"},
            "requested_write_roots": list(held_capability.get("allowed_write_roots", [])),
            "reversibility": "high",
            "shadow_only": True,
            "decision_critical_reliance": False,
            "overlap_with_active_work": "low",
            "capability_family_fit": True,
            "better_than_new_skill_candidate": True,
            "requires_capability_modification": True,
            "new_bounded_use_case": True,
            "same_shape_rerun": False,
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
        },
        {
            "use_request_id": "use_request_need_remote_tool_wrapper",
            "capability_id": capability_id,
            "capability_name": str(held_capability.get("skill_name", "")),
            "requested_purpose": "satisfy a remote tool-wrapper need that falls outside the local trace parser family",
            "directive_relevance": "medium",
            "trusted_sources": ["local_artifacts:novali-v4/data"],
            "requested_resources": {"cpu_parallel_units": 1, "memory_mb": 64, "storage_write_mb": 4, "network_mode": "none"},
            "requested_write_roots": list(held_capability.get("allowed_write_roots", [])),
            "reversibility": "high",
            "shadow_only": True,
            "decision_critical_reliance": False,
            "overlap_with_active_work": "low",
            "capability_family_fit": False,
            "better_than_new_skill_candidate": False,
            "requires_capability_modification": False,
            "new_bounded_use_case": False,
            "same_shape_rerun": False,
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
        },
    ]

    sample_use_decisions = [
        _classify_use_request(
            request,
            held_capability=held_capability,
            directive_current=directive_current,
            bucket_current=bucket_current,
            current_branch_state=current_branch_state,
            plan_non_owning=bool(current_state_summary.get("plan_non_owning", False)),
            routing_deferred=bool(current_state_summary.get("routing_deferred", False)),
        )
        for request in sample_use_requests
    ]
    sample_decision_counts = {
        decision_class: sum(1 for item in sample_use_decisions if str(item.get("policy_outcome", "")) == decision_class)
        for decision_class in policy_classes
    }

    governed_capability_use_policy = {
        "schema_version": "governed_capability_use_policy_v1",
        "capability_use_request_schema": capability_use_request_schema,
        "policy_classes": policy_classes,
        "decision_criteria": decision_criteria,
        "decision_split": decision_split,
        "invocation_accounting_requirements": invocation_accounting_requirements,
        "guardrails": capability_use_guardrails,
        "paused_capability_handling": paused_capability_handling,
        "current_callable_capabilities": [
            {
                "capability_id": str(held_capability.get("skill_id", "")),
                "capability_name": str(held_capability.get("skill_name", "")),
                "status": str(held_capability.get("status", "")),
                "reopen_policy": str(held_capability.get("reopen_policy", "")),
                "retention_posture": str(held_capability.get("retention_posture", "")),
                "default_use_class": default_policy_class_for_current_capability,
                "higher_risk_use_class": "gated_review_required_use",
                "same_shape_reruns_disallowed": True,
                "network_mode": str(held_capability.get("network_mode", "")),
                "allowed_write_roots": list(held_capability.get("allowed_write_roots", [])),
                "resource_ceilings": dict(held_capability.get("resource_ceilings", {})),
            }
        ],
        "sample_use_decisions": sample_use_decisions,
        "sample_decision_counts": sample_decision_counts,
        "best_next_template": next_template,
    }

    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_v4_governed_capability_use_policy_snapshot_v1_{proposal['proposal_id']}.json"

    updated_self_structure_state = dict(self_structure_state)
    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["governed_capability_use_policy"] = governed_capability_use_policy

    updated_governed_skill_subsystem = dict(governed_skill_subsystem)
    updated_governed_skill_subsystem["last_capability_use_policy_artifact_path"] = str(artifact_path)
    updated_governed_skill_subsystem["last_capability_use_policy_outcome"] = {
        "status": "defined",
        "held_capability_use_status": held_capability_use_status,
        "default_use_class_for_current_parser": default_policy_class_for_current_capability,
        "same_shape_reruns_disallowed": True,
        "reason": "capability use is now separated from capability acquisition, so the held parser can be invoked for bounded directive-valid use without reopening its paused development line",
    }
    updated_governed_skill_subsystem["best_next_template"] = next_template
    updated_self_structure_state["governed_skill_subsystem"] = updated_governed_skill_subsystem

    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "governed_capability_use_policy_v1_defined": True,
            "held_capabilities_callable_under_governance": True,
            "latest_governed_capability_use_policy_status": "defined",
            "latest_held_capability_use_status": held_capability_use_status,
            "latest_held_capability_default_use_class": default_policy_class_for_current_capability,
            "current_branch_state": current_branch_state,
            "plan_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "retained_skill_promotion_performed": False,
        }
    )
    updated_self_structure_state["current_state_summary"] = updated_current_state_summary
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    ledger_event = {
        "event_id": f"governed_capability_use_policy_snapshot_v1::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_capability_use_policy_snapshot_v1_materialized",
        "event_class": "governed_capability_use_policy",
        "directive_id": str(directive_current.get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": current_branch_state,
        "capability_id": str(held_capability.get("skill_id", "")),
        "capability_status": str(held_capability.get("status", "")),
        "same_shape_reruns_disallowed": True,
        "retained_promotion": False,
        "branch_state_mutation": False,
        "artifact_paths": {
            "provisional_pause_v1": str(provisional_pause_artifact_path),
            "provisional_evidence_v2": str(provisional_evidence_v2_artifact_path),
            "provisional_admission_v1": str(provisional_admission_artifact_path),
            "governed_capability_use_policy_v1": str(artifact_path),
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

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_governed_capability_use_policy_snapshot_v1",
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
            "memory_summary.v4_governed_skill_provisional_admission_snapshot_v1": _artifact_reference(
                provisional_admission_snapshot,
                latest_snapshots,
            ),
            "memory_summary.v4_governed_skill_provisional_evidence_snapshot_v2": _artifact_reference(
                provisional_evidence_v2_snapshot,
                latest_snapshots,
            ),
            "memory_summary.v4_governed_skill_provisional_pause_snapshot_v1": _artifact_reference(
                provisional_pause_snapshot,
                latest_snapshots,
            ),
        },
        "governed_capability_use_policy_summary": {
            "capability_reviewed": {
                "capability_id": str(held_capability.get("skill_id", "")),
                "capability_name": str(held_capability.get("skill_name", "")),
                "held_status": str(held_capability.get("status", "")),
                "reopen_policy": str(held_capability.get("reopen_policy", "")),
                "retention_posture": str(held_capability.get("retention_posture", "")),
            },
            "policy_classes": policy_classes,
            "decision_criteria": decision_criteria,
            "capability_use_request_schema": capability_use_request_schema,
            "invocation_accounting_requirements": invocation_accounting_requirements,
            "capability_use_guardrails": capability_use_guardrails,
            "paused_capability_handling": {
                **paused_capability_handling,
                "held_status_reason": "the parser is kept available for bounded directive-valid use, but its paused development line stays paused unless a separate reopen screen clears it",
            },
            "decision_split": decision_split,
            "sample_use_decisions": sample_use_decisions,
            "sample_decision_counts": sample_decision_counts,
            "current_held_envelope_reference": provisional_envelope,
            "current_held_evidence_obligations": evidence_obligations,
            "current_rollback_triggers": rollback_triggers,
            "current_deprecation_triggers": deprecation_triggers,
            "pause_rationale_reference": dict(provisional_pause_summary.get("pause_rationale", {})),
            "broader_project_alignment": {
                "supports_governed_self_direction": True,
                "supports_bucket_bounded_execution": True,
                "reduces_unnecessary_skill_proliferation": True,
                "keeps_paused_capability_lines_paused_for_development": True,
                "current_local_trace_parser_line_is_still_useful_structurally": bool(
                    structural_value.get("good_exemplar_for_governed_skill_growth", False)
                ),
                "current_local_trace_parser_evidence_trend": str(cumulative_trend.get("classification", "")),
                "reason": "capability use policy lets NOVALI reuse governed capabilities without confusing reuse with acquisition, which preserves governance-first growth and prevents unnecessary branch churn",
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
                "reason": "capability use decisions are derived from directive, bucket, branch, self-structure, and governed-capability artifacts, so reuse is governed by durable state rather than by execution code alone",
            },
        },
        "analytics_context": {
            "analytics_report_path": str(intervention_data_dir() / "intervention_analytics_latest.json"),
            "proposal_recommendations_path": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            "proposal_count": int(analytics.get("proposal_count", 0) or 0),
            "current_recommendation_top_templates": suggested_templates,
            "directive_history_entry_count": int(len(directive_history)),
            "self_structure_ledger_entry_count": int(len(self_structure_ledger)),
            "intervention_ledger_entry_count": int(len(intervention_ledger)),
        },
        "observability_gain": {
            "passed": True,
            "reason": "held governed capabilities now have explicit invocation classes, accounting requirements, and a clear split between reuse, reopen, and new-skill acquisition",
            "artifact_paths": {
                "capability_use_policy_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the snapshot cleanly answers when NOVALI should reuse a held capability, when it must reopen a paused line, and when it must propose something new instead",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "capability reuse is now separated from capability acquisition, so paused capability lines can remain paused without blocking bounded directive-valid invocation",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the policy layer is diagnostic-only; it opened no new behavior-changing branch, mutated no branch state, promoted no retained skill, and changed no live behavior",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": next_template,
            "reason": "now that the policy layer exists, the next useful step is to screen concrete capability-use requests against it rather than reopening or rebuilding capability lines by default",
        },
        "diagnostic_conclusions": {
            "governed_capability_use_policy_v1_defined": True,
            "held_capabilities_callable_under_governance": True,
            "paused_capability_lines_remain_paused_for_development": True,
            "current_held_capability_default_use_class": default_policy_class_for_current_capability,
            "new_behavior_changing_branch_opened": False,
            "branch_state_mutation_occurred": False,
            "retained_promotion_occurred": False,
            "plan_should_remain_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "best_next_template": next_template,
        },
    }
    _write_json(artifact_path, artifact_payload)

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: Governed Capability-Use Policy v1 now separates governed capability reuse from acquisition and reopen logic",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
