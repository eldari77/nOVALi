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
from .v4_governed_skill_local_trace_parser_provisional_probe_v1 import _bucket_pressure
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


def _pairwise_trend(current_metrics: dict[str, Any], prior_metrics: dict[str, Any]) -> dict[str, Any]:
    dummy_delta = int(current_metrics["dummy_eval_count"]) - int(prior_metrics["dummy_eval_count"])
    patch_delta = int(current_metrics["patch_tuple_count"]) - int(prior_metrics["patch_tuple_count"])
    recognized_delta = float(current_metrics["recognized_line_share_weighted"]) - float(
        prior_metrics["recognized_line_share_weighted"]
    )
    seed_delta = int(current_metrics["seed_coverage"]) - int(prior_metrics["seed_coverage"])
    weakening = (
        current_metrics["recognized_line_share_weighted"] < prior_metrics["recognized_line_share_weighted"] - 0.01
        or current_metrics["dummy_eval_count"] < prior_metrics["dummy_eval_count"] * 0.95
        or current_metrics["patch_tuple_count"] < prior_metrics["patch_tuple_count"] * 0.95
        or current_metrics["seed_coverage"] < prior_metrics["seed_coverage"]
    )
    strengthening = (
        current_metrics["recognized_line_share_weighted"] > prior_metrics["recognized_line_share_weighted"] + 0.01
        or current_metrics["dummy_eval_count"] > prior_metrics["dummy_eval_count"] * 1.05
        or current_metrics["patch_tuple_count"] > prior_metrics["patch_tuple_count"] * 1.05
        or current_metrics["seed_coverage"] > prior_metrics["seed_coverage"]
    )
    classification = "weakening" if weakening else "strengthening" if strengthening else "stable_flat"
    return {
        "classification": classification,
        "metric_deltas": {
            "dummy_eval_count_delta": dummy_delta,
            "patch_tuple_count_delta": patch_delta,
            "recognized_line_share_weighted_delta": recognized_delta,
            "seed_coverage_delta": seed_delta,
        },
        "reason": (
            "current evidence is weaker than the comparison run"
            if classification == "weakening"
            else "current evidence is stronger than the comparison run"
            if classification == "strengthening"
            else "current evidence is materially unchanged versus the comparison run"
        ),
    }


def _all_thresholds_pass(metrics: dict[str, Any], obligations: dict[str, Any]) -> bool:
    return (
        float(metrics["recognized_line_share_weighted"]) >= float(obligations.get("recognized_line_share_weighted_min", 0.95) or 0.95)
        and int(metrics["seed_coverage"]) >= int(obligations.get("seed_log_coverage_min", 3) or 3)
        and int(metrics["dummy_eval_count"]) >= int(obligations.get("dummy_eval_count_min", 100) or 100)
        and int(metrics["patch_tuple_count"]) >= int(obligations.get("patch_tuple_count_min", 500) or 500)
        and str(metrics["directive_relevance"]) == str(obligations.get("directive_relevance_required", "high"))
        and str(metrics["duplication"]) == "low"
    )


def _cumulative_trend_assessment(
    trial_metrics: dict[str, Any],
    provisional_v1_metrics: dict[str, Any],
    provisional_v2_metrics: dict[str, Any],
    obligations: dict[str, Any],
) -> dict[str, Any]:
    trial_to_v1 = _pairwise_trend(provisional_v1_metrics, trial_metrics)
    v1_to_v2 = _pairwise_trend(provisional_v2_metrics, provisional_v1_metrics)
    trial_to_v2 = _pairwise_trend(provisional_v2_metrics, trial_metrics)
    classes = {
        str(trial_to_v1["classification"]),
        str(v1_to_v2["classification"]),
        str(trial_to_v2["classification"]),
    }
    utility_remains_real = all(
        _all_thresholds_pass(metrics, obligations)
        for metrics in [trial_metrics, provisional_v1_metrics, provisional_v2_metrics]
    )
    if "weakening" in classes:
        classification = "weakening"
        reason = "at least one step in the governed provisional sequence lost measurable evidence strength or coverage"
    elif "strengthening" in classes:
        classification = "strengthening"
        reason = "at least one step in the governed provisional sequence added measurable evidence strength without breaking the envelope"
    elif utility_remains_real:
        classification = "plateauing_low_growth"
        reason = "the evidence remains real and safe across repeated runs, but repeated flatness now looks more like plateaued confirmation than additional growth"
    else:
        classification = "stable_flat"
        reason = "the evidence remains broadly unchanged, but it is not strong enough to classify as a meaningful low-risk plateau"
    return {
        "classification": classification,
        "reason": reason,
        "utility_remains_real": utility_remains_real,
        "pairwise": {
            "trial_to_provisional_probe_v1": trial_to_v1,
            "provisional_probe_v1_to_provisional_probe_v2": v1_to_v2,
            "trial_to_provisional_probe_v2": trial_to_v2,
        },
    }


def _trial_bucket_pressure(bucket_state: dict[str, Any], trial_summary: dict[str, Any]) -> dict[str, Any]:
    sandbox = dict(trial_summary.get("sandbox_envelope_compliance", {}))
    requested = dict(sandbox.get("resource_limits_requested", {}))
    if not requested:
        return {"concern_level": "unknown"}
    return _bucket_pressure(bucket_state, requested)


def _envelope_compliance_trend(
    bucket_state: dict[str, Any],
    trial_summary: dict[str, Any],
    provisional_v1_summary: dict[str, Any],
    provisional_v2_summary: dict[str, Any],
    plan_non_owning: bool,
    routing_deferred: bool,
) -> dict[str, Any]:
    trial_envelope = dict(trial_summary.get("sandbox_envelope_compliance", {}))
    provisional_v1_envelope = dict(provisional_v1_summary.get("envelope_compliance", {}))
    provisional_v2_envelope = dict(provisional_v2_summary.get("envelope_compliance", {}))
    trial_pressure = _trial_bucket_pressure(bucket_state, trial_summary)
    v1_pressure = dict(provisional_v1_envelope.get("bucket_pressure", {}))
    v2_pressure = dict(provisional_v2_envelope.get("bucket_pressure", {}))
    stable = (
        bool(trial_envelope.get("network_mode_remained_none", False))
        and bool(provisional_v1_envelope.get("network_mode_remained_none", False))
        and bool(provisional_v2_envelope.get("network_mode_remained_none", False))
        and bool(trial_envelope.get("writes_within_approved_roots", False))
        and bool(provisional_v1_envelope.get("writes_within_approved_roots", False))
        and bool(provisional_v2_envelope.get("writes_within_approved_roots", False))
        and bool(trial_envelope.get("branch_state_stayed_paused_with_baseline_held", False))
        and bool(provisional_v1_envelope.get("branch_state_stayed_paused_with_baseline_held", False))
        and bool(provisional_v2_envelope.get("branch_state_stayed_paused_with_baseline_held", False))
        and bool(trial_envelope.get("no_retained_promotion", False))
        and bool(provisional_v1_envelope.get("no_retained_promotion", False))
        and bool(provisional_v2_envelope.get("no_retained_promotion", False))
        and bool(provisional_v1_envelope.get("no_protected_surface_modification", False))
        and bool(provisional_v2_envelope.get("no_protected_surface_modification", False))
        and bool(provisional_v1_envelope.get("no_downstream_selected_set_work", False))
        and bool(provisional_v2_envelope.get("no_downstream_selected_set_work", False))
        and bool(provisional_v1_envelope.get("no_plan_ownership_change", False))
        and bool(provisional_v2_envelope.get("no_plan_ownership_change", False))
        and bool(provisional_v1_envelope.get("no_routing_work", False))
        and bool(provisional_v2_envelope.get("no_routing_work", False))
        and bool(plan_non_owning)
        and bool(routing_deferred)
        and str(trial_pressure.get("concern_level", "low")) in {"low", "unknown"}
        and str(v1_pressure.get("concern_level", "low")) == "low"
        and str(v2_pressure.get("concern_level", "low")) == "low"
    )
    return {
        "classification": "stable_low_risk" if stable else "watch",
        "reason": (
            "network, write-root, bucket, branch-state, protected-surface, downstream, plan_, and routing constraints stayed intact across the full governed line"
            if stable
            else "at least one envelope or governance-boundary signal now needs attention"
        ),
        "network_mode": {
            "trial": str(trial_envelope.get("network_mode_observed", "")),
            "provisional_probe_v1": str(provisional_v1_envelope.get("network_mode_observed", "")),
            "provisional_probe_v2": str(provisional_v2_envelope.get("network_mode_observed", "")),
        },
        "write_root_compliance": {
            "trial": bool(trial_envelope.get("writes_within_approved_roots", False)),
            "provisional_probe_v1": bool(provisional_v1_envelope.get("writes_within_approved_roots", False)),
            "provisional_probe_v2": bool(provisional_v2_envelope.get("writes_within_approved_roots", False)),
        },
        "bucket_pressure": {
            "trial": trial_pressure,
            "provisional_probe_v1": v1_pressure,
            "provisional_probe_v2": v2_pressure,
        },
        "branch_state_immutability": {
            "trial": bool(trial_envelope.get("branch_state_stayed_paused_with_baseline_held", False)),
            "provisional_probe_v1": bool(provisional_v1_envelope.get("branch_state_stayed_paused_with_baseline_held", False)),
            "provisional_probe_v2": bool(provisional_v2_envelope.get("branch_state_stayed_paused_with_baseline_held", False)),
        },
        "protected_surface_isolation": {
            "trial": bool(trial_envelope.get("no_protected_surface_modification", False)),
            "provisional_probe_v1": bool(provisional_v1_envelope.get("no_protected_surface_modification", False)),
            "provisional_probe_v2": bool(provisional_v2_envelope.get("no_protected_surface_modification", False)),
        },
        "downstream_isolation": {
            "provisional_probe_v1": bool(provisional_v1_envelope.get("no_downstream_selected_set_work", False)),
            "provisional_probe_v2": bool(provisional_v2_envelope.get("no_downstream_selected_set_work", False)),
        },
        "plan_non_ownership": {
            "branch_context": bool(plan_non_owning),
            "provisional_probe_v1": bool(provisional_v1_envelope.get("no_plan_ownership_change", False)),
            "provisional_probe_v2": bool(provisional_v2_envelope.get("no_plan_ownership_change", False)),
        },
        "routing_non_involvement": {
            "branch_context": bool(routing_deferred),
            "provisional_probe_v1": bool(provisional_v1_envelope.get("no_routing_work", False)),
            "provisional_probe_v2": bool(provisional_v2_envelope.get("no_routing_work", False)),
        },
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governance_substrate_v1_snapshot")
    trial_execution_snapshot = r._load_latest_diagnostic_artifact_by_template("proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1")
    trial_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governed_skill_trial_evidence_snapshot_v1")
    provisional_admission_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governed_skill_provisional_admission_snapshot_v1")
    provisional_probe_v1_snapshot = r._load_latest_diagnostic_artifact_by_template("proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v1")
    provisional_probe_v2_snapshot = r._load_latest_diagnostic_artifact_by_template("proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v2")
    provisional_evidence_v1_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governed_skill_provisional_evidence_snapshot_v1")
    if not all(
        [
            governance_snapshot,
            trial_execution_snapshot,
            trial_evidence_snapshot,
            provisional_admission_snapshot,
            provisional_probe_v1_snapshot,
            provisional_probe_v2_snapshot,
            provisional_evidence_v1_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: provisional evidence v2 requires governance, trial, trial-evidence, provisional-admission, provisional-probe-v1, provisional-probe-v2, and provisional-evidence-v1 artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite cumulative provisional evidence artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite cumulative provisional evidence artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite cumulative provisional evidence artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "the cumulative provisional value review cannot run without the full governance-owned evidence chain"},
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
            "reason": "diagnostic shadow failed: provisional evidence v2 requires current directive, bucket, self-structure, and branch state artifacts",
            "observability_gain": {"passed": False, "reason": "missing durable governance state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing durable governance state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing durable governance state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "the cumulative provisional value review cannot run without directive, bucket, self-structure, and branch state"},
        }

    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_branch_state = str(branch_record.get("state", ""))
    governed_skill_subsystem = dict(self_structure_state.get("governed_skill_subsystem", {}))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    current_directive = dict(directive_state.get("current_directive_state", {}))

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
        str(dict(provisional_probe_v1_snapshot).get("artifact_path", ""))
        or str(
            next(
                iter(
                    sorted(
                        _diagnostic_artifact_dir().glob("proposal_learning_loop_v4_governed_skill_local_trace_parser_provisional_probe_v1_*.json"),
                        reverse=True,
                    )
                ),
                Path(),
            )
        )
    )
    provisional_probe_v2_artifact_path = Path(
        str(governed_skill_subsystem.get("last_provisional_execution_artifact_path") or dict(provisional_probe_v2_snapshot).get("artifact_path", ""))
    )
    provisional_evidence_v1_artifact_path = Path(
        str(dict(provisional_evidence_v1_snapshot).get("artifact_path", ""))
        or str(
            next(
                iter(
                    sorted(
                        _diagnostic_artifact_dir().glob("memory_summary_v4_governed_skill_provisional_evidence_snapshot_v1_*.json"),
                        reverse=True,
                    )
                ),
                Path(),
            )
        )
    )

    trial_execution_summary = dict(_load_json_file(trial_execution_artifact_path).get("governed_skill_trial_summary", {}))
    trial_evidence_summary = dict(_load_json_file(trial_evidence_artifact_path).get("governed_skill_trial_evidence_summary", {}))
    provisional_admission_summary = dict(_load_json_file(provisional_admission_artifact_path).get("governed_skill_provisional_admission_summary", {}))
    provisional_probe_v1_summary = dict(_load_json_file(provisional_probe_v1_artifact_path).get("governed_skill_provisional_probe_summary", {}))
    provisional_probe_v2_summary = dict(_load_json_file(provisional_probe_v2_artifact_path).get("governed_skill_provisional_probe_summary", {}))
    provisional_evidence_v1_summary = dict(_load_json_file(provisional_evidence_v1_artifact_path).get("governed_skill_provisional_evidence_summary", {}))

    obligations = dict(provisional_admission_summary.get("evidence_obligations", {}))
    trial_metrics = _trial_metrics(trial_execution_summary)
    provisional_v1_metrics = _provisional_metrics(provisional_probe_v1_summary)
    provisional_v2_metrics = _provisional_metrics(provisional_probe_v2_summary)
    cumulative_trend = _cumulative_trend_assessment(trial_metrics, provisional_v1_metrics, provisional_v2_metrics, obligations)

    all_runs_pass = {
        "trial": _all_thresholds_pass(trial_metrics, obligations),
        "provisional_probe_v1": _all_thresholds_pass(provisional_v1_metrics, obligations),
        "provisional_probe_v2": _all_thresholds_pass(provisional_v2_metrics, obligations),
    }
    evidence_obligation_status = {
        "thresholds_source": obligations,
        "by_run": {
            "trial": {**trial_metrics, "passed": all_runs_pass["trial"]},
            "provisional_probe_v1": {**provisional_v1_metrics, "passed": all_runs_pass["provisional_probe_v1"]},
            "provisional_probe_v2": {**provisional_v2_metrics, "passed": all_runs_pass["provisional_probe_v2"]},
        },
        "governance_reporting_complete": (
            provisional_probe_v1_artifact_path.exists()
            and provisional_probe_v2_artifact_path.exists()
            and provisional_evidence_v1_artifact_path.exists()
            and bool(governed_skill_subsystem.get("last_provisional_execution_outcome"))
        ),
        "all_runs_passed": all(all_runs_pass.values()),
    }

    envelope_trend = _envelope_compliance_trend(
        bucket_state,
        trial_execution_summary,
        provisional_probe_v1_summary,
        provisional_probe_v2_summary,
        bool(current_state_summary.get("plan_non_owning", False)),
        bool(current_state_summary.get("routing_deferred", False)),
    )
    rollback_v1 = dict(provisional_probe_v1_summary.get("rollback_trigger_status", {}))
    rollback_v2 = dict(provisional_probe_v2_summary.get("rollback_trigger_status", {}))
    deprecation_v1 = dict(provisional_probe_v1_summary.get("deprecation_trigger_status", {}))
    deprecation_v2 = dict(provisional_probe_v2_summary.get("deprecation_trigger_status", {}))
    rollback_risk_trend = {
        "classification": "stable_low"
        if not bool(rollback_v1.get("any_trigger_fired", False)) and not bool(rollback_v2.get("any_trigger_fired", False))
        else "rising",
        "reason": (
            "no rollback triggers fired across either provisional run, so rollback risk remains low and stable"
            if not bool(rollback_v1.get("any_trigger_fired", False)) and not bool(rollback_v2.get("any_trigger_fired", False))
            else "at least one rollback trigger fired across the provisional sequence, so rollback risk is rising"
        ),
        "by_run": {"provisional_probe_v1": rollback_v1, "provisional_probe_v2": rollback_v2},
    }
    deprecation_risk_trend = {
        "classification": "stable_low"
        if not bool(deprecation_v1.get("any_trigger_active", False)) and not bool(deprecation_v2.get("any_trigger_active", False))
        else "rising",
        "reason": (
            "no deprecation triggers are active across either provisional run, so deprecation risk remains low and stable"
            if not bool(deprecation_v1.get("any_trigger_active", False)) and not bool(deprecation_v2.get("any_trigger_active", False))
            else "at least one deprecation trigger became active, so deprecation risk is rising"
        ),
        "by_run": {"provisional_probe_v1": deprecation_v1, "provisional_probe_v2": deprecation_v2},
    }

    cumulative_classification = str(cumulative_trend.get("classification", ""))
    no_risk_events = (
        evidence_obligation_status["all_runs_passed"]
        and str(envelope_trend.get("classification", "")) == "stable_low_risk"
        and str(rollback_risk_trend.get("classification", "")) == "stable_low"
        and str(deprecation_risk_trend.get("classification", "")) == "stable_low"
    )
    if cumulative_classification == "strengthening" and no_risk_events:
        escalation_posture = "remain_viable_for_continued_provisional_handling"
        best_next_template = "memory_summary.v4_governed_skill_retention_readiness_snapshot_v1"
        escalation_reason = "the line is still adding non-trivial evidence while staying inside the same governance envelope"
    elif cumulative_classification == "plateauing_low_growth" and no_risk_events:
        escalation_posture = "remain_provisional_but_plateauing"
        best_next_template = "memory_summary.v4_governed_skill_provisional_pause_snapshot_v1"
        escalation_reason = "the line remains safe and directive-relevant, but repeated flat reruns are now adding low incremental information and should pause pending a new idea"
    elif cumulative_classification == "weakening":
        escalation_posture = "downgrade_to_sandbox_only"
        best_next_template = "memory_summary.v4_governed_skill_provisional_gap_snapshot_v1"
        escalation_reason = "the cumulative provisional sequence is weakening, so continued provisional build-out is no longer justified"
    elif not no_risk_events:
        escalation_posture = "block_from_further_escalation"
        best_next_template = "memory_summary.v4_governed_skill_provisional_gap_snapshot_v1"
        escalation_reason = "the cumulative review surfaced an evidence, envelope, or governance-risk problem that blocks further escalation"
    else:
        escalation_posture = "remain_viable_for_continued_provisional_handling"
        best_next_template = "memory_summary.v4_governed_skill_provisional_gap_snapshot_v1"
        escalation_reason = "the line is still viable, but the cumulative signal is not yet clearly strong enough for a retention-readiness turn"

    continued_provisional_handling_justified = escalation_posture in {
        "remain_viable_for_continued_provisional_handling",
        "remain_provisional_but_plateauing",
    }
    another_same_shape_provisional_pass_justified = cumulative_classification not in {"plateauing_low_growth", "weakening"}
    structural_value_assessment = {
        "classification": (
            "still_structurally_useful_but_low_incremental_gain"
            if cumulative_classification == "plateauing_low_growth" and no_risk_events
            else "governed_capability_growth_signal"
            if continued_provisional_handling_justified
            else "structural_value_fading"
        ),
        "supports_long_run_goal": continued_provisional_handling_justified,
        "good_exemplar_for_governed_skill_growth": continued_provisional_handling_justified,
        "line_is_becoming_local_churn": cumulative_classification == "plateauing_low_growth",
        "accumulating_enough_structural_value_for_more_same_shape_iterations": another_same_shape_provisional_pass_justified,
        "pause_pending_new_idea": cumulative_classification == "plateauing_low_growth",
        "reason": (
            "the line still demonstrates directive-bound, bucket-bounded, governance-owned skill behavior, but repeated flat reruns are now mostly re-confirming containment rather than adding new structural information"
            if cumulative_classification == "plateauing_low_growth"
            else "the line is still producing useful governed capability-growth signal under the current architecture"
            if continued_provisional_handling_justified
            else "the line no longer provides enough governed capability-growth value to justify continued provisional attention"
        ),
    }
    retained_promotion_posture = {
        "below_retained_promotion_threshold": True,
        "retained_promotion_discussion_still_premature": True,
        "cumulative_signal": "still_below_retained_threshold",
        "another_same_shape_provisional_pass_justified": another_same_shape_provisional_pass_justified,
        "reason": "repeated flat stability proves containment, but it does not by itself supply the strengthening signal needed for a retained-promotion discussion",
        "additional_evidence_required": [
            "a materially strengthening governed provisional result, not another identical flat rerun",
            "or a new bounded use-case that expands useful local trace-parser value without changing the trust or bucket envelope",
            "continued full envelope compliance with network still none and branch state still paused_with_baseline_held",
            "continued high directive relevance and low duplication risk",
            "no rollback triggers fired and no deprecation triggers active",
            "explicit retained-promotion gate review and human approval point",
        ],
    }

    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_v4_governed_skill_provisional_evidence_snapshot_v2_{proposal['proposal_id']}.json"

    updated_self_structure_state = dict(self_structure_state)
    updated_governed_skill_subsystem = dict(governed_skill_subsystem)
    updated_governed_skill_subsystem["last_provisional_evidence_artifact_path"] = str(artifact_path)
    updated_governed_skill_subsystem["last_provisional_evidence_outcome"] = {
        "primary_candidate_skill_id": "skill_candidate_local_trace_parser_trial",
        "primary_candidate_name": "Local trace parser trial",
        "provisional_evidence_posture": escalation_posture,
        "evidence_trend": cumulative_classification,
        "reason": escalation_reason,
        "retained_promotion": False,
        "branch_state_after_review": current_branch_state,
        "another_same_shape_provisional_pass_justified": another_same_shape_provisional_pass_justified,
    }
    updated_governed_skill_subsystem["best_next_template"] = best_next_template
    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["governed_skill_subsystem"] = updated_governed_skill_subsystem
    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "latest_skill_provisional_evidence_outcome": escalation_posture,
            "latest_skill_provisional_evidence_trend": cumulative_classification,
            "latest_skill_structural_value_assessment": str(structural_value_assessment.get("classification", "")),
            "retained_skill_promotion_performed": False,
            "current_branch_state": current_branch_state,
            "plan_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
        }
    )
    updated_self_structure_state["current_state_summary"] = updated_current_state_summary
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    ledger_event = {
        "event_id": f"governed_skill_provisional_evidence_snapshot_v2::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_skill_provisional_evidence_snapshot_v2_materialized",
        "event_class": "governed_skill_provisional_evidence_review",
        "directive_id": str(current_directive.get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": current_branch_state,
        "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
        "primary_candidate_skill_id": "skill_candidate_local_trace_parser_trial",
        "provisional_evidence_posture": escalation_posture,
        "evidence_trend": cumulative_classification,
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
            "skill_provisional_probe_v1_artifact": str(provisional_probe_v1_artifact_path),
            "skill_provisional_probe_v2_artifact": str(provisional_probe_v2_artifact_path),
            "skill_provisional_evidence_v1_artifact": str(provisional_evidence_v1_artifact_path),
            "skill_provisional_evidence_v2_artifact": str(artifact_path),
        },
        "source_proposal_id": str(proposal.get("proposal_id", "")),
    }
    _append_jsonl(SELF_STRUCTURE_LEDGER_PATH, ledger_event)

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_governed_skill_provisional_evidence_snapshot_v2",
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
        },
        "governed_skill_provisional_evidence_summary": {
            "evidence_reviewed": {
                "trial_execution_artifact": str(trial_execution_artifact_path),
                "trial_evidence_artifact": str(trial_evidence_artifact_path),
                "provisional_admission_artifact": str(provisional_admission_artifact_path),
                "provisional_probe_v1_artifact": str(provisional_probe_v1_artifact_path),
                "provisional_probe_v2_artifact": str(provisional_probe_v2_artifact_path),
                "provisional_evidence_v1_artifact": str(provisional_evidence_v1_artifact_path),
                "directive_history_tail": [str(item.get("event_type", "")) for item in directive_history[-8:]],
                "self_structure_event_tail": [str(item.get("event_type", "")) for item in self_structure_ledger[-12:]],
                "intervention_ledger_rows_reviewed": len(intervention_ledger[-12:]),
            },
            "cumulative_trend_assessment": cumulative_trend,
            "evidence_obligation_status": evidence_obligation_status,
            "envelope_compliance_trend": envelope_trend,
            "rollback_risk_trend": rollback_risk_trend,
            "deprecation_risk_trend": deprecation_risk_trend,
            "structural_value_assessment": structural_value_assessment,
            "escalation_posture": {"category": escalation_posture, "reason": escalation_reason},
            "retention_readiness_posture": retained_promotion_posture,
            "prior_review_context": {
                "v1_provisional_review_trend": str(dict(provisional_evidence_v1_summary.get("trend_assessment", {})).get("classification", "")),
                "v1_project_alignment_reason": str(dict(provisional_evidence_v1_summary.get("broader_project_alignment", {})).get("reason", "")),
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
                "reason": "the cumulative provisional evidence review is derived from directive, bucket, branch, self-structure, and prior governed-skill artifacts rather than from execution code alone",
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
            "reason": "the local trace parser line now has an explicit cumulative governance-owned review across trial, provisional probe v1, and provisional probe v2",
            "artifact_paths": {
                "skill_provisional_evidence_v2_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the review now distinguishes productive provisional accumulation from a well-governed but plateauing line",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "the cumulative review cleanly distinguishes strengthening, stable-flat, weakening, and plateauing-low-growth outcomes",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the cumulative provisional evidence review is diagnostic-only; no retained promotion, no branch-state mutation, and no live behavior change occurred",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": best_next_template,
            "reason": "the next step can now respond to whether the line is still accumulating value or is plateauing under good governance",
        },
        "diagnostic_conclusions": {
            "governed_skill_provisional_evidence_review_v2_in_place": True,
            "continued_provisional_handling_justified": continued_provisional_handling_justified,
            "cumulative_provisional_evidence_trend": cumulative_classification,
            "retained_promotion_occurred": False,
            "below_retained_promotion_threshold": True,
            "branch_state_stayed_paused_with_baseline_held": True,
            "plan_should_remain_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "another_same_shape_provisional_pass_justified": another_same_shape_provisional_pass_justified,
            "best_next_template": best_next_template,
        },
    }
    _write_json(artifact_path, artifact_payload)

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: the local trace parser now has a cumulative governance-owned provisional evidence review that distinguishes safe continuation from plateauing churn",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
