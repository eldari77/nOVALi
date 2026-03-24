from __future__ import annotations

import json
from typing import Any

from .analytics import build_intervention_ledger_analytics
from .ledger import intervention_data_dir, load_latest_snapshots
from .v4_first_hypothesis_landscape_snapshot_v1 import (
    ACTIVE_STATUS_PATH,
    HANDOFF_STATUS_PATH,
    PROPOSAL_LOOP_PATH,
    _load_json_file,
    _load_text_file,
)
from .v4_wm_context_signal_overlap_snapshot_v1 import _artifact_reference
from .v4_wm_primary_plan_structure_probe_v1 import _safe_float


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(sum(values) / len(values))


def _find_seed(reports: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    for report in reports:
        if int(report.get("seed", -1)) == int(seed):
            return dict(report)
    return {}


def _find_slice(reports: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for report in reports:
        if str(report.get("slice", "")) == str(name):
            return dict(report)
    return {}


def _positive_seed_count(reports: list[dict[str, Any]]) -> int:
    return int(
        sum(
            1
            for report in reports
            if (_safe_float(report.get("selection_score_pre_gate_gap_delta"), 0.0) or 0.0) > 0.0
        )
    )


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or abs(float(denominator)) <= 1e-12:
        return None
    return float(float(numerator) / float(denominator))


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    scoped_probe_artifact = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1"
    )
    stabilization_probe_artifact = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_wm_hybrid_context_stabilization_probe_v1"
    )
    stability_snapshot_v1 = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v1"
    )
    scope_effect_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_context_scope_effect_snapshot_v1"
    )
    hybrid_probe_artifact = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1"
    )
    frontier_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.false_safe_frontier_control_characterization_snapshot_v1"
    )
    if not all(
        [
            scoped_probe_artifact,
            stabilization_probe_artifact,
            stability_snapshot_v1,
            scope_effect_snapshot,
            hybrid_probe_artifact,
            frontier_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: scoped-hybrid stability v2 requires the scoped probe, the stabilization probe, the prior stability snapshot, and the scope-effect snapshot",
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
                "reason": "cannot classify stabilization repeatability without the prerequisite scoped-hybrid and stabilization artifacts",
            },
        }

    active_status_text = _load_text_file(ACTIVE_STATUS_PATH)
    handoff_status = _load_json_file(HANDOFF_STATUS_PATH)
    analytics = build_intervention_ledger_analytics()
    latest_snapshots = load_latest_snapshots()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")
    proposal_loop_text = _load_text_file(PROPOSAL_LOOP_PATH)

    scoped_shadow = dict(scoped_probe_artifact.get("shadow_metrics", {}))
    stabilized_shadow = dict(stabilization_probe_artifact.get("shadow_metrics", {}))
    scoped_effect = dict(scoped_probe_artifact.get("context_scoped_effect_report", {}))
    stabilized_effect = dict(stabilization_probe_artifact.get("stabilization_effect_report", {}))
    scope_effect_report = dict(scope_effect_snapshot.get("effect_decomposition_report", {}))
    stability_report_v1 = dict(stability_snapshot_v1.get("stability_report", {}))

    scoped_vs_baseline = dict(scoped_shadow.get("comparison_vs_baseline", {}))
    stabilized_vs_baseline = dict(stabilized_shadow.get("comparison_vs_baseline", {}))
    stabilized_vs_hybrid = dict(stabilized_shadow.get("comparison_vs_hybrid", {}))
    stabilized_vs_scoped = dict(stabilized_shadow.get("comparison_vs_context_scoped", {}))

    scoped_partial_signal = dict(scoped_shadow.get("partial_signal_given_baseline", {}))
    stabilized_partial_signal = dict(stabilized_shadow.get("partial_signal_given_baseline", {}))

    scoped_seed_effects = list(dict(scoped_effect.get("seed_level_effects", {})).get("context_scoped", []))
    stabilized_seed_effects = list(
        dict(stabilized_effect.get("seed_level_effects", {})).get("context_stabilized", [])
    )

    scoped_slice_effects = list(dict(scoped_effect.get("context_slice_effects", {})).get("context_scoped", []))
    stabilized_slice_effects = list(
        dict(stabilized_effect.get("context_slice_effects", {})).get("context_stabilized", [])
    )

    scoped_status_effects = dict(dict(scoped_effect.get("row_level_effects", {})).get("status_effects", {}))
    stabilized_status_effects = dict(
        dict(stabilized_effect.get("row_level_effects", {})).get("context_stabilized", {})
    )

    scope_multiplier_effect = dict(scope_effect_report.get("scope_multiplier_effect", {}))
    interaction_effect = dict(scope_effect_report.get("interaction_effect", {}))
    seed_deltas_vs_hybrid = list(
        dict(dict(scope_effect_report.get("row_seed_context_benefit_map", {})).get("seed_level", {})).get(
            "seed_deltas_vs_hybrid",
            [],
        )
    )

    scoped_seed2 = _find_seed(scoped_seed_effects, 2)
    stabilized_seed2 = _find_seed(stabilized_seed_effects, 2)
    scoped_seed2_vs_hybrid = _find_seed(seed_deltas_vs_hybrid, 2)

    scoped_strong = _find_slice(scoped_slice_effects, "high_context_low_risk")
    stabilized_strong = _find_slice(stabilized_slice_effects, "high_context_low_risk")
    scoped_weak = _find_slice(scoped_slice_effects, "low_context_high_risk")
    stabilized_weak = _find_slice(stabilized_slice_effects, "low_context_high_risk")

    scoped_pre_gate_gap = _safe_float(
        dict(dict(scoped_shadow.get("context_scoped_separation", {})).get("gap_metrics", {})).get(
            "selection_score_pre_gate_provisional_minus_blocked"
        ),
        0.0,
    ) or 0.0
    stabilized_pre_gate_gap = _safe_float(
        dict(dict(stabilized_shadow.get("context_stabilized_separation", {})).get("gap_metrics", {})).get(
            "selection_score_pre_gate_provisional_minus_blocked"
        ),
        0.0,
    ) or 0.0
    scoped_signal_corr = _safe_float(scoped_vs_baseline.get("context_scoped_signal_availability_corr"), 0.0) or 0.0
    stabilized_signal_corr = (
        _safe_float(stabilized_vs_baseline.get("context_stabilized_signal_availability_corr"), 0.0) or 0.0
    )
    scoped_signal_gap = _safe_float(scoped_vs_baseline.get("context_scoped_signal_gap"), 0.0) or 0.0
    stabilized_signal_gap = _safe_float(stabilized_vs_baseline.get("context_stabilized_signal_gap"), 0.0) or 0.0
    scoped_distinctness = _safe_float(scoped_vs_baseline.get("context_scoped_distinctness_score"), 0.0) or 0.0
    stabilized_distinctness = (
        _safe_float(stabilized_vs_baseline.get("context_stabilized_distinctness_score"), 0.0) or 0.0
    )
    scoped_overlap = _safe_float(
        scoped_vs_baseline.get("context_scoped_signal_overlap_to_baseline_pre_gate"),
        0.0,
    ) or 0.0
    stabilized_overlap = _safe_float(
        stabilized_vs_baseline.get("context_stabilized_signal_overlap_to_baseline_pre_gate"),
        0.0,
    ) or 0.0

    main_gap_delta_vs_scoped = _safe_float(
        stabilized_vs_scoped.get("selection_score_pre_gate_gap_delta"),
        0.0,
    ) or 0.0
    signal_corr_delta_vs_scoped = _safe_float(
        stabilized_vs_scoped.get("signal_availability_corr_delta"),
        0.0,
    ) or 0.0
    signal_gap_delta_vs_scoped = _safe_float(stabilized_vs_scoped.get("signal_gap_delta"), 0.0) or 0.0
    overlap_delta_vs_scoped = _safe_float(
        stabilized_vs_scoped.get("signal_overlap_to_baseline_pre_gate_delta"),
        0.0,
    ) or 0.0
    distinctness_delta_vs_scoped = _safe_float(
        stabilized_vs_scoped.get("distinctness_score_delta"),
        0.0,
    ) or 0.0

    seed2_gap_scoped = _safe_float(scoped_seed2.get("selection_score_pre_gate_gap_delta"), 0.0) or 0.0
    seed2_gap_stabilized = _safe_float(stabilized_seed2.get("selection_score_pre_gate_gap_delta"), 0.0) or 0.0
    seed2_gap_delta = _safe_float(stabilized_vs_scoped.get("seed_2_gap_delta"), 0.0) or 0.0
    seed2_gain_ratio_vs_scoped = _safe_ratio(seed2_gap_delta, seed2_gap_scoped)
    seed2_scope_deficit_vs_hybrid = _safe_float(
        scoped_seed2_vs_hybrid.get("selection_score_pre_gate_gap_delta_vs_hybrid"),
        0.0,
    ) or 0.0
    seed2_recovery_share_vs_scope_deficit = _safe_ratio(seed2_gap_delta, abs(seed2_scope_deficit_vs_hybrid))

    strong_slice_delta_scoped = _safe_float(scoped_strong.get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0
    strong_slice_delta_stabilized = (
        _safe_float(stabilized_strong.get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0
    )
    strong_slice_delta_delta = float(strong_slice_delta_stabilized - strong_slice_delta_scoped)
    strong_slice_share_scoped = _safe_float(scoped_strong.get("positive_delta_share"), 0.0) or 0.0
    strong_slice_share_stabilized = _safe_float(stabilized_strong.get("positive_delta_share"), 0.0) or 0.0
    strong_slice_share_delta = float(strong_slice_share_stabilized - strong_slice_share_scoped)

    weak_slice_delta_scoped = _safe_float(scoped_weak.get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0
    weak_slice_delta_stabilized = _safe_float(stabilized_weak.get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0
    weak_slice_delta_delta = float(weak_slice_delta_stabilized - weak_slice_delta_scoped)
    weak_slice_share_scoped = _safe_float(scoped_weak.get("positive_delta_share"), 0.0) or 0.0
    weak_slice_share_stabilized = _safe_float(stabilized_weak.get("positive_delta_share"), 0.0) or 0.0
    weak_slice_share_delta = float(weak_slice_share_stabilized - weak_slice_share_scoped)

    scope_contribution_gap = _safe_float(
        scope_multiplier_effect.get("selection_score_pre_gate_gap_delta_vs_hybrid"),
        0.0,
    ) or 0.0
    scope_strong_delta = _safe_float(interaction_effect.get("high_context_low_risk_delta_delta"), 0.0) or 0.0
    scope_weak_protection = _safe_float(interaction_effect.get("low_context_high_risk_delta_delta"), 0.0) or 0.0

    stabilization_gap_share_of_scope_step = _safe_ratio(main_gap_delta_vs_scoped, scope_contribution_gap)
    stabilization_strong_share_of_scope_step = _safe_ratio(strong_slice_delta_delta, scope_strong_delta)
    stabilization_weak_share_of_scope_step = _safe_ratio(
        weak_slice_delta_delta,
        abs(scope_weak_protection),
    )

    positive_seed_count_scoped = _positive_seed_count(scoped_seed_effects)
    positive_seed_count_stabilized = _positive_seed_count(stabilized_seed_effects)
    scoped_seed_gaps = [
        float(report.get("selection_score_pre_gate_gap_delta", 0.0))
        for report in scoped_seed_effects
        if _safe_float(report.get("selection_score_pre_gate_gap_delta"), None) is not None
    ]
    stabilized_seed_gaps = [
        float(report.get("selection_score_pre_gate_gap_delta", 0.0))
        for report in stabilized_seed_effects
        if _safe_float(report.get("selection_score_pre_gate_gap_delta"), None) is not None
    ]

    safety_preserved = bool(dict(stabilization_probe_artifact.get("safety_neutrality", {})).get("passed", False))
    upstream_preserved = bool(
        dict(stabilization_probe_artifact.get("diagnostic_conclusions", {})).get(
            "branch_stayed_cleanly_upstream",
            False,
        )
    )

    repeatable_improvement = bool(
        safety_preserved
        and upstream_preserved
        and main_gap_delta_vs_scoped > 0.00005
        and signal_gap_delta_vs_scoped > 0.0
        and distinctness_delta_vs_scoped > 0.003
        and (seed2_gain_ratio_vs_scoped or 0.0) >= 0.10
    )
    if repeatable_improvement:
        repeatability_classification = "repeatable_improvement"
    elif (
        abs(main_gap_delta_vs_scoped) <= 0.00001
        and (seed2_gain_ratio_vs_scoped or 0.0) < 0.05
        and signal_gap_delta_vs_scoped <= 0.0
    ):
        repeatability_classification = "small_metric_drift"
    else:
        repeatability_classification = "mixed_secondary_drift"

    if seed2_gap_delta <= 0.0:
        seed2_significance = "none"
    elif (seed2_gain_ratio_vs_scoped or 0.0) >= 0.20 or (seed2_recovery_share_vs_scope_deficit or 0.0) >= 0.15:
        seed2_significance = "meaningful"
    elif (seed2_gain_ratio_vs_scoped or 0.0) >= 0.05 or (seed2_recovery_share_vs_scope_deficit or 0.0) >= 0.05:
        seed2_significance = "suggestive"
    else:
        seed2_significance = "marginal"

    if strong_slice_delta_stabilized > 0.0 and strong_slice_delta_delta >= -0.00010:
        if strong_slice_delta_delta > 0.00005 and strong_slice_share_delta > 0.0:
            supported_slice_retention = "materially_strengthened"
        else:
            supported_slice_retention = "preserved_not_materially_stronger"
    else:
        supported_slice_retention = "regressed"

    if weak_slice_delta_stabilized >= 0.0:
        if weak_slice_delta_delta > 0.00001:
            weak_slice_protection = "protected_with_small_gain"
        else:
            weak_slice_protection = "protected_non_negative"
    else:
        weak_slice_protection = "protection_regressed"

    if repeatable_improvement:
        best_working_configuration = "proposal_learning_loop.v4_wm_hybrid_context_stabilization_probe_v1"
        best_working_reason = "stabilization would have converted its small seed correction into a repeatable primary-metric gain"
        another_stabilization_iteration_justified = True
        next_family = "proposal_learning_loop"
        next_template = "proposal_learning_loop.v4_wm_hybrid_context_stabilization_probe_v2"
        next_rationale = "the stabilization layer would have shown repeatable value, so the next move would be a revised narrow stabilization pass"
    else:
        best_working_configuration = "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1"
        best_working_reason = "the scoped probe still holds the best main provisional-vs-blocked gap while stabilization adds only marginal seed-2 correction and mixed secondary drift"
        another_stabilization_iteration_justified = False
        next_family = "memory_summary"
        next_template = "memory_summary.v4_wm_hybrid_scoped_working_baseline_snapshot_v1"
        next_rationale = "the safest next move is to keep the current scoped-hybrid configuration as the narrow working baseline and formalize reopen criteria before any new stabilization pass"

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v2",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "branch_context": {
            "active_status_path": str(ACTIVE_STATUS_PATH),
            "handoff_status_path": str(HANDOFF_STATUS_PATH),
            "proposal_learning_loop_path": str(PROPOSAL_LOOP_PATH),
            "active_status_mentions_v4_active": "`novali-v4` is the active working version." in active_status_text,
            "carried_forward_baseline": dict(handoff_status.get("carried_forward_baseline", {})),
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
        },
        "comparison_references": {
            "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1": _artifact_reference(
                scoped_probe_artifact,
                latest_snapshots,
            ),
            "proposal_learning_loop.v4_wm_hybrid_context_stabilization_probe_v1": _artifact_reference(
                stabilization_probe_artifact,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v1": _artifact_reference(
                stability_snapshot_v1,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_hybrid_context_scope_effect_snapshot_v1": _artifact_reference(
                scope_effect_snapshot,
                latest_snapshots,
            ),
            "proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1": _artifact_reference(
                hybrid_probe_artifact,
                latest_snapshots,
            ),
            "memory_summary.false_safe_frontier_control_characterization_snapshot_v1": _artifact_reference(
                frontier_snapshot,
                latest_snapshots,
            ),
        },
        "stability_v2_report": {
            "scoped_vs_stabilization_direct_comparison": {
                "scoped_probe": {
                    "selection_score_pre_gate_gap": float(scoped_pre_gate_gap),
                    "signal_availability_corr": float(scoped_signal_corr),
                    "signal_gap": float(scoped_signal_gap),
                    "signal_overlap_to_baseline_pre_gate": float(scoped_overlap),
                    "distinctness_score": float(scoped_distinctness),
                    "partial_signal_given_baseline": _safe_float(
                        scoped_partial_signal.get("context_scoped"),
                        None,
                    ),
                    "positive_seed_count_vs_baseline": int(positive_seed_count_scoped),
                    "strong_slice_delta": float(strong_slice_delta_scoped),
                    "strong_slice_positive_delta_share": float(strong_slice_share_scoped),
                    "weak_slice_delta": float(weak_slice_delta_scoped),
                    "weak_slice_positive_delta_share": float(weak_slice_share_scoped),
                    "seed_2_gap": float(seed2_gap_scoped),
                },
                "stabilization_probe": {
                    "selection_score_pre_gate_gap": float(stabilized_pre_gate_gap),
                    "signal_availability_corr": float(stabilized_signal_corr),
                    "signal_gap": float(stabilized_signal_gap),
                    "signal_overlap_to_baseline_pre_gate": float(stabilized_overlap),
                    "distinctness_score": float(stabilized_distinctness),
                    "partial_signal_given_baseline": _safe_float(
                        stabilized_partial_signal.get("context_stabilized"),
                        None,
                    ),
                    "positive_seed_count_vs_baseline": int(positive_seed_count_stabilized),
                    "strong_slice_delta": float(strong_slice_delta_stabilized),
                    "strong_slice_positive_delta_share": float(strong_slice_share_stabilized),
                    "weak_slice_delta": float(weak_slice_delta_stabilized),
                    "weak_slice_positive_delta_share": float(weak_slice_share_stabilized),
                    "seed_2_gap": float(seed2_gap_stabilized),
                },
                "delta_stabilization_minus_scoped": {
                    "selection_score_pre_gate_gap_delta": float(main_gap_delta_vs_scoped),
                    "signal_availability_corr_delta": float(signal_corr_delta_vs_scoped),
                    "signal_gap_delta": float(signal_gap_delta_vs_scoped),
                    "signal_overlap_to_baseline_pre_gate_delta": float(overlap_delta_vs_scoped),
                    "distinctness_score_delta": float(distinctness_delta_vs_scoped),
                    "partial_signal_given_baseline_delta": (
                        None
                        if _safe_float(stabilized_partial_signal.get("context_stabilized"), None) is None
                        or _safe_float(scoped_partial_signal.get("context_scoped"), None) is None
                        else float(
                            _safe_float(stabilized_partial_signal.get("context_stabilized"), 0.0)
                            - _safe_float(scoped_partial_signal.get("context_scoped"), 0.0)
                        )
                    ),
                },
            },
            "repeatability_vs_drift": {
                "classification": str(repeatability_classification),
                "repeatable_improvement": bool(repeatable_improvement),
                "safety_preserved": bool(safety_preserved),
                "branch_stayed_cleanly_upstream": bool(upstream_preserved),
                "scoped_positive_seed_count_vs_baseline": int(positive_seed_count_scoped),
                "stabilized_positive_seed_count_vs_baseline": int(positive_seed_count_stabilized),
                "scoped_seed_gap_mean": _mean(scoped_seed_gaps),
                "stabilized_seed_gap_mean": _mean(stabilized_seed_gaps),
                "scope_multiplier_gap_delta_vs_hybrid": float(scope_contribution_gap),
                "stabilization_gap_delta_vs_scoped": float(main_gap_delta_vs_scoped),
                "stabilization_gap_share_of_prior_scope_step": stabilization_gap_share_of_scope_step,
                "reason": (
                    "stabilization adds repeatable primary and secondary improvement beyond the scoped configuration"
                    if repeatable_improvement
                    else "stabilization adds only small mixed metric drift around the current scoped configuration and does not convert into a repeatable primary-gap win"
                ),
            },
            "seed_2_correction_significance": {
                "classification": str(seed2_significance),
                "scoped_seed_2_gap": float(seed2_gap_scoped),
                "stabilized_seed_2_gap": float(seed2_gap_stabilized),
                "seed_2_gap_delta": float(seed2_gap_delta),
                "seed_2_gain_ratio_vs_scoped": seed2_gain_ratio_vs_scoped,
                "scoped_seed_2_gap_delta_vs_hybrid": float(seed2_scope_deficit_vs_hybrid),
                "stabilization_recovery_share_of_seed_2_scope_deficit": seed2_recovery_share_vs_scope_deficit,
                "reason": (
                    "seed 2 correction is large enough to justify another stabilization iteration"
                    if seed2_significance == "meaningful"
                    else "seed 2 correction is real but still too small to outweigh the lack of main-gap improvement"
                    if seed2_significance in {"suggestive", "marginal"}
                    else "seed 2 correction did not materialize in a meaningful way"
                ),
            },
            "supported_slice_retention": {
                "classification": str(supported_slice_retention),
                "strong_slice_delta_delta": float(strong_slice_delta_delta),
                "strong_slice_positive_delta_share_delta": float(strong_slice_share_delta),
                "strong_slice_delta_share_of_prior_scope_step": stabilization_strong_share_of_scope_step,
                "weak_slice_protection": str(weak_slice_protection),
                "weak_slice_delta_delta": float(weak_slice_delta_delta),
                "weak_slice_positive_delta_share_delta": float(weak_slice_share_delta),
                "weak_slice_protection_share_of_prior_scope_step": stabilization_weak_share_of_scope_step,
                "reason": (
                    "supported-slice gains are preserved strongly enough and weak-slice protection remains intact"
                    if supported_slice_retention != "regressed" and weak_slice_protection != "protection_regressed"
                    else "stabilization softened either the supported slice or the weak-slice protection too much"
                ),
            },
            "best_current_narrow_working_configuration": {
                "best_template": str(best_working_configuration),
                "reason": str(best_working_reason),
                "stable_narrow_targeting_reference": str(
                    dict(dict(stability_report_v1.get("overall_classification", {}))).get(
                        "classification",
                        "",
                    )
                ),
                "seed_2_weakness_reference": str(
                    dict(dict(stability_report_v1.get("weak_region_risk", {})).get("seed_2", {})).get(
                        "weakness_classification",
                        "",
                    )
                ),
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
            "proposal_learning_loop_reference_present": "proposal_learning_loop" in proposal_loop_text,
        },
        "decision_recommendation": {
            "another_stabilization_iteration_justified": bool(another_stabilization_iteration_justified),
            "plan_should_remain_non_owning": True,
            "best_current_narrow_working_configuration": str(best_working_configuration),
            "recommended_next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "rationale": str(next_rationale),
        },
        "observability_gain": {
            "passed": True,
            "reason": "the snapshot compares scoped and stabilized artifacts directly and measures how much of the observed change is repeatable improvement versus narrow metric drift",
            "scoped_seed_report_count": int(len(scoped_seed_effects)),
            "stabilized_seed_report_count": int(len(stabilized_seed_effects)),
            "scoped_slice_report_count": int(len(scoped_slice_effects)),
            "stabilized_slice_report_count": int(len(stabilized_slice_effects)),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the snapshot resolves whether stabilization adds enough repeatable value to replace the current scoped-hybrid working configuration",
            "another_stabilization_iteration_justified": bool(another_stabilization_iteration_justified),
            "plan_non_owning_preserved": True,
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": float(
                min(
                    1.0,
                    0.60
                    + 0.10 * int(repeatability_classification == "small_metric_drift")
                    + 0.08 * int(seed2_significance == "marginal")
                    + 0.08 * int(supported_slice_retention == "preserved_not_materially_stronger")
                    + 0.08 * int(best_working_configuration.endswith("context_scoped_probe_v1"))
                )
            ),
            "reason": "the snapshot resolves whether stabilization adds real repeatable value or only small drift and identifies the best narrow working configuration",
        },
        "safety_neutrality": {
            "passed": bool(safety_preserved),
            "scope": str(proposal.get("scope", "")),
            "reason": "diagnostic-only stability comparison with live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": str(next_template),
            "reason": str(next_rationale),
        },
        "diagnostic_conclusions": {
            "another_stabilization_iteration_justified": bool(another_stabilization_iteration_justified),
            "plan_should_remain_non_owning": True,
            "best_current_narrow_working_configuration": str(best_working_configuration),
            "recommended_next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
            "repeatability_classification": str(repeatability_classification),
            "seed_2_correction_significance": str(seed2_significance),
        },
    }

    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"memory_summary_v4_wm_hybrid_context_scope_stability_snapshot_v2_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": bool(safety_preserved),
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": (
            "diagnostic shadow passed: stabilization repeatability versus scoped-hybrid drift was classified without changing behavior"
            if safety_preserved
            else "diagnostic shadow failed: stabilization repeatability analysis detected an unexpected safety regression"
        ),
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
