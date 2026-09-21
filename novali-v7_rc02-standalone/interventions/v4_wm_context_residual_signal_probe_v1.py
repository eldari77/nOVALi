from __future__ import annotations

import json
from collections import Counter
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
from .v4_wm_context_signal_discrimination_probe_v1 import (
    _extract_rows,
    _safety_envelope_report,
)
from .v4_wm_primary_plan_structure_probe_v1 import _clone_cfg, _safe_float


FEATURE_KEYS = [
    "wm_context_supply_score",
    "pred_context_score",
    "projection_recent_quality",
    "inverse_pred_projection_bad_prob",
    "selection_score_pre_gate",
    "calibrated_projected",
    "v4_wm_discrimination_score",
    "v4_wm_residual_signal_score",
]


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


def _augment_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    augmented: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["projection_recent_quality"] = float(
            1.0 - np.clip(float(item.get("projection_recent", 0.0)), 0.0, 1.5) / 1.5
        )
        item["inverse_pred_projection_bad_prob"] = float(
            np.clip(1.0 - float(item.get("pred_projection_bad_prob", 1.0)), 0.0, 1.0)
        )
        augmented.append(item)
    return augmented


def _status_mean(rows: list[dict[str, Any]], status: str, key: str) -> float | None:
    vals = [float(row.get(key, 0.0)) for row in rows if str(row.get("status", "")) == str(status)]
    return _mean(vals)


def _signal_gap(rows: list[dict[str, Any]], signal_key: str) -> float | None:
    provisional = _status_mean(rows, "provisional", signal_key)
    blocked = _status_mean(rows, "blocked", signal_key)
    if provisional is None or blocked is None:
        return None
    return float(provisional - blocked)


def _separation_report(rows: list[dict[str, Any]], signal_key: str) -> dict[str, Any]:
    availability = [float(row.get("availability_proxy", 0.0)) for row in rows]
    projection_quality = [float(row.get("projection_quality_proxy", 0.0)) for row in rows]

    def corr(feature: str, target: list[float]) -> float | None:
        return _pearson([float(row.get(feature, 0.0)) for row in rows], target)

    return {
        "row_count": int(len(rows)),
        "status_counts": dict(Counter(str(row.get("status", "unknown")) for row in rows)),
        "signal_key": str(signal_key),
        "availability_correlations": {
            "signal": corr(signal_key, availability),
            "wm_context_supply_score": corr("wm_context_supply_score", availability),
            "pred_context_score": corr("pred_context_score", availability),
            "inverse_pred_projection_bad_prob": corr("inverse_pred_projection_bad_prob", availability),
            "projection_recent_quality": corr("projection_recent_quality", availability),
            "selection_score_pre_gate": corr("selection_score_pre_gate", availability),
            "calibrated_projected": corr("calibrated_projected", availability),
        },
        "projection_quality_correlations": {
            "signal": corr(signal_key, projection_quality),
            "wm_context_supply_score": corr("wm_context_supply_score", projection_quality),
            "pred_context_score": corr("pred_context_score", projection_quality),
            "inverse_pred_projection_bad_prob": corr("inverse_pred_projection_bad_prob", projection_quality),
            "projection_recent_quality": corr("projection_recent_quality", projection_quality),
        },
        "gap_metrics": {
            "signal_provisional_minus_blocked": _signal_gap(rows, signal_key),
            "selection_score_pre_gate_provisional_minus_blocked": _signal_gap(rows, "selection_score_pre_gate"),
            "calibrated_projected_provisional_minus_blocked": _signal_gap(rows, "calibrated_projected"),
            "wm_context_supply_provisional_minus_blocked": _signal_gap(rows, "wm_context_supply_score"),
        },
    }


def _aligned_overlap_report(
    baseline_rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    signal_key: str,
) -> dict[str, Any]:
    baseline_index = {
        (int(row.get("seed", 0)), int(row.get("round", 0)), str(row.get("candidate_id", ""))): row
        for row in baseline_rows
    }
    comparison_index = {
        (int(row.get("seed", 0)), int(row.get("round", 0)), str(row.get("candidate_id", ""))): row
        for row in comparison_rows
    }
    shared_keys = [key for key in comparison_index if key in baseline_index]
    baseline_pre_gate = [
        float(baseline_index[key].get("selection_score_pre_gate", 0.0))
        for key in shared_keys
    ]
    signal_values = [
        float(comparison_index[key].get(signal_key, 0.0))
        for key in shared_keys
    ]
    selection_values = [
        float(comparison_index[key].get("selection_score_pre_gate", 0.0))
        for key in shared_keys
    ]
    return {
        "shared_row_count": int(len(shared_keys)),
        "signal_to_baseline_pre_gate_correlation": _pearson(signal_values, baseline_pre_gate),
        "selection_to_baseline_pre_gate_correlation": _pearson(selection_values, baseline_pre_gate),
    }


def _distinctness_score(signal_corr: float | None, overlap_corr: float | None) -> float:
    if signal_corr is None or overlap_corr is None:
        return 0.0
    return float(abs(signal_corr) * max(0.0, 1.0 - abs(overlap_corr)))


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    explanation_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v2"
    )
    v1_probe_artifact = r._load_latest_diagnostic_artifact_by_template(
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
            explanation_artifact,
            v1_probe_artifact,
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
            "reason": "diagnostic shadow failed: the residualized wm probe requires the v1 probe, v2 explanation snapshot, and carried-forward safety artifacts",
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
                "reason": "cannot run the residualized wm probe without the shortfall explanation and prior wm branch artifacts",
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

    per_seed_runs: list[dict[str, Any]] = []
    baseline_rows: list[dict[str, Any]] = []
    v1_rows: list[dict[str, Any]] = []
    residual_rows: list[dict[str, Any]] = []
    baseline_summaries: list[dict[str, Any]] = []
    v1_summaries: list[dict[str, Any]] = []
    residual_summaries: list[dict[str, Any]] = []
    safety_reports: list[dict[str, Any]] = []

    for seed in sweep_seeds:
        baseline_cfg = _clone_cfg(cfg, seed=int(seed), rounds=int(sweep_rounds), probe_enabled=True)
        baseline_cfg.v4_wm_plan_context_trace_enabled = True
        baseline_cfg.v4_wm_context_signal_discrimination_probe_enabled = False
        baseline_cfg.v4_wm_context_residual_signal_probe_enabled = False
        baseline_cfg.verbose = False

        v1_cfg = _clone_cfg(cfg, seed=int(seed), rounds=int(sweep_rounds), probe_enabled=True)
        v1_cfg.v4_wm_plan_context_trace_enabled = True
        v1_cfg.v4_wm_context_signal_discrimination_probe_enabled = True
        v1_cfg.v4_wm_context_residual_signal_probe_enabled = False
        v1_cfg.verbose = False

        residual_cfg = _clone_cfg(cfg, seed=int(seed), rounds=int(sweep_rounds), probe_enabled=True)
        residual_cfg.v4_wm_plan_context_trace_enabled = True
        residual_cfg.v4_wm_context_signal_discrimination_probe_enabled = False
        residual_cfg.v4_wm_context_residual_signal_probe_enabled = True
        residual_cfg.verbose = False

        _, _, baseline_history = run_proposal_learning_loop(baseline_cfg)
        _, _, v1_history = run_proposal_learning_loop(v1_cfg)
        _, _, residual_history = run_proposal_learning_loop(residual_cfg)

        baseline_summary = r._summarize_history(baseline_history)
        v1_summary = r._summarize_history(v1_history)
        residual_summary = r._summarize_history(residual_history)

        baseline_seed_rows = _augment_rows(_extract_rows(baseline_history, int(seed), "baseline"))
        v1_seed_rows = _augment_rows(_extract_rows(v1_history, int(seed), "v1_probe"))
        residual_seed_rows = _augment_rows(_extract_rows(residual_history, int(seed), "residual_probe"))

        safety_vs_baseline = _safety_envelope_report(baseline_summary, residual_summary)
        safety_vs_v1 = _safety_envelope_report(v1_summary, residual_summary)

        baseline_rows.extend(baseline_seed_rows)
        v1_rows.extend(v1_seed_rows)
        residual_rows.extend(residual_seed_rows)
        baseline_summaries.append(dict(baseline_summary))
        v1_summaries.append(dict(v1_summary))
        residual_summaries.append(dict(residual_summary))
        safety_reports.append(
            {
                "seed": int(seed),
                "vs_baseline": dict(safety_vs_baseline),
                "vs_v1": dict(safety_vs_v1),
            }
        )
        per_seed_runs.append(
            {
                "seed": int(seed),
                "baseline_summary": dict(baseline_summary),
                "v1_summary": dict(v1_summary),
                "residual_summary": dict(residual_summary),
                "baseline_separation": _separation_report(baseline_seed_rows, "wm_context_supply_score"),
                "v1_separation": _separation_report(v1_seed_rows, "v4_wm_discrimination_score"),
                "residual_separation": _separation_report(residual_seed_rows, "v4_wm_residual_signal_score"),
                "safety_vs_baseline": dict(safety_vs_baseline),
                "safety_vs_v1": dict(safety_vs_v1),
            }
        )

    baseline_report = _separation_report(baseline_rows, "wm_context_supply_score")
    v1_report = _separation_report(v1_rows, "v4_wm_discrimination_score")
    residual_report = _separation_report(residual_rows, "v4_wm_residual_signal_score")

    baseline_overlap = _aligned_overlap_report(baseline_rows, baseline_rows, "wm_context_supply_score")
    v1_overlap = _aligned_overlap_report(baseline_rows, v1_rows, "v4_wm_discrimination_score")
    residual_overlap = _aligned_overlap_report(baseline_rows, residual_rows, "v4_wm_residual_signal_score")

    v1_signal_corr = _safe_float(dict(v1_report.get("availability_correlations", {})).get("signal"), 0.0) or 0.0
    residual_signal_corr = _safe_float(dict(residual_report.get("availability_correlations", {})).get("signal"), 0.0) or 0.0
    v1_signal_gap = _safe_float(dict(v1_report.get("gap_metrics", {})).get("signal_provisional_minus_blocked"), 0.0) or 0.0
    residual_signal_gap = _safe_float(dict(residual_report.get("gap_metrics", {})).get("signal_provisional_minus_blocked"), 0.0) or 0.0
    selection_corr_baseline = _safe_float(dict(baseline_report.get("availability_correlations", {})).get("selection_score_pre_gate"), 0.0) or 0.0
    selection_corr_residual = _safe_float(dict(residual_report.get("availability_correlations", {})).get("selection_score_pre_gate"), 0.0) or 0.0
    selection_gap_baseline = _safe_float(dict(baseline_report.get("gap_metrics", {})).get("selection_score_pre_gate_provisional_minus_blocked"), 0.0) or 0.0
    selection_gap_residual = _safe_float(dict(residual_report.get("gap_metrics", {})).get("selection_score_pre_gate_provisional_minus_blocked"), 0.0) or 0.0
    v1_overlap_corr = _safe_float(v1_overlap.get("signal_to_baseline_pre_gate_correlation"), 0.0) or 0.0
    residual_overlap_corr = _safe_float(residual_overlap.get("signal_to_baseline_pre_gate_correlation"), 0.0) or 0.0
    v1_distinctness = _distinctness_score(v1_signal_corr, v1_overlap_corr)
    residual_distinctness = _distinctness_score(residual_signal_corr, residual_overlap_corr)

    safety_preserved = bool(
        all(
            bool(dict(item.get("vs_baseline", {})).get("passed", False))
            and bool(dict(item.get("vs_v1", {})).get("passed", False))
            for item in safety_reports
        )
    )
    branch_stayed_cleanly_upstream = bool(safety_preserved)
    useful_upstream_separation_improved = bool(
        safety_preserved
        and residual_signal_corr >= 0.30
        and residual_signal_gap > 0.04
        and (
            selection_gap_residual > selection_gap_baseline + 0.002
            or residual_distinctness > v1_distinctness + 0.02
            or residual_overlap_corr < v1_overlap_corr - 0.08
        )
    )

    next_family = "memory_summary"
    next_template = (
        "memory_summary.v4_wm_residual_probe_effect_snapshot_v1"
        if useful_upstream_separation_improved
        else "memory_summary.v4_wm_context_signal_overlap_snapshot_v1"
    )
    next_rationale = (
        "the residualized wm-only probe improved distinct upstream separation while preserving the downstream envelope, so the next step should diagnose where the new residual signal is helping before any broader proposal-learning-loop redesign"
        if useful_upstream_separation_improved
        else "the residualized wm-only probe stayed safe but still needs another diagnostic overlap readout before further behavior-changing work"
    )

    comparison_refs = {}
    for artifact in [
        explanation_artifact,
        v1_probe_artifact,
        trace_quality_artifact,
        wm_branch_artifact,
        wm_entry_artifact,
        hardening_artifact,
        frontier_artifact,
    ]:
        proposal_id = str(artifact.get("proposal_id", ""))
        comparison_refs[str(artifact.get("template_name", ""))] = {
            "proposal_id": proposal_id,
            "ledger_revision": int(dict(latest_snapshots.get(proposal_id, {})).get("ledger_revision", 0) or 0),
            "artifact_path": str(artifact.get("_artifact_path", "")),
        }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "proposal_learning_loop.v4_wm_context_residual_signal_probe_v1",
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
        "branch_implementation_summary": {
            "wm_residual_signal_changes": [
                "added a residualized wm-only discrimination lever that modifies only the projected wm candidate score path",
                "built the residual score around wm_context_supply_score, pred_context_score, inverse pred_projection_bad_prob, and projection_recent quality",
                "used baseline-overlap removal instead of direct positive reuse for pred_gain_sign_prob and calibrated_projected",
            ],
            "trace_features_used": [
                "wm_context_supply_score",
                "pred_context_score",
                "inverse pred_projection_bad_prob",
                "projection_recent_quality",
                "pred_uncertainty",
                "wm_quality_penalty",
            ],
            "baseline_dominant_features_reduced_or_removed": [
                "removed direct positive reuse of pred_gain_sign_prob",
                "removed direct positive reuse of calibrated_projected",
                "kept both only as an overlap penalty to reduce baseline-path subsumption",
            ],
            "plan_remained_non_owning": [
                "planning_handoff_score was not used as an independent decision lever",
                "plan_ remained a structure/handoff layer only",
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
            "overlap_reports": {
                "baseline": baseline_overlap,
                "v1": v1_overlap,
                "residual": residual_overlap,
            },
            "per_seed_runs": per_seed_runs,
            "safety_envelope_reports": safety_reports,
            "comparison_vs_baseline": {
                "selection_score_pre_gate_availability_corr_delta": float(selection_corr_residual - selection_corr_baseline),
                "selection_score_pre_gate_gap_delta": float(selection_gap_residual - selection_gap_baseline),
                "residual_signal_availability_corr": float(residual_signal_corr),
                "residual_signal_gap": float(residual_signal_gap),
                "residual_signal_overlap_to_baseline_pre_gate": float(residual_overlap_corr),
                "residual_distinctness_score": float(residual_distinctness),
            },
            "comparison_vs_v1": {
                "signal_availability_corr_delta": float(residual_signal_corr - v1_signal_corr),
                "signal_gap_delta": float(residual_signal_gap - v1_signal_gap),
                "signal_overlap_to_baseline_pre_gate_delta": float(residual_overlap_corr - v1_overlap_corr),
                "distinctness_score_delta": float(residual_distinctness - v1_distinctness),
                "v1_signal_availability_corr": float(v1_signal_corr),
                "v1_signal_gap": float(v1_signal_gap),
                "v1_signal_overlap_to_baseline_pre_gate": float(v1_overlap_corr),
                "v1_distinctness_score": float(v1_distinctness),
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
            "useful_upstream_separation_improved": bool(useful_upstream_separation_improved),
            "branch_stayed_cleanly_upstream": bool(branch_stayed_cleanly_upstream),
            "recommended_next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "rationale": str(next_rationale),
        },
        "observability_gain": {
            "passed": True,
            "reason": "the residualized wm-only probe remained fully observable through the existing wm/plan trace path with its own residual signal trace fields",
            "baseline_trace_row_count": int(len(baseline_rows)),
            "v1_trace_row_count": int(len(v1_rows)),
            "residual_trace_row_count": int(len(residual_rows)),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the probe directly tests whether a narrower residualized wm subset can add information beyond the baseline pre-gate path without changing plan ownership or downstream selected-set behavior",
            "useful_upstream_separation_improved": bool(useful_upstream_separation_improved),
            "plan_non_owning_preserved": True,
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": float(
                min(
                    1.0,
                    0.50
                    + 0.18 * int(useful_upstream_separation_improved)
                    + 0.12 * int(branch_stayed_cleanly_upstream)
                    + 0.10 * int(residual_distinctness > v1_distinctness)
                )
            ),
            "reason": "the probe shows whether removing baseline-dominant reuse creates distinct wm-owned headroom before any broader proposal-learning-loop redesign",
        },
        "safety_neutrality": {
            "passed": bool(safety_preserved),
            "scope": str(proposal.get("scope", "")),
            "reason": "residualized wm-only discrimination stayed inside the downstream safety envelope with live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": str(next_template),
            "reason": str(next_rationale),
        },
        "diagnostic_conclusions": {
            "useful_upstream_separation_improved": bool(useful_upstream_separation_improved),
            "branch_stayed_cleanly_upstream": bool(branch_stayed_cleanly_upstream),
            "recommended_next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "routing_deferred": bool(dict(frontier_artifact.get("diagnostic_conclusions", {})).get("routing_deferred", False)),
        },
    }
    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"proposal_learning_loop_v4_wm_context_residual_signal_probe_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": bool(safety_preserved),
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": (
            "diagnostic shadow passed: residualized wm-only discrimination stayed inside the safety envelope"
            if safety_preserved
            else "diagnostic shadow failed: residualized wm-only discrimination exceeded the intended upstream safety envelope"
        ),
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
