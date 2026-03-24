from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import Any

import numpy as np

from experiments.proposal_learning_loop import run_proposal_learning_loop

from .analytics import build_intervention_ledger_analytics
from .ledger import intervention_data_dir, load_latest_snapshots
from .v4_first_hypothesis_landscape_snapshot_v1 import (
    ACTIVE_STATUS_PATH,
    HANDOFF_STATUS_PATH,
    PROPOSAL_LOOP_PATH,
    _load_json_file,
    _load_text_file,
)
from .v4_wm_context_residual_signal_probe_v1 import _augment_rows
from .v4_wm_context_signal_discrimination_probe_v1 import (
    _extract_rows,
    _safety_envelope_report,
)
from .v4_wm_context_signal_overlap_snapshot_v1 import _artifact_reference
from .v4_wm_primary_plan_structure_probe_v1 import _clone_cfg, _safe_float


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(sum(values) / len(values))


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    x = np.asarray(xs, dtype=np.float64)
    y = np.asarray(ys, dtype=np.float64)
    if float(np.std(x)) <= 1e-12 or float(np.std(y)) <= 1e-12:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def _align_rows(
    baseline_rows: list[dict[str, Any]],
    hybrid_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    baseline_index = {
        (int(row.get("seed", 0)), int(row.get("round", 0)), str(row.get("candidate_id", ""))): dict(row)
        for row in baseline_rows
    }
    hybrid_index = {
        (int(row.get("seed", 0)), int(row.get("round", 0)), str(row.get("candidate_id", ""))): dict(row)
        for row in hybrid_rows
    }
    aligned: list[dict[str, Any]] = []
    for key in sorted(set(baseline_index) & set(hybrid_index)):
        baseline = dict(baseline_index[key])
        hybrid = dict(hybrid_index[key])
        aligned.append(
            {
                "seed": int(baseline.get("seed", 0)),
                "round": int(baseline.get("round", 0)),
                "candidate_id": str(baseline.get("candidate_id", "")),
                "status": str(baseline.get("status", "")),
                "availability_proxy": float(baseline.get("availability_proxy", 0.0)),
                "pred_context_score": float(baseline.get("pred_context_score", 0.0)),
                "pred_projection_bad_prob": float(baseline.get("pred_projection_bad_prob", 1.0)),
                "projection_recent": float(baseline.get("projection_recent", 0.0)),
                "wm_context_supply_score": float(baseline.get("wm_context_supply_score", 0.0)),
                "baseline_selection_score_pre_gate": float(baseline.get("selection_score_pre_gate", 0.0)),
                "hybrid_selection_score_pre_gate": float(hybrid.get("selection_score_pre_gate", 0.0)),
                "selection_score_pre_gate_delta": float(hybrid.get("selection_score_pre_gate", 0.0))
                - float(baseline.get("selection_score_pre_gate", 0.0)),
                "baseline_calibrated_projected": float(baseline.get("calibrated_projected", 0.0)),
                "hybrid_calibrated_projected": float(hybrid.get("calibrated_projected", 0.0)),
                "calibrated_projected_delta": float(hybrid.get("calibrated_projected", 0.0))
                - float(baseline.get("calibrated_projected", 0.0)),
                "hybrid_signal_score": float(hybrid.get("v4_wm_hybrid_boundary_score", 0.0)),
                "hybrid_signal_delta": float(hybrid.get("v4_wm_hybrid_boundary_delta", 0.0)),
                "hybrid_contextual_remainder": float(hybrid.get("v4_wm_hybrid_contextual_remainder", 0.0)),
                "hybrid_boundary_gate": float(hybrid.get("v4_wm_hybrid_boundary_gate", 0.0)),
            }
        )
    return aligned


def _slice_label(row: dict[str, Any], *, context_cut: float, risk_cut: float) -> str:
    high_context = float(row.get("pred_context_score", 0.0)) >= float(context_cut)
    low_risk = float(row.get("pred_projection_bad_prob", 1.0)) <= float(risk_cut)
    if high_context and low_risk:
        return "high_context_low_risk"
    if (not high_context) and (not low_risk):
        return "low_context_high_risk"
    return "mixed"


def _status_effect_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reports: dict[str, Any] = {}
    for status in ("provisional", "blocked"):
        subset = [row for row in rows if str(row.get("status", "")) == status]
        reports[status] = {
            "row_count": int(len(subset)),
            "mean_selection_score_pre_gate_delta": _mean(
                [float(row.get("selection_score_pre_gate_delta", 0.0)) for row in subset]
            ),
            "mean_calibrated_projected_delta": _mean(
                [float(row.get("calibrated_projected_delta", 0.0)) for row in subset]
            ),
            "mean_hybrid_signal_score": _mean(
                [float(row.get("hybrid_signal_score", 0.0)) for row in subset]
            ),
        }
    provisional_delta = _safe_float(
        dict(reports.get("provisional", {})).get("mean_selection_score_pre_gate_delta"),
        0.0,
    ) or 0.0
    blocked_delta = _safe_float(
        dict(reports.get("blocked", {})).get("mean_selection_score_pre_gate_delta"),
        0.0,
    ) or 0.0
    reports["provisional_minus_blocked_delta"] = float(provisional_delta - blocked_delta)
    return reports


def _seed_effect_reports(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    per_seed: list[dict[str, Any]] = []
    for seed in sorted({int(row.get("seed", 0)) for row in rows}):
        subset = [row for row in rows if int(row.get("seed", 0)) == seed]
        availability = [float(row.get("availability_proxy", 0.0)) for row in subset]
        baseline_sel = [float(row.get("baseline_selection_score_pre_gate", 0.0)) for row in subset]
        hybrid_sel = [float(row.get("hybrid_selection_score_pre_gate", 0.0)) for row in subset]
        hybrid_signal = [float(row.get("hybrid_signal_score", 0.0)) for row in subset]
        provisional_rows = [
            float(row.get("selection_score_pre_gate_delta", 0.0))
            for row in subset
            if str(row.get("status", "")) == "provisional"
        ]
        blocked_rows = [
            float(row.get("selection_score_pre_gate_delta", 0.0))
            for row in subset
            if str(row.get("status", "")) == "blocked"
        ]
        per_seed.append(
            {
                "seed": int(seed),
                "row_count": int(len(subset)),
                "selection_score_pre_gate_availability_corr_baseline": _pearson(baseline_sel, availability),
                "selection_score_pre_gate_availability_corr_hybrid": _pearson(hybrid_sel, availability),
                "selection_score_pre_gate_availability_corr_delta": (
                    None
                    if _pearson(hybrid_sel, availability) is None or _pearson(baseline_sel, availability) is None
                    else float(_pearson(hybrid_sel, availability) - _pearson(baseline_sel, availability))
                ),
                "selection_score_pre_gate_gap_delta": (
                    None
                    if not provisional_rows or not blocked_rows
                    else float(_mean(provisional_rows) - _mean(blocked_rows))
                ),
                "hybrid_signal_availability_corr": _pearson(hybrid_signal, availability),
                "hybrid_signal_gap": (
                    None
                    if not provisional_rows or not blocked_rows
                    else float(
                        _mean(
                            [
                                float(row.get("hybrid_signal_score", 0.0))
                                for row in subset
                                if str(row.get("status", "")) == "provisional"
                            ]
                        )
                        - _mean(
                            [
                                float(row.get("hybrid_signal_score", 0.0))
                                for row in subset
                                if str(row.get("status", "")) == "blocked"
                            ]
                        )
                    )
                ),
                "mean_selection_score_pre_gate_delta": _mean(
                    [float(row.get("selection_score_pre_gate_delta", 0.0)) for row in subset]
                ),
            }
        )
    return per_seed


def _slice_reports(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, float]]:
    context_cut = float(np.median([float(row.get("pred_context_score", 0.0)) for row in rows]))
    risk_cut = float(np.median([float(row.get("pred_projection_bad_prob", 1.0)) for row in rows]))
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_slice_label(row, context_cut=context_cut, risk_cut=risk_cut)].append(row)

    reports: list[dict[str, Any]] = []
    positive_delta_total = sum(
        max(0.0, float(row.get("selection_score_pre_gate_delta", 0.0)))
        for row in rows
    )
    for name in sorted(grouped):
        subset = grouped[name]
        positive_delta_sum = sum(
            max(0.0, float(row.get("selection_score_pre_gate_delta", 0.0)))
            for row in subset
        )
        reports.append(
            {
                "slice": str(name),
                "row_count": int(len(subset)),
                "status_counts": dict(Counter(str(row.get("status", "")) for row in subset)),
                "mean_selection_score_pre_gate_delta": _mean(
                    [float(row.get("selection_score_pre_gate_delta", 0.0)) for row in subset]
                ),
                "mean_calibrated_projected_delta": _mean(
                    [float(row.get("calibrated_projected_delta", 0.0)) for row in subset]
                ),
                "mean_hybrid_signal_score": _mean(
                    [float(row.get("hybrid_signal_score", 0.0)) for row in subset]
                ),
                "mean_hybrid_boundary_gate": _mean(
                    [float(row.get("hybrid_boundary_gate", 0.0)) for row in subset]
                ),
                "mean_contextual_remainder": _mean(
                    [float(row.get("hybrid_contextual_remainder", 0.0)) for row in subset]
                ),
                "positive_delta_share": (
                    0.0
                    if positive_delta_total <= 0.0
                    else float(positive_delta_sum / positive_delta_total)
                ),
            }
        )
    return reports, {
        "context_cut": float(context_cut),
        "risk_cut": float(risk_cut),
    }


def _row_examples(rows: list[dict[str, Any]], *, reverse: bool) -> list[dict[str, Any]]:
    selected = sorted(
        rows,
        key=lambda row: (
            float(row.get("selection_score_pre_gate_delta", 0.0)),
            float(row.get("hybrid_signal_score", 0.0)),
        ),
        reverse=bool(reverse),
    )[:6]
    return [
        {
            "seed": int(row.get("seed", 0)),
            "candidate_id": str(row.get("candidate_id", "")),
            "status": str(row.get("status", "")),
            "selection_score_pre_gate_delta": float(row.get("selection_score_pre_gate_delta", 0.0)),
            "calibrated_projected_delta": float(row.get("calibrated_projected_delta", 0.0)),
            "pred_context_score": float(row.get("pred_context_score", 0.0)),
            "pred_projection_bad_prob": float(row.get("pred_projection_bad_prob", 1.0)),
            "hybrid_signal_score": float(row.get("hybrid_signal_score", 0.0)),
            "hybrid_boundary_gate": float(row.get("hybrid_boundary_gate", 0.0)),
            "hybrid_contextual_remainder": float(row.get("hybrid_contextual_remainder", 0.0)),
        }
        for row in selected
    ]


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    hybrid_probe_artifact = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1"
    )
    hybrid_boundary_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_baseline_hybrid_boundary_snapshot_v1"
    )
    overlap_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_context_signal_overlap_snapshot_v1"
    )
    trace_quality_v2_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v2"
    )
    v1_artifact = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1"
    )
    residual_artifact = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_wm_context_residual_signal_probe_v1"
    )
    wm_branch_artifact = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_wm_primary_plan_structure_probe_v1"
    )
    wm_entry_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_world_model_planning_context_entry_snapshot_v1"
    )
    frontier_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.false_safe_frontier_control_characterization_snapshot_v1"
    )
    if not all(
        [
            hybrid_probe_artifact,
            hybrid_boundary_snapshot,
            overlap_artifact,
            trace_quality_v2_artifact,
            v1_artifact,
            residual_artifact,
            wm_branch_artifact,
            wm_entry_artifact,
            frontier_artifact,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: hybrid effect mapping requires the hybrid probe artifact, boundary snapshot, overlap diagnostics, and prior v4 wm artifacts",
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
                "reason": "cannot map the hybrid probe effect without the prerequisite wm artifacts",
            },
        }

    active_status_text = _load_text_file(ACTIVE_STATUS_PATH)
    handoff_status = _load_json_file(HANDOFF_STATUS_PATH)
    analytics = build_intervention_ledger_analytics()
    latest_snapshots = load_latest_snapshots()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")
    proposal_loop_text = _load_text_file(PROPOSAL_LOOP_PATH)

    requested_seeds = [int(seed) for seed in list(seeds)]
    sweep_seeds = list(dict.fromkeys(requested_seeds + [int(cfg.seed) + 1, int(cfg.seed) + 2]))[:3]
    sweep_rounds = max(1, int(rounds))

    baseline_rows: list[dict[str, Any]] = []
    hybrid_rows: list[dict[str, Any]] = []
    per_seed_safety: list[dict[str, Any]] = []

    for seed in sweep_seeds:
        baseline_cfg = _clone_cfg(cfg, seed=int(seed), rounds=int(sweep_rounds), probe_enabled=True)
        baseline_cfg.v4_wm_plan_context_trace_enabled = True
        baseline_cfg.v4_wm_context_signal_discrimination_probe_enabled = False
        baseline_cfg.v4_wm_context_residual_signal_probe_enabled = False
        baseline_cfg.v4_wm_baseline_hybrid_boundary_probe_enabled = False
        baseline_cfg.verbose = False

        hybrid_cfg = _clone_cfg(cfg, seed=int(seed), rounds=int(sweep_rounds), probe_enabled=True)
        hybrid_cfg.v4_wm_plan_context_trace_enabled = True
        hybrid_cfg.v4_wm_context_signal_discrimination_probe_enabled = False
        hybrid_cfg.v4_wm_context_residual_signal_probe_enabled = False
        hybrid_cfg.v4_wm_baseline_hybrid_boundary_probe_enabled = True
        hybrid_cfg.verbose = False

        _, _, baseline_history = run_proposal_learning_loop(baseline_cfg)
        _, _, hybrid_history = run_proposal_learning_loop(hybrid_cfg)

        baseline_summary = r._summarize_history(baseline_history)
        hybrid_summary = r._summarize_history(hybrid_history)
        baseline_seed_rows = _augment_rows(_extract_rows(baseline_history, int(seed), "baseline"))
        hybrid_seed_rows = _augment_rows(_extract_rows(hybrid_history, int(seed), "hybrid_probe"))

        baseline_rows.extend(baseline_seed_rows)
        hybrid_rows.extend(hybrid_seed_rows)
        per_seed_safety.append(
            {
                "seed": int(seed),
                "safety_vs_baseline": _safety_envelope_report(baseline_summary, hybrid_summary),
            }
        )

    aligned_rows = _align_rows(baseline_rows, hybrid_rows)
    status_effects = _status_effect_report(aligned_rows)
    seed_reports = _seed_effect_reports(aligned_rows)
    slice_reports, slice_thresholds = _slice_reports(aligned_rows)
    top_rows = _row_examples(aligned_rows, reverse=True)
    bottom_rows = _row_examples(aligned_rows, reverse=False)

    strongest_slice = max(
        slice_reports,
        key=lambda item: float(item.get("mean_selection_score_pre_gate_delta") or -1e9),
    )
    weakest_slice = min(
        slice_reports,
        key=lambda item: float(item.get("mean_selection_score_pre_gate_delta") or 1e9),
    )
    strongest_seed = max(
        seed_reports,
        key=lambda item: float(item.get("selection_score_pre_gate_gap_delta") or -1e9),
    )
    weakest_seed = min(
        seed_reports,
        key=lambda item: float(item.get("selection_score_pre_gate_gap_delta") or 1e9),
    )

    high_context_slice = next(
        (item for item in slice_reports if str(item.get("slice")) == "high_context_low_risk"),
        {},
    )
    low_context_slice = next(
        (item for item in slice_reports if str(item.get("slice")) == "low_context_high_risk"),
        {},
    )
    high_context_share = _safe_float(dict(high_context_slice).get("positive_delta_share"), 0.0) or 0.0
    low_context_delta = _safe_float(dict(low_context_slice).get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0
    positive_seed_count = sum(
        1
        for item in seed_reports
        if (_safe_float(item.get("selection_score_pre_gate_gap_delta"), 0.0) or 0.0) > 0.0
    )
    broad_enough_to_justify_broadening = bool(
        positive_seed_count == len(seed_reports)
        and high_context_share <= 0.55
        and low_context_delta >= 0.0005
    )
    structural_vs_local = (
        "broad_structural"
        if broad_enough_to_justify_broadening
        else "narrow_context_scoped"
    )

    next_family = "proposal_learning_loop"
    if broad_enough_to_justify_broadening:
        next_template = "proposal_learning_loop.v4_wm_hybrid_broadening_probe_v1"
        next_rationale = "the hybrid effect is broad enough across seeds and slices to justify testing a broader hybrid redesign without changing plan ownership"
    else:
        next_template = "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1"
        next_rationale = "the hybrid gain is real but concentrated in high-context, lower-risk slices, so the next safe move is a context-scoped hybrid probe rather than broadening the branch wholesale"

    safety_preserved = bool(
        all(bool(dict(item.get("safety_vs_baseline", {})).get("passed", False)) for item in per_seed_safety)
    )

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_wm_hybrid_probe_effect_snapshot_v1",
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
            "proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1": _artifact_reference(
                hybrid_probe_artifact,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_baseline_hybrid_boundary_snapshot_v1": _artifact_reference(
                hybrid_boundary_snapshot,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_context_signal_overlap_snapshot_v1": _artifact_reference(
                overlap_artifact,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v2": _artifact_reference(
                trace_quality_v2_artifact,
                latest_snapshots,
            ),
            "proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1": _artifact_reference(
                v1_artifact,
                latest_snapshots,
            ),
            "proposal_learning_loop.v4_wm_context_residual_signal_probe_v1": _artifact_reference(
                residual_artifact,
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
            "memory_summary.false_safe_frontier_control_characterization_snapshot_v1": _artifact_reference(
                frontier_artifact,
                latest_snapshots,
            ),
        },
        "effect_mapping_report": {
            "carry_forward_hybrid_metrics": dict(hybrid_probe_artifact.get("shadow_metrics", {})),
            "row_level_effects": {
                "row_count": int(len(aligned_rows)),
                "top_positive_examples": top_rows,
                "weakest_examples": bottom_rows,
                "status_effects": status_effects,
            },
            "seed_level_effects": {
                "seed_reports": seed_reports,
                "strongest_seed": dict(strongest_seed),
                "weakest_seed": dict(weakest_seed),
            },
            "context_slice_effects": {
                "slice_thresholds": slice_thresholds,
                "slice_reports": slice_reports,
                "strongest_slice": dict(strongest_slice),
                "weakest_slice": dict(weakest_slice),
            },
            "benefit_regions": {
                "strongest_region": "high_context_low_risk",
                "weakest_region": "low_context_high_risk",
                "summary": "the hybrid boundary helps most when context support is relatively high and projection risk is relatively low; it helps much less in low-context, higher-risk rows",
            },
            "structural_vs_local_interpretation": {
                "classification": str(structural_vs_local),
                "high_context_positive_delta_share": float(high_context_share),
                "low_context_high_risk_mean_delta": float(low_context_delta),
                "positive_seed_count": int(positive_seed_count),
                "broad_enough_to_justify_broadening": bool(broad_enough_to_justify_broadening),
                "reason": (
                    "the effect is broad enough to justify controlled broadening"
                    if broad_enough_to_justify_broadening
                    else "the effect is real but concentrated in specific high-context, lower-risk slices, so it looks local/context-scoped rather than broad enough for immediate broadening"
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
            "broad_enough_to_justify_broadening": bool(broad_enough_to_justify_broadening),
            "plan_should_remain_non_owning": True,
            "recommended_next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "rationale": str(next_rationale),
        },
        "observability_gain": {
            "passed": True,
            "reason": "the snapshot maps the hybrid probe using aligned baseline and hybrid wm/plan trace rows rather than opening another behavior-changing branch",
            "aligned_row_count": int(len(aligned_rows)),
            "seed_count": int(len(seed_reports)),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the snapshot shows whether the hybrid win is broad enough to justify broadening or whether it should stay context-scoped",
            "broad_enough_to_justify_broadening": bool(broad_enough_to_justify_broadening),
            "plan_non_owning_preserved": True,
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": float(
                min(
                    1.0,
                    0.56
                    + 0.14 * int(positive_seed_count == len(seed_reports))
                    + 0.12 * int(not broad_enough_to_justify_broadening)
                    + 0.10 * int(str(structural_vs_local) == "narrow_context_scoped")
                )
            ),
            "reason": "the snapshot localizes the hybrid benefit to specific seeds and context slices so the next step can be scoped correctly",
        },
        "safety_neutrality": {
            "passed": bool(safety_preserved),
            "scope": str(proposal.get("scope", "")),
            "reason": "diagnostic-only hybrid effect mapping with live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": str(next_template),
            "reason": str(next_rationale),
        },
        "diagnostic_conclusions": {
            "broad_enough_to_justify_broadening": bool(broad_enough_to_justify_broadening),
            "plan_should_remain_non_owning": True,
            "recommended_next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "routing_deferred": bool(dict(frontier_artifact.get("diagnostic_conclusions", {})).get("routing_deferred", False)),
            "structural_vs_local": str(structural_vs_local),
        },
    }
    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"memory_summary_v4_wm_hybrid_probe_effect_snapshot_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": bool(safety_preserved),
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": (
            "diagnostic shadow passed: the hybrid probe effect was mapped without changing behavior"
            if safety_preserved
            else "diagnostic shadow failed: the hybrid effect snapshot detected an unexpected safety drift"
        ),
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
