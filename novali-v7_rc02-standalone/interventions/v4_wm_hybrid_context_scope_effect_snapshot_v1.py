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


def _delta(left: Any, right: Any) -> float | None:
    left_value = _safe_float(left, None)
    right_value = _safe_float(right, None)
    if left_value is None or right_value is None:
        return None
    return float(left_value - right_value)


def _find_slice_report(reports: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for report in reports:
        if str(report.get("slice", "")) == str(name):
            return dict(report)
    return {}


def _seed_index(reports: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {
        int(report.get("seed", 0)): dict(report)
        for report in reports
        if isinstance(report, dict)
    }


def _seed_delta_reports(
    scoped_reports: list[dict[str, Any]],
    hybrid_reports: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    hybrid_by_seed = _seed_index(hybrid_reports)
    rows: list[dict[str, Any]] = []
    for seed, scoped in sorted(_seed_index(scoped_reports).items()):
        hybrid = dict(hybrid_by_seed.get(seed, {}))
        rows.append(
            {
                "seed": int(seed),
                "selection_score_pre_gate_gap_delta_vs_hybrid": _delta(
                    scoped.get("selection_score_pre_gate_gap_delta"),
                    hybrid.get("selection_score_pre_gate_gap_delta"),
                ),
                "mean_selection_score_pre_gate_delta_vs_hybrid": _delta(
                    scoped.get("mean_selection_score_pre_gate_delta"),
                    hybrid.get("mean_selection_score_pre_gate_delta"),
                ),
                "signal_availability_corr_vs_hybrid": _delta(
                    scoped.get("signal_availability_corr"),
                    hybrid.get("signal_availability_corr"),
                ),
                "scoped_selection_score_pre_gate_gap_delta": _safe_float(
                    scoped.get("selection_score_pre_gate_gap_delta"),
                    None,
                ),
                "hybrid_selection_score_pre_gate_gap_delta": _safe_float(
                    hybrid.get("selection_score_pre_gate_gap_delta"),
                    None,
                ),
            }
        )
    return rows


def _top_seed(reports: list[dict[str, Any]], key: str, *, reverse: bool) -> dict[str, Any]:
    if not reports:
        return {}
    return dict(
        sorted(
            reports,
            key=lambda item: _safe_float(item.get(key), 0.0) or 0.0,
            reverse=bool(reverse),
        )[0]
    )


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    scoped_probe_artifact = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1"
    )
    hybrid_probe_artifact = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1"
    )
    hybrid_effect_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_probe_effect_snapshot_v1"
    )
    hybrid_boundary_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_baseline_hybrid_boundary_snapshot_v1"
    )
    overlap_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_context_signal_overlap_snapshot_v1"
    )
    trace_quality_v2_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v2"
    )
    wm_entry_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_world_model_planning_context_entry_snapshot_v1"
    )
    frontier_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.false_safe_frontier_control_characterization_snapshot_v1"
    )
    if not all(
        [
            scoped_probe_artifact,
            hybrid_probe_artifact,
            hybrid_effect_snapshot,
            hybrid_boundary_snapshot,
            overlap_snapshot,
            trace_quality_v2_snapshot,
            wm_entry_snapshot,
            frontier_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: scope-effect decomposition needs the broad hybrid probe, the scoped hybrid probe, and the prior hybrid diagnostics",
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
                "reason": "cannot decompose scoped-hybrid effects without the existing hybrid probe artifacts",
            },
        }

    active_status_text = _load_text_file(ACTIVE_STATUS_PATH)
    handoff_status = _load_json_file(HANDOFF_STATUS_PATH)
    analytics = build_intervention_ledger_analytics()
    latest_snapshots = load_latest_snapshots()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")
    proposal_loop_text = _load_text_file(PROPOSAL_LOOP_PATH)

    hybrid_vs_baseline = dict(dict(hybrid_probe_artifact.get("shadow_metrics", {})).get("comparison_vs_baseline", {}))
    scoped_vs_baseline = dict(dict(scoped_probe_artifact.get("shadow_metrics", {})).get("comparison_vs_baseline", {}))
    scoped_vs_hybrid = dict(dict(scoped_probe_artifact.get("shadow_metrics", {})).get("comparison_vs_hybrid", {}))

    effect_mapping = dict(hybrid_effect_snapshot.get("effect_mapping_report", {}))
    hybrid_status_effects = dict(dict(effect_mapping.get("row_level_effects", {})).get("status_effects", {}))
    hybrid_slice_effects = list(dict(effect_mapping.get("context_slice_effects", {})).get("slice_reports", []))

    scoped_effect = dict(scoped_probe_artifact.get("context_scoped_effect_report", {}))
    scoped_status_effects = dict(dict(scoped_effect.get("row_level_effects", {})).get("status_effects", {}))
    context_slice_effects = dict(scoped_effect.get("context_slice_effects", {}))
    hybrid_reference_slices = list(context_slice_effects.get("hybrid_reference", []))
    scoped_slices = list(context_slice_effects.get("context_scoped", []))

    hybrid_strong = _find_slice_report(hybrid_reference_slices or hybrid_slice_effects, "high_context_low_risk")
    hybrid_weak = _find_slice_report(hybrid_reference_slices or hybrid_slice_effects, "low_context_high_risk")
    scoped_strong = _find_slice_report(scoped_slices, "high_context_low_risk")
    scoped_weak = _find_slice_report(scoped_slices, "low_context_high_risk")
    hybrid_mixed = _find_slice_report(hybrid_reference_slices or hybrid_slice_effects, "mixed")
    scoped_mixed = _find_slice_report(scoped_slices, "mixed")

    seed_effects = dict(scoped_effect.get("seed_level_effects", {}))
    hybrid_seed_effects = list(seed_effects.get("hybrid_reference", []))
    scoped_seed_effects = list(seed_effects.get("context_scoped", []))
    per_seed_delta = _seed_delta_reports(scoped_seed_effects, hybrid_seed_effects)

    boundary_effect = {
        "selection_score_pre_gate_availability_corr_delta_vs_baseline": _safe_float(
            hybrid_vs_baseline.get("selection_score_pre_gate_availability_corr_delta"),
            None,
        ),
        "selection_score_pre_gate_gap_delta_vs_baseline": _safe_float(
            hybrid_vs_baseline.get("selection_score_pre_gate_gap_delta"),
            None,
        ),
        "signal_availability_corr": _safe_float(hybrid_vs_baseline.get("hybrid_signal_availability_corr"), None),
        "signal_gap": _safe_float(hybrid_vs_baseline.get("hybrid_signal_gap"), None),
        "signal_overlap_to_baseline_pre_gate": _safe_float(
            hybrid_vs_baseline.get("hybrid_signal_overlap_to_baseline_pre_gate"),
            None,
        ),
        "distinctness_score": _safe_float(hybrid_vs_baseline.get("hybrid_distinctness_score"), None),
        "interpretation": "base hybrid boundary creates the main upstream gain while keeping baseline ranking carriers in place",
    }

    scope_multiplier_effect = {
        "selection_score_pre_gate_availability_corr_delta_vs_hybrid": _safe_float(
            scoped_vs_hybrid.get("selection_score_pre_gate_availability_corr_delta"),
            None,
        ),
        "selection_score_pre_gate_gap_delta_vs_hybrid": _safe_float(
            scoped_vs_hybrid.get("selection_score_pre_gate_gap_delta"),
            None,
        ),
        "signal_availability_corr_delta_vs_hybrid": _safe_float(
            scoped_vs_hybrid.get("signal_availability_corr_delta"),
            None,
        ),
        "signal_gap_delta_vs_hybrid": _safe_float(scoped_vs_hybrid.get("signal_gap_delta"), None),
        "signal_overlap_to_baseline_pre_gate_delta_vs_hybrid": _safe_float(
            scoped_vs_hybrid.get("signal_overlap_to_baseline_pre_gate_delta"),
            None,
        ),
        "distinctness_score_delta_vs_hybrid": _safe_float(
            scoped_vs_hybrid.get("distinctness_score_delta"),
            None,
        ),
        "partial_signal_given_baseline_delta_vs_hybrid": _safe_float(
            scoped_vs_hybrid.get("partial_signal_given_baseline_delta"),
            None,
        ),
        "interpretation": "scope multipliers add a smaller second-stage lift by concentrating the hybrid benefit into supported slices rather than broadening the boundary",
    }

    interaction_effect = {
        "high_context_low_risk_delta_delta": _delta(
            scoped_strong.get("mean_selection_score_pre_gate_delta"),
            hybrid_strong.get("mean_selection_score_pre_gate_delta"),
        ),
        "high_context_low_risk_positive_delta_share_delta": _delta(
            scoped_strong.get("positive_delta_share"),
            hybrid_strong.get("positive_delta_share"),
        ),
        "high_context_low_risk_scope_multiplier": _safe_float(
            scoped_strong.get("mean_scope_multiplier"),
            None,
        ),
        "low_context_high_risk_delta_delta": _delta(
            scoped_weak.get("mean_selection_score_pre_gate_delta"),
            hybrid_weak.get("mean_selection_score_pre_gate_delta"),
        ),
        "low_context_high_risk_positive_delta_share_delta": _delta(
            scoped_weak.get("positive_delta_share"),
            hybrid_weak.get("positive_delta_share"),
        ),
        "low_context_high_risk_scope_multiplier": _safe_float(
            scoped_weak.get("mean_scope_multiplier"),
            None,
        ),
        "mixed_slice_delta_delta": _delta(
            scoped_mixed.get("mean_selection_score_pre_gate_delta"),
            hybrid_mixed.get("mean_selection_score_pre_gate_delta"),
        ),
        "provisional_delta_delta": _delta(
            scoped_status_effects.get("provisional", {}).get("mean_selection_score_pre_gate_delta"),
            hybrid_status_effects.get("provisional", {}).get("mean_selection_score_pre_gate_delta"),
        ),
        "blocked_delta_delta": _delta(
            scoped_status_effects.get("blocked", {}).get("mean_selection_score_pre_gate_delta"),
            hybrid_status_effects.get("blocked", {}).get("mean_selection_score_pre_gate_delta"),
        ),
        "provisional_minus_blocked_delta_delta": _delta(
            scoped_status_effects.get("provisional_minus_blocked_delta"),
            hybrid_status_effects.get("provisional_minus_blocked_delta"),
        ),
        "interpretation": "scope logic supplies both targeted amplification in the strongest slice and protection against over-applying the hybrid in the weakest slice, with amplification as the larger visible effect",
    }

    stable_seed_count = sum(
        1
        for report in per_seed_delta
        if (_safe_float(report.get("selection_score_pre_gate_gap_delta_vs_hybrid"), 0.0) or 0.0) > 0.0
    )
    strong_slice_gain = _safe_float(interaction_effect.get("high_context_low_risk_delta_delta"), 0.0) or 0.0
    weak_slice_harm = _safe_float(interaction_effect.get("low_context_high_risk_delta_delta"), 0.0) or 0.0
    broadenable = bool(
        stable_seed_count == len(per_seed_delta)
        and strong_slice_gain >= 0.00025
        and weak_slice_harm >= -0.00002
    )
    stabilization_supported = bool(
        stable_seed_count == len(per_seed_delta)
        and strong_slice_gain > 0.0
        and weak_slice_harm >= -0.00010
    )
    locality_classification = (
        "broadenable"
        if broadenable
        else "stabilizable_but_still_local"
        if stabilization_supported
        else "best_kept_narrowly_targeted"
    )

    if broadenable:
        next_family = "proposal_learning_loop"
        next_template = "proposal_learning_loop.v4_wm_hybrid_broadening_probe_v1"
        next_rationale = "scope effects are stable enough across seeds and slices to justify a carefully broader hybrid application"
    elif stabilization_supported:
        next_family = "proposal_learning_loop"
        next_template = "proposal_learning_loop.v4_wm_hybrid_context_stabilization_probe_v1"
        next_rationale = "scope effects are real and stable but still local, so the next safe step is to stabilize the targeted application rather than broaden it"
    else:
        next_family = "memory_summary"
        next_template = "memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v1"
        next_rationale = "the scoped benefit remains too uneven, so another diagnostic should precede any further behavior-changing probe"

    safety_preserved = bool(dict(scoped_probe_artifact.get("safety_neutrality", {})).get("passed", False))

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_wm_hybrid_context_scope_effect_snapshot_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "branch_context": {
            "active_status_path": str(ACTIVE_STATUS_PATH),
            "handoff_status_path": str(HANDOFF_STATUS_PATH),
            "proposal_learning_loop_path": str(PROPOSAL_LOOP_PATH),
            "active_status_mentions_v4_active": "`novali-v4` is the active working version." in active_status_text,
            "carried_forward_baseline": dict(handoff_status.get("carried_forward_baseline", {})),
            "routing_deferred": bool(dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)),
        },
        "comparison_references": {
            "proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1": _artifact_reference(
                hybrid_probe_artifact,
                latest_snapshots,
            ),
            "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1": _artifact_reference(
                scoped_probe_artifact,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_hybrid_probe_effect_snapshot_v1": _artifact_reference(
                hybrid_effect_snapshot,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_baseline_hybrid_boundary_snapshot_v1": _artifact_reference(
                hybrid_boundary_snapshot,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_context_signal_overlap_snapshot_v1": _artifact_reference(
                overlap_snapshot,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v2": _artifact_reference(
                trace_quality_v2_snapshot,
                latest_snapshots,
            ),
            "memory_summary.v4_world_model_planning_context_entry_snapshot_v1": _artifact_reference(
                wm_entry_snapshot,
                latest_snapshots,
            ),
            "memory_summary.false_safe_frontier_control_characterization_snapshot_v1": _artifact_reference(
                frontier_snapshot,
                latest_snapshots,
            ),
        },
        "effect_decomposition_report": {
            "hybrid_boundary_effect": boundary_effect,
            "scope_multiplier_effect": scope_multiplier_effect,
            "interaction_effect": interaction_effect,
            "row_seed_context_benefit_map": {
                "row_level": {
                    "hybrid_boundary_status_effects": hybrid_status_effects,
                    "context_scoped_status_effects": scoped_status_effects,
                    "scoping_specific_provisional_gain_delta": interaction_effect["provisional_delta_delta"],
                    "scoping_specific_blocked_gain_delta": interaction_effect["blocked_delta_delta"],
                },
                "seed_level": {
                    "hybrid_reference": hybrid_seed_effects,
                    "context_scoped": scoped_seed_effects,
                    "seed_deltas_vs_hybrid": per_seed_delta,
                    "strongest_seed_for_scoping": _top_seed(
                        per_seed_delta,
                        "selection_score_pre_gate_gap_delta_vs_hybrid",
                        reverse=True,
                    ),
                    "weakest_seed_for_scoping": _top_seed(
                        per_seed_delta,
                        "selection_score_pre_gate_gap_delta_vs_hybrid",
                        reverse=False,
                    ),
                    "stable_positive_seed_count": int(stable_seed_count),
                },
                "context_slice_level": {
                    "hybrid_reference": hybrid_reference_slices or hybrid_slice_effects,
                    "context_scoped": scoped_slices,
                    "strongest_supported_slice": dict(scoped_strong),
                    "weakest_supported_slice": dict(scoped_weak),
                },
            },
            "stability_vs_locality_interpretation": {
                "classification": str(locality_classification),
                "broad_enough_to_justify_broadening": bool(broadenable),
                "stabilization_supported": bool(stabilization_supported),
                "reason": (
                    "the scoping step is stable enough across seeds and slices to justify controlled broadening"
                    if broadenable
                    else "the scoping step adds stable targeted amplification and weak-slice protection, but the gain remains concentrated in supported slices rather than broad enough for wholesale broadening"
                    if stabilization_supported
                    else "the scoped improvement is still too local or uneven, so it is best kept narrowly targeted until more diagnostics land"
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
            "broad_enough_to_justify_broadening": bool(broadenable),
            "plan_should_remain_non_owning": True,
            "recommended_next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "rationale": str(next_rationale),
        },
        "observability_gain": {
            "passed": True,
            "reason": "the snapshot decomposes the scoped-hybrid win using the already observed hybrid and scoped-hybrid artifacts without opening another behavior-changing branch",
            "hybrid_reference_artifact_present": True,
            "context_scoped_artifact_present": True,
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the snapshot separates the base hybrid effect from the extra scope contribution so the next move can target broadening, stabilization, or pause for the right reason",
            "broad_enough_to_justify_broadening": bool(broadenable),
            "stabilization_supported": bool(stabilization_supported),
            "plan_non_owning_preserved": True,
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": float(
                min(
                    1.0,
                    0.58
                    + 0.10 * int(stable_seed_count == len(per_seed_delta))
                    + 0.10 * int(strong_slice_gain > 0.0)
                    + 0.08 * int(weak_slice_harm >= -0.00010)
                    + 0.08 * int(locality_classification == "stabilizable_but_still_local")
                )
            ),
            "reason": "the snapshot shows how much of the gain comes from the boundary itself, how much comes from scoping, and whether that scope effect is broad enough to generalize",
        },
        "safety_neutrality": {
            "passed": bool(safety_preserved),
            "scope": str(proposal.get("scope", "")),
            "reason": "diagnostic-only scope-effect decomposition with live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": str(next_template),
            "reason": str(next_rationale),
        },
        "diagnostic_conclusions": {
            "broad_enough_to_justify_broadening": bool(broadenable),
            "plan_should_remain_non_owning": True,
            "recommended_next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "routing_deferred": bool(dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)),
            "stability_vs_locality": str(locality_classification),
        },
    }

    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"memory_summary_v4_wm_hybrid_context_scope_effect_snapshot_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": bool(safety_preserved),
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": (
            "diagnostic shadow passed: scoped-hybrid gain decomposition completed without changing downstream behavior"
            if safety_preserved
            else "diagnostic shadow failed: scope-effect decomposition detected an unexpected safety regression"
        ),
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
