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


def _std(values: list[float]) -> float | None:
    if not values:
        return None
    mean_value = _mean(values)
    if mean_value is None:
        return None
    return float((sum((float(value) - mean_value) ** 2 for value in values) / len(values)) ** 0.5)


def _coefficient_of_variation(values: list[float]) -> float | None:
    mean_value = _mean(values)
    std_value = _std(values)
    if mean_value is None or std_value is None or abs(mean_value) <= 1e-12:
        return None
    return float(std_value / abs(mean_value))


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
    hybrid_effect_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_probe_effect_snapshot_v1"
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
            hybrid_effect_snapshot,
            scope_effect_snapshot,
            hybrid_probe_artifact,
            frontier_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: scoped-hybrid stability analysis requires the scoped probe, the broad hybrid effect snapshot, and the scope-effect decomposition snapshot",
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
                "reason": "cannot classify scoped-hybrid stability without the prerequisite scoped-hybrid artifacts",
            },
        }

    active_status_text = _load_text_file(ACTIVE_STATUS_PATH)
    handoff_status = _load_json_file(HANDOFF_STATUS_PATH)
    analytics = build_intervention_ledger_analytics()
    latest_snapshots = load_latest_snapshots()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")
    proposal_loop_text = _load_text_file(PROPOSAL_LOOP_PATH)

    scoped_effect = dict(scoped_probe_artifact.get("context_scoped_effect_report", {}))
    seed_level = dict(scoped_effect.get("seed_level_effects", {}))
    scoped_seed_reports = list(seed_level.get("context_scoped", []))
    hybrid_seed_reports = list(seed_level.get("hybrid_reference", []))
    positive_seed_count = int(seed_level.get("positive_seed_count", 0))

    context_slice_effects = dict(scoped_effect.get("context_slice_effects", {}))
    scoped_slice_reports = list(context_slice_effects.get("context_scoped", []))
    strongest_slice = dict(context_slice_effects.get("strongest_slice", {}))
    weakest_slice = dict(context_slice_effects.get("weakest_slice", {}))

    effect_decomposition = dict(scope_effect_snapshot.get("effect_decomposition_report", {}))
    seed_deltas_vs_hybrid = list(
        dict(effect_decomposition.get("row_seed_context_benefit_map", {}))
        .get("seed_level", {})
        .get("seed_deltas_vs_hybrid", [])
    )
    stability_locality = dict(effect_decomposition.get("stability_vs_locality_interpretation", {}))

    scoped_seed_gaps = [
        float(report.get("selection_score_pre_gate_gap_delta", 0.0))
        for report in scoped_seed_reports
        if _safe_float(report.get("selection_score_pre_gate_gap_delta"), None) is not None
    ]
    scoped_seed_signal_gaps = [
        float(report.get("signal_gap", 0.0))
        for report in scoped_seed_reports
        if _safe_float(report.get("signal_gap"), None) is not None
    ]
    positive_hybrid_relative_seed_count = sum(
        1
        for report in seed_deltas_vs_hybrid
        if (_safe_float(report.get("selection_score_pre_gate_gap_delta_vs_hybrid"), 0.0) or 0.0) > 0.0
    )

    seed2_scoped = _find_seed(scoped_seed_reports, 2)
    seed2_hybrid = _find_seed(hybrid_seed_reports, 2)
    seed2_delta_vs_hybrid = _find_seed(seed_deltas_vs_hybrid, 2)

    seed01_mean_gap = _mean(
        [
            float(report.get("selection_score_pre_gate_gap_delta", 0.0))
            for report in scoped_seed_reports
            if int(report.get("seed", -1)) in {0, 1}
        ]
    )
    seed2_gap = _safe_float(seed2_scoped.get("selection_score_pre_gate_gap_delta"), 0.0) or 0.0
    seed2_gap_ratio = (
        None
        if seed01_mean_gap is None or abs(seed01_mean_gap) <= 1e-12
        else float(seed2_gap / seed01_mean_gap)
    )
    seed2_vs_hybrid_gap_delta = _safe_float(
        seed2_delta_vs_hybrid.get("selection_score_pre_gate_gap_delta_vs_hybrid"),
        0.0,
    ) or 0.0

    weak_slice_delta = _safe_float(weakest_slice.get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0
    strong_slice_delta = _safe_float(strongest_slice.get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0
    weak_slice_share = _safe_float(weakest_slice.get("positive_delta_share"), 0.0) or 0.0
    strong_slice_share = _safe_float(strongest_slice.get("positive_delta_share"), 0.0) or 0.0

    if seed2_gap <= 0.0 or weak_slice_delta < 0.0:
        seed2_weakness = "disqualifying"
    elif seed2_vs_hybrid_gap_delta < 0.0 and (seed2_gap_ratio or 0.0) < 0.20:
        seed2_weakness = "correctable"
    else:
        seed2_weakness = "tolerable"

    safety_preserved = bool(dict(scoped_probe_artifact.get("safety_neutrality", {})).get("passed", False))
    stable_narrow_targeting = bool(
        safety_preserved
        and positive_seed_count == len(scoped_seed_reports)
        and strong_slice_delta > 0.0020
        and strong_slice_share > 0.85
        and weak_slice_delta >= 0.0
        and seed2_weakness in {"tolerable", "correctable"}
    )
    fragile_local_improvement = bool(
        not stable_narrow_targeting
        and (
            seed2_weakness == "disqualifying"
            or positive_seed_count < max(1, len(scoped_seed_reports) - 1)
            or weak_slice_delta < 0.0
        )
    )
    if stable_narrow_targeting:
        classification = "stable_narrow_targeting"
    elif fragile_local_improvement:
        classification = "fragile_local_improvement"
    else:
        classification = "diagnostic_only_promising_signal"

    stable_enough_to_build_on = bool(stable_narrow_targeting)

    if stable_narrow_targeting:
        next_family = "proposal_learning_loop"
        next_template = "proposal_learning_loop.v4_wm_hybrid_context_stabilization_probe_v1"
        next_rationale = "the scoped-hybrid gain is stable enough in its supported slices to justify a narrow stabilization probe focused on the weak seed and weak slice without broadening ownership"
    elif classification == "diagnostic_only_promising_signal":
        next_family = "memory_summary"
        next_template = "memory_summary.v4_wm_hybrid_seed2_weakness_snapshot_v1"
        next_rationale = "the signal remains promising but uneven, so the next safe move is a seed-2-specific diagnostic before another behavior-changing step"
    else:
        next_family = "memory_summary"
        next_template = "memory_summary.v4_wm_hybrid_branch_pause_snapshot_v1"
        next_rationale = "the current scoped-hybrid gain is too fragile to extend safely, so the branch should pause unless new evidence changes the weak-region picture"

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v1",
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
            "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1": _artifact_reference(
                scoped_probe_artifact,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_hybrid_probe_effect_snapshot_v1": _artifact_reference(
                hybrid_effect_snapshot,
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
        "stability_report": {
            "seed_stability": {
                "positive_seed_count_vs_baseline": int(positive_seed_count),
                "positive_seed_count_vs_hybrid": int(positive_hybrid_relative_seed_count),
                "seed_gap_mean": _mean(scoped_seed_gaps),
                "seed_gap_std": _std(scoped_seed_gaps),
                "seed_gap_cv": _coefficient_of_variation(scoped_seed_gaps),
                "signal_gap_mean": _mean(scoped_seed_signal_gaps),
                "signal_gap_std": _std(scoped_seed_signal_gaps),
                "per_seed_context_scoped": scoped_seed_reports,
                "per_seed_hybrid_reference": hybrid_seed_reports,
                "per_seed_delta_vs_hybrid": seed_deltas_vs_hybrid,
            },
            "slice_stability": {
                "strongest_slice": dict(strongest_slice),
                "weakest_slice": dict(weakest_slice),
                "all_context_scoped_slices": scoped_slice_reports,
                "strong_to_weak_delta_ratio": (
                    None
                    if abs(weak_slice_delta) <= 1e-12
                    else float(strong_slice_delta / max(abs(weak_slice_delta), 1e-12))
                ),
                "weak_slice_non_negative": bool(weak_slice_delta >= 0.0),
            },
            "weak_region_risk": {
                "seed_2": {
                    "context_scoped": dict(seed2_scoped),
                    "hybrid_reference": dict(seed2_hybrid),
                    "delta_vs_hybrid": dict(seed2_delta_vs_hybrid),
                    "gap_ratio_to_seed_0_1_mean": seed2_gap_ratio,
                    "weakness_classification": str(seed2_weakness),
                    "reason": (
                        "seed 2 remains weaker than seeds 0 and 1, but it still retains a positive scoped gap over baseline and a protected weak slice, so the weakness looks correctable rather than disqualifying"
                        if seed2_weakness == "correctable"
                        else "seed 2 remains weaker but still within the acceptable narrow-targeting envelope"
                        if seed2_weakness == "tolerable"
                        else "seed 2 weakness is strong enough to block another behavior-changing step"
                    ),
                },
                "low_context_high_risk_slice": {
                    "mean_selection_score_pre_gate_delta": float(weak_slice_delta),
                    "positive_delta_share": float(weak_slice_share),
                    "protection_status": (
                        "protected_non_negative" if weak_slice_delta >= 0.0 else "regressing"
                    ),
                },
            },
            "overall_classification": {
                "classification": str(classification),
                "stable_enough_to_build_on": bool(stable_enough_to_build_on),
                "reason": (
                    "the scoped-hybrid gain is stable enough to keep building on narrowly: all seeds remain positive against baseline, the strongest slice is robust, and the weak slice stays protected"
                    if classification == "stable_narrow_targeting"
                    else "the scoped-hybrid gain is still informative but too uneven for a direct next probe without more diagnosis"
                    if classification == "diagnostic_only_promising_signal"
                    else "the scoped-hybrid gain is too fragile in its weak regions to justify another behavior-changing step right now"
                ),
                "prior_scope_effect_classification": str(stability_locality.get("classification", "")),
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
            "stable_enough_to_build_on": bool(stable_enough_to_build_on),
            "plan_should_remain_non_owning": True,
            "recommended_next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "rationale": str(next_rationale),
        },
        "observability_gain": {
            "passed": True,
            "reason": "the snapshot reuses the existing scoped-hybrid trace outputs to classify stability without opening another behavior-changing branch",
            "seed_report_count": int(len(scoped_seed_reports)),
            "slice_report_count": int(len(scoped_slice_reports)),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the snapshot decides whether the scoped-hybrid gain is stable enough for a stabilization step or still too uneven",
            "stable_enough_to_build_on": bool(stable_enough_to_build_on),
            "plan_non_owning_preserved": True,
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": float(
                min(
                    1.0,
                    0.58
                    + 0.10 * int(positive_seed_count == len(scoped_seed_reports))
                    + 0.10 * int(weak_slice_delta >= 0.0)
                    + 0.08 * int(seed2_weakness == "correctable")
                    + 0.08 * int(classification == "stable_narrow_targeting")
                )
            ),
            "reason": "the snapshot resolves whether seed-2 weakness is tolerable, correctable, or disqualifying, and whether the current gain is stable narrow targeting or only a fragile local signal",
        },
        "safety_neutrality": {
            "passed": bool(safety_preserved),
            "scope": str(proposal.get("scope", "")),
            "reason": "diagnostic-only stability characterization with live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": str(next_template),
            "reason": str(next_rationale),
        },
        "diagnostic_conclusions": {
            "stable_enough_to_build_on": bool(stable_enough_to_build_on),
            "plan_should_remain_non_owning": True,
            "recommended_next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "routing_deferred": bool(dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)),
            "stability_classification": str(classification),
            "seed_2_weakness": str(seed2_weakness),
        },
    }

    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"memory_summary_v4_wm_hybrid_context_scope_stability_snapshot_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": bool(safety_preserved),
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": (
            "diagnostic shadow passed: scoped-hybrid stability characterization completed without changing behavior"
            if safety_preserved
            else "diagnostic shadow failed: stability characterization detected an unexpected safety regression"
        ),
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
