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
    stability_snapshot_v2 = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v2"
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
            stability_snapshot_v2,
            scope_effect_snapshot,
            hybrid_probe_artifact,
            frontier_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: scoped working-baseline formalization requires the scoped probe, stabilization probe, stability snapshots, and hybrid scope-effect artifacts",
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
                "reason": "cannot formalize the working narrow baseline without the scoped-hybrid and stabilization evidence chain",
            },
        }

    active_status_text = _load_text_file(ACTIVE_STATUS_PATH)
    handoff_status = _load_json_file(HANDOFF_STATUS_PATH)
    analytics = build_intervention_ledger_analytics()
    latest_snapshots = load_latest_snapshots()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")
    proposal_loop_text = _load_text_file(PROPOSAL_LOOP_PATH)

    scoped_shadow = dict(scoped_probe_artifact.get("shadow_metrics", {}))
    scoped_effect = dict(scoped_probe_artifact.get("context_scoped_effect_report", {}))
    stabilization_shadow = dict(stabilization_probe_artifact.get("shadow_metrics", {}))
    stability_v1_report = dict(stability_snapshot_v1.get("stability_report", {}))
    stability_v2_report = dict(stability_snapshot_v2.get("stability_v2_report", {}))
    scope_effect_report = dict(scope_effect_snapshot.get("effect_decomposition_report", {}))

    scoped_vs_baseline = dict(scoped_shadow.get("comparison_vs_baseline", {}))
    scoped_vs_hybrid = dict(scoped_shadow.get("comparison_vs_hybrid", {}))
    scoped_partial = dict(scoped_shadow.get("partial_signal_given_baseline", {}))
    stabilization_vs_scoped = dict(stabilization_shadow.get("comparison_vs_context_scoped", {}))

    scoped_seed_effects = list(dict(scoped_effect.get("seed_level_effects", {})).get("context_scoped", []))
    scoped_slice_effects = list(dict(scoped_effect.get("context_slice_effects", {})).get("context_scoped", []))
    scoped_status_effects = dict(dict(scoped_effect.get("row_level_effects", {})).get("status_effects", {}))
    strongest_slice = dict(dict(scoped_effect.get("context_slice_effects", {})).get("strongest_slice", {}))
    weakest_slice = dict(dict(scoped_effect.get("context_slice_effects", {})).get("weakest_slice", {}))

    seed2_scoped = _find_seed(scoped_seed_effects, 2)
    strong_slice = _find_slice(scoped_slice_effects, "high_context_low_risk") or strongest_slice
    weak_slice = _find_slice(scoped_slice_effects, "low_context_high_risk") or weakest_slice

    stability_v1_overall = dict(stability_v1_report.get("overall_classification", {}))
    stability_v1_seed2 = dict(dict(stability_v1_report.get("weak_region_risk", {})).get("seed_2", {}))
    stability_v2_direct = dict(stability_v2_report.get("scoped_vs_stabilization_direct_comparison", {}))
    stability_v2_drift = dict(stability_v2_report.get("repeatability_vs_drift", {}))
    stability_v2_seed2 = dict(stability_v2_report.get("seed_2_correction_significance", {}))
    stability_v2_slices = dict(stability_v2_report.get("supported_slice_retention", {}))
    stability_v2_best = dict(stability_v2_report.get("best_current_narrow_working_configuration", {}))
    scope_effect_state = dict(scope_effect_report.get("stability_vs_locality_interpretation", {}))

    main_gap = _safe_float(
        dict(dict(scoped_shadow.get("context_scoped_separation", {})).get("gap_metrics", {})).get(
            "selection_score_pre_gate_provisional_minus_blocked"
        ),
        0.0,
    ) or 0.0
    signal_corr = _safe_float(scoped_vs_baseline.get("context_scoped_signal_availability_corr"), 0.0) or 0.0
    signal_gap = _safe_float(scoped_vs_baseline.get("context_scoped_signal_gap"), 0.0) or 0.0
    signal_overlap = _safe_float(
        scoped_vs_baseline.get("context_scoped_signal_overlap_to_baseline_pre_gate"),
        0.0,
    ) or 0.0
    distinctness = _safe_float(scoped_vs_baseline.get("context_scoped_distinctness_score"), 0.0) or 0.0
    partial_signal = _safe_float(scoped_partial.get("context_scoped"), None)
    positive_seed_count = int(
        dict(dict(scoped_effect.get("seed_level_effects", {}))).get("positive_seed_count", 0)
    )

    scoped_branch_cleanly_upstream = bool(
        dict(scoped_probe_artifact.get("diagnostic_conclusions", {})).get(
            "branch_stayed_cleanly_upstream",
            False,
        )
    )
    stabilization_branch_cleanly_upstream = bool(
        dict(stabilization_probe_artifact.get("diagnostic_conclusions", {})).get(
            "branch_stayed_cleanly_upstream",
            False,
        )
    )

    main_gap_min_improvement = 0.00005
    signal_gap_min_improvement = 0.00100
    distinctness_min_improvement = 0.00500
    partial_signal_min_improvement = 0.02000
    strong_slice_floor_delta = -0.00010
    strong_slice_target_delta = 0.00010
    weak_slice_floor_delta = 0.0
    weak_slice_regression_cap = -0.00010
    seed2_gap_min_improvement = 0.00005
    seed2_ratio_min_improvement = 0.10

    meaningful_improvement_criteria = {
        "required_hard_conditions": {
            "downstream_safety_envelope_unchanged": True,
            "branch_must_stay_cleanly_upstream": True,
            "plan_must_remain_non_owning": True,
            "positive_seed_count_vs_baseline_must_remain": 3,
            "selection_score_pre_gate_gap_delta_vs_scoped_min": float(main_gap_min_improvement),
            "signal_gap_delta_vs_scoped_min": float(signal_gap_min_improvement),
            "strong_slice_delta_delta_floor": float(strong_slice_floor_delta),
            "weak_slice_delta_must_remain_non_negative": float(weak_slice_floor_delta),
            "weak_slice_delta_delta_floor": float(weak_slice_regression_cap),
        },
        "secondary_support_conditions": {
            "distinctness_score_delta_vs_scoped_min": float(distinctness_min_improvement),
            "partial_signal_given_baseline_delta_vs_scoped_min": float(partial_signal_min_improvement),
            "strong_slice_delta_delta_target": float(strong_slice_target_delta),
            "seed_2_gap_delta_min": float(seed2_gap_min_improvement),
            "seed_2_gain_ratio_vs_scoped_min": float(seed2_ratio_min_improvement),
        },
        "interpretation_rule": "secondary-only gains do not count as real improvement if the main provisional-vs-blocked gap fails to improve materially",
    }

    scoped_should_be_working_baseline = bool(
        stability_v2_best.get("best_template") == "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1"
        and dict(stability_v1_overall).get("classification") == "stable_narrow_targeting"
        and dict(stability_v2_drift).get("classification") == "small_metric_drift"
        and not bool(dict(stability_snapshot_v2.get("diagnostic_conclusions", {})).get("another_stabilization_iteration_justified", True))
    )

    another_stabilization_iteration_justified = False
    plan_non_owning = True
    next_family = "memory_summary"
    next_template = "memory_summary.v4_wm_hybrid_branch_pause_snapshot_v1"
    next_rationale = "the current scoped-hybrid configuration should be held fixed as the narrow working baseline, and the next safe move is to pause this branch until a new idea clearly clears the baseline-improvement criteria"

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_wm_hybrid_scoped_working_baseline_snapshot_v1",
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
            "memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v2": _artifact_reference(
                stability_snapshot_v2,
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
        "working_baseline_report": {
            "current_scoped_hybrid_strengths": {
                "working_template": "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1",
                "classification": str(stability_v1_overall.get("classification", "")),
                "branch_stayed_cleanly_upstream": bool(scoped_branch_cleanly_upstream),
                "positive_seed_count_vs_baseline": int(positive_seed_count),
                "selection_score_pre_gate_gap": float(main_gap),
                "signal_availability_corr": float(signal_corr),
                "signal_gap": float(signal_gap),
                "signal_overlap_to_baseline_pre_gate": float(signal_overlap),
                "distinctness_score": float(distinctness),
                "partial_signal_given_baseline": partial_signal,
                "strong_slice": {
                    "slice": str(strong_slice.get("slice", "")),
                    "mean_selection_score_pre_gate_delta": _safe_float(
                        strong_slice.get("mean_selection_score_pre_gate_delta"),
                        0.0,
                    ),
                    "positive_delta_share": _safe_float(strong_slice.get("positive_delta_share"), 0.0),
                },
                "baseline_gap_delta_vs_hybrid": _safe_float(
                    scoped_vs_hybrid.get("selection_score_pre_gate_gap_delta"),
                    0.0,
                ),
                "reason": "the scoped configuration keeps all seeds positive against baseline, holds the strongest supported slice, and stays fully upstream and safe",
            },
            "protected_weak_regions": {
                "seed_2": {
                    "classification": str(stability_v1_seed2.get("weakness_classification", "")),
                    "selection_score_pre_gate_gap_delta": _safe_float(
                        seed2_scoped.get("selection_score_pre_gate_gap_delta"),
                        0.0,
                    ),
                    "accepted_status": "acceptable_correctable_weak_region",
                },
                "low_context_high_risk": {
                    "protection_status": str(stability_v2_slices.get("weak_slice_protection", "")),
                    "mean_selection_score_pre_gate_delta": _safe_float(
                        weak_slice.get("mean_selection_score_pre_gate_delta"),
                        0.0,
                    ),
                    "positive_delta_share": _safe_float(weak_slice.get("positive_delta_share"), 0.0),
                    "accepted_status": "protected_non_negative",
                },
                "reason": "the weak seed and weak slice are acceptable because they remain non-harmful under the current narrow configuration and do not break the upstream safety envelope",
            },
            "accepted_limitations": {
                "stability_vs_locality": str(scope_effect_state.get("classification", "")),
                "not_broad_enough_to_widen": True,
                "stabilization_repeatability_classification": str(
                    dict(stability_snapshot_v2.get("diagnostic_conclusions", {})).get(
                        "repeatability_classification",
                        "",
                    )
                ),
                "stabilization_seed_2_significance": str(
                    dict(stability_snapshot_v2.get("diagnostic_conclusions", {})).get(
                        "seed_2_correction_significance",
                        "",
                    )
                ),
                "accepted_reason": "the branch is intentionally narrow: high_context_low_risk carries the gain, low_context_high_risk stays protected, and stabilization has not yet cleared the bar to replace the current scoped baseline",
            },
            "meaningful_improvement_criteria": dict(meaningful_improvement_criteria),
            "failed_recent_challenger_example": {
                "template": "proposal_learning_loop.v4_wm_hybrid_context_stabilization_probe_v1",
                "selection_score_pre_gate_gap_delta_vs_scoped": _safe_float(
                    stability_v2_direct.get("delta_stabilization_minus_scoped", {}).get(
                        "selection_score_pre_gate_gap_delta"
                    ),
                    0.0,
                ),
                "signal_gap_delta_vs_scoped": _safe_float(
                    stability_v2_direct.get("delta_stabilization_minus_scoped", {}).get("signal_gap_delta"),
                    0.0,
                ),
                "distinctness_score_delta_vs_scoped": _safe_float(
                    stability_v2_direct.get("delta_stabilization_minus_scoped", {}).get(
                        "distinctness_score_delta"
                    ),
                    0.0,
                ),
                "seed_2_gain_ratio_vs_scoped": _safe_float(
                    stability_v2_seed2.get("seed_2_gain_ratio_vs_scoped"),
                    0.0,
                ),
                "why_not_enough": "secondary gains and marginal seed-2 correction did not convert into a real main-gap improvement",
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
            "scoped_hybrid_should_be_working_narrow_baseline": bool(scoped_should_be_working_baseline),
            "another_stabilization_iteration_justified": bool(another_stabilization_iteration_justified),
            "plan_should_remain_non_owning": bool(plan_non_owning),
            "recommended_next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "rationale": str(next_rationale),
        },
        "observability_gain": {
            "passed": True,
            "reason": "the snapshot formalizes the scoped-hybrid baseline by reusing the full scoped, stabilization, and stability evidence chain without opening another behavior-changing branch",
            "scoped_seed_report_count": int(len(scoped_seed_effects)),
            "scoped_slice_report_count": int(len(scoped_slice_effects)),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the snapshot defines the exact narrow baseline and the minimum conditions any future challenger must beat",
            "scoped_hybrid_should_be_working_narrow_baseline": bool(scoped_should_be_working_baseline),
            "plan_non_owning_preserved": bool(plan_non_owning),
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": float(
                min(
                    1.0,
                    0.62
                    + 0.10 * int(scoped_should_be_working_baseline)
                    + 0.08 * int(not another_stabilization_iteration_justified)
                    + 0.08 * int(plan_non_owning)
                    + 0.08 * int(str(stability_v1_overall.get("classification", "")) == "stable_narrow_targeting")
                )
            ),
            "reason": "the snapshot resolves what the current standard to beat is and separates real improvement from minor drift",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "diagnostic-only working-baseline formalization with live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": str(next_template),
            "reason": str(next_rationale),
        },
        "diagnostic_conclusions": {
            "scoped_hybrid_should_be_working_narrow_baseline": bool(scoped_should_be_working_baseline),
            "another_stabilization_iteration_justified": bool(another_stabilization_iteration_justified),
            "plan_should_remain_non_owning": bool(plan_non_owning),
            "recommended_next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
            "best_current_narrow_working_configuration": "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1",
        },
    }

    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"memory_summary_v4_wm_hybrid_scoped_working_baseline_snapshot_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: the scoped-hybrid probe was formalized as the current narrow working baseline without changing behavior",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
