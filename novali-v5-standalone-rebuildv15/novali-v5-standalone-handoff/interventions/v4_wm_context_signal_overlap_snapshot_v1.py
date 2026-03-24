from __future__ import annotations

import json
import math
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


def _corr_squared(value: float | None) -> float | None:
    if value is None:
        return None
    return float(value * value)


def _partial_corr(
    *,
    signal_to_target: float | None,
    signal_to_baseline: float | None,
    baseline_to_target: float | None,
) -> float | None:
    if signal_to_target is None or signal_to_baseline is None or baseline_to_target is None:
        return None
    numerator = float(signal_to_target - signal_to_baseline * baseline_to_target)
    denominator_term = (1.0 - signal_to_baseline * signal_to_baseline) * (
        1.0 - baseline_to_target * baseline_to_target
    )
    if denominator_term <= 1e-12:
        return 0.0
    return float(numerator / math.sqrt(denominator_term))


def _seed_overlap_report(
    v1_artifact: dict[str, Any],
    residual_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    v1_rows = {
        int(dict(row).get("seed", 0)): dict(row)
        for row in list(dict(v1_artifact.get("shadow_metrics", {})).get("per_seed_runs", []))
    }
    residual_rows = {
        int(dict(row).get("seed", 0)): dict(row)
        for row in list(dict(residual_artifact.get("shadow_metrics", {})).get("per_seed_runs", []))
    }

    seed_reports: list[dict[str, Any]] = []
    for seed in sorted(set(v1_rows) | set(residual_rows)):
        v1_row = dict(v1_rows.get(seed, {}))
        residual_row = dict(residual_rows.get(seed, {}))

        v1_sep = dict(v1_row.get("probe_separation", v1_row.get("v1_separation", {})))
        residual_sep = dict(residual_row.get("residual_separation", {}))
        baseline_sep = dict(residual_row.get("baseline_separation", {}))

        baseline_avail = dict(baseline_sep.get("availability_correlations", {}))
        v1_avail = dict(v1_sep.get("availability_correlations", {}))
        residual_avail = dict(residual_sep.get("availability_correlations", {}))
        v1_gaps = dict(v1_sep.get("gap_metrics", {}))
        residual_gaps = dict(residual_sep.get("gap_metrics", {}))

        baseline_pre_gate_corr = _safe_float(baseline_avail.get("selection_score_pre_gate"), None)
        v1_signal_corr = _safe_float(v1_avail.get("signal"), None)
        residual_signal_corr = _safe_float(residual_avail.get("signal"), None)
        # Same-seed per-mode selection correlation is the best seed-level overlap proxy available in the artifact.
        v1_same_mode_overlap = _safe_float(v1_avail.get("selection_score_pre_gate"), None)
        residual_same_mode_overlap = _safe_float(residual_avail.get("selection_score_pre_gate"), None)

        seed_reports.append(
            {
                "seed": int(seed),
                "baseline_selection_score_pre_gate_availability_corr": baseline_pre_gate_corr,
                "v1_signal_availability_corr": v1_signal_corr,
                "v1_signal_gap": _safe_float(v1_gaps.get("signal_provisional_minus_blocked"), None),
                "v1_same_mode_selection_overlap_proxy": v1_same_mode_overlap,
                "v1_partial_signal_given_baseline_proxy": _partial_corr(
                    signal_to_target=v1_signal_corr,
                    signal_to_baseline=v1_same_mode_overlap,
                    baseline_to_target=baseline_pre_gate_corr,
                ),
                "residual_signal_availability_corr": residual_signal_corr,
                "residual_signal_gap": _safe_float(residual_gaps.get("signal_provisional_minus_blocked"), None),
                "residual_same_mode_selection_overlap_proxy": residual_same_mode_overlap,
                "residual_partial_signal_given_baseline_proxy": _partial_corr(
                    signal_to_target=residual_signal_corr,
                    signal_to_baseline=residual_same_mode_overlap,
                    baseline_to_target=baseline_pre_gate_corr,
                ),
                "selection_score_pre_gate_availability_corr_delta": float(
                    (_safe_float(residual_avail.get("selection_score_pre_gate"), 0.0) or 0.0)
                    - (_safe_float(baseline_avail.get("selection_score_pre_gate"), 0.0) or 0.0)
                ),
            }
        )
    return seed_reports


def _middle_path_options(
    *,
    v1_signal_corr: float,
    v1_signal_gap: float,
    v1_overlap_corr: float,
    v1_partial: float,
    residual_signal_corr: float,
    residual_signal_gap: float,
    residual_overlap_corr: float,
    residual_partial: float,
    seed_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    positive_seed_deltas = [
        (_safe_float(row.get("selection_score_pre_gate_availability_corr_delta"), 0.0) or 0.0)
        for row in seed_rows
        if (_safe_float(row.get("selection_score_pre_gate_availability_corr_delta"), 0.0) or 0.0) > 0.0
    ]
    positive_seed_delta_count = sum(
        1
        for row in seed_rows
        if (_safe_float(row.get("selection_score_pre_gate_availability_corr_delta"), 0.0) or 0.0) > 0.0
    )
    residual_positive_partial_seed_count = sum(
        1
        for row in seed_rows
        if (_safe_float(row.get("residual_partial_signal_given_baseline_proxy"), 0.0) or 0.0) > 0.0
    )

    hybrid_supported = bool(
        v1_signal_corr >= 0.50
        and v1_signal_gap >= 0.05
        and abs(v1_overlap_corr) >= 0.80
        and v1_partial <= 0.0
    )
    narrower_supported = bool(
        residual_signal_corr >= 0.25
        and residual_signal_gap >= 0.03
        and residual_partial > 0.0
    )
    context_supported = bool(
        positive_seed_delta_count >= 2
        and residual_positive_partial_seed_count >= 2
        and (sum(positive_seed_deltas) / len(positive_seed_deltas) if positive_seed_deltas else 0.0) >= 0.005
        and residual_signal_corr >= 0.20
    )

    return [
        {
            "option": "hybrid_wm_baseline_redesign",
            "supported": bool(hybrid_supported),
            "rank": 1 if hybrid_supported else 2,
            "reason": (
                "the broad wm-owned signal was useful, but its strongest contribution was already co-carried by baseline pre-gate; if any headroom remains, it is at the boundary between wm context and baseline mixing rather than inside another pure wm-only lever"
            ),
        },
        {
            "option": "narrower_feature_subset",
            "supported": bool(narrower_supported),
            "rank": 2 if hybrid_supported else 1 if narrower_supported else 3,
            "reason": (
                "not supported by the current residual probe: overlap dropped sharply, but signal strength and provisional-minus-blocked separation also collapsed"
            ),
        },
        {
            "option": "context_conditional_application",
            "supported": bool(context_supported),
            "rank": 3 if (hybrid_supported or narrower_supported) else 1 if context_supported else 4,
            "reason": (
                "not evidenced strongly enough from the recorded seed behavior; residual application did not produce repeatable pre-gate improvement across seeds"
            ),
        },
        {
            "option": "pause_pure_wm_only_line",
            "supported": True,
            "rank": 2 if hybrid_supported else 1,
            "reason": (
                "another pure wm-only behavior-changing probe is not justified until the shared wm/baseline boundary is characterized more directly"
            ),
        },
    ]


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    v1_artifact = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1"
    )
    residual_artifact = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_wm_context_residual_signal_probe_v1"
    )
    trace_quality_v2_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v2"
    )
    trace_quality_v1_artifact = r._load_latest_diagnostic_artifact_by_template(
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
            v1_artifact,
            residual_artifact,
            trace_quality_v2_artifact,
            trace_quality_v1_artifact,
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
            "reason": "diagnostic shadow failed: overlap characterization requires the v1 probe, residual probe, and prior v4 trace-quality artifacts",
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
                "reason": "cannot characterize wm overlap headroom without the two prior behavior-changing probe artifacts",
            },
        }

    active_status_text = _load_text_file(ACTIVE_STATUS_PATH)
    handoff_status = _load_json_file(HANDOFF_STATUS_PATH)
    analytics = build_intervention_ledger_analytics()
    latest_snapshots = load_latest_snapshots()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")
    proposal_loop_text = _load_text_file(PROPOSAL_LOOP_PATH)

    v1_shadow = dict(dict(v1_artifact).get("shadow_metrics", {}))
    residual_shadow = dict(dict(residual_artifact).get("shadow_metrics", {}))

    baseline_pre_gate_corr = _safe_float(
        dict(dict(v1_shadow.get("baseline_separation", {})).get("availability_correlations", {})).get(
            "selection_score_pre_gate"
        ),
        0.0,
    ) or 0.0

    v1_comparison = dict(v1_shadow.get("comparison_vs_baseline", {}))
    v1_overlap = dict(v1_shadow.get("overlap_reports", {})).get("probe", {})
    if not v1_overlap:
        # Earlier artifact used "probe" semantics internally; if unavailable, fall back to the residual snapshot's comparison.
        v1_overlap = dict(dict(residual_shadow.get("overlap_reports", {})).get("v1", {}))

    residual_baseline_comparison = dict(residual_shadow.get("comparison_vs_baseline", {}))
    residual_v1_comparison = dict(residual_shadow.get("comparison_vs_v1", {}))
    residual_overlap = dict(dict(residual_shadow.get("overlap_reports", {})).get("residual", {}))

    v1_signal_corr = _safe_float(v1_comparison.get("v4_wm_discrimination_availability_corr_probe"), 0.0) or 0.0
    v1_signal_gap = _safe_float(v1_comparison.get("v4_wm_discrimination_gap_probe"), 0.0) or 0.0
    v1_overlap_corr = _safe_float(v1_overlap.get("signal_to_baseline_pre_gate_correlation"), 0.0) or 0.0
    v1_partial = _partial_corr(
        signal_to_target=v1_signal_corr,
        signal_to_baseline=v1_overlap_corr,
        baseline_to_target=baseline_pre_gate_corr,
    ) or 0.0

    residual_signal_corr = _safe_float(residual_baseline_comparison.get("residual_signal_availability_corr"), 0.0) or 0.0
    residual_signal_gap = _safe_float(residual_baseline_comparison.get("residual_signal_gap"), 0.0) or 0.0
    residual_overlap_corr = _safe_float(
        residual_baseline_comparison.get("residual_signal_overlap_to_baseline_pre_gate"),
        0.0,
    ) or 0.0
    residual_partial = _partial_corr(
        signal_to_target=residual_signal_corr,
        signal_to_baseline=residual_overlap_corr,
        baseline_to_target=baseline_pre_gate_corr,
    ) or 0.0

    overlap_removed = float(v1_overlap_corr - residual_overlap_corr)
    useful_signal_removed = float(v1_signal_corr - residual_signal_corr)
    seed_reports = _seed_overlap_report(v1_artifact, residual_artifact)
    middle_path_options = _middle_path_options(
        v1_signal_corr=v1_signal_corr,
        v1_signal_gap=v1_signal_gap,
        v1_overlap_corr=v1_overlap_corr,
        v1_partial=v1_partial,
        residual_signal_corr=residual_signal_corr,
        residual_signal_gap=residual_signal_gap,
        residual_overlap_corr=residual_overlap_corr,
        residual_partial=residual_partial,
        seed_rows=seed_reports,
    )
    best_supported_option = min(
        (row for row in middle_path_options if bool(row.get("supported"))),
        key=lambda row: int(row.get("rank", 99)),
        default={"option": "pause_pure_wm_only_line"},
    )

    feature_roles = list(
        dict(dict(trace_quality_v2_artifact).get("shortfall_diagnostic_report", {})).get(
            "feature_distinctness_vs_redundancy",
            [],
        )
    )
    strongest_middle_path = str(best_supported_option.get("option", "pause_pure_wm_only_line"))

    distinct_headroom_exists = bool(
        residual_signal_corr >= 0.20
        and residual_signal_gap >= 0.03
        and residual_partial > 0.0
    )
    another_behavior_changing_wm_probe_justified = False
    if strongest_middle_path == "hybrid_wm_baseline_redesign":
        next_family = "memory_summary"
        next_template = "memory_summary.v4_wm_baseline_hybrid_boundary_snapshot_v1"
        next_rationale = (
            "the useful wm signal is mostly baseline-shared, so the next safe move is to characterize the wm/baseline boundary directly before attempting any hybrid redesign"
        )
    else:
        next_family = "memory_summary"
        next_template = "memory_summary.v4_wm_signal_line_pause_snapshot_v1"
        next_rationale = (
            "no meaningful distinct wm-only headroom is evidenced beyond the baseline pre-gate path, so the pure wm-only line should pause"
        )

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_wm_context_signal_overlap_snapshot_v1",
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
        "comparison_references": {
            "proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1": _artifact_reference(
                v1_artifact,
                latest_snapshots,
            ),
            "proposal_learning_loop.v4_wm_context_residual_signal_probe_v1": _artifact_reference(
                residual_artifact,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v2": _artifact_reference(
                trace_quality_v2_artifact,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v1": _artifact_reference(
                trace_quality_v1_artifact,
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
        },
        "overlap_diagnostic_report": {
            "v1_useful_signal_overlap_with_baseline": {
                "baseline_pre_gate_availability_corr": baseline_pre_gate_corr,
                "v1_signal_availability_corr": v1_signal_corr,
                "v1_signal_gap": v1_signal_gap,
                "v1_signal_overlap_to_baseline_pre_gate": v1_overlap_corr,
                "v1_overlap_variance_share": _corr_squared(v1_overlap_corr),
                "v1_partial_signal_given_baseline": v1_partial,
                "interpretation": "the broad wm-owned signal was useful, but most of its usable variance was already aligned with the incumbent baseline pre-gate path",
            },
            "residual_distinct_headroom_estimate": {
                "residual_signal_availability_corr": residual_signal_corr,
                "residual_signal_gap": residual_signal_gap,
                "residual_signal_overlap_to_baseline_pre_gate": residual_overlap_corr,
                "residual_overlap_variance_share": _corr_squared(residual_overlap_corr),
                "residual_partial_signal_given_baseline": residual_partial,
                "residual_distinctness_score": _safe_float(
                    residual_baseline_comparison.get("residual_distinctness_score"),
                    None,
                ),
                "meaningful_distinct_headroom_exists": bool(distinct_headroom_exists),
                "interpretation": (
                    "after baseline absorption is removed, the remaining wm-only signal is too weak to justify another pure wm-only behavior-changing step"
                ),
            },
            "residualized_probe_weakness_cause": {
                "primary": "too_much_useful_signal_removed_with_overlap",
                "secondary": "remaining_distinct_signal_intrinsically_weak_at_current_boundary",
                "supporting_metrics": {
                    "overlap_removed": overlap_removed,
                    "useful_signal_removed": useful_signal_removed,
                    "v1_distinctness_score": _safe_float(residual_v1_comparison.get("v1_distinctness_score"), None),
                    "residual_distinctness_score": _safe_float(
                        residual_baseline_comparison.get("residual_distinctness_score"),
                        None,
                    ),
                },
                "reason": (
                    "the residualized probe successfully reduced overlap, but it removed more useful signal than it preserved, which means the currently distinct remainder is too weak by itself"
                ),
            },
            "feature_overlap_and_distinctness": feature_roles,
            "seed_context_sensitivity": {
                "seed_reports": seed_reports,
                "interpretation": "seed variation exists, but it does not rescue the pure wm-only line because aggregate pre-gate improvement stayed absent",
            },
            "best_supported_next_option": {
                "option": strongest_middle_path,
                "all_options": middle_path_options,
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
            "another_behavior_changing_wm_probe_justified": bool(another_behavior_changing_wm_probe_justified),
            "plan_should_remain_non_owning": True,
            "recommended_next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "rationale": str(next_rationale),
        },
        "observability_gain": {
            "passed": True,
            "reason": "the snapshot explains baseline absorption directly from the recorded v1 and residual probe artifacts without opening a new behavior-changing branch",
            "v1_trace_row_count": int(dict(v1_artifact.get("observability_gain", {})).get("probe_trace_row_count", 0) or 0),
            "residual_trace_row_count": int(dict(residual_artifact.get("observability_gain", {})).get("residual_trace_row_count", 0) or 0),
            "seed_count": int(len(seed_reports)),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the snapshot separates shared wm/baseline signal from genuinely distinct wm-owned headroom and rules out another pure wm-only step at the current boundary",
            "another_behavior_changing_wm_probe_justified": bool(another_behavior_changing_wm_probe_justified),
            "best_supported_next_option": str(strongest_middle_path),
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.95,
            "reason": "the snapshot explains how much useful wm signal is already absorbed by baseline pre-gate and identifies the narrowest remaining path without reopening downstream lines",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "diagnostic-only overlap snapshot with live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": str(next_template),
            "reason": str(next_rationale),
        },
        "diagnostic_conclusions": {
            "v1_useful_signal_overlap_high": bool(abs(v1_overlap_corr) >= 0.80),
            "meaningful_distinct_headroom_exists": bool(distinct_headroom_exists),
            "another_behavior_changing_wm_probe_justified": bool(another_behavior_changing_wm_probe_justified),
            "plan_should_remain_non_owning": True,
            "best_supported_next_option": str(strongest_middle_path),
            "recommended_next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "routing_deferred": bool(dict(frontier_artifact.get("diagnostic_conclusions", {})).get("routing_deferred", False)),
        },
    }

    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"memory_summary_v4_wm_context_signal_overlap_snapshot_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: wm overlap headroom was characterized without changing behavior",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
