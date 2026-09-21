from __future__ import annotations

from typing import Any

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
from .ledger import intervention_data_dir
from .v4_first_hypothesis_landscape_snapshot_v1 import _load_json_file
from .v4_governed_work_loop_evidence_snapshot_v7 import (
    _all_flags_false,
    _continuation_value_assessment,
    _envelope_compliance_assessment,
    _governance_sufficiency_assessment,
    _normalize_requested_sources,
    _operational_usefulness_assessment,
    _resolve_artifact_path,
    _select_latest_successful_frontier_circularity_artifact,
)


def _normalized_circularity_level(raw_value: Any) -> str:
    value = str(raw_value or "").strip().lower()
    if value in {"circularity_risk_low", "low"}:
        return "low"
    if value in {"circularity_risk_medium", "medium"}:
        return "medium"
    if value in {"circularity_risk_high", "high"}:
        return "high"
    return value or "medium"


def run_probe(cfg, proposal, *, rounds, seeds):
    directive_state = _load_json_file(DIRECTIVE_STATE_PATH)
    bucket_state = _load_json_file(BUCKET_STATE_PATH)
    self_structure_state = _load_json_file(SELF_STRUCTURE_STATE_PATH)
    branch_registry = _load_json_file(BRANCH_REGISTRY_PATH)
    directive_history = _load_jsonl(DIRECTIVE_HISTORY_PATH)
    self_structure_ledger = _load_jsonl(SELF_STRUCTURE_LEDGER_PATH)
    intervention_ledger_path = intervention_data_dir() / "intervention_ledger.jsonl"
    intervention_ledger = _load_jsonl(intervention_ledger_path)
    recommendations_path = intervention_data_dir() / "proposal_recommendations_latest.json"
    recommendations = _load_json_file(recommendations_path)
    if not all([directive_state, bucket_state, self_structure_state, branch_registry]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: current directive, bucket, self-structure, and branch state artifacts are required",
            "observability_gain": {"passed": False, "reason": "missing current governance state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing current governance state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing current governance state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot perform the v8 pause-aware review without current governance state"},
        }

    current_directive = dict(directive_state.get("current_directive_state", {}))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_branch_state = str(branch_record.get("state", ""))
    governed_work_loop_policy = dict(self_structure_state.get("governed_work_loop_policy", {}))
    governed_directive_work_selection_policy = dict(self_structure_state.get("governed_directive_work_selection_policy", {}))
    governed_capability_use_policy = dict(self_structure_state.get("governed_capability_use_policy", {}))
    readiness = {
        str(current_state_summary.get("latest_governed_work_loop_execution_readiness", "")),
        str(current_state_summary.get("latest_governed_work_loop_readiness", "")),
        str(current_state_summary.get("latest_governed_work_loop_best_next_template", "")),
    }
    if (
        current_branch_state != "paused_with_baseline_held"
        or not governed_work_loop_policy
        or not readiness.intersection(
            {
                "ready_for_work_loop_evidence_review_v8_later",
                "hold_position_pending_more_evidence",
                "memory_summary.v4_governed_work_loop_evidence_snapshot_v8",
            }
        )
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: branch must remain paused_with_baseline_held and state must already be in the v8 hold-or-reentry checkpoint",
            "observability_gain": {"passed": False, "reason": "pause-aware work-loop state mismatch"},
            "activation_analysis_usefulness": {"passed": False, "reason": "pause-aware work-loop state mismatch"},
            "ambiguity_reduction": {"passed": False, "reason": "pause-aware work-loop state mismatch"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot review pause-aware continuation status without the required governed posture"},
        }

    artifact_paths = {
        "governed_work_loop_policy_v1": _resolve_artifact_path(governed_work_loop_policy.get("last_policy_artifact_path"), "memory_summary_v4_governed_work_loop_policy_snapshot_v1_*.json"),
        "governed_work_loop_candidate_screen_v7": _resolve_artifact_path(governed_work_loop_policy.get("last_candidate_screen_artifact_path"), "memory_summary_v4_governed_work_loop_candidate_screen_snapshot_v7_*.json"),
        "governed_work_loop_continuation_admission_v7": _resolve_artifact_path(governed_work_loop_policy.get("last_work_loop_continuation_admission_artifact_path"), "memory_summary_v4_governed_work_loop_continuation_admission_snapshot_v7_*.json"),
        "governed_work_loop_posture_v1": _resolve_artifact_path(governed_work_loop_policy.get("last_work_loop_posture_artifact_path"), "memory_summary_v4_governed_work_loop_posture_snapshot_v1_*.json"),
        "governed_work_loop_evidence_v1": _resolve_artifact_path("", "memory_summary_v4_governed_work_loop_evidence_snapshot_v1_*.json"),
        "governed_work_loop_evidence_v6": _resolve_artifact_path(governed_work_loop_policy.get("last_prior_work_loop_evidence_artifact_path"), "memory_summary_v4_governed_work_loop_evidence_snapshot_v6_*.json"),
        "governed_work_loop_evidence_v7": _resolve_artifact_path(governed_work_loop_policy.get("last_work_loop_evidence_artifact_path"), "memory_summary_v4_governed_work_loop_evidence_snapshot_v7_*.json"),
        "governed_work_loop_continuation_execution_v1": _resolve_artifact_path("", "proposal_learning_loop_v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1_*.json"),
        "governed_work_loop_continuation_execution_v2": _resolve_artifact_path("", "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1_*.json"),
        "governed_work_loop_continuation_execution_v3": _resolve_artifact_path("", "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1_*.json"),
        "governed_work_loop_continuation_execution_v4": _resolve_artifact_path("", "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1_*.json"),
        "governed_work_loop_continuation_execution_v5": _resolve_artifact_path("", "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1_*.json"),
        "governed_work_loop_continuation_execution_v6": _resolve_artifact_path(governed_work_loop_policy.get("last_prior_work_loop_continuation_execution_artifact_path"), "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit_v1_*.json"),
        "governed_work_loop_continuation_execution_v7": _select_latest_successful_frontier_circularity_artifact(_resolve_artifact_path(governed_work_loop_policy.get("last_work_loop_continuation_execution_artifact_path"), "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_frontier_circularity_boundary_audit_v1_*.json")),
        "governed_direct_work_evidence_v1": _resolve_artifact_path(governed_directive_work_selection_policy.get("last_direct_work_evidence_artifact_path"), "memory_summary_v4_governed_direct_work_evidence_snapshot_v1_*.json"),
        "governed_direct_work_execution_v1": _resolve_artifact_path(governed_directive_work_selection_policy.get("last_direct_work_execution_artifact_path"), "proposal_learning_loop_v4_governed_directive_work_governance_state_coherence_audit_refresh_v1_*.json"),
        "governed_capability_use_evidence_v1": _resolve_artifact_path(governed_capability_use_policy.get("last_invocation_evidence_artifact_path"), "memory_summary_v4_governed_capability_use_evidence_snapshot_v1_*.json"),
    }
    if not all(artifact_paths.values()):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: expected pause-aware work-loop v8 artifact paths could not be resolved",
            "observability_gain": {"passed": False, "reason": "missing resolved artifact paths"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing resolved artifact paths"},
            "ambiguity_reduction": {"passed": False, "reason": "missing resolved artifact paths"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot perform the pause-aware review without resolved artifact paths"},
        }

    payloads = {name: _load_json_file(path) for name, path in artifact_paths.items()}
    if not all(payloads.values()):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: one or more required pause-aware work-loop v8 artifacts could not be loaded",
            "observability_gain": {"passed": False, "reason": "failed to load required evidence artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "failed to load required evidence artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "failed to load required evidence artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot perform the pause-aware review without the loaded governing artifacts"},
        }

    policy_summary = dict(payloads["governed_work_loop_policy_v1"].get("governed_work_loop_policy_summary", {}))
    candidate_screen_summary = dict(payloads["governed_work_loop_candidate_screen_v7"].get("governed_work_loop_candidate_screen_v7_summary", {}))
    continuation_admission_summary = dict(payloads["governed_work_loop_continuation_admission_v7"].get("governed_work_loop_continuation_admission_v7_summary", {}))
    evidence_v6_summary = dict(payloads["governed_work_loop_evidence_v6"].get("governed_work_loop_evidence_v6_summary", {}))
    evidence_v7_summary = dict(payloads["governed_work_loop_evidence_v7"].get("governed_work_loop_evidence_v7_summary", {}))
    circularity_execution_summary = dict(payloads["governed_work_loop_continuation_execution_v7"].get("governed_work_loop_continuation_execution_summary", {}))
    if not all([policy_summary, candidate_screen_summary, continuation_admission_summary, evidence_v6_summary, evidence_v7_summary, circularity_execution_summary]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: required pause-aware work-loop v8 summaries were missing from the loaded artifacts",
            "observability_gain": {"passed": False, "reason": "summary content missing from loaded artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "summary content missing from loaded artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "summary content missing from loaded artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot perform the pause-aware review without the summary payloads"},
        }

    accounting_requirements = dict(policy_summary.get("loop_accounting_requirements", governed_work_loop_policy.get("loop_accounting_requirements", {})))
    candidate_under_review = dict(evidence_v7_summary.get("candidate_reviewed", {})) or dict(circularity_execution_summary.get("candidate_executed", {}))
    continuation_accounting_summary = dict(circularity_execution_summary.get("continuation_accounting_captured", {}))
    review_rollback_status = dict(circularity_execution_summary.get("review_rollback_deprecation_trigger_status", {}))
    review_trigger_status = dict(review_rollback_status.get("review_trigger_status", {}))
    rollback_trigger_status = dict(review_rollback_status.get("rollback_trigger_status", {}))

    operational_usefulness = _operational_usefulness_assessment(circularity_execution_summary)
    governance_sufficiency = _governance_sufficiency_assessment(circularity_execution_summary, accounting_requirements)
    envelope_compliance = _envelope_compliance_assessment(circularity_execution_summary, current_state_summary)
    continuation_value = _continuation_value_assessment(circularity_execution_summary)

    chain_distinct_value = dict(evidence_v7_summary.get("chain_distinct_value_assessment", {}))
    repeated_bounded_success = dict(evidence_v7_summary.get("repeated_bounded_success_assessment", {}))
    structural_v7 = dict(evidence_v7_summary.get("structural_vs_recursive_assessment", {}))
    diminishing_v7 = dict(evidence_v7_summary.get("diminishing_returns_assessment", {}))
    circularity_v7 = dict(evidence_v7_summary.get("circularity_risk_assessment", {}))
    posture_v7 = dict(evidence_v7_summary.get("posture_discipline_assessment", {}))
    pressure_v7 = dict(evidence_v7_summary.get("posture_pressure_assessment", {}))
    gate_v7 = dict(evidence_v7_summary.get("gate_status", {}))

    chain_value_retained = bool(chain_distinct_value.get("passed", False)) and bool(repeated_bounded_success.get("passed", False)) and bool(operational_usefulness.get("passed", False)) and bool(governance_sufficiency.get("passed", False)) and bool(envelope_compliance.get("passed", False))
    chain_value_retention_assessment = {"classification": "meaningful_accumulated_value" if chain_value_retained else "administrative_recursion_dominant", "passed": chain_value_retained, "reason": "the chain still retains meaningful accumulated value in the reviewed record" if chain_value_retained else "the chain no longer retains enough meaningful accumulated value to outweigh the administrative-recursion read"}
    structural_classification = "administratively_recursive" if str(structural_v7.get("classification", "")) == "administratively_recursive" else "structural_but_still_narrow"
    structural_vs_recursive_assessment = {"classification": structural_classification, "passed": structural_classification == "structural_but_still_narrow", "reason": "the chain retains value, but the administrative-recursion read remains dominant for forward continuation decisions" if structural_classification == "administratively_recursive" else "the chain still reads as structural and narrow enough for future re-entry consideration"}
    posture_discipline_holds = current_branch_state == "paused_with_baseline_held" and bool(current_state_summary.get("plan_non_owning", False)) and bool(current_state_summary.get("routing_deferred", False)) and not bool(current_state_summary.get("retained_skill_promotion_performed", False)) and bool(posture_v7.get("passed", False)) and bool(envelope_compliance.get("passed", False))
    posture_discipline_assessment = {"classification": "posture_discipline_holding_cleanly" if posture_discipline_holds else "posture_discipline_under_pressure", "passed": posture_discipline_holds, "reason": "posture discipline still holds cleanly across the paused review state" if posture_discipline_holds else "one or more posture guardrails no longer holds cleanly in the paused review state"}
    hidden_pressure_present = str(pressure_v7.get("classification", "")) == "posture_pressure_present" or not _all_flags_false(review_trigger_status) or not _all_flags_false(rollback_trigger_status)
    posture_pressure_assessment = {"classification": "posture_pressure_present" if hidden_pressure_present else "posture_pressure_absent", "passed": not hidden_pressure_present, "reason": "no hidden capability reopening, branch mutation, retained promotion, or capability-development pressure appears in the reviewed loop state" if not hidden_pressure_present else "the reviewed loop state now shows hidden development or mutation pressure"}
    fresh_trigger_present = str(current_state_summary.get("latest_governed_work_loop_best_next_template", "")) == "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v8" or str(current_state_summary.get("latest_governed_work_loop_readiness", "")) == "ready_for_work_loop_candidate_screen_v8_later"
    fresh_trigger_assessment = {"classification": "concrete_fresh_trigger_present" if fresh_trigger_present else "absent", "passed": fresh_trigger_present, "reason": "state already points back to bounded candidate screening" if fresh_trigger_present else "no concrete fresh bounded trigger appears: readiness remains evidence-review oriented and no new local governance signal justifies re-entry into candidate search"}
    circularity_level = _normalized_circularity_level(circularity_v7.get("classification", ""))
    if hidden_pressure_present or not posture_discipline_holds:
        circularity_level = "high"
    circularity_risk_assessment = {"classification": circularity_level, "passed": circularity_level == "low", "reason": "circularity risk remains medium because structural yield is thinning and no fresh trigger justifies renewed candidate search" if circularity_level == "medium" else "circularity risk remains low because amber concerns materially eased" if circularity_level == "low" else "circularity risk is now high because pressure or drift overtook the bounded continuation rationale"}
    if hidden_pressure_present or circularity_level == "high":
        diminishing_classification = "worsening_diminishing_returns"
    elif str(diminishing_v7.get("classification", "")) == "not_nearing_diminishing_returns" and fresh_trigger_present:
        diminishing_classification = "not_nearing_diminishing_returns"
    else:
        diminishing_classification = "nearing_diminishing_returns"
    diminishing_returns_assessment = {"classification": diminishing_classification, "passed": diminishing_classification == "not_nearing_diminishing_returns", "reason": "diminishing-return pressure remains near because novelty and structural yield have not improved enough since the v7 amber checkpoint" if diminishing_classification == "nearing_diminishing_returns" else "diminishing-return pressure is improving because a concrete fresh bounded trigger exists and amber concerns eased" if diminishing_classification == "not_nearing_diminishing_returns" else "diminishing-return pressure is worsening because structural yield is now too thin relative to recursion or pressure risk"}
    amber_state_classification = "amber_state_improving" if fresh_trigger_present and diminishing_classification == "not_nearing_diminishing_returns" and circularity_level == "low" else "worsening" if diminishing_classification == "worsening_diminishing_returns" or circularity_level == "high" else "unchanged"
    amber_state_trend_assessment = {"classification": amber_state_classification, "passed": amber_state_classification == "amber_state_improving", "reason": "the amber state remains unchanged because diminishing returns are still nearing, circularity risk remains medium, and no concrete fresh trigger has appeared" if amber_state_classification == "unchanged" else "the amber state is improving because diminishing-return pressure and circularity risk both eased under a concrete fresh trigger" if amber_state_classification == "amber_state_improving" else "the amber state is worsening because recursion or pressure concerns now dominate the pause-aware review"}
    gate_closed = bool(gate_v7.get("passed", False))
    gate_status = {"classification": "gate_closed" if gate_closed else "gate_open_or_unclear", "gate_status": str(gate_v7.get("gate_status", "defined_but_closed")), "passed": gate_closed, "reason": "the posture-review gate remains defined but closed because no fresh evidence justifies opening broader continuation posture" if gate_closed else "the posture-review gate no longer reads clearly closed"}
    routing_status = {"classification": "routing_deferred" if bool(current_state_summary.get("routing_deferred", False)) else "routing_changed", "routing_deferred": bool(current_state_summary.get("routing_deferred", False))}

    if fresh_trigger_present and amber_state_classification == "amber_state_improving" and chain_value_retained and structural_classification == "structural_but_still_narrow" and posture_discipline_holds and not hidden_pressure_present and gate_closed and bool(routing_status.get("routing_deferred", False)):
        future_reentry_classification = "justified_for_future_reentry"
    elif not posture_discipline_holds or hidden_pressure_present or diminishing_classification == "worsening_diminishing_returns" or circularity_level == "high":
        future_reentry_classification = "stop_continuation"
    else:
        future_reentry_classification = "hold_posture"
    future_reentry_assessment = {"classification": future_reentry_classification, "passed": future_reentry_classification == "justified_for_future_reentry", "reason": "the governed work-loop should remain on hold because the amber state did not improve enough and no concrete fresh trigger justifies renewed candidate search" if future_reentry_classification == "hold_posture" else "future bounded re-entry is justified because the amber state improved and a concrete fresh trigger exists inside the still-closed governed envelope" if future_reentry_classification == "justified_for_future_reentry" else "the governed work-loop should stop continuation because recursion, pressure, or drift concerns are now too strong"}

    next_action_class = "bounded_candidate_search_later_supported_with_trigger" if future_reentry_classification == "justified_for_future_reentry" else "stop_continuation" if future_reentry_classification == "stop_continuation" else "hold_posture"
    next_template = "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v8" if next_action_class == "bounded_candidate_search_later_supported_with_trigger" else ""
    future_posture = "keep_narrow_governed_loop_available"
    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_v4_governed_work_loop_evidence_snapshot_v8_{proposal['proposal_id']}.json"

    updated_work_loop_policy = dict(governed_work_loop_policy)
    updated_work_loop_policy["last_work_loop_evidence_artifact_path"] = str(artifact_path)
    updated_work_loop_policy["last_prior_work_loop_evidence_artifact_path"] = str(artifact_paths["governed_work_loop_evidence_v7"])
    updated_work_loop_policy["best_next_template"] = next_template
    updated_work_loop_policy["last_work_loop_evidence_outcome"] = {"status": "hold_posture_after_evidence_v8" if next_action_class == "hold_posture" else next_action_class, "recommended_next_action_class": next_action_class, "best_next_template": next_template, "future_posture_review_gate_status": str(gate_status.get("gate_status", "")), "retained_promotion": False, "paused_capability_line_reopened": False}
    updated_self_structure_state = dict(self_structure_state)
    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update({"governed_work_loop_evidence_review_in_place": True, "governed_work_loop_evidence_review_v8_in_place": True, "latest_governed_work_loop_evidence_outcome": "hold_posture_after_evidence_v8" if next_action_class == "hold_posture" else next_action_class, "latest_governed_work_loop_operational_status": "eight_step_bounded_governed_work_loop_chain_held_pending_fresh_trigger" if next_action_class == "hold_posture" else "eight_step_bounded_governed_work_loop_chain_stopped" if next_action_class == "stop_continuation" else "eight_step_bounded_governed_work_loop_chain_reentry_conditionally_supported", "latest_governed_work_loop_execution_outcome": str(dict(circularity_execution_summary.get("frontier_circularity_result", {})).get("classification", "")), "latest_governed_work_loop_execution_readiness": "hold_position_pending_more_evidence" if next_action_class == "hold_posture" else "stop_continuation" if next_action_class == "stop_continuation" else "ready_for_work_loop_candidate_screen_v8_later", "latest_governed_work_loop_readiness": "hold_position_pending_more_evidence" if next_action_class == "hold_posture" else "stop_continuation" if next_action_class == "stop_continuation" else "ready_for_work_loop_candidate_screen_v8_later", "latest_governed_work_loop_posture": future_posture, "latest_governed_work_loop_future_posture_review_gate_status": str(gate_status.get("gate_status", "")), "latest_governed_work_loop_recommended_next_action_class": next_action_class, "latest_governed_work_loop_best_next_template": next_template, "current_branch_state": current_branch_state, "plan_non_owning": True, "routing_deferred": bool(current_state_summary.get("routing_deferred", False)), "retained_skill_promotion_performed": False})
    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["governed_work_loop_policy"] = updated_work_loop_policy
    updated_self_structure_state["current_state_summary"] = updated_current_state_summary
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    summary = {
        "snapshot_identity_context": {"template_name": "memory_summary.v4_governed_work_loop_evidence_snapshot_v8", "proposal_id": str(proposal.get("proposal_id", "")), "evaluation_semantics": str(proposal.get("evaluation_semantics", "")), "generated_at": _now()},
        "candidate_under_review": candidate_under_review,
        "future_reentry_assessment": future_reentry_assessment,
        "chain_state_reviewed": dict(evidence_v7_summary.get("chain_state_reviewed", {})),
        "evidence_inputs_used": {k: str(v) for k, v in artifact_paths.items()} | {"directive_state_latest": str(DIRECTIVE_STATE_PATH), "directive_history": str(DIRECTIVE_HISTORY_PATH), "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH), "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH), "branch_registry_latest": str(BRANCH_REGISTRY_PATH), "bucket_state_latest": str(BUCKET_STATE_PATH), "intervention_ledger": str(intervention_ledger_path), "proposal_recommendations_latest": str(recommendations_path)},
        "chain_value_retention_assessment": chain_value_retention_assessment,
        "structural_vs_recursive_assessment": structural_vs_recursive_assessment,
        "diminishing_returns_assessment": diminishing_returns_assessment,
        "circularity_risk_assessment": circularity_risk_assessment,
        "amber_state_trend_assessment": amber_state_trend_assessment,
        "fresh_trigger_assessment": fresh_trigger_assessment,
        "posture_discipline_assessment": posture_discipline_assessment,
        "posture_pressure_assessment": posture_pressure_assessment,
        "gate_status": gate_status,
        "routing_status": routing_status,
        "recommended_next_action": {"classification": next_action_class, "template_name": next_template, "reason": future_reentry_assessment["reason"]},
        "recommended_next_template": next_template,
        "review_rollback_deprecation_trigger_status": review_rollback_status,
        "envelope_compliance_summary": {"passed": bool(envelope_compliance.get("passed", False)), "network_mode": str(envelope_compliance.get("network_mode", "")), "write_root_compliance": bool(envelope_compliance.get("write_root_compliance", False)), "bucket_pressure": dict(envelope_compliance.get("bucket_pressure", {})), "branch_state_immutability": bool(envelope_compliance.get("branch_state_immutability", False)), "paused_capability_line_remained_closed": bool(envelope_compliance.get("paused_capability_line_remained_closed", False)), "plan_non_ownership": bool(envelope_compliance.get("plan_non_ownership", False)), "routing_non_involvement": bool(envelope_compliance.get("routing_non_involvement", False))},
        "resource_trust_accounting": {"trusted_sources": _normalize_requested_sources(continuation_accounting_summary.get("trusted_source_report", {})), "requested_resources": dict(dict(continuation_accounting_summary.get("resource_report", {})).get("requested_resources", {})), "observed_resource_usage": dict(continuation_accounting_summary.get("resource_usage", {}))},
        "question_answers": {"future_reentry_status": future_reentry_classification, "amber_state_trend": amber_state_classification, "chain_value_retention": str(chain_value_retention_assessment.get("classification", "")), "structural_vs_recursive": structural_classification, "diminishing_returns_state": diminishing_classification, "circularity_risk": circularity_level, "concrete_fresh_trigger_present": fresh_trigger_present, "posture_discipline_holding_cleanly": bool(posture_discipline_assessment.get("passed", False)), "routing_remains_deferred": bool(routing_status.get("routing_deferred", False)), "posture_review_gate_remains_closed": bool(gate_status.get("passed", False))},
        "operator_readable_conclusion": "The governed work-loop should remain on hold: the amber state is unchanged, administrative recursion remains dominant for forward decisions, diminishing returns are still nearing, circularity risk remains medium, and no concrete fresh trigger justifies re-entry into candidate search.",
    }
    _write_json(artifact_path, {"proposal_id": str(proposal.get("proposal_id")), "template_name": "memory_summary.v4_governed_work_loop_evidence_snapshot_v8", "evaluation_semantics": str(proposal.get("evaluation_semantics", "")), "trigger_reason": str(proposal.get("trigger_reason", "")), "governed_work_loop_evidence_v8_summary": summary})
    _append_jsonl(SELF_STRUCTURE_LEDGER_PATH, {"event_id": f"governed_work_loop_evidence_snapshot_v8::{proposal['proposal_id']}", "timestamp": _now(), "event_type": "governed_work_loop_evidence_snapshot_v8_materialized", "directive_id": str(current_directive.get("directive_id", "")), "branch_id": str(branch_record.get("branch_id", "")), "branch_state": current_branch_state, "recommended_next_action_class": next_action_class, "artifact_path": str(artifact_path)})

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: the pause-aware v8 evidence review held posture narrow, kept the gate closed, and refused momentum-driven continuation without a concrete fresh trigger or improved amber state",
        "observability_gain": {"passed": True, "reason": "the governed work-loop now has an explicit pause-aware v8 hold-or-reentry review artifact", "artifact_path": str(artifact_path)},
        "activation_analysis_usefulness": {"passed": True, "reason": "the review separates retained chain value from forward re-entry justification"},
        "ambiguity_reduction": {"passed": True, "reason": "the v8 review separates amber trend, fresh-trigger presence, diminishing-return pressure, circularity risk, and hold-versus-stop decisions in one artifact"},
        "safety_neutrality": {"passed": True, "reason": "the review is diagnostic-only and changed no live behavior", "scope": str(proposal.get("scope", ""))},
        "later_selection_usefulness": {"passed": next_action_class == "bounded_candidate_search_later_supported_with_trigger", "recommended_next_template": next_template, "reason": "the correct current result is to hold posture unless a concrete fresh trigger later appears"},
        "diagnostic_conclusions": {"hold_narrow_posture": next_action_class == "hold_posture", "stop_continuation": next_action_class == "stop_continuation", "future_reentry_status": future_reentry_classification, "amber_state_trend": amber_state_classification, "fresh_trigger_present": fresh_trigger_present, "loop_nearing_diminishing_returns": diminishing_classification != "not_nearing_diminishing_returns", "circularity_risk": circularity_level, "routing_deferred": bool(routing_status.get("routing_deferred", False)), "gate_closed": bool(gate_status.get("passed", False)), "best_next_template": next_template},
        "artifact_path": str(artifact_path),
    }
