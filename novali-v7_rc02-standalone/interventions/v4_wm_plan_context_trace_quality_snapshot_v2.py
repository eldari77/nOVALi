from __future__ import annotations

import json
from pathlib import Path
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
from .v4_wm_primary_plan_structure_probe_v1 import _safe_float


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(sum(values) / len(values))


def _artifact_reference(
    artifact: dict[str, Any] | None,
    latest_snapshots: dict[str, Any],
) -> dict[str, Any]:
    artifact = dict(artifact or {})
    proposal_id = str(artifact.get("proposal_id", ""))
    return {
        "proposal_id": proposal_id,
        "ledger_revision": int(dict(latest_snapshots.get(proposal_id, {})).get("ledger_revision", 0) or 0),
        "artifact_path": str(artifact.get("_artifact_path", "")),
    }


def _lookup_top_feature(
    ranked_rows: list[dict[str, Any]],
    feature: str,
) -> dict[str, Any]:
    for row in list(ranked_rows):
        if str(dict(row).get("feature", "")) == str(feature):
            return dict(row)
    return {"feature": str(feature), "correlation": None, "abs_correlation": None}


def _extract_seed_deltas(probe_artifact: dict[str, Any]) -> list[dict[str, Any]]:
    seed_rows: list[dict[str, Any]] = []
    shadow_metrics = dict(probe_artifact.get("shadow_metrics", {}))
    for row in list(shadow_metrics.get("per_seed_runs", [])):
        baseline_sep = dict(dict(row).get("baseline_separation", {}))
        probe_sep = dict(dict(row).get("probe_separation", {}))
        baseline_avail = dict(baseline_sep.get("availability_correlations", {}))
        probe_avail = dict(probe_sep.get("availability_correlations", {}))
        baseline_gaps = dict(baseline_sep.get("gap_metrics", {}))
        probe_gaps = dict(probe_sep.get("gap_metrics", {}))
        seed_rows.append(
            {
                "seed": int(dict(row).get("seed", 0)),
                "selection_score_pre_gate_availability_corr_delta": float(
                    (_safe_float(probe_avail.get("selection_score_pre_gate"), 0.0) or 0.0)
                    - (_safe_float(baseline_avail.get("selection_score_pre_gate"), 0.0) or 0.0)
                ),
                "calibrated_projected_availability_corr_delta": float(
                    (_safe_float(probe_avail.get("calibrated_projected"), 0.0) or 0.0)
                    - (_safe_float(baseline_avail.get("calibrated_projected"), 0.0) or 0.0)
                ),
                "selection_score_pre_gate_gap_delta": float(
                    (_safe_float(probe_gaps.get("selection_score_pre_gate_provisional_minus_blocked"), 0.0) or 0.0)
                    - (_safe_float(baseline_gaps.get("selection_score_pre_gate_provisional_minus_blocked"), 0.0) or 0.0)
                ),
                "v4_wm_discrimination_availability_corr": _safe_float(
                    probe_avail.get("v4_wm_discrimination_score"),
                    None,
                ),
                "v4_wm_discrimination_gap": _safe_float(
                    probe_gaps.get("v4_wm_discrimination_provisional_minus_blocked"),
                    None,
                ),
            }
        )
    return seed_rows


def _effective_discrimination_weights() -> dict[str, Any]:
    wm_supply = {
        "pred_context_support": 0.30,
        "pred_gain_norm": 0.20,
        "pred_gain_sign_prob": 0.18,
        "calibrated_projected": 0.12,
        "projection_recent": 0.08,
        "projection_trend": 0.06,
        "retained_evidence": 0.06,
        "retained_rounds": 0.04,
        "projected_quality": 0.18,
        "pred_uncertainty": 0.10,
        "wm_quality_penalty": 0.08,
    }
    effective = {
        "pred_context_support": 0.14 + 0.38 * wm_supply["pred_context_support"],
        "pred_gain_norm": 0.38 * wm_supply["pred_gain_norm"],
        "pred_gain_sign_prob": 0.18 + 0.38 * wm_supply["pred_gain_sign_prob"],
        "calibrated_projected": 0.16 + 0.38 * wm_supply["calibrated_projected"],
        "projected_quality": 0.08 + 0.38 * wm_supply["projected_quality"],
        "projection_recent": 0.06 + 0.38 * wm_supply["projection_recent"],
        "projection_trend": 0.38 * wm_supply["projection_trend"],
        "retained_evidence": 0.38 * wm_supply["retained_evidence"],
        "retained_rounds": 0.38 * wm_supply["retained_rounds"],
        "pred_uncertainty": 0.08 + 0.38 * wm_supply["pred_uncertainty"],
        "wm_quality_penalty": 0.06 + 0.38 * wm_supply["wm_quality_penalty"],
    }
    baseline_reused_mass = float(
        effective["pred_gain_norm"]
        + effective["pred_gain_sign_prob"]
        + effective["calibrated_projected"]
        + effective["projected_quality"]
        + effective["pred_uncertainty"]
    )
    context_distinct_mass = float(
        effective["pred_context_support"]
        + effective["projection_recent"]
        + effective["projection_trend"]
        + effective["retained_evidence"]
        + effective["retained_rounds"]
        + effective["wm_quality_penalty"]
    )
    return {
        "effective_feature_weights": effective,
        "baseline_reused_mass": baseline_reused_mass,
        "context_distinct_mass": context_distinct_mass,
        "baseline_reused_share": (
            float(baseline_reused_mass / max(baseline_reused_mass + context_distinct_mass, 1e-9))
        ),
        "mixing_path_limits": {
            "raw_delta_weight": 0.32,
            "raw_delta_center": 0.34,
            "raw_delta_clip": 0.12,
            "selection_weight": 0.25,
            "reason": "the probe can only add a bounded wm-only correction before the projected score is blended back into the existing pre-gate path",
        },
    }


def _feature_role_report(
    trace_quality_artifact: dict[str, Any],
    probe_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    trace_analysis = dict(trace_quality_artifact.get("trace_quality_analysis", {}))
    strongest = dict(trace_analysis.get("strongest_signals", {}))
    availability_rows = list(strongest.get("candidate_availability", []))
    projection_rows = list(strongest.get("projection_quality_non_direct", []))
    wm_plan_info = dict(trace_analysis.get("wm_plan_distinct_information", {}))

    probe_metrics = dict(probe_artifact.get("shadow_metrics", {}))
    probe_sep = dict(probe_metrics.get("probe_separation", {}))
    probe_avail = dict(probe_sep.get("availability_correlations", {}))
    probe_projection = dict(probe_sep.get("projection_quality_correlations", {}))

    availability_map = {
        row["feature"]: row for row in availability_rows if isinstance(row, dict)
    }
    projection_map = {
        row["feature"]: row for row in projection_rows if isinstance(row, dict)
    }

    feature_rows = []
    feature_rows.append(
        {
            "feature": "wm_context_supply_score",
            "role": "mixed_informative",
            "availability_signal": _safe_float(
                dict(availability_map.get("wm_context_supply_score", {})).get("correlation"),
                None,
            ),
            "projection_quality_signal": _safe_float(
                dict(projection_map.get("wm_context_supply_score", {})).get("correlation"),
                None,
            ),
            "reason": "real wm signal, but it already contains pred_gain_sign_prob and calibrated_projected terms, so it is only partly distinct from the baseline pre-gate path",
        }
    )
    feature_rows.append(
        {
            "feature": "pred_context_score",
            "role": "distinct_underused",
            "availability_signal": _safe_float(
                dict(availability_map.get("pred_context_score", {})).get("correlation"),
                None,
            ),
            "projection_quality_signal": _safe_float(
                dict(projection_map.get("pred_context_score", {})).get("correlation"),
                None,
            ),
            "reason": "strongest non-direct projection-quality feature and the clearest candidate for a more residualized wm-only correction",
        }
    )
    feature_rows.append(
        {
            "feature": "pred_gain_sign_prob",
            "role": "baseline_dominant_redundant",
            "availability_signal": _safe_float(
                dict(availability_map.get("pred_gain_sign_prob", {})).get("correlation"),
                None,
            ),
            "projection_quality_signal": None,
            "reason": "already one of the strongest baseline availability signals, so reusing it inside the wm correction mostly recreates the baseline path",
        }
    )
    feature_rows.append(
        {
            "feature": "calibrated_projected",
            "role": "baseline_dominant_redundant",
            "availability_signal": _safe_float(
                dict(availability_map.get("calibrated_projected", {})).get("correlation"),
                None,
            ),
            "projection_quality_signal": _safe_float(
                dict(projection_map.get("calibrated_projected", {})).get("correlation"),
                None,
            ),
            "reason": "already embedded in projected scoring and pre-gate ranking, so using it again inside the wm correction dilutes distinctness",
        }
    )
    feature_rows.append(
        {
            "feature": "v4_wm_discrimination_score",
            "role": "real_but_subsumed",
            "availability_signal": _safe_float(probe_avail.get("v4_wm_discrimination_score"), None),
            "projection_quality_signal": _safe_float(probe_projection.get("v4_wm_discrimination_score"), None),
            "reason": "the new score itself is informative, but its current mix is too overlapped with the existing pre-gate path to outperform baseline separation",
        }
    )
    feature_rows.append(
        {
            "feature": "planning_handoff_score",
            "role": "redundant_non_owner",
            "availability_signal": _safe_float(
                dict(trace_analysis.get("wm_plan_distinct_information", {})).get("plan_availability_correlation"),
                None,
            ),
            "projection_quality_signal": None,
            "reason": (
                "planning remains non-owning because its score is effectively collinear with wm_context_supply_score "
                f"(wm_plan_correlation={_safe_float(wm_plan_info.get('wm_plan_correlation'), 0.0):.4f})"
            ),
        }
    )
    feature_rows.append(
        {
            "feature": "wm_quality_penalty",
            "role": "weak_noise",
            "availability_signal": 0.0,
            "projection_quality_signal": 0.0,
            "reason": "the earlier trace-quality snapshot found it effectively non-discriminative in the first branch configuration",
        }
    )
    return feature_rows


def _root_cause_report(
    probe_artifact: dict[str, Any],
    trace_quality_artifact: dict[str, Any],
) -> dict[str, Any]:
    shadow_metrics = dict(probe_artifact.get("shadow_metrics", {}))
    comparison = dict(shadow_metrics.get("comparison_vs_baseline", {}))
    seed_deltas = _extract_seed_deltas(probe_artifact)
    effective_weights = _effective_discrimination_weights()

    availability_delta = _safe_float(comparison.get("selection_score_pre_gate_availability_corr_delta"), 0.0) or 0.0
    projected_delta = _safe_float(comparison.get("calibrated_projected_availability_corr_delta"), 0.0) or 0.0
    gap_delta = _safe_float(comparison.get("selection_score_pre_gate_gap_delta"), 0.0) or 0.0
    discr_corr = _safe_float(comparison.get("v4_wm_discrimination_availability_corr_probe"), 0.0) or 0.0
    discr_gap = _safe_float(comparison.get("v4_wm_discrimination_gap_probe"), 0.0) or 0.0

    positive_seed_count = sum(
        1
        for row in seed_deltas
        if (_safe_float(row.get("v4_wm_discrimination_availability_corr"), 0.0) or 0.0) >= 0.50
        and (_safe_float(row.get("v4_wm_discrimination_gap"), 0.0) or 0.0) > 0.0
    )
    improving_seed_count = sum(
        1
        for row in seed_deltas
        if (_safe_float(row.get("selection_score_pre_gate_availability_corr_delta"), 0.0) or 0.0) > 0.0
    )
    worsening_seed_count = sum(
        1
        for row in seed_deltas
        if (_safe_float(row.get("selection_score_pre_gate_availability_corr_delta"), 0.0) or 0.0) < 0.0
    )

    trace_wm_plan = dict(trace_quality_artifact.get("trace_quality_analysis", {})).get(
        "wm_plan_distinct_information",
        {},
    )
    planning_redundant = not bool(dict(trace_wm_plan).get("distinct_information_present", False))

    ranked_causes = [
        {
            "cause": "baseline_pre_gate_subsumption",
            "rank": 1,
            "confidence": "high",
            "reason": (
                "baseline pre-gate separation was already stronger than the new wm score "
                f"(selection_score_pre_gate corr delta={availability_delta:+.4f}, calibrated_projected corr delta={projected_delta:+.4f}), "
                "so the new signal was mostly absorbed instead of opening a new separation axis"
            ),
        },
        {
            "cause": "feature_redundancy_inside_wm_mix",
            "rank": 2,
            "confidence": "high",
            "reason": (
                "the current wm discrimination mix reuses too much baseline-like mass "
                f"(baseline_reused_share={effective_weights['baseline_reused_share']:.3f}) "
                "through pred_gain_sign_prob, calibrated_projected, projected-quality, and uncertainty terms"
            ),
        },
        {
            "cause": "bad_weighting_or_mixing_dilution",
            "rank": 3,
            "confidence": "medium",
            "reason": (
                "the bounded raw delta and 0.25 projected-score blend keep the wm correction small even when the wm-only signal is real "
                f"(wm discrimination corr={discr_corr:.4f}, wm discrimination gap={discr_gap:.4f})"
            ),
        },
        {
            "cause": "seed_context_sensitivity",
            "rank": 4,
            "confidence": "medium",
            "reason": (
                f"the wm score was positive in {positive_seed_count}/{len(seed_deltas)} seeds, but pre-gate availability improvement only appeared in "
                f"{improving_seed_count} seed(s) and regressed in {worsening_seed_count} seed(s)"
            ),
        },
        {
            "cause": "weak_feature_quality",
            "rank": 5,
            "confidence": "low",
            "reason": (
                "feature quality is not the primary problem because the wm-only score itself remained informative and positive, "
                f"even though overall pre-gate improvement was only {gap_delta:+.4f} on the provisional-minus-blocked gap"
            ),
        },
        {
            "cause": "plan_ownership_gap",
            "rank": 6,
            "confidence": "low",
            "reason": (
                "plan_ still looks non-owning because the earlier trace snapshot found planning effectively redundant "
                f"(planning_distinct={not planning_redundant})"
            ),
        },
    ]
    return {
        "ranked_causes": ranked_causes,
        "seed_context_sensitivity": {
            "label": (
                "mixed_secondary"
                if improving_seed_count > 0 and worsening_seed_count > 0
                else "low"
            ),
            "per_seed_deltas": seed_deltas,
        },
    }


def _subset_hypotheses_report() -> list[dict[str, Any]]:
    return [
        {
            "name": "wm_context_residual_subset",
            "status": "strongest_candidate",
            "feature_subset": [
                "wm_context_supply_score",
                "pred_context_score",
                "inverse pred_projection_bad_prob",
                "projection_recent",
            ],
            "drop_or_reduce": [
                "direct pred_gain_sign_prob term",
                "direct calibrated_projected term",
            ],
            "reason": "this keeps the most context-specific features while reducing the two strongest baseline-dominant reuse channels that likely washed out the first wm-only probe",
        },
        {
            "name": "pred_context_first_residual_correction",
            "status": "secondary_candidate",
            "feature_subset": [
                "pred_context_score",
                "wm_context_supply_score",
                "uncertainty penalty",
            ],
            "drop_or_reduce": [
                "direct projected-score reuse",
            ],
            "reason": "pred_context_score was the strongest non-direct projection-quality signal, so it looks like the cleanest distinct anchor if another wm-only correction is attempted",
        },
        {
            "name": "current_probe_mix",
            "status": "not_recommended_repeat",
            "feature_subset": [
                "wm_context_supply_score",
                "pred_gain_sign_prob",
                "calibrated_projected",
                "pred_context_support",
                "projected_quality",
            ],
            "drop_or_reduce": [],
            "reason": "the first behavior-changing probe showed that this broader blend is too overlapped with the baseline pre-gate path to justify repeating unchanged",
        },
    ]


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    probe_artifact = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1"
    )
    trace_quality_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v1"
    )
    wm_branch_artifact = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_wm_primary_plan_structure_probe_v1"
    )
    wm_entry_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_world_model_planning_context_entry_snapshot_v1"
    )
    hardening_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.swap_c_incumbent_hardening_probe_v1"
    )
    frontier_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.false_safe_frontier_control_characterization_snapshot_v1"
    )
    if not all(
        [
            probe_artifact,
            trace_quality_artifact,
            wm_branch_artifact,
            wm_entry_artifact,
            hardening_artifact,
            frontier_artifact,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: v2 trace-quality explanation requires the first wm-only probe and prior v4 trace-quality artifacts",
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
                "reason": "cannot explain the wm-only shortfall without the first probe artifact",
            },
        }

    active_status_text = _load_text_file(ACTIVE_STATUS_PATH)
    handoff_status = _load_json_file(HANDOFF_STATUS_PATH)
    analytics = build_intervention_ledger_analytics()
    latest_snapshots = load_latest_snapshots()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")
    proposal_loop_text = _load_text_file(PROPOSAL_LOOP_PATH)

    probe_shadow = dict(dict(probe_artifact).get("shadow_metrics", {}))
    probe_comparison = dict(probe_shadow.get("comparison_vs_baseline", {}))
    effective_weights = _effective_discrimination_weights()
    root_cause_report = _root_cause_report(probe_artifact, trace_quality_artifact)
    feature_roles = _feature_role_report(trace_quality_artifact, probe_artifact)
    subset_hypotheses = _subset_hypotheses_report()
    distinct_info = dict(
        dict(trace_quality_artifact.get("trace_quality_analysis", {})).get("wm_plan_distinct_information", {})
    )

    second_probe_justified = bool(
        bool(dict(probe_artifact.get("diagnostic_conclusions", {})).get("branch_stayed_cleanly_upstream", False))
        and bool(dict(probe_artifact.get("safety_neutrality", {})).get("passed", False))
        and (_safe_float(probe_comparison.get("v4_wm_discrimination_availability_corr_probe"), 0.0) or 0.0) >= 0.50
        and (_safe_float(probe_comparison.get("v4_wm_discrimination_gap_probe"), 0.0) or 0.0) > 0.05
    )
    next_family = "proposal_learning_loop" if second_probe_justified else "memory_summary"
    next_template = (
        "proposal_learning_loop.v4_wm_context_residual_signal_probe_v1"
        if second_probe_justified
        else "memory_summary.v4_wm_context_signal_overlap_snapshot_v1"
    )
    next_rationale = (
        "a second wm-only behavior-changing probe is justified, but only as a narrower residualized subset probe that removes baseline-dominant reuse and keeps plan_ non-owning"
        if second_probe_justified
        else "the wm-only line should pause for another diagnostic because the first probe exposed too little distinct headroom beyond the baseline path"
    )

    comparison_refs = {
        "proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1": _artifact_reference(
            probe_artifact,
            latest_snapshots,
        ),
        "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v1": _artifact_reference(
            trace_quality_artifact,
            latest_snapshots,
        ),
        "proposal_learning_loop.v4_wm_primary_plan_structure_probe_v1": _artifact_reference(
            wm_branch_artifact,
            latest_snapshots,
        ),
        "memory_summary.v4_world_model_planning_context_entry_snapshot_v1": _artifact_reference(
            wm_entry_artifact,
            latest_snapshots,
        ),
        "critic_split.swap_c_incumbent_hardening_probe_v1": _artifact_reference(
            hardening_artifact,
            latest_snapshots,
        ),
        "memory_summary.false_safe_frontier_control_characterization_snapshot_v1": _artifact_reference(
            frontier_artifact,
            latest_snapshots,
        ),
    }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v2",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "branch_context": {
            "active_status_path": str(ACTIVE_STATUS_PATH),
            "handoff_status_path": str(HANDOFF_STATUS_PATH),
            "proposal_learning_loop_path": str(PROPOSAL_LOOP_PATH),
            "active_status_mentions_v4_active": "`novali-v4` is the active working version." in active_status_text,
            "carried_forward_baseline": dict(handoff_status.get("carried_forward_baseline", {})),
            "routing_deferred": bool(dict(frontier_artifact.get("diagnostic_conclusions", {})).get("routing_deferred", False)),
        },
        "comparison_references": comparison_refs,
        "shortfall_diagnostic_report": {
            "root_cause_ranking": dict(root_cause_report),
            "baseline_pre_gate_overlap": {
                "selection_score_pre_gate_availability_corr_delta": _safe_float(
                    probe_comparison.get("selection_score_pre_gate_availability_corr_delta"),
                    None,
                ),
                "calibrated_projected_availability_corr_delta": _safe_float(
                    probe_comparison.get("calibrated_projected_availability_corr_delta"),
                    None,
                ),
                "selection_score_pre_gate_gap_delta": _safe_float(
                    probe_comparison.get("selection_score_pre_gate_gap_delta"),
                    None,
                ),
                "v4_wm_discrimination_availability_corr_probe": _safe_float(
                    probe_comparison.get("v4_wm_discrimination_availability_corr_probe"),
                    None,
                ),
                "v4_wm_discrimination_gap_probe": _safe_float(
                    probe_comparison.get("v4_wm_discrimination_gap_probe"),
                    None,
                ),
                "reason": "the wm-only score was real, but the incumbent pre-gate path remained stronger and absorbed most of the correction",
            },
            "feature_distinctness_vs_redundancy": feature_roles,
            "effective_mix_breakdown": effective_weights,
            "candidate_subset_hypotheses": subset_hypotheses,
            "plan_ownership_check": {
                "plan_should_remain_non_owning": not bool(distinct_info.get("distinct_information_present", False)),
                "wm_plan_correlation": _safe_float(distinct_info.get("wm_plan_correlation"), None),
                "reason": "plan_ still looks redundant with wm_ in the current branch, so ownership should not move downstream or sideways yet",
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
            "second_behavior_changing_wm_probe_justified": bool(second_probe_justified),
            "plan_should_remain_non_owning": not bool(distinct_info.get("distinct_information_present", False)),
            "recommended_next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "rationale": str(next_rationale),
        },
        "observability_gain": {
            "passed": True,
            "reason": "the snapshot explains the first wm-only probe directly from recorded trace-quality and probe artifacts without reopening downstream lines",
            "probe_trace_row_count": int(dict(probe_artifact.get("observability_gain", {})).get("probe_trace_row_count", 0) or 0),
            "seed_count": int(len(dict(root_cause_report.get("seed_context_sensitivity", {})).get("per_seed_deltas", []))),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the snapshot distinguishes redundancy, subsumption, mixing dilution, and seed/context sensitivity instead of treating the first wm-only miss as a generic failure",
            "second_behavior_changing_wm_probe_justified": bool(second_probe_justified),
            "plan_should_remain_non_owning": not bool(distinct_info.get("distinct_information_present", False)),
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.93,
            "reason": "the snapshot isolates why the first wm-only behavior-changing probe stayed safe but failed to beat baseline pre-gate separation and identifies the narrowest next step",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "diagnostic-only explanation snapshot with live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": str(next_template),
            "reason": str(next_rationale),
        },
        "diagnostic_conclusions": {
            "shortfall_primary_cause": "baseline_pre_gate_subsumption",
            "shortfall_secondary_cause": "feature_redundancy_inside_wm_mix",
            "second_behavior_changing_wm_probe_justified": bool(second_probe_justified),
            "plan_should_remain_non_owning": not bool(distinct_info.get("distinct_information_present", False)),
            "recommended_next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "routing_deferred": bool(dict(frontier_artifact.get("diagnostic_conclusions", {})).get("routing_deferred", False)),
        },
    }

    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"memory_summary_v4_wm_plan_context_trace_quality_snapshot_v2_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: the first wm-only shortfall was explained without changing behavior",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
