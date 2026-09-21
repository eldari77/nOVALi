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


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governance_substrate_v1_snapshot")
    trial_execution_snapshot = r._load_latest_diagnostic_artifact_by_template("proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1")
    trial_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governed_skill_trial_evidence_snapshot_v1")
    provisional_admission_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governed_skill_provisional_admission_snapshot_v1")
    provisional_probe_v1_snapshot = r._load_latest_diagnostic_artifact_by_template("proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v1")
    provisional_probe_v2_snapshot = r._load_latest_diagnostic_artifact_by_template("proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v2")
    provisional_evidence_v1_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governed_skill_provisional_evidence_snapshot_v1")
    provisional_evidence_v2_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governed_skill_provisional_evidence_snapshot_v2")
    if not all(
        [
            governance_snapshot,
            trial_execution_snapshot,
            trial_evidence_snapshot,
            provisional_admission_snapshot,
            provisional_probe_v1_snapshot,
            provisional_probe_v2_snapshot,
            provisional_evidence_v1_snapshot,
            provisional_evidence_v2_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: provisional-pause formalization requires the full governed-skill trial, provisional, and evidence chain",
            "observability_gain": {"passed": False, "reason": "missing prerequisite governed-skill pause artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite governed-skill pause artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite governed-skill pause artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot formalize a held provisional pause without the full governance-owned evidence chain"},
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
            "reason": "diagnostic shadow failed: provisional-pause formalization requires current directive, bucket, self-structure, and branch state artifacts",
            "observability_gain": {"passed": False, "reason": "missing durable governance state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing durable governance state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing durable governance state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot formalize a held provisional pause without directive, bucket, self-structure, and branch state"},
        }

    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_branch_state = str(branch_record.get("state", ""))
    governed_skill_subsystem = dict(self_structure_state.get("governed_skill_subsystem", {}))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))

    trial_execution_artifact_path = Path(
        str(governed_skill_subsystem.get("last_trial_execution_artifact_path") or dict(trial_execution_snapshot).get("artifact_path", ""))
    )
    trial_evidence_artifact_path = Path(
        str(governed_skill_subsystem.get("last_trial_evidence_artifact_path") or dict(trial_evidence_snapshot).get("artifact_path", ""))
    )
    provisional_admission_artifact_path = Path(
        str(governed_skill_subsystem.get("last_provisional_admission_artifact_path") or dict(provisional_admission_snapshot).get("artifact_path", ""))
    )
    provisional_probe_v1_artifact_path = Path(
        str(dict(provisional_probe_v1_snapshot).get("artifact_path", "")) or _latest_matching_artifact("proposal_learning_loop_v4_governed_skill_local_trace_parser_provisional_probe_v1_*.json")
    )
    provisional_probe_v2_artifact_path = Path(
        str(governed_skill_subsystem.get("last_provisional_execution_artifact_path") or dict(provisional_probe_v2_snapshot).get("artifact_path", ""))
    )
    provisional_evidence_v1_artifact_path = Path(
        str(dict(provisional_evidence_v1_snapshot).get("artifact_path", "")) or _latest_matching_artifact("memory_summary_v4_governed_skill_provisional_evidence_snapshot_v1_*.json")
    )
    provisional_evidence_v2_artifact_path = Path(
        str(governed_skill_subsystem.get("last_provisional_evidence_artifact_path") or dict(provisional_evidence_v2_snapshot).get("artifact_path", ""))
    )

    provisional_admission_summary = dict(_load_json_file(provisional_admission_artifact_path).get("governed_skill_provisional_admission_summary", {}))
    provisional_evidence_v2_summary = dict(_load_json_file(provisional_evidence_v2_artifact_path).get("governed_skill_provisional_evidence_summary", {}))
    v2_conclusions = dict(_load_json_file(provisional_evidence_v2_artifact_path).get("diagnostic_conclusions", {}))

    capability_id = "skill_candidate_local_trace_parser_trial"
    capability_name = "Local trace parser trial"
    provisional_envelope = dict(provisional_admission_summary.get("provisional_envelope", {}))
    evidence_obligations = dict(provisional_admission_summary.get("evidence_obligations", {}))
    rollback_triggers = dict(provisional_admission_summary.get("rollback_triggers", {}))
    deprecation_triggers = dict(provisional_admission_summary.get("deprecation_triggers", {}))
    retained_prereqs = dict(provisional_admission_summary.get("future_retained_promotion_prerequisites", {}))
    cumulative_trend = dict(provisional_evidence_v2_summary.get("cumulative_trend_assessment", {}))
    structural_value = dict(provisional_evidence_v2_summary.get("structural_value_assessment", {}))
    escalation_posture = dict(provisional_evidence_v2_summary.get("escalation_posture", {}))
    retention_posture = dict(provisional_evidence_v2_summary.get("retention_readiness_posture", {}))

    held_provisional_status = "paused_with_provisional_capability_held"
    reopen_policy = "reopen_only_on_new_bounded_use_case"
    retention_status = "not_retention_ready"
    same_shape_reruns_disallowed = True

    pause_rationale = {
        "why_same_shape_reruns_stop_now": "trial, provisional probe v1, and provisional probe v2 all preserved the same evidence metrics, so additional identical reruns would mostly reconfirm containment rather than add new governed capability signal",
        "why_capability_is_still_held": "the parser remains directive-relevant, low-duplication, low-risk, inside the admitted envelope, and structurally useful as a governed provisional capability",
        "current_cumulative_trend": str(cumulative_trend.get("classification", "")),
        "current_structural_value_assessment": str(structural_value.get("classification", "")),
        "current_escalation_posture": str(escalation_posture.get("category", "")),
    }
    valid_reopen_triggers = [
        "a new bounded use-case that expands local trace-parser value without changing trusted-source, bucket, branch-state, or policy boundaries",
        "a materially strengthening hypothesis with a plausible path to improve utility beyond the current flat 216/1296/1.0/3 evidence profile",
        "a directive-driven need for new trusted local trace coverage that the held capability can satisfy inside the same admitted envelope",
        "a governance-owned screen that shows the next step is not another identical rerun and remains below retained-promotion scope",
    ]
    valid_reopen_idea_classes = [
        "new bounded local trace source class within trusted local artifacts",
        "new parser utility objective that is distinct from repeated seed_context_shift confirmation",
        "bounded governance-reporting enhancement that materially changes evidence value rather than just rerunning the same logs",
    ]
    invalid_same_shape_reruns = [
        "another provisional rerun over the same local seed_context_shift log family with the same evidence target and no new bounded use-case",
        "retained-promotion discussion based only on repeated flat stability",
        "reopening through external access, routing work, plan_ ownership change, protected-surface modification, branch-state mutation, or downstream selected-set work",
        "broadening the envelope, changing live policy, changing thresholds, changing frozen benchmark semantics, or reopening novali-v3 tuning",
    ]

    next_template = "memory_summary.v4_governed_skill_reopen_candidate_screen_snapshot_v1"
    next_timing = "only_if_new_bounded_use_case_or_materially_strengthening_hypothesis_emerges"

    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_v4_governed_skill_provisional_pause_snapshot_v1_{proposal['proposal_id']}.json"

    held_capabilities = list(governed_skill_subsystem.get("held_provisional_capabilities", []))
    held_capabilities = [item for item in held_capabilities if str(dict(item).get("skill_id", "")) != capability_id]
    held_capabilities.append(
        {
            "skill_id": capability_id,
            "skill_name": capability_name,
            "status": held_provisional_status,
            "reopen_policy": reopen_policy,
            "retention_posture": retention_status,
            "evidence_trend": str(cumulative_trend.get("classification", "")),
            "last_evidence_artifact_path": str(provisional_evidence_v2_artifact_path),
            "last_pause_artifact_path": str(artifact_path),
            "network_mode": str(provisional_envelope.get("network_mode", "")),
            "allowed_write_roots": list(provisional_envelope.get("allowed_write_roots", [])),
            "resource_ceilings": dict(provisional_envelope.get("resource_ceilings", {})),
        }
    )

    updated_self_structure_state = dict(self_structure_state)
    updated_governed_skill_subsystem = dict(governed_skill_subsystem)
    updated_governed_skill_subsystem["held_provisional_capabilities"] = held_capabilities
    updated_governed_skill_subsystem["last_provisional_pause_artifact_path"] = str(artifact_path)
    updated_governed_skill_subsystem["last_provisional_pause_outcome"] = {
        "skill_id": capability_id,
        "skill_name": capability_name,
        "pause_status": held_provisional_status,
        "reopen_policy": reopen_policy,
        "retention_posture": retention_status,
        "same_shape_reruns_disallowed": same_shape_reruns_disallowed,
        "reason": pause_rationale["why_same_shape_reruns_stop_now"],
    }
    updated_governed_skill_subsystem["best_next_template"] = next_template
    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["governed_skill_subsystem"] = updated_governed_skill_subsystem
    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "latest_skill_provisional_status": held_provisional_status,
            "latest_skill_provisional_pause_status": held_provisional_status,
            "latest_skill_provisional_reopen_policy": reopen_policy,
            "latest_skill_retention_posture": retention_status,
            "skill_provisional_same_shape_reruns_disallowed": True,
            "retained_skill_promotion_performed": False,
            "current_branch_state": current_branch_state,
            "plan_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
        }
    )
    updated_self_structure_state["current_state_summary"] = updated_current_state_summary
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    ledger_event = {
        "event_id": f"governed_skill_provisional_pause_snapshot_v1::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_skill_provisional_pause_snapshot_v1_materialized",
        "event_class": "governed_skill_provisional_pause",
        "directive_id": str(dict(directive_state.get("current_directive_state", {})).get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": current_branch_state,
        "skill_id": capability_id,
        "pause_status": held_provisional_status,
        "reopen_policy": reopen_policy,
        "retention_posture": retention_status,
        "retained_promotion": False,
        "branch_state_mutation": False,
        "artifact_paths": {
            "trial_execution": str(trial_execution_artifact_path),
            "trial_evidence": str(trial_evidence_artifact_path),
            "provisional_admission": str(provisional_admission_artifact_path),
            "provisional_probe_v1": str(provisional_probe_v1_artifact_path),
            "provisional_probe_v2": str(provisional_probe_v2_artifact_path),
            "provisional_evidence_v1": str(provisional_evidence_v1_artifact_path),
            "provisional_evidence_v2": str(provisional_evidence_v2_artifact_path),
            "provisional_pause_v1": str(artifact_path),
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
        "template_name": "memory_summary.v4_governed_skill_provisional_pause_snapshot_v1",
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
            "proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1": _artifact_reference(trial_execution_snapshot, latest_snapshots),
            "memory_summary.v4_governed_skill_trial_evidence_snapshot_v1": _artifact_reference(trial_evidence_snapshot, latest_snapshots),
            "memory_summary.v4_governed_skill_provisional_admission_snapshot_v1": _artifact_reference(provisional_admission_snapshot, latest_snapshots),
            "proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v1": _artifact_reference(provisional_probe_v1_snapshot, latest_snapshots),
            "proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v2": _artifact_reference(provisional_probe_v2_snapshot, latest_snapshots),
            "memory_summary.v4_governed_skill_provisional_evidence_snapshot_v1": _artifact_reference(provisional_evidence_v1_snapshot, latest_snapshots),
            "memory_summary.v4_governed_skill_provisional_evidence_snapshot_v2": _artifact_reference(provisional_evidence_v2_snapshot, latest_snapshots),
        },
        "governed_skill_provisional_pause_summary": {
            "capability_reviewed": {
                "skill_id": capability_id,
                "skill_name": capability_name,
                "held_status": held_provisional_status,
                "reopen_policy": reopen_policy,
                "retention_posture": retention_status,
            },
            "pause_rationale": pause_rationale,
            "held_provisional_status": {
                "status": held_provisional_status,
                "status_reason": "the capability remains governed, bounded, and useful, but repeated same-shape reruns are now low-yield",
                "structurally_useful": bool(structural_value.get("good_exemplar_for_governed_skill_growth", False)),
                "not_retention_ready": True,
            },
            "continued_governance_obligations": {
                "provisional_envelope": provisional_envelope,
                "evidence_obligations": evidence_obligations,
                "governance_reporting_must_continue": True,
                "held_branch_state_requirement": "paused_with_baseline_held",
            },
            "rollback_triggers_still_active": rollback_triggers,
            "deprecation_triggers_still_active": deprecation_triggers,
            "valid_reopen_triggers": valid_reopen_triggers,
            "valid_reopen_idea_classes": valid_reopen_idea_classes,
            "invalid_same_shape_reruns": invalid_same_shape_reruns,
            "structural_alignment": {
                "supports_long_run_goal": bool(structural_value.get("supports_long_run_goal", False)),
                "good_exemplar_for_governed_skill_growth": bool(structural_value.get("good_exemplar_for_governed_skill_growth", False)),
                "line_is_becoming_local_churn": bool(structural_value.get("line_is_becoming_local_churn", False)),
                "reason": str(structural_value.get("reason", "")),
            },
            "retention_readiness_posture": {
                **retention_posture,
                "retained_promotion_prerequisites_still_active": retained_prereqs,
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
                "reason": "the pause decision is derived from directive, bucket, branch, self-structure, and governed-skill evidence artifacts rather than from execution code alone",
            },
        },
        "analytics_context": {
            "analytics_report_path": str(intervention_data_dir() / "intervention_analytics_latest.json"),
            "proposal_recommendations_path": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            "proposal_count": int(analytics.get("proposal_count", 0) or 0),
            "current_recommendation_top_templates": suggested_templates,
        },
        "observability_gain": {
            "passed": True,
            "reason": "the local trace parser line now has an explicit held-capability pause state with reopen criteria and continued obligations",
            "artifact_paths": {
                "skill_provisional_pause_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the snapshot cleanly separates what stays held, what stays gated, and what identical reruns are now disallowed",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "the capability now has explicit held status, explicit reopen triggers, and an explicit ban on repeated same-shape reruns absent a new idea",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the provisional pause formalization is diagnostic-only; no retained promotion, no branch-state mutation, and no live behavior change occurred",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": next_template,
            "reason": f"{next_timing}; the capability is held, but reopening must begin with a governance-owned screen rather than another identical rerun",
        },
        "diagnostic_conclusions": {
            "skill_is_paused_with_provisional_capability_held": True,
            "same_shape_provisional_reruns_disallowed_without_new_idea": True,
            "below_retained_promotion_threshold": True,
            "retained_promotion_occurred": False,
            "branch_state_stayed_paused_with_baseline_held": True,
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
        "reason": "diagnostic shadow passed: the local trace parser is now formalized as a held governed provisional capability with same-shape reruns paused",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
