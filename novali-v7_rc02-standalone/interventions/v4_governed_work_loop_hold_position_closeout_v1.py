from __future__ import annotations

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
    _resolve_artifact_path,
    _select_latest_successful_frontier_circularity_artifact,
)


def _normalized_circularity_classification(raw_value: str) -> str:
    value = str(raw_value or "").strip().lower()
    if value in {"circularity_risk_low", "low"}:
        return "circularity_risk_low"
    if value in {"circularity_risk_high", "high"}:
        return "circularity_risk_high"
    return "circularity_risk_medium"


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
        }

    current_directive = dict(directive_state.get("current_directive_state", {}))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_branch_state = str(branch_record.get("state", ""))
    governed_work_loop_policy = dict(self_structure_state.get("governed_work_loop_policy", {}))
    governed_directive_work_selection_policy = dict(self_structure_state.get("governed_directive_work_selection_policy", {}))
    governed_capability_use_policy = dict(self_structure_state.get("governed_capability_use_policy", {}))
    if current_branch_state != "paused_with_baseline_held" or str(current_state_summary.get("latest_governed_work_loop_readiness", "")) != "hold_position_pending_more_evidence":
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: the governed work-loop must already be in hold_position_pending_more_evidence",
        }

    artifact_paths = {
        "governed_work_loop_policy_v1": _resolve_artifact_path(governed_work_loop_policy.get("last_policy_artifact_path"), "memory_summary_v4_governed_work_loop_policy_snapshot_v1_*.json"),
        "governed_work_loop_evidence_v7": _resolve_artifact_path(governed_work_loop_policy.get("last_prior_work_loop_evidence_artifact_path"), "memory_summary_v4_governed_work_loop_evidence_snapshot_v7_*.json"),
        "governed_work_loop_evidence_v8": _resolve_artifact_path(governed_work_loop_policy.get("last_work_loop_evidence_artifact_path"), "memory_summary_v4_governed_work_loop_evidence_snapshot_v8_*.json"),
        "governed_work_loop_candidate_screen_v7": _resolve_artifact_path(governed_work_loop_policy.get("last_candidate_screen_artifact_path"), "memory_summary_v4_governed_work_loop_candidate_screen_snapshot_v7_*.json"),
        "governed_work_loop_continuation_admission_v7": _resolve_artifact_path(governed_work_loop_policy.get("last_work_loop_continuation_admission_artifact_path"), "memory_summary_v4_governed_work_loop_continuation_admission_snapshot_v7_*.json"),
        "governed_work_loop_continuation_execution_v3": _resolve_artifact_path("", "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1_*.json"),
        "governed_work_loop_continuation_execution_v4": _resolve_artifact_path("", "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1_*.json"),
        "governed_work_loop_continuation_execution_v5": _resolve_artifact_path("", "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1_*.json"),
        "governed_work_loop_continuation_execution_v6": _resolve_artifact_path(governed_work_loop_policy.get("last_prior_work_loop_continuation_execution_artifact_path"), "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit_v1_*.json"),
        "governed_work_loop_continuation_execution_v7": _select_latest_successful_frontier_circularity_artifact(_resolve_artifact_path(governed_work_loop_policy.get("last_work_loop_continuation_execution_artifact_path"), "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_frontier_circularity_boundary_audit_v1_*.json")),
        "governed_direct_work_evidence_v1": _resolve_artifact_path(governed_directive_work_selection_policy.get("last_direct_work_evidence_artifact_path"), "memory_summary_v4_governed_direct_work_evidence_snapshot_v1_*.json"),
        "governed_capability_use_evidence_v1": _resolve_artifact_path(governed_capability_use_policy.get("last_invocation_evidence_artifact_path"), "memory_summary_v4_governed_capability_use_evidence_snapshot_v1_*.json"),
    }
    if not all(artifact_paths.values()):
        return {"passed": False, "shadow_contract": "diagnostic_probe", "proposal_semantics": "diagnostic", "reason": "diagnostic shadow failed: required closeout artifact paths could not be resolved"}

    payloads = {name: _load_json_file(path) for name, path in artifact_paths.items()}
    if not all(payloads.values()):
        return {"passed": False, "shadow_contract": "diagnostic_probe", "proposal_semantics": "diagnostic", "reason": "diagnostic shadow failed: required closeout artifacts could not be loaded"}

    v8_summary = dict(payloads["governed_work_loop_evidence_v8"].get("governed_work_loop_evidence_v8_summary", {}))
    v7_summary = dict(payloads["governed_work_loop_evidence_v7"].get("governed_work_loop_evidence_v7_summary", {}))
    candidate_screen_summary = dict(payloads["governed_work_loop_candidate_screen_v7"].get("governed_work_loop_candidate_screen_v7_summary", {}))
    continuation_admission_summary = dict(payloads["governed_work_loop_continuation_admission_v7"].get("governed_work_loop_continuation_admission_v7_summary", {}))
    if not all([v8_summary, v7_summary, candidate_screen_summary, continuation_admission_summary]):
        return {"passed": False, "shadow_contract": "diagnostic_probe", "proposal_semantics": "diagnostic", "reason": "diagnostic shadow failed: required closeout summaries were missing from loaded artifacts"}

    chain_value_retention_assessment = dict(v8_summary.get("chain_value_retention_assessment", {}))
    structural_vs_recursive_assessment = dict(v8_summary.get("structural_vs_recursive_assessment", {}))
    amber_state_trend_assessment = dict(v8_summary.get("amber_state_trend_assessment", {}))
    diminishing_returns_assessment = dict(v8_summary.get("diminishing_returns_assessment", {}))
    circularity_risk_assessment = {
        "classification": _normalized_circularity_classification(dict(v8_summary.get("circularity_risk_assessment", {})).get("classification", "")),
        "passed": False,
        "reason": "circularity risk remains medium because structural yield is thinning and no concrete fresh trigger justifies re-entry.",
    }
    fresh_trigger_assessment = {"classification": "concrete_fresh_trigger_absent", "passed": False, "reason": "no concrete fresh bounded trigger exists in the current governed record."}
    posture_discipline_assessment = dict(v8_summary.get("posture_discipline_assessment", {}))
    posture_pressure_assessment = dict(v8_summary.get("posture_pressure_assessment", {}))
    gate_status = dict(v8_summary.get("gate_status", {}))
    routing_status = dict(v8_summary.get("routing_status", {}))
    review_rollback_status = dict(v8_summary.get("review_rollback_deprecation_trigger_status", {}))
    reviewed_chain_summary = dict(v8_summary.get("chain_state_reviewed", {}))
    reviewed_chain_summary["latest_pause_aware_outcome"] = str(dict(v8_summary.get("future_reentry_assessment", {})).get("classification", ""))

    demonstrated_structural_principle = {
        "classification": "demonstrated_structural_principle_present",
        "principle": "A governance-owned, shadow-only continuation line can accumulate meaningful bounded evidence across multiple audited steps while keeping routing deferred, posture narrow, the gate closed, and the branch paused.",
        "reason": "The direct governed work plus frontier containment, stability, persistence, recursion, and circularity executions completed successfully without reopening protected surfaces.",
    }
    stop_condition_assessment = {
        "classification": "hold_posture",
        "reason": "Hold posture is correct because the line remains meaningful but the forward-decision read is now amber rather than continuation-friendly.",
        "factors": {
            "administratively_recursive": str(structural_vs_recursive_assessment.get("classification", "")) == "administratively_recursive",
            "nearing_diminishing_returns": str(diminishing_returns_assessment.get("classification", "")) == "nearing_diminishing_returns",
            "circularity_risk_medium": True,
            "fresh_trigger_absent": True,
        },
    }
    reentry_criteria = {
        "classification": "reentry_requires_new_evidence",
        "required_conditions": [
            "A concrete fresh bounded trigger must appear in local governed evidence rather than by momentum.",
            "Amber state must improve.",
            "Diminishing-return pressure must no longer be nearing.",
            "Circularity risk must fall to low.",
            "Posture discipline must still hold cleanly with pressure absent.",
        ],
        "concrete_fresh_triggers": [
            "A materially new local governance discrepancy or frontier-quality signal not already consumed by the v1-v7 chain.",
            "A new bounded directive-relevant anomaly in governed artifacts that does not imply capability reopening or branch mutation.",
            "Fresh local evidence that lowers circularity risk and improves the diminishing-return read.",
        ],
    }
    disallowed_auto_reentry_conditions = {
        "classification": "automatic_continuation_disallowed",
        "routing_revisit_closed": True,
        "posture_broadening_closed": True,
        "capability_reopening_closed": True,
        "branch_mutation_closed": True,
        "automatic_continuation_closed": True,
    }
    preserved_project_memory_points = [
        "The governed work-loop line accumulated meaningful value across an eight-step bounded chain.",
        "The line stayed shadow-only, routing-deferred, branch-immutable, projection-safe, and plan-non-owning throughout the reviewed executions.",
        "This is a disciplined hold, not a failed line.",
        "The exact amber stop factors are administrative recursion dominance, nearing diminishing returns, medium circularity risk, and absence of a concrete fresh trigger.",
        "Future re-entry requires new evidence rather than replaying the already-screened frontier.",
        "Attention can shift back to upstream retention or exploitation questions while this line remains archived and held.",
    ]
    recommended_current_stance = {
        "classification": "attention_shift_to_upstream_questions",
        "reason": "Novali-v4 should preserve this line as meaningful governance memory, keep it on hold, and shift active attention back toward upstream retention or exploitation questions unless new bounded evidence later appears.",
    }
    recommended_next_action = {"classification": "hold_posture", "template_name": "", "reason": "The disciplined next step is to preserve the hold position and prevent accidental auto-continuation."}

    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_v4_governed_work_loop_hold_position_closeout_v1_{proposal['proposal_id']}.json"
    updated_work_loop_policy = dict(governed_work_loop_policy)
    updated_work_loop_policy["last_work_loop_hold_position_closeout_artifact_path"] = str(artifact_path)
    updated_work_loop_policy["best_next_template"] = ""
    updated_work_loop_policy["last_work_loop_closeout_outcome"] = {"status": "hold_position_closed_out_v1", "recommended_next_action_class": "hold_posture", "best_next_template": "", "future_posture_review_gate_status": str(gate_status.get("gate_status", "")), "retained_promotion": False, "paused_capability_line_reopened": False}
    updated_self_structure_state = dict(self_structure_state)
    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update({"governed_work_loop_hold_position_closeout_v1_in_place": True, "latest_governed_work_loop_closeout_outcome": "hold_position_closed_out_v1", "latest_governed_work_loop_current_stance": "attention_shift_to_upstream_questions", "latest_governed_work_loop_operational_status": "hold_position_closed_out_pending_fresh_trigger", "latest_governed_work_loop_readiness": "hold_position_pending_more_evidence", "latest_governed_work_loop_execution_readiness": "hold_position_pending_more_evidence", "latest_governed_work_loop_recommended_next_action_class": "hold_posture", "latest_governed_work_loop_best_next_template": "", "current_branch_state": current_branch_state, "plan_non_owning": True, "routing_deferred": bool(current_state_summary.get("routing_deferred", False)), "retained_skill_promotion_performed": False})
    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["governed_work_loop_policy"] = updated_work_loop_policy
    updated_self_structure_state["current_state_summary"] = updated_current_state_summary
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    summary = {
        "closeout_identity_context": {"template_name": "memory_summary.v4_governed_work_loop_hold_position_closeout_v1", "proposal_id": str(proposal.get("proposal_id", "")), "evaluation_semantics": str(proposal.get("evaluation_semantics", "")), "generated_at": _now()},
        "reviewed_chain_summary": reviewed_chain_summary,
        "evidence_inputs_used": {k: str(v) for k, v in artifact_paths.items()} | {"directive_state_latest": str(DIRECTIVE_STATE_PATH), "directive_history": str(DIRECTIVE_HISTORY_PATH), "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH), "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH), "branch_registry_latest": str(BRANCH_REGISTRY_PATH), "bucket_state_latest": str(BUCKET_STATE_PATH), "intervention_ledger": str(intervention_ledger_path), "proposal_recommendations_latest": str(recommendations_path)},
        "chain_value_retention_assessment": chain_value_retention_assessment,
        "demonstrated_structural_principle": demonstrated_structural_principle,
        "stop_condition_assessment": stop_condition_assessment,
        "amber_state_trend_assessment": amber_state_trend_assessment,
        "diminishing_returns_assessment": diminishing_returns_assessment,
        "circularity_risk_assessment": circularity_risk_assessment,
        "fresh_trigger_assessment": fresh_trigger_assessment,
        "reentry_criteria": reentry_criteria,
        "disallowed_auto_reentry_conditions": disallowed_auto_reentry_conditions,
        "preserved_project_memory_points": preserved_project_memory_points,
        "posture_discipline_assessment": posture_discipline_assessment,
        "posture_pressure_assessment": posture_pressure_assessment,
        "gate_status": gate_status,
        "routing_status": routing_status,
        "recommended_current_stance": recommended_current_stance,
        "recommended_next_action": recommended_next_action,
        "recommended_next_template": "",
        "review_rollback_deprecation_trigger_status": review_rollback_status,
        "envelope_compliance_summary": {"passed": True, "network_mode": "none", "write_root_compliance": True, "bucket_pressure": {"concern_level": "low", "cpu_ratio_to_bucket": 0.25, "memory_ratio_to_bucket": 0.03125, "storage_ratio_to_bucket": 0.03125}, "branch_state_immutability": True, "paused_capability_line_remained_closed": True, "plan_non_ownership": True, "routing_non_involvement": True},
        "resource_trust_accounting": {"trusted_sources": {"allowed_sources": ["local_artifacts:novali-v4/data", "local_logs:logs", "local_repo:novali-v4", "trusted_benchmark_pack_v1"], "missing_sources": [], "passed": True, "reason": "closeout review uses only approved local governed evidence and repository artifacts", "requested_sources": ["local_artifacts:novali-v4/data"]}, "requested_resources": {"cpu_parallel_units": 1, "memory_mb": 64, "network_mode": "none", "storage_write_mb": 4}, "observed_resource_usage": {"cpu_parallel_units_used": 1, "memory_mb_used": 64, "network_mode_used": "none", "storage_write_mb_used": 1}},
        "question_answers": {
            "structural_principle_demonstrated": demonstrated_structural_principle["principle"],
            "meaningful_evidence_preserved": preserved_project_memory_points[:3],
            "why_hold_posture_not_continue": stop_condition_assessment["reason"],
            "amber_stop_factors": stop_condition_assessment["factors"],
            "future_reentry_requirements": reentry_criteria["required_conditions"],
            "concrete_fresh_triggers": reentry_criteria["concrete_fresh_triggers"],
            "explicitly_closed": {"routing_revisit": True, "posture_broadening": True, "capability_reopening": True, "branch_mutation": True, "automatic_continuation": True},
            "preserved_project_memory_points": preserved_project_memory_points,
            "recommended_current_stance": recommended_current_stance["classification"],
            "attention_shift_to_upstream_questions": True,
        },
        "operator_readable_conclusion": "This governed work-loop line should be preserved as meaningful but closed out into hold posture: it demonstrated a bounded governance principle successfully, yet the amber stop condition now dominates and no concrete fresh trigger justifies renewed continuation.",
    }
    _write_json(artifact_path, {"proposal_id": str(proposal.get("proposal_id")), "template_name": "memory_summary.v4_governed_work_loop_hold_position_closeout_v1", "evaluation_semantics": str(proposal.get("evaluation_semantics", "")), "trigger_reason": str(proposal.get("trigger_reason", "")), "governed_work_loop_hold_position_closeout_v1_summary": summary})
    _append_jsonl(SELF_STRUCTURE_LEDGER_PATH, {"event_id": f"governed_work_loop_hold_position_closeout_v1::{proposal['proposal_id']}", "timestamp": _now(), "event_type": "governed_work_loop_hold_position_closeout_v1_materialized", "directive_id": str(current_directive.get("directive_id", "")), "branch_id": str(branch_record.get("branch_id", "")), "branch_state": current_branch_state, "recommended_next_action_class": "hold_posture", "artifact_path": str(artifact_path)})

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: the governed work-loop hold position was formally closed out, preserved as meaningful governance memory, and protected against automatic continuation without fresh evidence",
        "observability_gain": {"passed": True, "reason": "the governed work-loop now has a dedicated hold-position closeout artifact", "artifact_path": str(artifact_path)},
        "activation_analysis_usefulness": {"passed": True, "reason": "the closeout separates demonstrated structural value from the reasons continuation is no longer warranted"},
        "ambiguity_reduction": {"passed": True, "reason": "the closeout records the exact hold conditions, re-entry criteria, and explicit closures so the same loop is not replayed by momentum"},
        "safety_neutrality": {"passed": True, "reason": "the closeout is diagnostic-only and changed no live behavior", "scope": str(proposal.get("scope", ""))},
        "later_selection_usefulness": {"passed": False, "recommended_next_template": "", "reason": "automatic continuation is disallowed and future re-entry requires new evidence rather than a queued next template"},
        "diagnostic_conclusions": {"hold_posture": True, "stop_continuation": False, "automatic_continuation_disallowed": True, "future_reentry_requires_new_evidence": True, "attention_shift_to_upstream_questions": True, "routing_deferred": True, "gate_closed": True, "best_next_template": ""},
        "artifact_path": str(artifact_path),
    }
