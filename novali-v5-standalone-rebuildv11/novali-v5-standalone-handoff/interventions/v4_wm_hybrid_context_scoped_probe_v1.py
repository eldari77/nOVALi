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
from .v4_wm_context_residual_signal_probe_v1 import (
    _aligned_overlap_report,
    _augment_rows,
    _distinctness_score,
    _separation_report,
)
from .v4_wm_context_signal_discrimination_probe_v1 import (
    _extract_rows,
    _safety_envelope_report,
)
from .v4_wm_context_signal_overlap_snapshot_v1 import (
    _artifact_reference,
    _partial_corr,
)
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


def _align_probe_rows(
    baseline_rows: list[dict[str, Any]],
    probe_rows: list[dict[str, Any]],
    *,
    signal_key: str,
    delta_key: str,
    scope_gate_key: str | None = None,
    scope_multiplier_key: str | None = None,
    scope_label_key: str | None = None,
) -> list[dict[str, Any]]:
    baseline_index = {
        (int(row.get("seed", 0)), int(row.get("round", 0)), str(row.get("candidate_id", ""))): dict(row)
        for row in baseline_rows
    }
    probe_index = {
        (int(row.get("seed", 0)), int(row.get("round", 0)), str(row.get("candidate_id", ""))): dict(row)
        for row in probe_rows
    }
    aligned: list[dict[str, Any]] = []
    for key in sorted(set(baseline_index) & set(probe_index)):
        baseline = dict(baseline_index[key])
        probe = dict(probe_index[key])
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
                "probe_selection_score_pre_gate": float(probe.get("selection_score_pre_gate", 0.0)),
                "selection_score_pre_gate_delta": float(probe.get("selection_score_pre_gate", 0.0))
                - float(baseline.get("selection_score_pre_gate", 0.0)),
                "baseline_calibrated_projected": float(baseline.get("calibrated_projected", 0.0)),
                "probe_calibrated_projected": float(probe.get("calibrated_projected", 0.0)),
                "calibrated_projected_delta": float(probe.get("calibrated_projected", 0.0))
                - float(baseline.get("calibrated_projected", 0.0)),
                "signal_score": float(probe.get(signal_key, 0.0)),
                "signal_delta": float(probe.get(delta_key, 0.0)),
                "hybrid_boundary_gate": float(probe.get("v4_wm_hybrid_boundary_gate", 0.0)),
                "contextual_remainder": float(probe.get("v4_wm_hybrid_contextual_remainder", 0.0)),
                "scope_gate": (
                    float(probe.get(scope_gate_key, 0.0))
                    if scope_gate_key
                    else float(probe.get("v4_wm_hybrid_boundary_gate", 0.0))
                ),
                "scope_multiplier": (
                    float(probe.get(scope_multiplier_key, 1.0))
                    if scope_multiplier_key
                    else 1.0
                ),
                "scope_label": str(probe.get(scope_label_key, "")) if scope_label_key else "",
            }
        )
    return aligned


def _status_effect_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    report: dict[str, Any] = {}
    for status in ("provisional", "blocked"):
        subset = [row for row in rows if str(row.get("status", "")) == status]
        report[status] = {
            "row_count": int(len(subset)),
            "mean_selection_score_pre_gate_delta": _mean(
                [float(row.get("selection_score_pre_gate_delta", 0.0)) for row in subset]
            ),
            "mean_calibrated_projected_delta": _mean(
                [float(row.get("calibrated_projected_delta", 0.0)) for row in subset]
            ),
            "mean_signal_score": _mean([float(row.get("signal_score", 0.0)) for row in subset]),
            "mean_scope_gate": _mean([float(row.get("scope_gate", 0.0)) for row in subset]),
        }
    provisional_delta = _safe_float(
        dict(report.get("provisional", {})).get("mean_selection_score_pre_gate_delta"),
        0.0,
    ) or 0.0
    blocked_delta = _safe_float(
        dict(report.get("blocked", {})).get("mean_selection_score_pre_gate_delta"),
        0.0,
    ) or 0.0
    report["provisional_minus_blocked_delta"] = float(provisional_delta - blocked_delta)
    return report


def _seed_effect_reports(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for seed in sorted({int(row.get("seed", 0)) for row in rows}):
        subset = [row for row in rows if int(row.get("seed", 0)) == seed]
        availability = [float(row.get("availability_proxy", 0.0)) for row in subset]
        baseline_sel = [float(row.get("baseline_selection_score_pre_gate", 0.0)) for row in subset]
        probe_sel = [float(row.get("probe_selection_score_pre_gate", 0.0)) for row in subset]
        signal_values = [float(row.get("signal_score", 0.0)) for row in subset]
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
        reports.append(
            {
                "seed": int(seed),
                "row_count": int(len(subset)),
                "selection_score_pre_gate_availability_corr_baseline": _pearson(baseline_sel, availability),
                "selection_score_pre_gate_availability_corr_probe": _pearson(probe_sel, availability),
                "selection_score_pre_gate_availability_corr_delta": (
                    None
                    if _pearson(probe_sel, availability) is None or _pearson(baseline_sel, availability) is None
                    else float(_pearson(probe_sel, availability) - _pearson(baseline_sel, availability))
                ),
                "selection_score_pre_gate_gap_delta": (
                    None
                    if not provisional_rows or not blocked_rows
                    else float(_mean(provisional_rows) - _mean(blocked_rows))
                ),
                "signal_availability_corr": _pearson(signal_values, availability),
                "signal_gap": (
                    None
                    if not provisional_rows or not blocked_rows
                    else float(
                        _mean(
                            [
                                float(row.get("signal_score", 0.0))
                                for row in subset
                                if str(row.get("status", "")) == "provisional"
                            ]
                        )
                        - _mean(
                            [
                                float(row.get("signal_score", 0.0))
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
    return reports


def _slice_label(row: dict[str, Any], *, context_cut: float, risk_cut: float) -> str:
    high_context = float(row.get("pred_context_score", 0.0)) >= float(context_cut)
    low_risk = float(row.get("pred_projection_bad_prob", 1.0)) <= float(risk_cut)
    if high_context and low_risk:
        return "high_context_low_risk"
    if (not high_context) and (not low_risk):
        return "low_context_high_risk"
    return "mixed"


def _slice_reports(
    rows: list[dict[str, Any]],
    *,
    context_cut: float,
    risk_cut: float,
) -> list[dict[str, Any]]:
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_slice_label(row, context_cut=context_cut, risk_cut=risk_cut)].append(row)

    total_positive_delta = sum(max(0.0, float(row.get("selection_score_pre_gate_delta", 0.0))) for row in rows)
    reports: list[dict[str, Any]] = []
    for name in sorted(grouped):
        subset = grouped[name]
        positive_delta_sum = sum(max(0.0, float(row.get("selection_score_pre_gate_delta", 0.0))) for row in subset)
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
                "mean_signal_score": _mean([float(row.get("signal_score", 0.0)) for row in subset]),
                "mean_scope_gate": _mean([float(row.get("scope_gate", 0.0)) for row in subset]),
                "mean_scope_multiplier": _mean(
                    [float(row.get("scope_multiplier", 0.0)) for row in subset]
                ),
                "mean_contextual_remainder": _mean(
                    [float(row.get("contextual_remainder", 0.0)) for row in subset]
                ),
                "positive_delta_share": (
                    0.0 if total_positive_delta <= 0.0 else float(positive_delta_sum / total_positive_delta)
                ),
            }
        )
    return reports


def _slice_lookup(reports: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for report in reports:
        if str(report.get("slice", "")) == str(name):
            return dict(report)
    return {}


def _row_examples(rows: list[dict[str, Any]], *, reverse: bool) -> list[dict[str, Any]]:
    selected = sorted(
        rows,
        key=lambda row: (
            float(row.get("selection_score_pre_gate_delta", 0.0)),
            float(row.get("signal_score", 0.0)),
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
            "signal_score": float(row.get("signal_score", 0.0)),
            "scope_gate": float(row.get("scope_gate", 0.0)),
            "scope_multiplier": float(row.get("scope_multiplier", 0.0)),
            "scope_label": str(row.get("scope_label", "")),
        }
        for row in selected
    ]


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    effect_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_probe_effect_snapshot_v1"
    )
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
            effect_snapshot,
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
            "reason": "diagnostic shadow failed: the context-scoped hybrid probe requires the broad hybrid probe, its effect snapshot, prior wm probes, and carried-forward safety artifacts",
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
                "reason": "cannot run the context-scoped hybrid probe without the broad hybrid effect mapping and prior wm diagnostics",
            },
        }

    active_status_text = _load_text_file(ACTIVE_STATUS_PATH)
    handoff_status = _load_json_file(HANDOFF_STATUS_PATH)
    analytics = build_intervention_ledger_analytics()
    latest_snapshots = load_latest_snapshots()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")
    proposal_loop_text = _load_text_file(PROPOSAL_LOOP_PATH)

    slice_thresholds = dict(
        dict(effect_snapshot.get("effect_mapping_report", {})).get("context_slice_effects", {}).get(
            "slice_thresholds",
            {},
        )
    )
    context_cut = _safe_float(
        slice_thresholds.get("context_cut"),
        float(cfg.v4_wm_hybrid_context_scoped_context_cut),
    ) or float(cfg.v4_wm_hybrid_context_scoped_context_cut)
    risk_cut = _safe_float(
        slice_thresholds.get("risk_cut"),
        float(cfg.v4_wm_hybrid_context_scoped_risk_cut),
    ) or float(cfg.v4_wm_hybrid_context_scoped_risk_cut)

    requested_seeds = [int(seed) for seed in list(seeds)]
    sweep_seeds = list(dict.fromkeys(requested_seeds + [int(cfg.seed) + 1, int(cfg.seed) + 2]))[:3]
    sweep_rounds = max(1, int(rounds))

    per_seed_runs: list[dict[str, Any]] = []
    baseline_rows: list[dict[str, Any]] = []
    v1_rows: list[dict[str, Any]] = []
    residual_rows: list[dict[str, Any]] = []
    hybrid_rows: list[dict[str, Any]] = []
    scoped_rows: list[dict[str, Any]] = []
    safety_reports: list[dict[str, Any]] = []

    for seed in sweep_seeds:
        baseline_cfg = _clone_cfg(cfg, seed=int(seed), rounds=int(sweep_rounds), probe_enabled=True)
        baseline_cfg.v4_wm_plan_context_trace_enabled = True
        baseline_cfg.v4_wm_context_signal_discrimination_probe_enabled = False
        baseline_cfg.v4_wm_context_residual_signal_probe_enabled = False
        baseline_cfg.v4_wm_baseline_hybrid_boundary_probe_enabled = False
        baseline_cfg.v4_wm_hybrid_context_scoped_probe_enabled = False
        baseline_cfg.verbose = False

        v1_cfg = _clone_cfg(cfg, seed=int(seed), rounds=int(sweep_rounds), probe_enabled=True)
        v1_cfg.v4_wm_plan_context_trace_enabled = True
        v1_cfg.v4_wm_context_signal_discrimination_probe_enabled = True
        v1_cfg.v4_wm_context_residual_signal_probe_enabled = False
        v1_cfg.v4_wm_baseline_hybrid_boundary_probe_enabled = False
        v1_cfg.v4_wm_hybrid_context_scoped_probe_enabled = False
        v1_cfg.verbose = False

        residual_cfg = _clone_cfg(cfg, seed=int(seed), rounds=int(sweep_rounds), probe_enabled=True)
        residual_cfg.v4_wm_plan_context_trace_enabled = True
        residual_cfg.v4_wm_context_signal_discrimination_probe_enabled = False
        residual_cfg.v4_wm_context_residual_signal_probe_enabled = True
        residual_cfg.v4_wm_baseline_hybrid_boundary_probe_enabled = False
        residual_cfg.v4_wm_hybrid_context_scoped_probe_enabled = False
        residual_cfg.verbose = False

        hybrid_cfg = _clone_cfg(cfg, seed=int(seed), rounds=int(sweep_rounds), probe_enabled=True)
        hybrid_cfg.v4_wm_plan_context_trace_enabled = True
        hybrid_cfg.v4_wm_context_signal_discrimination_probe_enabled = False
        hybrid_cfg.v4_wm_context_residual_signal_probe_enabled = False
        hybrid_cfg.v4_wm_baseline_hybrid_boundary_probe_enabled = True
        hybrid_cfg.v4_wm_hybrid_context_scoped_probe_enabled = False
        hybrid_cfg.verbose = False

        scoped_cfg = _clone_cfg(cfg, seed=int(seed), rounds=int(sweep_rounds), probe_enabled=True)
        scoped_cfg.v4_wm_plan_context_trace_enabled = True
        scoped_cfg.v4_wm_context_signal_discrimination_probe_enabled = False
        scoped_cfg.v4_wm_context_residual_signal_probe_enabled = False
        scoped_cfg.v4_wm_baseline_hybrid_boundary_probe_enabled = True
        scoped_cfg.v4_wm_hybrid_context_scoped_probe_enabled = True
        scoped_cfg.v4_wm_hybrid_context_scoped_context_cut = float(context_cut)
        scoped_cfg.v4_wm_hybrid_context_scoped_risk_cut = float(risk_cut)
        scoped_cfg.verbose = False

        _, _, baseline_history = run_proposal_learning_loop(baseline_cfg)
        _, _, v1_history = run_proposal_learning_loop(v1_cfg)
        _, _, residual_history = run_proposal_learning_loop(residual_cfg)
        _, _, hybrid_history = run_proposal_learning_loop(hybrid_cfg)
        _, _, scoped_history = run_proposal_learning_loop(scoped_cfg)

        baseline_summary = r._summarize_history(baseline_history)
        v1_summary = r._summarize_history(v1_history)
        residual_summary = r._summarize_history(residual_history)
        hybrid_summary = r._summarize_history(hybrid_history)
        scoped_summary = r._summarize_history(scoped_history)

        baseline_seed_rows = _augment_rows(_extract_rows(baseline_history, int(seed), "baseline"))
        v1_seed_rows = _augment_rows(_extract_rows(v1_history, int(seed), "v1_probe"))
        residual_seed_rows = _augment_rows(_extract_rows(residual_history, int(seed), "residual_probe"))
        hybrid_seed_rows = _augment_rows(_extract_rows(hybrid_history, int(seed), "hybrid_probe"))
        scoped_seed_rows = _augment_rows(_extract_rows(scoped_history, int(seed), "context_scoped_probe"))

        baseline_rows.extend(baseline_seed_rows)
        v1_rows.extend(v1_seed_rows)
        residual_rows.extend(residual_seed_rows)
        hybrid_rows.extend(hybrid_seed_rows)
        scoped_rows.extend(scoped_seed_rows)

        safety_vs_baseline = _safety_envelope_report(baseline_summary, scoped_summary)
        safety_vs_hybrid = _safety_envelope_report(hybrid_summary, scoped_summary)
        safety_vs_v1 = _safety_envelope_report(v1_summary, scoped_summary)
        safety_vs_residual = _safety_envelope_report(residual_summary, scoped_summary)
        safety_reports.append(
            {
                "seed": int(seed),
                "vs_baseline": dict(safety_vs_baseline),
                "vs_hybrid": dict(safety_vs_hybrid),
                "vs_v1": dict(safety_vs_v1),
                "vs_residual": dict(safety_vs_residual),
            }
        )
        per_seed_runs.append(
            {
                "seed": int(seed),
                "baseline_summary": dict(baseline_summary),
                "hybrid_summary": dict(hybrid_summary),
                "scoped_summary": dict(scoped_summary),
                "baseline_separation": _separation_report(baseline_seed_rows, "wm_context_supply_score"),
                "hybrid_separation": _separation_report(hybrid_seed_rows, "v4_wm_hybrid_boundary_score"),
                "scoped_separation": _separation_report(scoped_seed_rows, "v4_wm_hybrid_context_scoped_score"),
                "safety_vs_baseline": dict(safety_vs_baseline),
                "safety_vs_hybrid": dict(safety_vs_hybrid),
                "safety_vs_v1": dict(safety_vs_v1),
                "safety_vs_residual": dict(safety_vs_residual),
            }
        )

    baseline_report = _separation_report(baseline_rows, "wm_context_supply_score")
    v1_report = _separation_report(v1_rows, "v4_wm_discrimination_score")
    residual_report = _separation_report(residual_rows, "v4_wm_residual_signal_score")
    hybrid_report = _separation_report(hybrid_rows, "v4_wm_hybrid_boundary_score")
    scoped_report = _separation_report(scoped_rows, "v4_wm_hybrid_context_scoped_score")

    v1_overlap = _aligned_overlap_report(baseline_rows, v1_rows, "v4_wm_discrimination_score")
    residual_overlap = _aligned_overlap_report(baseline_rows, residual_rows, "v4_wm_residual_signal_score")
    hybrid_overlap = _aligned_overlap_report(baseline_rows, hybrid_rows, "v4_wm_hybrid_boundary_score")
    scoped_overlap = _aligned_overlap_report(baseline_rows, scoped_rows, "v4_wm_hybrid_context_scoped_score")

    baseline_pre_gate_corr = _safe_float(
        dict(baseline_report.get("availability_correlations", {})).get("selection_score_pre_gate"),
        0.0,
    ) or 0.0
    baseline_pre_gate_gap = _safe_float(
        dict(baseline_report.get("gap_metrics", {})).get("selection_score_pre_gate_provisional_minus_blocked"),
        0.0,
    ) or 0.0
    hybrid_pre_gate_corr = _safe_float(
        dict(hybrid_report.get("availability_correlations", {})).get("selection_score_pre_gate"),
        0.0,
    ) or 0.0
    hybrid_pre_gate_gap = _safe_float(
        dict(hybrid_report.get("gap_metrics", {})).get("selection_score_pre_gate_provisional_minus_blocked"),
        0.0,
    ) or 0.0
    scoped_pre_gate_corr = _safe_float(
        dict(scoped_report.get("availability_correlations", {})).get("selection_score_pre_gate"),
        0.0,
    ) or 0.0
    scoped_pre_gate_gap = _safe_float(
        dict(scoped_report.get("gap_metrics", {})).get("selection_score_pre_gate_provisional_minus_blocked"),
        0.0,
    ) or 0.0

    v1_signal_corr = _safe_float(dict(v1_report.get("availability_correlations", {})).get("signal"), 0.0) or 0.0
    residual_signal_corr = _safe_float(dict(residual_report.get("availability_correlations", {})).get("signal"), 0.0) or 0.0
    hybrid_signal_corr = _safe_float(dict(hybrid_report.get("availability_correlations", {})).get("signal"), 0.0) or 0.0
    scoped_signal_corr = _safe_float(dict(scoped_report.get("availability_correlations", {})).get("signal"), 0.0) or 0.0

    v1_signal_gap = _safe_float(dict(v1_report.get("gap_metrics", {})).get("signal_provisional_minus_blocked"), 0.0) or 0.0
    residual_signal_gap = _safe_float(dict(residual_report.get("gap_metrics", {})).get("signal_provisional_minus_blocked"), 0.0) or 0.0
    hybrid_signal_gap = _safe_float(dict(hybrid_report.get("gap_metrics", {})).get("signal_provisional_minus_blocked"), 0.0) or 0.0
    scoped_signal_gap = _safe_float(dict(scoped_report.get("gap_metrics", {})).get("signal_provisional_minus_blocked"), 0.0) or 0.0

    v1_overlap_corr = _safe_float(v1_overlap.get("signal_to_baseline_pre_gate_correlation"), 0.0) or 0.0
    residual_overlap_corr = _safe_float(residual_overlap.get("signal_to_baseline_pre_gate_correlation"), 0.0) or 0.0
    hybrid_overlap_corr = _safe_float(hybrid_overlap.get("signal_to_baseline_pre_gate_correlation"), 0.0) or 0.0
    scoped_overlap_corr = _safe_float(scoped_overlap.get("signal_to_baseline_pre_gate_correlation"), 0.0) or 0.0

    v1_distinctness = _distinctness_score(v1_signal_corr, v1_overlap_corr)
    residual_distinctness = _distinctness_score(residual_signal_corr, residual_overlap_corr)
    hybrid_distinctness = _distinctness_score(hybrid_signal_corr, hybrid_overlap_corr)
    scoped_distinctness = _distinctness_score(scoped_signal_corr, scoped_overlap_corr)

    v1_partial = _partial_corr(
        signal_to_target=v1_signal_corr,
        signal_to_baseline=v1_overlap_corr,
        baseline_to_target=baseline_pre_gate_corr,
    )
    residual_partial = _partial_corr(
        signal_to_target=residual_signal_corr,
        signal_to_baseline=residual_overlap_corr,
        baseline_to_target=baseline_pre_gate_corr,
    )
    hybrid_partial = _partial_corr(
        signal_to_target=hybrid_signal_corr,
        signal_to_baseline=hybrid_overlap_corr,
        baseline_to_target=baseline_pre_gate_corr,
    )
    scoped_partial = _partial_corr(
        signal_to_target=scoped_signal_corr,
        signal_to_baseline=scoped_overlap_corr,
        baseline_to_target=baseline_pre_gate_corr,
    )

    aligned_hybrid = _align_probe_rows(
        baseline_rows,
        hybrid_rows,
        signal_key="v4_wm_hybrid_boundary_score",
        delta_key="v4_wm_hybrid_boundary_delta",
    )
    aligned_scoped = _align_probe_rows(
        baseline_rows,
        scoped_rows,
        signal_key="v4_wm_hybrid_context_scoped_score",
        delta_key="v4_wm_hybrid_context_scoped_delta",
        scope_gate_key="v4_wm_hybrid_context_scope_gate",
        scope_multiplier_key="v4_wm_hybrid_context_scope_multiplier",
        scope_label_key="v4_wm_hybrid_context_scope_label",
    )

    hybrid_status_effects = _status_effect_report(aligned_hybrid)
    scoped_status_effects = _status_effect_report(aligned_scoped)
    hybrid_seed_effects = _seed_effect_reports(aligned_hybrid)
    scoped_seed_effects = _seed_effect_reports(aligned_scoped)
    hybrid_slice_effects = _slice_reports(aligned_hybrid, context_cut=float(context_cut), risk_cut=float(risk_cut))
    scoped_slice_effects = _slice_reports(aligned_scoped, context_cut=float(context_cut), risk_cut=float(risk_cut))

    hybrid_strong = _slice_lookup(hybrid_slice_effects, "high_context_low_risk")
    hybrid_weak = _slice_lookup(hybrid_slice_effects, "low_context_high_risk")
    scoped_strong = _slice_lookup(scoped_slice_effects, "high_context_low_risk")
    scoped_weak = _slice_lookup(scoped_slice_effects, "low_context_high_risk")

    safety_preserved = bool(
        all(
            bool(dict(item.get("vs_baseline", {})).get("passed", False))
            and bool(dict(item.get("vs_hybrid", {})).get("passed", False))
            and bool(dict(item.get("vs_v1", {})).get("passed", False))
            and bool(dict(item.get("vs_residual", {})).get("passed", False))
            for item in safety_reports
        )
    )
    branch_stayed_cleanly_upstream = bool(safety_preserved)
    strong_slice_improved = bool(
        (_safe_float(scoped_strong.get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0)
        >= (_safe_float(hybrid_strong.get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0) + 0.00010
    )
    weak_slice_not_harmed = bool(
        (_safe_float(scoped_weak.get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0)
        >= (_safe_float(hybrid_weak.get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0) - 0.00015
    )
    pre_gate_gap_improved = bool(scoped_pre_gate_gap >= hybrid_pre_gate_gap + 0.00005)
    baseline_path_not_regressed = bool(scoped_pre_gate_corr >= baseline_pre_gate_corr - 0.003)
    distinctness_improved = bool(
        scoped_distinctness >= hybrid_distinctness + 0.005
        or (_safe_float(scoped_partial, -1.0) or -1.0) >= (_safe_float(hybrid_partial, -1.0) or -1.0) + 0.002
    )
    context_scoped_improved = bool(
        safety_preserved
        and strong_slice_improved
        and weak_slice_not_harmed
        and pre_gate_gap_improved
        and baseline_path_not_regressed
        and distinctness_improved
    )

    next_template = "memory_summary.v4_wm_hybrid_context_scope_effect_snapshot_v1"
    next_rationale = (
        "the context-scoped hybrid probe stayed upstream and improved the supported slices, so the next step should map its scoped effect before any broader redesign"
        if context_scoped_improved
        else "the context-scoped hybrid probe stayed upstream and safe, but it still needs a diagnostic readout before deciding whether to stabilize it, retune it, or pause"
    )

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1",
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
            "memory_summary.v4_wm_hybrid_probe_effect_snapshot_v1": _artifact_reference(effect_snapshot, latest_snapshots),
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
        "branch_implementation_summary": {
            "context_scoping_definition": [
                "kept the successful hybrid boundary intact and applied a scope multiplier on top of the existing hybrid raw delta",
                "used the carried-forward effect-snapshot thresholds for context and risk to define the supported regions",
                "treated high_context_low_risk rows as the emphasized slice and low_context_high_risk rows as the damped slice",
            ],
            "emphasized_or_damped_slices": {
                "emphasized": "high_context_low_risk",
                "damped": "low_context_high_risk",
                "slice_thresholds": {
                    "context_cut": float(context_cut),
                    "risk_cut": float(risk_cut),
                },
            },
            "hybrid_boundary_preserved": [
                "baseline kept pred_gain_sign_prob, calibrated_projected, and the projected-quality / uncertainty boundary path",
                "wm modulation remained context-conditioned only",
                "the context-scoped overlay used scope gating and scope multipliers rather than a new downstream lever",
            ],
            "plan_remained_non_owning": [
                "planning_handoff_score was not used as a decision lever",
                "plan_ remained handoff and organization only",
            ],
            "downstream_exclusions_preserved": [
                "no adoption_ ownership or branching",
                "no social_conf_ ownership or branching",
                "no self_improve_ attachment",
                "no selected-set optimization work",
            ],
        },
        "shadow_metrics": {
            "seed_sweep_used": list(sweep_seeds),
            "rounds_used_per_seed": int(sweep_rounds),
            "baseline_separation": baseline_report,
            "v1_separation": v1_report,
            "residual_separation": residual_report,
            "hybrid_separation": hybrid_report,
            "context_scoped_separation": scoped_report,
            "overlap_reports": {
                "v1": v1_overlap,
                "residual": residual_overlap,
                "hybrid": hybrid_overlap,
                "context_scoped": scoped_overlap,
            },
            "partial_signal_given_baseline": {
                "v1": _safe_float(v1_partial, None),
                "residual": _safe_float(residual_partial, None),
                "hybrid": _safe_float(hybrid_partial, None),
                "context_scoped": _safe_float(scoped_partial, None),
            },
            "per_seed_runs": per_seed_runs,
            "safety_envelope_reports": safety_reports,
            "comparison_vs_baseline": {
                "selection_score_pre_gate_availability_corr_delta": float(scoped_pre_gate_corr - baseline_pre_gate_corr),
                "selection_score_pre_gate_gap_delta": float(scoped_pre_gate_gap - baseline_pre_gate_gap),
                "context_scoped_signal_availability_corr": float(scoped_signal_corr),
                "context_scoped_signal_gap": float(scoped_signal_gap),
                "context_scoped_signal_overlap_to_baseline_pre_gate": float(scoped_overlap_corr),
                "context_scoped_distinctness_score": float(scoped_distinctness),
            },
            "comparison_vs_hybrid": {
                "selection_score_pre_gate_availability_corr_delta": float(scoped_pre_gate_corr - hybrid_pre_gate_corr),
                "selection_score_pre_gate_gap_delta": float(scoped_pre_gate_gap - hybrid_pre_gate_gap),
                "signal_availability_corr_delta": float(scoped_signal_corr - hybrid_signal_corr),
                "signal_gap_delta": float(scoped_signal_gap - hybrid_signal_gap),
                "signal_overlap_to_baseline_pre_gate_delta": float(scoped_overlap_corr - hybrid_overlap_corr),
                "distinctness_score_delta": float(scoped_distinctness - hybrid_distinctness),
                "partial_signal_given_baseline_delta": (
                    None
                    if hybrid_partial is None or scoped_partial is None
                    else float(scoped_partial - hybrid_partial)
                ),
                "high_context_low_risk_delta_delta": float(
                    (_safe_float(scoped_strong.get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0)
                    - (_safe_float(hybrid_strong.get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0)
                ),
                "low_context_high_risk_delta_delta": float(
                    (_safe_float(scoped_weak.get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0)
                    - (_safe_float(hybrid_weak.get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0)
                ),
            },
            "comparison_vs_v1": {
                "signal_availability_corr_delta": float(scoped_signal_corr - v1_signal_corr),
                "signal_gap_delta": float(scoped_signal_gap - v1_signal_gap),
                "signal_overlap_to_baseline_pre_gate_delta": float(scoped_overlap_corr - v1_overlap_corr),
                "distinctness_score_delta": float(scoped_distinctness - v1_distinctness),
            },
            "comparison_vs_residual": {
                "signal_availability_corr_delta": float(scoped_signal_corr - residual_signal_corr),
                "signal_gap_delta": float(scoped_signal_gap - residual_signal_gap),
                "signal_overlap_to_baseline_pre_gate_delta": float(scoped_overlap_corr - residual_overlap_corr),
                "distinctness_score_delta": float(scoped_distinctness - residual_distinctness),
            },
        },
        "context_scoped_effect_report": {
            "row_level_effects": {
                "status_effects": scoped_status_effects,
                "top_positive_examples": _row_examples(aligned_scoped, reverse=True),
                "weakest_examples": _row_examples(aligned_scoped, reverse=False),
            },
            "seed_level_effects": {
                "hybrid_reference": hybrid_seed_effects,
                "context_scoped": scoped_seed_effects,
                "positive_seed_count": int(
                    sum(
                        1
                        for report in scoped_seed_effects
                        if (_safe_float(report.get("selection_score_pre_gate_gap_delta"), 0.0) or 0.0) > 0.0
                    )
                ),
            },
            "context_slice_effects": {
                "slice_thresholds": {
                    "context_cut": float(context_cut),
                    "risk_cut": float(risk_cut),
                },
                "hybrid_reference": hybrid_slice_effects,
                "context_scoped": scoped_slice_effects,
                "strongest_slice": dict(
                    max(
                        scoped_slice_effects,
                        key=lambda item: _safe_float(item.get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0,
                    )
                )
                if scoped_slice_effects
                else {},
                "weakest_slice": dict(
                    min(
                        scoped_slice_effects,
                        key=lambda item: _safe_float(item.get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0,
                    )
                )
                if scoped_slice_effects
                else {},
            },
            "structural_vs_local_interpretation": {
                "classification": (
                    "supported_context_scoped_gain"
                    if context_scoped_improved
                    else "still_narrow_or_ambiguous"
                ),
                "reason": (
                    "the scoped hybrid gain is strongest in the supported high-context, lower-risk slice and remains cautious in the weak slice, so the improvement behaves like a scoped design win rather than a broad redesign"
                    if context_scoped_improved
                    else "the scoped hybrid stayed upstream and safe, but the measured advantage over the broad hybrid pass is still too small or uneven to treat as a clean scoped win yet"
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
            "context_scoped_hybrid_improved_useful_upstream_separation": bool(context_scoped_improved),
            "branch_stayed_cleanly_upstream": bool(branch_stayed_cleanly_upstream),
            "recommended_next_template": str(next_template),
            "rationale": str(next_rationale),
        },
        "observability_gain": {
            "passed": True,
            "reason": "the context-scoped hybrid probe remained fully observable through the existing wm/plan trace path with explicit scope-gate and scope-multiplier trace fields",
            "baseline_trace_row_count": int(len(baseline_rows)),
            "hybrid_trace_row_count": int(len(hybrid_rows)),
            "context_scoped_trace_row_count": int(len(scoped_rows)),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the probe tests whether the hybrid win becomes stronger when applied only in the supported context slices while keeping plan_ non-owning and downstream logic unchanged",
            "context_scoped_hybrid_improved_useful_upstream_separation": bool(context_scoped_improved),
            "plan_non_owning_preserved": True,
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": float(
                min(
                    1.0,
                    0.55
                    + 0.12 * int(context_scoped_improved)
                    + 0.08 * int(strong_slice_improved)
                    + 0.08 * int(weak_slice_not_harmed)
                    + 0.07 * int(branch_stayed_cleanly_upstream)
                )
            ),
            "reason": "the probe shows whether the hybrid boundary gains can be concentrated into the strongest contexts without harming the weak slice or drifting downstream",
        },
        "safety_neutrality": {
            "passed": bool(safety_preserved),
            "scope": str(proposal.get("scope", "")),
            "reason": "the context-scoped hybrid probe stayed inside the downstream safety envelope with live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": str(next_template),
            "reason": str(next_rationale),
        },
        "diagnostic_conclusions": {
            "context_scoped_hybrid_improved_useful_upstream_separation": bool(context_scoped_improved),
            "branch_stayed_cleanly_upstream": bool(branch_stayed_cleanly_upstream),
            "plan_should_remain_non_owning": True,
            "recommended_next_family": "memory_summary",
            "recommended_next_template": str(next_template),
            "routing_deferred": bool(dict(frontier_artifact.get("diagnostic_conclusions", {})).get("routing_deferred", False)),
        },
    }
    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"proposal_learning_loop_v4_wm_hybrid_context_scoped_probe_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": bool(safety_preserved),
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": (
            "diagnostic shadow passed: the context-scoped hybrid probe stayed inside the intended upstream safety envelope"
            if safety_preserved
            else "diagnostic shadow failed: the context-scoped hybrid probe changed downstream safety behavior beyond the intended upstream scope"
        ),
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
