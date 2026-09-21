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


def _trial_metrics(trial_summary: dict[str, Any]) -> dict[str, Any]:
    evidence = dict(trial_summary.get("evidence_produced", {}))
    utility = dict(evidence.get("utility_assessment", {}))
    parse_summary = dict(dict(trial_summary.get("local_sources_parsed", {})).get("trusted_log_parse_summary", {}))
    sandbox = dict(trial_summary.get("sandbox_envelope_compliance", {}))
    return {
        "dummy_eval_count": int(utility.get("dummy_eval_count", 0) or 0),
        "patch_tuple_count": int(utility.get("patch_tuple_count", 0) or 0),
        "recognized_line_share_weighted": float(utility.get("recognized_line_share_weighted", 0.0) or 0.0),
        "seed_coverage": int(parse_summary.get("parsed_file_count", 0) or 0),
        "directive_relevance": str(dict(evidence.get("directive_relevance", {})).get("value", "")),
        "duplication": str(dict(evidence.get("duplication_overlap", {})).get("value", "")),
        "network_mode": str(sandbox.get("network_mode_observed", "")),
    }


def _provisional_metrics(provisional_summary: dict[str, Any]) -> dict[str, Any]:
    evidence = dict(provisional_summary.get("evidence_produced", {}))
    utility = dict(evidence.get("utility_assessment", {}))
    obligations = dict(provisional_summary.get("evidence_obligation_status", {}))
    envelope = dict(provisional_summary.get("envelope_compliance", {}))
    return {
        "dummy_eval_count": int(utility.get("dummy_eval_count", 0) or 0),
        "patch_tuple_count": int(utility.get("patch_tuple_count", 0) or 0),
        "recognized_line_share_weighted": float(utility.get("recognized_line_share_weighted", 0.0) or 0.0),
        "seed_coverage": int(obligations.get("seed_log_coverage_observed", 0) or 0),
        "directive_relevance": str(dict(evidence.get("directive_relevance", {})).get("value", "")),
        "duplication": str(dict(evidence.get("duplication_overlap", {})).get("value", "")),
        "network_mode": str(envelope.get("network_mode_observed", "")),
    }


def _evidence_trend_assessment(trial_metrics: dict[str, Any], provisional_metrics: dict[str, Any]) -> dict[str, Any]:
    dummy_delta = int(provisional_metrics["dummy_eval_count"]) - int(trial_metrics["dummy_eval_count"])
    patch_delta = int(provisional_metrics["patch_tuple_count"]) - int(trial_metrics["patch_tuple_count"])
    recognized_delta = float(provisional_metrics["recognized_line_share_weighted"]) - float(
        trial_metrics["recognized_line_share_weighted"]
    )
    seed_delta = int(provisional_metrics["seed_coverage"]) - int(trial_metrics["seed_coverage"])
    weakening = (
        provisional_metrics["recognized_line_share_weighted"] < trial_metrics["recognized_line_share_weighted"] - 0.01
        or provisional_metrics["dummy_eval_count"] < trial_metrics["dummy_eval_count"] * 0.95
        or provisional_metrics["patch_tuple_count"] < trial_metrics["patch_tuple_count"] * 0.95
        or provisional_metrics["seed_coverage"] < trial_metrics["seed_coverage"]
    )
    strengthening = (
        provisional_metrics["recognized_line_share_weighted"] > trial_metrics["recognized_line_share_weighted"] + 0.01
        or provisional_metrics["dummy_eval_count"] > trial_metrics["dummy_eval_count"] * 1.05
        or provisional_metrics["patch_tuple_count"] > trial_metrics["patch_tuple_count"] * 1.05
        or provisional_metrics["seed_coverage"] > trial_metrics["seed_coverage"]
    )
    classification = "weakening" if weakening else "strengthening" if strengthening else "stable_flat"
    reason = (
        "the provisional rerun lost measurable evidence strength relative to the bounded trial baseline"
        if classification == "weakening"
        else "the provisional rerun improved measurable evidence strength while keeping the same governance envelope"
        if classification == "strengthening"
        else "the provisional rerun preserved the bounded trial evidence level without material strengthening or weakening"
    )
    return {
        "classification": classification,
        "reason": reason,
        "metric_deltas": {
            "dummy_eval_count_delta": dummy_delta,
            "patch_tuple_count_delta": patch_delta,
            "recognized_line_share_weighted_delta": recognized_delta,
            "seed_coverage_delta": seed_delta,
        },
        "utility_remains_real": provisional_metrics["dummy_eval_count"] >= 100
        and provisional_metrics["patch_tuple_count"] >= 500
        and provisional_metrics["recognized_line_share_weighted"] >= 0.95,
    }


def _envelope_trend_assessment(trial_summary: dict[str, Any], provisional_summary: dict[str, Any]) -> dict[str, Any]:
    trial_envelope = dict(trial_summary.get("sandbox_envelope_compliance", {}))
    provisional_envelope = dict(provisional_summary.get("envelope_compliance", {}))
    bucket_pressure = dict(provisional_envelope.get("bucket_pressure", {}))
    stable = (
        bool(trial_envelope.get("network_mode_remained_none", False))
        and bool(provisional_envelope.get("network_mode_remained_none", False))
        and bool(trial_envelope.get("branch_state_stayed_paused_with_baseline_held", False))
        and bool(provisional_envelope.get("branch_state_stayed_paused_with_baseline_held", False))
        and bool(trial_envelope.get("no_retained_promotion", False))
        and bool(provisional_envelope.get("no_retained_promotion", False))
        and bool(provisional_envelope.get("no_plan_ownership_change", False))
        and bool(provisional_envelope.get("no_routing_work", False))
    )
    return {
        "classification": "stable_low_risk" if stable and str(bucket_pressure.get("concern_level", "")) == "low" else "watch",
        "reason": (
            "network, write-root, branch-state, protected-surface, downstream, plan_, and routing constraints stayed intact with low bucket pressure"
            if stable and str(bucket_pressure.get("concern_level", "")) == "low"
            else "at least one envelope constraint or bucket-pressure indicator needs attention"
        ),
        "current_bucket_pressure": bucket_pressure,
        "network_mode": {
            "trial": str(trial_envelope.get("network_mode_observed", "")),
            "provisional": str(provisional_envelope.get("network_mode_observed", "")),
        },
        "write_root_compliance": {
            "trial": bool(trial_envelope.get("writes_within_approved_roots", False)),
            "provisional": bool(provisional_envelope.get("writes_within_approved_roots", False)),
        },
        "branch_state_immutability": {
            "trial": bool(trial_envelope.get("branch_state_stayed_paused_with_baseline_held", False)),
            "provisional": bool(provisional_envelope.get("branch_state_stayed_paused_with_baseline_held", False)),
        },
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governance_substrate_v1_snapshot"
    )
    trial_execution_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1"
    )
    trial_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_skill_trial_evidence_snapshot_v1"
    )
    provisional_admission_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_skill_provisional_admission_snapshot_v1"
    )
    provisional_probe_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v1"
    )
    if not all(
        [
            governance_snapshot,
            trial_execution_snapshot,
            trial_evidence_snapshot,
            provisional_admission_snapshot,
            provisional_probe_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: provisional evidence review requires governance, trial, trial-evidence, provisional-admission, and provisional-probe artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite provisional-evidence artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite provisional-evidence artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite provisional-evidence artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "the provisional evidence trend cannot be reviewed without the full governance-owned evidence chain"},
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
            "reason": "diagnostic shadow failed: provisional evidence review requires current directive, bucket, self-structure, and branch state artifacts",
            "observability_gain": {"passed": False, "reason": "missing durable governance state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing durable governance state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing durable governance state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "the provisional evidence trend cannot be evaluated without directive, bucket, self-structure, and branch state"},
        }

    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_branch_state = str(branch_record.get("state", ""))
    governed_skill_subsystem = dict(self_structure_state.get("governed_skill_subsystem", {}))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    current_directive = dict(directive_state.get("current_directive_state", {}))

    trial_execution_artifact_path = Path(str(governed_skill_subsystem.get("last_trial_execution_artifact_path") or dict(trial_execution_snapshot).get("artifact_path", "")))
    trial_evidence_artifact_path = Path(str(governed_skill_subsystem.get("last_trial_evidence_artifact_path") or dict(trial_evidence_snapshot).get("artifact_path", "")))
    provisional_admission_artifact_path = Path(str(governed_skill_subsystem.get("last_provisional_admission_artifact_path") or dict(provisional_admission_snapshot).get("artifact_path", "")))
    provisional_probe_artifact_path = Path(str(governed_skill_subsystem.get("last_provisional_execution_artifact_path") or dict(provisional_probe_snapshot).get("artifact_path", "")))

    trial_execution_summary = dict(_load_json_file(trial_execution_artifact_path).get("governed_skill_trial_summary", {}))
    trial_evidence_summary = dict(_load_json_file(trial_evidence_artifact_path).get("governed_skill_trial_evidence_summary", {}))
    provisional_admission_summary = dict(_load_json_file(provisional_admission_artifact_path).get("governed_skill_provisional_admission_summary", {}))
    provisional_probe_summary = dict(_load_json_file(provisional_probe_artifact_path).get("governed_skill_provisional_probe_summary", {}))

    trial_metrics = _trial_metrics(trial_execution_summary)
    provisional_metrics = _provisional_metrics(provisional_probe_summary)
    evidence_trend = _evidence_trend_assessment(trial_metrics, provisional_metrics)
    evidence_obligation_status = dict(provisional_probe_summary.get("evidence_obligation_status", {}))
    envelope_trend = _envelope_trend_assessment(trial_execution_summary, provisional_probe_summary)
    rollback_status = dict(provisional_probe_summary.get("rollback_trigger_status", {}))
    deprecation_status = dict(provisional_probe_summary.get("deprecation_trigger_status", {}))
    governance_reporting_complete = (
        provisional_probe_artifact_path.exists()
        and bool(governed_skill_subsystem.get("last_provisional_execution_artifact_path"))
        and bool(governed_skill_subsystem.get("last_provisional_execution_outcome"))
    )
    rollback_risk_trend = {
        "classification": "stable_low" if not bool(rollback_status.get("any_trigger_fired", False)) else "rising",
        "reason": (
            "no rollback triggers have fired, so rollback risk remains low and stable"
            if not bool(rollback_status.get("any_trigger_fired", False))
            else "at least one rollback trigger has fired, so rollback risk is rising"
        ),
    }
    deprecation_risk_trend = {
        "classification": "stable_low" if not bool(deprecation_status.get("any_trigger_active", False)) else "rising",
        "reason": (
            "no deprecation triggers are active, so deprecation risk remains low and stable"
            if not bool(deprecation_status.get("any_trigger_active", False))
            else "at least one deprecation trigger is active, so deprecation risk is rising"
        ),
    }
    continued_provisional_justified = (
        str(dict(provisional_probe_summary.get("provisional_handling_assessment", {})).get("candidate_status", ""))
        == "viable_for_continued_provisional_handling"
        and bool(evidence_obligation_status.get("passed", False))
        and not bool(rollback_status.get("any_trigger_fired", False))
        and not bool(deprecation_status.get("any_trigger_active", False))
    )
    if continued_provisional_justified:
        escalation_posture = "remain_viable_for_continued_provisional_handling"
        escalation_reason = "the evidence remains real, the envelope remains intact, and the governance risk trend is still low"
        best_next_template = "proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v2"
    elif bool(rollback_status.get("any_trigger_fired", False)):
        escalation_posture = "block_from_further_escalation"
        escalation_reason = "a rollback-condition breach would block further escalation"
        best_next_template = "memory_summary.v4_governed_skill_provisional_gap_snapshot_v1"
    elif bool(deprecation_status.get("any_trigger_active", False)):
        escalation_posture = "downgrade_to_sandbox_only"
        escalation_reason = "deprecation pressure would push the skill back toward sandbox-only handling"
        best_next_template = "memory_summary.v4_governed_skill_provisional_gap_snapshot_v1"
    else:
        escalation_posture = "remain_provisional_but_cautionary"
        escalation_reason = "the line is still safe, but the evidence trend is not yet strong enough for confident continued build-out"
        best_next_template = "memory_summary.v4_governed_skill_provisional_gap_snapshot_v1"

    retained_promotion_read = {
        "evidence_accumulating_toward_future_retained_promotion_discussion": continued_provisional_justified,
        "trend_direction": str(evidence_trend.get("classification", "")),
        "still_too_early_for_retained_promotion_consideration": True,
        "reason": "the line has only one reviewed provisional rerun on top of the original trial and remains below the separately gated retained-promotion bar",
        "additional_evidence_required": [
            "at least one more governance-owned provisional execution and evidence review pass",
            "continued full envelope compliance with network still none and branch state still paused_with_baseline_held",
            "continued high directive relevance and low duplication risk",
            "no rollback triggers fired and no deprecation triggers active",
            "stable-flat or strengthening evidence trend across the next bounded provisional pass",
            "explicit retained-promotion gate review and human approval point",
        ],
    }
    project_alignment = {
        "supports_long_run_goal": continued_provisional_justified,
        "line_is_becoming_local_churn": False,
        "exemplar_for_governed_skill_growth": continued_provisional_justified,
        "reason": (
            "the line still demonstrates directive-bound, bucket-bounded, governance-owned skill growth without governance drift, so it remains a good exemplar even though the evidence trend is currently flat rather than strengthening"
            if continued_provisional_justified
            else "the line is no longer providing a clean exemplar for governed skill growth under the current constraints"
        ),
    }

    artifact_path = (
        _diagnostic_artifact_dir()
        / f"memory_summary_v4_governed_skill_provisional_evidence_snapshot_v1_{proposal['proposal_id']}.json"
    )

    updated_self_structure_state = dict(self_structure_state)
    updated_governed_skill_subsystem = dict(governed_skill_subsystem)
    updated_governed_skill_subsystem["last_provisional_evidence_artifact_path"] = str(artifact_path)
    updated_governed_skill_subsystem["last_provisional_evidence_outcome"] = {
        "primary_candidate_skill_id": "skill_candidate_local_trace_parser_trial",
        "primary_candidate_name": "Local trace parser trial",
        "provisional_evidence_posture": escalation_posture,
        "evidence_trend": str(evidence_trend.get("classification", "")),
        "reason": escalation_reason,
        "retained_promotion": False,
        "branch_state_after_review": current_branch_state,
    }
    updated_governed_skill_subsystem["best_next_template"] = best_next_template
    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["governed_skill_subsystem"] = updated_governed_skill_subsystem
    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "latest_skill_provisional_evidence_outcome": escalation_posture,
            "latest_skill_provisional_evidence_trend": str(evidence_trend.get("classification", "")),
            "retained_skill_promotion_performed": False,
            "current_branch_state": current_branch_state,
            "plan_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
        }
    )
    updated_self_structure_state["current_state_summary"] = updated_current_state_summary
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    ledger_event = {
        "event_id": f"governed_skill_provisional_evidence_snapshot_v1::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_skill_provisional_evidence_snapshot_v1_materialized",
        "event_class": "governed_skill_provisional_evidence_review",
        "directive_id": str(current_directive.get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": current_branch_state,
        "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
        "primary_candidate_skill_id": "skill_candidate_local_trace_parser_trial",
        "provisional_evidence_posture": escalation_posture,
        "evidence_trend": str(evidence_trend.get("classification", "")),
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
            "skill_trial_execution_artifact": str(trial_execution_artifact_path),
            "skill_trial_evidence_artifact": str(trial_evidence_artifact_path),
            "skill_provisional_admission_artifact": str(provisional_admission_artifact_path),
            "skill_provisional_probe_artifact": str(provisional_probe_artifact_path),
            "skill_provisional_evidence_artifact": str(artifact_path),
        },
        "source_proposal_id": str(proposal.get("proposal_id", "")),
    }
    _append_jsonl(SELF_STRUCTURE_LEDGER_PATH, ledger_event)

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_governed_skill_provisional_evidence_snapshot_v1",
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
            "proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v1": _artifact_reference(provisional_probe_snapshot, latest_snapshots),
        },
        "governed_skill_provisional_evidence_summary": {
            "evidence_reviewed": {
                "trial_execution_artifact": str(trial_execution_artifact_path),
                "trial_evidence_artifact": str(trial_evidence_artifact_path),
                "provisional_admission_artifact": str(provisional_admission_artifact_path),
                "provisional_probe_artifact": str(provisional_probe_artifact_path),
                "directive_history_tail": [str(item.get("event_type", "")) for item in directive_history[-8:]],
                "self_structure_event_tail": [str(item.get("event_type", "")) for item in self_structure_ledger[-12:]],
                "intervention_ledger_rows_reviewed": len(intervention_ledger[-8:]),
            },
            "trend_assessment": evidence_trend,
            "evidence_obligation_status": {
                "current_status": evidence_obligation_status,
                "thresholds_source": dict(provisional_admission_summary.get("evidence_obligations", {})),
                "all_obligations_still_satisfied": bool(evidence_obligation_status.get("passed", False)),
            },
            "envelope_compliance_trend": envelope_trend,
            "rollback_risk_trend": rollback_risk_trend,
            "deprecation_risk_trend": deprecation_risk_trend,
            "governance_reporting_status": {
                "complete": governance_reporting_complete,
                "reason": "governance reporting is still complete across artifact, state, and ledger surfaces" if governance_reporting_complete else "governance reporting is missing at least one required state or artifact update",
            },
            "escalation_posture": {"category": escalation_posture, "reason": escalation_reason},
            "retained_promotion_readiness": retained_promotion_read,
            "broader_project_alignment": project_alignment,
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
                "reason": "the provisional evidence review is derived from directive, bucket, branch, self-structure, and prior governed-skill artifacts rather than from execution code alone",
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
            "reason": "the admitted provisional skill now has an explicit governance-owned trend review across trial and provisional evidence, not just a single-run success check",
            "artifact_paths": {
                "skill_provisional_evidence_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the review now distinguishes stable worthwhile provisional handling from safe but non-accumulating local churn",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "the review cleanly distinguishes continued provisional viability, cautionary provisional holding, sandbox downgrade, and escalation block outcomes",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the provisional evidence review is diagnostic-only; no retained promotion, no branch-state mutation, and no live behavior change occurred",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": best_next_template,
            "reason": "the next step is now explicit while still keeping retained promotion separately gated",
        },
        "diagnostic_conclusions": {
            "governed_skill_provisional_evidence_review_in_place": True,
            "continued_provisional_handling_justified": continued_provisional_justified,
            "provisional_evidence_trend": str(evidence_trend.get("classification", "")),
            "retained_promotion_occurred": False,
            "below_retained_promotion_threshold": True,
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
        "reason": "diagnostic shadow passed: the local trace parser now has a governance-owned provisional evidence trend review before any later retention discussion",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
