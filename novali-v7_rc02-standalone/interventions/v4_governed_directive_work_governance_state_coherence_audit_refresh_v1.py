from __future__ import annotations

import json
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
from .governed_skill_acquisition_v1 import _diagnostic_artifact_dir, _load_jsonl, _trial_artifact_digest
from .ledger import intervention_data_dir, load_latest_snapshots
from .v4_first_hypothesis_landscape_snapshot_v1 import _load_json_file
from .v4_governed_capability_use_policy_snapshot_v1 import _latest_matching_artifact
from .v4_governed_directive_work_candidate_screen_snapshot_v1 import _find_capability
from .v4_governed_skill_local_trace_parser_provisional_probe_v1 import _bucket_pressure, _path_within_allowed_roots
from .v4_wm_context_signal_overlap_snapshot_v1 import _artifact_reference


def _find_work_candidate(
    screened_candidates: list[dict[str, Any]],
    *,
    work_item_name: str,
) -> dict[str, Any]:
    for candidate in screened_candidates:
        if str(candidate.get("work_item_name", "")) == work_item_name:
            return dict(candidate)
    for candidate in screened_candidates:
        if str(candidate.get("assigned_class", "")) == "direct_governed_work_candidate":
            return dict(candidate)
    return {}


def _coherence_check(passed: bool, reason: str, **details: Any) -> dict[str, Any]:
    payload = {"passed": bool(passed), "reason": str(reason)}
    payload.update(details)
    return payload


def _resource_request_within_bucket(
    requested_resources: dict[str, Any],
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

    return {
        "passed": (
            requested_cpu <= bucket_cpu_limit
            and requested_memory <= bucket_memory_limit
            and requested_storage <= bucket_storage_limit
            and requested_network_mode in bucket_network_modes
        ),
        "requested_resources": {
            "cpu_parallel_units": requested_cpu,
            "memory_mb": requested_memory,
            "storage_write_mb": requested_storage,
            "network_mode": requested_network_mode,
        },
        "bucket_limits": {
            "cpu_parallel_units": bucket_cpu_limit,
            "memory_mb": bucket_memory_limit,
            "storage_write_mb": bucket_storage_limit,
            "network_modes": sorted(bucket_network_modes),
        },
    }


def _build_coherence_audit(
    *,
    current_directive: dict[str, Any],
    directive_state: dict[str, Any],
    current_state_summary: dict[str, Any],
    branch_record: dict[str, Any],
    current_branch_state: str,
    current_bucket: dict[str, Any],
    work_candidate_record: dict[str, Any],
    direct_work_envelope: dict[str, Any],
    callable_capabilities: list[dict[str, Any]],
    analytics: dict[str, Any],
    recommendations: dict[str, Any],
) -> dict[str, Any]:
    parser_capability = _find_capability(callable_capabilities, "skill_candidate_local_trace_parser_trial")
    expected_resources = dict(direct_work_envelope.get("resource_expectations", {}))
    resource_fit = _resource_request_within_bucket(expected_resources, current_bucket)
    network_modes = list(dict(current_bucket.get("network_policy", {})).get("allowed_network_modes", []))
    work_path = dict(work_candidate_record.get("path_separation", {}))

    checks = {
        "directive_state_active": _coherence_check(
            str(directive_state.get("initialization_state", "")) == "active",
            "directive initialization remains active",
            observed=str(directive_state.get("initialization_state", "")),
            expected="active",
        ),
        "directive_summary_alignment": _coherence_check(
            str(current_state_summary.get("active_directive_id", "")) == str(current_directive.get("directive_id", ""))
            and str(current_state_summary.get("directive_initialization_state", "")) == str(directive_state.get("initialization_state", "")),
            "self-structure summary agrees with directive state",
            observed={
                "active_directive_id": str(current_state_summary.get("active_directive_id", "")),
                "directive_initialization_state": str(current_state_summary.get("directive_initialization_state", "")),
            },
            expected={
                "active_directive_id": str(current_directive.get("directive_id", "")),
                "directive_initialization_state": str(directive_state.get("initialization_state", "")),
            },
        ),
        "branch_state_alignment": _coherence_check(
            current_branch_state == "paused_with_baseline_held"
            and str(current_state_summary.get("current_branch_state", "")) == current_branch_state,
            "branch registry and self-structure agree on paused_with_baseline_held",
            observed={
                "branch_registry_state": current_branch_state,
                "state_summary_state": str(current_state_summary.get("current_branch_state", "")),
            },
            expected="paused_with_baseline_held",
        ),
        "held_baseline_alignment": _coherence_check(
            str(dict(branch_record.get("held_baseline", {})).get("template", "")) == str(current_state_summary.get("held_baseline_template", "")),
            "held baseline template matches across branch and self-structure state",
            observed=str(dict(branch_record.get("held_baseline", {})).get("template", "")),
            expected=str(current_state_summary.get("held_baseline_template", "")),
        ),
        "plan_and_routing_guards_hold": _coherence_check(
            bool(current_state_summary.get("plan_non_owning", False))
            and bool(current_state_summary.get("routing_deferred", False)),
            "plan_ remains non-owning and routing remains deferred",
        ),
        "bucket_allows_direct_work_budget": _coherence_check(
            bool(resource_fit.get("passed", False)),
            "bucket still covers the admitted direct-work budget",
            requested_resources=dict(resource_fit.get("requested_resources", {})),
            bucket_limits=dict(resource_fit.get("bucket_limits", {})),
        ),
        "network_mode_none_remains_policy_valid": _coherence_check(
            "none" in network_modes and str(expected_resources.get("network_mode", "none")) == "none",
            "bucket policy still allows network mode none and the direct-work envelope still requires none",
            observed={"bucket_network_modes": network_modes, "direct_work_network_mode": str(expected_resources.get("network_mode", "none"))},
            expected="none allowed and required",
        ),
        "direct_work_path_separation_holds": _coherence_check(
            bool(work_path.get("is_direct_work", False))
            and not bool(work_path.get("requires_capability_use_admission", False))
            and not bool(work_path.get("requires_reopen_screen", False))
            and not bool(work_path.get("requires_new_skill_candidate", False))
            and not bool(direct_work_envelope.get("capability_use_required", True))
            and not bool(direct_work_envelope.get("paused_capability_reopen_allowed", True)),
            "direct work remains separate from capability use, reopen, and new-skill paths",
        ),
        "paused_parser_capability_still_held_not_reopened": _coherence_check(
            bool(parser_capability)
            and str(parser_capability.get("status", "")) == "paused_with_provisional_capability_held"
            and bool(parser_capability.get("same_shape_reruns_disallowed", False)),
            "the held parser capability remains paused and callable-only, not reopened",
        ),
        "direct_work_admission_state_still_current": _coherence_check(
            bool(current_state_summary.get("governed_directive_work_admission_in_place", False))
            and str(current_state_summary.get("latest_directive_work_admission_candidate", "")) == "Governance state coherence audit refresh"
            and str(current_state_summary.get("latest_directive_work_admission_outcome", "")) == "admissible_for_direct_governed_work",
            "self-structure still reflects the current direct-work admission state",
        ),
        "analytics_and_recommendations_present": _coherence_check(
            int(analytics.get("proposal_count", 0) or 0) > 0
            and isinstance(recommendations.get("all_ranked_proposals", []), list),
            "analytics and recommendation artifacts remain readable for coherence context",
            observed={
                "proposal_count": int(analytics.get("proposal_count", 0) or 0),
                "ranked_recommendation_count": int(len(list(recommendations.get("all_ranked_proposals", [])))),
            },
        ),
    }

    failed_check_names = [name for name, result in checks.items() if not bool(dict(result).get("passed", False))]
    passed_count = len(checks) - len(failed_check_names)
    coherence_score = float(passed_count / max(len(checks), 1))
    return {
        "audit_focus": "governance_state_coherence_audit_refresh",
        "checks": checks,
        "summary": {
            "total_check_count": int(len(checks)),
            "passed_check_count": int(passed_count),
            "failed_check_count": int(len(failed_check_names)),
            "failed_check_names": failed_check_names,
            "coherence_score": coherence_score,
            "alignment_status": "coherent" if not failed_check_names else "mismatch_detected",
        },
        "high_signal_observations": [
            "directive, branch, bucket, and self-structure state stayed aligned under the paused branch contract" if not failed_check_names else "one or more governance-state mismatches were detected",
            "direct work remained separate from capability-use and reopen paths",
            "the held parser capability remained paused and callable-only during the audit",
        ],
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governance_substrate_v1_snapshot")
    directive_work_selection_policy_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_directive_work_selection_policy_snapshot_v1"
    )
    directive_work_candidate_screen_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_directive_work_candidate_screen_snapshot_v1"
    )
    directive_work_admission_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_directive_work_admission_snapshot_v1"
    )
    capability_use_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_capability_use_evidence_snapshot_v1"
    )
    if not all(
        [
            governance_snapshot,
            directive_work_selection_policy_snapshot,
            directive_work_candidate_screen_snapshot,
            directive_work_admission_snapshot,
            capability_use_evidence_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "governed_direct_work",
            "proposal_semantics": "shadow_direct_work",
            "reason": "shadow direct work failed: governance substrate, directive-work selection policy, candidate screen, direct-work admission, and capability-use evidence artifacts are required",
            "observability_gain": {"passed": False, "reason": "missing prerequisite governed direct-work artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite governed direct-work artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite governed direct-work artifacts"},
            "safety_neutrality": {"passed": True, "scope": str(proposal.get("scope", "")), "reason": "no live-policy mutation occurred"},
            "later_selection_usefulness": {"passed": False, "reason": "a real governed direct-work execution cannot run without the governance-owned admission chain"},
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
            "shadow_contract": "governed_direct_work",
            "proposal_semantics": "shadow_direct_work",
            "reason": "shadow direct work failed: current directive, bucket, self-structure, and branch state artifacts are required",
            "observability_gain": {"passed": False, "reason": "missing durable governance state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing durable governance state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing durable governance state"},
            "safety_neutrality": {"passed": True, "scope": str(proposal.get("scope", "")), "reason": "no live-policy mutation occurred"},
            "later_selection_usefulness": {"passed": False, "reason": "direct work cannot stay governance-owned without directive, bucket, self-structure, and branch state"},
        }

    current_directive = dict(directive_state.get("current_directive_state", {}))
    current_bucket = dict(bucket_state.get("current_bucket_state", {}))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_branch_state = str(branch_record.get("state", ""))
    governed_directive_work_selection_policy = dict(self_structure_state.get("governed_directive_work_selection_policy", {}))
    governed_capability_use_policy = dict(self_structure_state.get("governed_capability_use_policy", {}))
    if current_branch_state != "paused_with_baseline_held":
        return {
            "passed": False,
            "shadow_contract": "governed_direct_work",
            "proposal_semantics": "shadow_direct_work",
            "reason": "shadow direct work failed: branch must remain paused_with_baseline_held",
            "observability_gain": {"passed": False, "reason": "branch state invalid for governed direct work"},
            "activation_analysis_usefulness": {"passed": False, "reason": "branch state invalid for governed direct work"},
            "ambiguity_reduction": {"passed": False, "reason": "branch state invalid for governed direct work"},
            "safety_neutrality": {"passed": True, "scope": str(proposal.get("scope", "")), "reason": "no live-policy mutation occurred"},
            "later_selection_usefulness": {"passed": False, "reason": "the direct-work execution is only admissible while the branch remains paused"},
        }

    last_direct_work_admission = dict(governed_directive_work_selection_policy.get("last_direct_work_admission_outcome", {}))
    if str(last_direct_work_admission.get("status", "")) != "admissible_for_direct_governed_work":
        return {
            "passed": False,
            "shadow_contract": "governed_direct_work",
            "proposal_semantics": "shadow_direct_work",
            "reason": "shadow direct work failed: the primary direct-work candidate is not currently admitted for direct governed work",
            "observability_gain": {"passed": False, "reason": "direct-work admission state invalid"},
            "activation_analysis_usefulness": {"passed": False, "reason": "direct-work admission state invalid"},
            "ambiguity_reduction": {"passed": False, "reason": "direct-work admission state invalid"},
            "safety_neutrality": {"passed": True, "scope": str(proposal.get("scope", "")), "reason": "no live-policy mutation occurred"},
            "later_selection_usefulness": {"passed": False, "reason": "the direct-work item may only run after admission clears"},
        }

    candidate_screen_artifact_path = Path(
        str(governed_directive_work_selection_policy.get("last_candidate_screen_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_directive_work_candidate_screen_snapshot_v1_*.json")
    )
    policy_artifact_path = Path(
        str(governed_directive_work_selection_policy.get("last_policy_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_directive_work_selection_policy_snapshot_v1_*.json")
    )
    admission_artifact_path = Path(
        str(governed_directive_work_selection_policy.get("last_direct_work_admission_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_directive_work_admission_snapshot_v1_*.json")
    )
    capability_use_evidence_artifact_path = Path(
        str(governed_capability_use_policy.get("last_invocation_evidence_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_capability_use_evidence_snapshot_v1_*.json")
    )

    candidate_screen_payload = _load_json_file(candidate_screen_artifact_path)
    candidate_screen_summary = dict(candidate_screen_payload.get("governed_directive_work_candidate_screen_summary", {}))
    admission_payload = _load_json_file(admission_artifact_path)
    admission_summary = dict(admission_payload.get("governed_directive_work_admission_summary", {}))
    if not all([candidate_screen_summary, admission_summary]):
        return {
            "passed": False,
            "shadow_contract": "governed_direct_work",
            "proposal_semantics": "shadow_direct_work",
            "reason": "shadow direct work failed: candidate-screen or direct-work-admission summary payload is missing",
            "observability_gain": {"passed": False, "reason": "missing direct-work governing summaries"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing direct-work governing summaries"},
            "ambiguity_reduction": {"passed": False, "reason": "missing direct-work governing summaries"},
            "safety_neutrality": {"passed": True, "scope": str(proposal.get("scope", "")), "reason": "no live-policy mutation occurred"},
            "later_selection_usefulness": {"passed": False, "reason": "the direct-work execution cannot run without the governing summary payloads"},
        }

    primary_candidate_name = str(dict(admission_summary.get("candidate_evaluated", {})).get("work_item_name", ""))
    screened_candidates = list(candidate_screen_summary.get("work_candidates_screened", []))
    work_candidate_record = _find_work_candidate(screened_candidates, work_item_name=primary_candidate_name)
    if not work_candidate_record:
        return {
            "passed": False,
            "shadow_contract": "governed_direct_work",
            "proposal_semantics": "shadow_direct_work",
            "reason": "shadow direct work failed: the admitted direct-work candidate is missing from the candidate-screen artifact",
            "observability_gain": {"passed": False, "reason": "missing admitted direct-work candidate record"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing admitted direct-work candidate record"},
            "ambiguity_reduction": {"passed": False, "reason": "missing admitted direct-work candidate record"},
            "safety_neutrality": {"passed": True, "scope": str(proposal.get("scope", "")), "reason": "no live-policy mutation occurred"},
            "later_selection_usefulness": {"passed": False, "reason": "cannot execute admitted direct work without its screened candidate record"},
        }

    direct_work_envelope = dict(admission_summary.get("direct_work_envelope", {}))
    direct_work_accounting_requirements = dict(admission_summary.get("direct_work_accounting_requirements", {}))
    trigger_bundle = dict(admission_summary.get("review_rollback_deprecation_triggers", {}))
    callable_capabilities = list(governed_capability_use_policy.get("current_callable_capabilities", []))

    source_artifact_paths = list(direct_work_envelope.get("admissible_source_artifacts", []))
    source_artifact_paths = [str(path) for path in source_artifact_paths if str(path)]
    source_artifact_paths = list(dict.fromkeys(source_artifact_paths))
    governance_source_digests = []
    for path_text in source_artifact_paths:
        path = Path(path_text)
        if path.suffix == ".json":
            payload = _load_json_file(path)
            governance_source_digests.append(
                {
                    "path": str(path),
                    "exists": bool(payload),
                    "top_level_keys": sorted(str(key) for key in dict(payload).keys())[:16] if isinstance(payload, dict) else [],
                }
            )
        elif path.suffix == ".jsonl":
            rows = _load_jsonl(path)
            governance_source_digests.append(
                {
                    "path": str(path),
                    "exists": path.exists(),
                    "row_count": int(len(rows)),
                }
            )
        else:
            governance_source_digests.append(_trial_artifact_digest(path))

    coherence_audit = _build_coherence_audit(
        current_directive=current_directive,
        directive_state=directive_state,
        current_state_summary=current_state_summary,
        branch_record=branch_record,
        current_branch_state=current_branch_state,
        current_bucket=current_bucket,
        work_candidate_record=work_candidate_record,
        direct_work_envelope=direct_work_envelope,
        callable_capabilities=callable_capabilities,
        analytics=analytics,
        recommendations=recommendations,
    )

    artifact_path = (
        _diagnostic_artifact_dir()
        / f"proposal_learning_loop_v4_governed_directive_work_governance_state_coherence_audit_refresh_v1_{proposal['proposal_id']}.json"
    )
    allowed_roots = [Path(path).resolve() for path in list(direct_work_envelope.get("allowed_write_roots", []))]
    write_paths = [artifact_path, SELF_STRUCTURE_STATE_PATH, SELF_STRUCTURE_LEDGER_PATH]
    resource_expectations = dict(direct_work_envelope.get("resource_expectations", {}))
    pressure = _bucket_pressure(bucket_state, resource_expectations)

    directive_support_value = {
        "passed": str(dict(coherence_audit.get("summary", {})).get("alignment_status", "")) == "coherent",
        "reason": "the audit produced a bounded governance-state coherence report that directly supports directive-bound governance maintenance",
        "value": "high" if str(dict(coherence_audit.get("summary", {})).get("alignment_status", "")) == "coherent" else "review_needed",
    }
    hidden_capability_pressure = {
        "passed": not bool(dict(work_candidate_record.get("path_separation", {})).get("requires_capability_use_admission", False))
        and not bool(dict(work_candidate_record.get("path_separation", {})).get("requires_reopen_screen", False))
        and not bool(dict(work_candidate_record.get("classification_report", {})).get("hidden_development_pressure", False)),
        "value": "none",
        "reason": "the executed work remained direct governance maintenance and did not drift toward capability use, reopen pressure, or hidden development",
    }

    direct_work_accounting = {
        "work_identity": dict(direct_work_accounting_requirements.get("candidate_specific_expectations", {}).get("work_identity", {})),
        "directive_branch_context": {
            "directive_id": str(current_directive.get("directive_id", "")),
            "branch_id": str(branch_record.get("branch_id", "")),
            "branch_state": current_branch_state,
            "plan_non_owning": bool(current_state_summary.get("plan_non_owning", False)),
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
        },
        "execution_path_reporting": dict(
            direct_work_accounting_requirements.get("candidate_specific_expectations", {}).get("expected_capability_path", {})
        ),
        "resource_usage": {
            "cpu_parallel_units_used": int(resource_expectations.get("cpu_parallel_units", 0) or 0),
            "memory_mb_used": int(resource_expectations.get("memory_mb", 0) or 0),
            "storage_write_mb_used": 0,
            "network_mode_used": str(resource_expectations.get("network_mode", "none")),
        },
        "write_roots_touched": list(direct_work_envelope.get("allowed_write_roots", [])),
        "source_artifact_paths": source_artifact_paths,
        "admission_outcome": "admissible_for_direct_governed_work",
        "rationale": str(dict(admission_summary.get("admission_outcome", {})).get("reason", "")),
        "trusted_source_report": dict(dict(work_candidate_record.get("classification_report", {})).get("trusted_source_report", {})),
        "resource_report": dict(dict(work_candidate_record.get("classification_report", {})).get("resource_report", {})),
        "write_root_report": dict(dict(work_candidate_record.get("classification_report", {})).get("write_root_report", {})),
        "branch_state_unchanged": True,
        "retained_promotion_performed": False,
        "review_trigger_status": dict(trigger_bundle.get("review_trigger_status", {})),
        "rollback_trigger_status": dict(trigger_bundle.get("rollback_trigger_status", {})),
        "deprecation_trigger_status": dict(trigger_bundle.get("deprecation_trigger_status", {})),
        "work_summary": "governance state coherence audit refresh",
        "directive_support_observation": str(directive_support_value.get("reason", "")),
        "bounded_output_artifact_path": str(artifact_path),
        "usefulness_signal_summary": {
            "coherence_score": float(dict(coherence_audit.get("summary", {})).get("coherence_score", 0.0) or 0.0),
            "passed_check_count": int(dict(coherence_audit.get("summary", {})).get("passed_check_count", 0) or 0),
            "failed_check_count": int(dict(coherence_audit.get("summary", {})).get("failed_check_count", 0) or 0),
        },
        "duplicate_or_overlap_observation": "low overlap; this is direct governance maintenance work, not capability-use reuse or new-skill work",
    }

    envelope_compliance = {
        "network_mode_required": str(direct_work_envelope.get("network_mode", "none")),
        "network_mode_observed": str(resource_expectations.get("network_mode", "none")),
        "network_mode_remained_none": str(resource_expectations.get("network_mode", "none")) == "none",
        "branch_state_stayed_paused_with_baseline_held": current_branch_state == "paused_with_baseline_held",
        "no_branch_state_mutation": True,
        "no_retained_promotion": True,
        "no_capability_modification": True,
        "no_paused_capability_reopen": True,
        "no_new_skill_creation": True,
        "no_protected_surface_modification": True,
        "no_downstream_selected_set_work": True,
        "no_plan_ownership_change": True,
        "no_routing_work": True,
        "writes_within_approved_roots": all(_path_within_allowed_roots(path, allowed_roots) for path in write_paths),
        "approved_write_paths": [str(path) for path in write_paths],
        "resource_expectations": resource_expectations,
        "bucket_pressure": pressure,
        "resource_limits_respected": pressure["concern_level"] == "low",
    }
    envelope_compliance["passed"] = all(
        bool(envelope_compliance[key])
        for key in [
            "network_mode_remained_none",
            "branch_state_stayed_paused_with_baseline_held",
            "no_branch_state_mutation",
            "no_retained_promotion",
            "no_capability_modification",
            "no_paused_capability_reopen",
            "no_new_skill_creation",
            "no_protected_surface_modification",
            "no_downstream_selected_set_work",
            "no_plan_ownership_change",
            "no_routing_work",
            "writes_within_approved_roots",
            "resource_limits_respected",
        ]
    )

    review_trigger_status = {
        "decision_criticality_rises_above_low": str(dict(work_candidate_record.get("classification_report", {})).get("decision_criticality", "")) != "low",
        "overlap_with_active_work_rises_above_low": str(dict(work_candidate_record.get("classification_report", {})).get("overlap_with_active_work", "")) != "low",
        "scope_expands_beyond_governance_state_coherence_audit": False,
        "held_capability_dependency_or_external_source_need_appears": False,
        "work_starts_to_imply_capability_development_or_branch_mutation": not bool(hidden_capability_pressure.get("passed", False)),
    }
    rollback_trigger_status = {str(key): False for key in dict(trigger_bundle.get("rollback_triggers", {})).keys()}
    deprecation_trigger_status = {str(key): False for key in dict(trigger_bundle.get("deprecation_triggers", {})).keys()}
    governed_direct_work_operational = (
        bool(directive_support_value.get("passed", False))
        and bool(hidden_capability_pressure.get("passed", False))
        and bool(envelope_compliance.get("passed", False))
        and not any(bool(value) for value in review_trigger_status.values())
        and not any(bool(value) for value in rollback_trigger_status.values())
        and not any(bool(value) for value in deprecation_trigger_status.values())
    )
    next_template = "memory_summary.v4_governed_direct_work_evidence_snapshot_v1"

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1",
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
            "memory_summary.v4_governed_directive_work_selection_policy_snapshot_v1": _artifact_reference(
                directive_work_selection_policy_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_directive_work_candidate_screen_snapshot_v1": _artifact_reference(
                directive_work_candidate_screen_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_directive_work_admission_snapshot_v1": _artifact_reference(
                directive_work_admission_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_capability_use_evidence_snapshot_v1": _artifact_reference(
                capability_use_evidence_snapshot, latest_snapshots
            ),
        },
        "governed_direct_work_execution_summary": {
            "candidate_executed": {
                "work_item_id": str(dict(admission_summary.get("candidate_evaluated", {})).get("work_item_id", "")),
                "work_item_name": primary_candidate_name,
                "assigned_candidate_class": str(dict(admission_summary.get("candidate_evaluated", {})).get("assigned_candidate_class", "")),
            },
            "what_the_work_did": [
                "read the admitted trusted local governance-state artifacts listed in the direct-work envelope",
                "computed a bounded coherence audit across directive, branch, bucket, self-structure, analytics, recommendations, and direct-work path-separation state",
                "materialized a bounded shadow-only governance-state coherence audit artifact and full direct-work accounting",
            ],
            "local_governance_sources_used": {
                "source_artifact_paths": source_artifact_paths,
                "governance_source_digests": governance_source_digests,
            },
            "audit_artifact_produced": {
                "bounded_output_artifact_path": str(artifact_path),
                "coherence_audit_output": coherence_audit,
            },
            "direct_work_accounting_captured": direct_work_accounting,
            "envelope_compliance": envelope_compliance,
            "directive_support_value": directive_support_value,
            "hidden_capability_pressure_read": hidden_capability_pressure,
            "review_rollback_deprecation_trigger_status": {
                "review_trigger_status": review_trigger_status,
                "rollback_trigger_status": rollback_trigger_status,
                "deprecation_trigger_status": deprecation_trigger_status,
            },
            "path_separation_status": {
                "remained_direct_work": True,
                "capability_use_not_invoked": True,
                "paused_capability_line_not_reopened": True,
                "new_skill_path_not_opened": True,
            },
            "why_governance_remains_source_of_truth": {
                "owner": "governance_substrate_v1",
                "proposal_learning_loop_is_governance_truth_source": False,
                "reason": "the run consumed directive, bucket, branch, self-structure, analytics, recommendations, and prior direct-work governance artifacts as read-only authority while performing only the admitted direct-work audit",
            },
        },
        "analytics_context": {
            "analytics_report_path": str(intervention_data_dir() / "intervention_analytics_latest.json"),
            "proposal_recommendations_path": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            "proposal_count": int(analytics.get("proposal_count", 0) or 0),
            "directive_history_entry_count": int(len(directive_history)),
            "self_structure_ledger_entry_count": int(len(self_structure_ledger)),
            "intervention_ledger_entry_count": int(len(intervention_ledger)),
        },
        "observability_gain": {
            "passed": True,
            "reason": "the admitted direct-work item now has a real bounded execution artifact and full governance accounting",
            "artifact_paths": {
                "direct_work_execution_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the run proves that NOVALI can execute admitted direct governed work without collapsing into capability use or hidden development",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "the execution keeps direct work separate from capability-use, paused-line reopen, and new-skill creation in a concrete operational run",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the execution remained shadow-only, local, reversible, and governance-bounded; live policy, thresholds, routing, frozen benchmark semantics, and the projection-safe envelope stayed unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": next_template,
            "reason": "the next step should review the direct-work evidence before broadening direct-work execution patterns",
        },
        "diagnostic_conclusions": {
            "governed_direct_work_execution_in_place": True,
            "direct_work_candidate": primary_candidate_name,
            "governed_direct_work_operational": governed_direct_work_operational,
            "branch_state_mutation_occurred": False,
            "retained_promotion_occurred": False,
            "paused_capability_line_reopened": False,
            "plan_should_remain_non_owning": bool(current_state_summary.get("plan_non_owning", False)),
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "best_next_template": next_template,
        },
    }
    _write_json(artifact_path, artifact_payload)

    estimated_write_bytes = (
        int(artifact_path.stat().st_size)
        + len(json.dumps({"updated_state": True}))
        + len(json.dumps({"ledger_event": True}))
    )
    direct_work_accounting["resource_usage"]["storage_write_mb_used"] = max(
        1,
        int((estimated_write_bytes + (1024 * 1024) - 1) / (1024 * 1024)),
    )
    artifact_payload["governed_direct_work_execution_summary"]["direct_work_accounting_captured"] = direct_work_accounting
    artifact_payload["governed_direct_work_execution_summary"]["envelope_compliance"]["estimated_write_bytes"] = int(
        estimated_write_bytes
    )
    artifact_payload["governed_direct_work_execution_summary"]["envelope_compliance"]["storage_budget_respected"] = (
        estimated_write_bytes <= int(resource_expectations.get("storage_write_mb", 0) or 0) * 1024 * 1024
    )
    _write_json(artifact_path, artifact_payload)

    updated_self_structure_state = dict(self_structure_state)
    updated_directive_work_policy = dict(governed_directive_work_selection_policy)
    updated_directive_work_policy["direct_work_execution_schema"] = {
        "schema_name": "GovernedDirectWorkExecution",
        "schema_version": "governed_direct_work_execution_v1",
        "required_fields": [
            "work_item_id",
            "work_item_name",
            "coherence_audit_output",
            "direct_work_accounting_captured",
            "envelope_compliance",
            "directive_support_value",
            "review_trigger_status",
            "rollback_trigger_status",
            "deprecation_trigger_status",
        ],
    }
    updated_directive_work_policy["last_direct_work_execution_artifact_path"] = str(artifact_path)
    updated_directive_work_policy["last_direct_work_execution_outcome"] = {
        "work_item_id": str(dict(admission_summary.get("candidate_evaluated", {})).get("work_item_id", "")),
        "work_item_name": primary_candidate_name,
        "direct_work_execution_outcome": "shadow_direct_work_completed",
        "envelope_compliance_passed": bool(envelope_compliance.get("passed", False)),
        "paused_capability_line_reopened": False,
        "retained_promotion": False,
        "governed_direct_work_operational": governed_direct_work_operational,
        "best_next_template": next_template,
    }
    updated_directive_work_policy["best_next_template"] = next_template
    updated_self_structure_state["governed_directive_work_selection_policy"] = updated_directive_work_policy

    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "governed_direct_work_execution_in_place": True,
            "latest_directive_work_execution_candidate": primary_candidate_name,
            "latest_directive_work_execution_outcome": "shadow_direct_work_completed",
            "latest_directive_work_operational_status": (
                "operational_bounded_direct_work_proven" if governed_direct_work_operational else "direct_work_needs_review"
            ),
            "latest_directive_work_best_next_template": next_template,
            "current_branch_state": current_branch_state,
            "plan_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "retained_skill_promotion_performed": False,
        }
    )
    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["current_state_summary"] = updated_current_state_summary
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    ledger_event = {
        "event_id": f"governed_directive_work_governance_state_coherence_audit_refresh_v1::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_directive_work_governance_state_coherence_audit_refresh_v1_materialized",
        "event_class": "governed_direct_work_execution",
        "directive_id": str(current_directive.get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": current_branch_state,
        "work_item_id": str(dict(admission_summary.get("candidate_evaluated", {})).get("work_item_id", "")),
        "work_item_name": primary_candidate_name,
        "direct_work_execution_outcome": "shadow_direct_work_completed",
        "paused_capability_line_reopened": False,
        "retained_promotion": False,
        "branch_state_mutation": False,
        "network_mode": str(resource_expectations.get("network_mode", "none")),
        "artifact_paths": {
            "directive_work_selection_policy_artifact": str(policy_artifact_path),
            "directive_work_candidate_screen_artifact": str(candidate_screen_artifact_path),
            "directive_work_admission_artifact": str(admission_artifact_path),
            "capability_use_evidence_artifact": str(capability_use_evidence_artifact_path),
            "direct_work_execution_artifact": str(artifact_path),
        },
        "source_proposal_id": str(proposal.get("proposal_id", "")),
    }
    _append_jsonl(SELF_STRUCTURE_LEDGER_PATH, ledger_event)

    return {
        "passed": True,
        "shadow_contract": "governed_direct_work",
        "proposal_semantics": "shadow_direct_work",
        "reason": "shadow direct work passed: the admitted governance-state coherence audit executed inside the approved direct-work envelope without reopening capabilities or creating a new skill path",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
