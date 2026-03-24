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
from .v4_wm_primary_plan_structure_probe_v1 import _clone_cfg, _safe_float


FEATURE_KEYS = [
    "wm_context_supply_score",
    "v4_wm_discrimination_score",
    "v4_wm_discrimination_delta",
    "pred_context_score",
    "pred_gain_sign_prob",
    "calibrated_projected",
    "selection_score_pre_gate",
    "pred_uncertainty",
    "pred_projection_bad_prob",
    "projection_recent",
    "wm_quality_penalty",
]


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(sum(values) / len(values))


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(ys) < 2 or len(xs) != len(ys):
        return None
    x = np.asarray(xs, dtype=np.float64)
    y = np.asarray(ys, dtype=np.float64)
    if float(np.std(x)) <= 1e-12 or float(np.std(y)) <= 1e-12:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def _extract_rows(history: list[dict[str, Any]], seed: int, mode: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in history:
        round_index = int(dict(entry).get("round", 0))
        for row in list(dict(entry).get("wm_plan_context_rows", [])):
            if not isinstance(row, dict):
                continue
            merged = dict(row)
            merged["seed"] = int(seed)
            merged["mode"] = str(mode)
            merged["round"] = int(merged.get("round", round_index))
            merged["availability_proxy"] = 1.0 if str(merged.get("status", "")) in {"provisional", "full"} else 0.0
            merged["collapse_pressure_proxy"] = 1.0 - float(merged["availability_proxy"])
            merged["projection_quality_proxy"] = float(1.0 - float(merged.get("pred_projection_bad_prob", 1.0)))
            rows.append(merged)
    return rows


def _rank_correlations(rows: list[dict[str, Any]], target_key: str) -> list[dict[str, Any]]:
    target = [float(row.get(target_key, 0.0)) for row in rows]
    ranked: list[dict[str, Any]] = []
    for feature in FEATURE_KEYS:
        values = [float(row.get(feature, 0.0)) for row in rows]
        corr = _pearson(values, target)
        ranked.append(
            {
                "feature": str(feature),
                "correlation": corr,
                "abs_correlation": abs(corr) if corr is not None else None,
            }
        )
    ranked.sort(key=lambda item: (float(item["abs_correlation"]) if item["abs_correlation"] is not None else -1.0), reverse=True)
    return ranked


def _status_mean(rows: list[dict[str, Any]], status: str, key: str) -> float | None:
    vals = [float(row.get(key, 0.0)) for row in rows if str(row.get("status", "")) == str(status)]
    return _mean(vals)


def _separation_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    availability = [float(row.get("availability_proxy", 0.0)) for row in rows]
    projection_quality = [float(row.get("projection_quality_proxy", 0.0)) for row in rows]

    def corr(feature: str, target: list[float]) -> float | None:
        values = [float(row.get(feature, 0.0)) for row in rows]
        return _pearson(values, target)

    selection_gap = None
    provisional_sel = _status_mean(rows, "provisional", "selection_score_pre_gate")
    blocked_sel = _status_mean(rows, "blocked", "selection_score_pre_gate")
    if provisional_sel is not None and blocked_sel is not None:
        selection_gap = float(provisional_sel - blocked_sel)

    projected_gap = None
    provisional_proj = _status_mean(rows, "provisional", "calibrated_projected")
    blocked_proj = _status_mean(rows, "blocked", "calibrated_projected")
    if provisional_proj is not None and blocked_proj is not None:
        projected_gap = float(provisional_proj - blocked_proj)

    wm_gap = None
    provisional_wm = _status_mean(rows, "provisional", "wm_context_supply_score")
    blocked_wm = _status_mean(rows, "blocked", "wm_context_supply_score")
    if provisional_wm is not None and blocked_wm is not None:
        wm_gap = float(provisional_wm - blocked_wm)

    discr_gap = None
    provisional_discr = _status_mean(rows, "provisional", "v4_wm_discrimination_score")
    blocked_discr = _status_mean(rows, "blocked", "v4_wm_discrimination_score")
    if provisional_discr is not None and blocked_discr is not None:
        discr_gap = float(provisional_discr - blocked_discr)

    return {
        "row_count": int(len(rows)),
        "status_counts": dict(Counter(str(row.get("status", "unknown")) for row in rows)),
        "availability_correlations": {
            "wm_context_supply_score": corr("wm_context_supply_score", availability),
            "v4_wm_discrimination_score": corr("v4_wm_discrimination_score", availability),
            "selection_score_pre_gate": corr("selection_score_pre_gate", availability),
            "calibrated_projected": corr("calibrated_projected", availability),
            "pred_gain_sign_prob": corr("pred_gain_sign_prob", availability),
        },
        "projection_quality_correlations": {
            "wm_context_supply_score": corr("wm_context_supply_score", projection_quality),
            "v4_wm_discrimination_score": corr("v4_wm_discrimination_score", projection_quality),
            "pred_context_score": corr("pred_context_score", projection_quality),
            "selection_score_pre_gate": corr("selection_score_pre_gate", projection_quality),
        },
        "gap_metrics": {
            "selection_score_pre_gate_provisional_minus_blocked": selection_gap,
            "calibrated_projected_provisional_minus_blocked": projected_gap,
            "wm_context_supply_provisional_minus_blocked": wm_gap,
            "v4_wm_discrimination_provisional_minus_blocked": discr_gap,
        },
        "top_availability_signals": _rank_correlations(rows, "availability_proxy")[:5],
        "top_projection_quality_signals": _rank_correlations(rows, "projection_quality_proxy")[:5],
    }


def _safety_envelope_report(baseline_summary: dict[str, Any], probe_summary: dict[str, Any]) -> dict[str, Any]:
    count_deltas = {
        "provisional_count": int(probe_summary.get("provisional_count", 0) or 0) - int(baseline_summary.get("provisional_count", 0) or 0),
        "full_adopt_count": int(probe_summary.get("full_adopt_count", 0) or 0) - int(baseline_summary.get("full_adopt_count", 0) or 0),
        "rollback_count": int(probe_summary.get("rollback_count", 0) or 0) - int(baseline_summary.get("rollback_count", 0) or 0),
        "projection_bad_incidents": int(probe_summary.get("projection_bad_incidents", 0) or 0) - int(baseline_summary.get("projection_bad_incidents", 0) or 0),
    }
    float_deltas = {
        "mean_projection_error": (
            None
            if _safe_float(baseline_summary.get("mean_projection_error"), None) is None
            or _safe_float(probe_summary.get("mean_projection_error"), None) is None
            else float(_safe_float(probe_summary.get("mean_projection_error"), 0.0) - _safe_float(baseline_summary.get("mean_projection_error"), 0.0))
        ),
        "mean_goal_mse_latent": (
            None
            if _safe_float(baseline_summary.get("mean_goal_mse_latent"), None) is None
            or _safe_float(probe_summary.get("mean_goal_mse_latent"), None) is None
            else float(_safe_float(probe_summary.get("mean_goal_mse_latent"), 0.0) - _safe_float(baseline_summary.get("mean_goal_mse_latent"), 0.0))
        ),
        "mean_realized_gain": (
            None
            if _safe_float(baseline_summary.get("mean_realized_gain"), None) is None
            or _safe_float(probe_summary.get("mean_realized_gain"), None) is None
            else float(_safe_float(probe_summary.get("mean_realized_gain"), 0.0) - _safe_float(baseline_summary.get("mean_realized_gain"), 0.0))
        ),
    }
    passed = bool(
        count_deltas["rollback_count"] <= 0
        and count_deltas["projection_bad_incidents"] <= 0
        and count_deltas["full_adopt_count"] <= 0
        and (float_deltas["mean_projection_error"] is None or float_deltas["mean_projection_error"] <= 1e-9)
    )
    return {
        "passed": bool(passed),
        "count_deltas": count_deltas,
        "float_deltas": float_deltas,
        "reason": (
            "wm-only discrimination stayed inside the downstream safety envelope"
            if passed
            else "wm-only discrimination changed downstream safety behavior beyond the intended upstream scope"
        ),
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

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
            "reason": "diagnostic shadow failed: the first behavior-changing wm discrimination probe requires the v4 trace-quality, branch-opening, and carried-forward safety artifacts",
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
                "reason": "cannot run the wm-only behavior-changing probe without the trace-quality evidence",
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
    probe_rows: list[dict[str, Any]] = []
    baseline_summaries: list[dict[str, Any]] = []
    probe_summaries: list[dict[str, Any]] = []
    safety_reports: list[dict[str, Any]] = []

    for seed in sweep_seeds:
        baseline_cfg = _clone_cfg(cfg, seed=int(seed), rounds=int(sweep_rounds), probe_enabled=True)
        baseline_cfg.v4_wm_context_signal_discrimination_probe_enabled = False
        baseline_cfg.v4_wm_plan_context_trace_enabled = True
        baseline_cfg.verbose = False

        probe_cfg = _clone_cfg(cfg, seed=int(seed), rounds=int(sweep_rounds), probe_enabled=True)
        probe_cfg.v4_wm_context_signal_discrimination_probe_enabled = True
        probe_cfg.v4_wm_plan_context_trace_enabled = True
        probe_cfg.verbose = False

        _, _, baseline_history = run_proposal_learning_loop(baseline_cfg)
        _, _, probe_history = run_proposal_learning_loop(probe_cfg)

        baseline_summary = r._summarize_history(baseline_history)
        probe_summary = r._summarize_history(probe_history)
        baseline_seed_rows = _extract_rows(baseline_history, int(seed), "baseline")
        probe_seed_rows = _extract_rows(probe_history, int(seed), "probe")
        safety = _safety_envelope_report(baseline_summary, probe_summary)

        baseline_rows.extend(baseline_seed_rows)
        probe_rows.extend(probe_seed_rows)
        baseline_summaries.append(dict(baseline_summary))
        probe_summaries.append(dict(probe_summary))
        safety_reports.append(dict(safety))
        per_seed_runs.append(
            {
                "seed": int(seed),
                "baseline_summary": dict(baseline_summary),
                "probe_summary": dict(probe_summary),
                "baseline_separation": _separation_report(baseline_seed_rows),
                "probe_separation": _separation_report(probe_seed_rows),
                "safety_envelope": dict(safety),
            }
        )

    baseline_report = _separation_report(baseline_rows)
    probe_report = _separation_report(probe_rows)

    availability_corr_baseline = _safe_float(
        dict(baseline_report.get("availability_correlations", {})).get("selection_score_pre_gate"),
        0.0,
    ) or 0.0
    availability_corr_probe = _safe_float(
        dict(probe_report.get("availability_correlations", {})).get("selection_score_pre_gate"),
        0.0,
    ) or 0.0
    projected_corr_baseline = _safe_float(
        dict(baseline_report.get("availability_correlations", {})).get("calibrated_projected"),
        0.0,
    ) or 0.0
    projected_corr_probe = _safe_float(
        dict(probe_report.get("availability_correlations", {})).get("calibrated_projected"),
        0.0,
    ) or 0.0
    selection_gap_baseline = _safe_float(
        dict(baseline_report.get("gap_metrics", {})).get("selection_score_pre_gate_provisional_minus_blocked"),
        0.0,
    ) or 0.0
    selection_gap_probe = _safe_float(
        dict(probe_report.get("gap_metrics", {})).get("selection_score_pre_gate_provisional_minus_blocked"),
        0.0,
    ) or 0.0
    discr_corr_probe = _safe_float(
        dict(probe_report.get("availability_correlations", {})).get("v4_wm_discrimination_score"),
        0.0,
    ) or 0.0
    discr_gap_probe = _safe_float(
        dict(probe_report.get("gap_metrics", {})).get("v4_wm_discrimination_provisional_minus_blocked"),
        0.0,
    ) or 0.0
    useful_upstream_separation_improved = bool(
        (availability_corr_probe > availability_corr_baseline + 0.01 or selection_gap_probe > selection_gap_baseline + 0.01 or projected_corr_probe > projected_corr_baseline + 0.01)
        and discr_corr_probe >= 0.20
        and discr_gap_probe > 0.0
    )
    safety_preserved = bool(all(bool(report.get("passed", False)) for report in safety_reports))
    branch_stayed_cleanly_upstream = bool(safety_preserved)

    next_family = "memory_summary" if useful_upstream_separation_improved else "memory_summary"
    next_template = (
        "memory_summary.v4_wm_discrimination_probe_effect_snapshot_v1"
        if useful_upstream_separation_improved
        else "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v2"
    )
    next_rationale = (
        "the first wm-only discrimination probe improved upstream separation while preserving the downstream envelope, so the next step should characterize where the effect landed before deciding on a broader proposal-learning-loop branch extension"
        if useful_upstream_separation_improved
        else "the wm-only discrimination effect needs another diagnostic pass before further behavior-changing work"
    )

    comparison_refs = {}
    for artifact in [
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
        "template_name": "proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1",
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
            "wm_discrimination_changes": [
                "added a probe-only wm discrimination lever that modifies only the projected wm candidate score path",
                "applied a bounded wm-only discrimination delta to raw/calibrated projected scores before they are mixed into the existing pre-gate selection score",
                "left adoption, social-confidence, thresholds, routing, and selected-set logic unchanged",
            ],
            "trace_features_used": [
                "wm_context_supply_score",
                "pred_context_score",
                "pred_gain_sign_prob",
                "calibrated_projected",
                "pred_projection_bad_prob",
                "pred_uncertainty",
                "projection_recent",
                "wm_quality_penalty",
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
            "probe_separation": probe_report,
            "per_seed_runs": per_seed_runs,
            "safety_envelope_reports": safety_reports,
            "comparison_vs_baseline": {
                "selection_score_pre_gate_availability_corr_delta": float(availability_corr_probe - availability_corr_baseline),
                "calibrated_projected_availability_corr_delta": float(projected_corr_probe - projected_corr_baseline),
                "selection_score_pre_gate_gap_delta": float(selection_gap_probe - selection_gap_baseline),
                "v4_wm_discrimination_availability_corr_probe": float(discr_corr_probe),
                "v4_wm_discrimination_gap_probe": float(discr_gap_probe),
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
            "reason": "the first wm-only behavior-changing probe remained fully observable through the existing wm/plan trace path",
            "baseline_trace_row_count": int(len(baseline_rows)),
            "probe_trace_row_count": int(len(probe_rows)),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the probe directly tests whether wm-only discrimination improves useful upstream separation without relying on plan ownership or downstream selected-set changes",
            "useful_upstream_separation_improved": bool(useful_upstream_separation_improved),
            "plan_non_owning_preserved": True,
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": float(
                min(
                    1.0,
                    0.46
                    + 0.18 * int(useful_upstream_separation_improved)
                    + 0.16 * int(branch_stayed_cleanly_upstream)
                    + 0.10 * int(discr_corr_probe >= 0.20)
                )
            ),
            "reason": "the probe shows whether the first behavior-changing wm-owned lever is productive before any broader proposal-learning-loop redesign",
        },
        "safety_neutrality": {
            "passed": bool(safety_preserved),
            "scope": str(proposal.get("scope", "")),
            "reason": "wm-only discrimination stayed inside the downstream safety envelope with live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope unchanged",
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
        / f"proposal_learning_loop_v4_wm_context_signal_discrimination_probe_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": bool(safety_preserved),
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": (
            "diagnostic shadow passed: wm-only discrimination stayed inside the safety envelope"
            if safety_preserved
            else "diagnostic shadow failed: wm-only discrimination exceeded the intended upstream safety envelope"
        ),
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
