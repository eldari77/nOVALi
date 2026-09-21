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
    "planning_handoff_score",
    "pred_context_score",
    "pred_gain_norm",
    "pred_gain_sign_prob",
    "pred_uncertainty",
    "selection_score_pre_gate",
    "calibrated_projected",
    "projection_recent",
    "projection_trend",
    "wm_quality_penalty",
    "retained_evidence",
    "retained_rounds",
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


def _extract_trace_rows(history: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in history:
        round_index = int(dict(entry).get("round", 0))
        for row in list(dict(entry).get("wm_plan_context_rows", [])):
            if not isinstance(row, dict):
                continue
            merged = dict(row)
            merged["seed"] = int(seed)
            merged["round"] = int(merged.get("round", round_index))
            merged["availability_proxy"] = 1.0 if str(merged.get("status", "")) in {"provisional", "full"} else 0.0
            merged["collapse_pressure_proxy"] = 1.0 - float(merged["availability_proxy"])
            merged["projection_quality_proxy"] = float(1.0 - float(merged.get("pred_projection_bad_prob", 1.0)))
            merged["benchmark_like_survival_opportunity_proxy"] = float(
                max(0.0, float(merged.get("selection_score_pre_gate", 0.0)))
                * float(merged["availability_proxy"])
                * max(0.0, 1.0 - float(merged.get("pred_projection_bad_prob", 1.0)))
            )
            rows.append(merged)
    return rows


def _feature_inventory(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"available": False, "row_count": 0, "all_keys": []}
    sample = dict(rows[0])
    return {
        "available": True,
        "row_count": int(len(rows)),
        "all_keys": sorted(sample.keys()),
        "structural_keys": [
            "seed",
            "round",
            "agent",
            "proposer",
            "candidate_id",
            "world_model_active",
            "planning_active",
            "plan_horizon",
            "plan_candidates",
            "status",
        ],
        "wm_predictive_keys": [
            "pred_context_score",
            "pred_gain_norm",
            "pred_gain_sign_prob",
            "pred_projection_bad_prob",
            "pred_uncertainty",
            "calibrated_projected",
            "selection_score_pre_gate",
        ],
        "trace_derived_keys": [
            "wm_context_supply_score",
            "planning_handoff_score",
            "projection_recent",
            "projection_trend",
            "wm_quality_penalty",
            "retained_evidence",
            "retained_rounds",
        ],
    }


def _seed_breakdown(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seeds = sorted({int(row.get("seed", 0)) for row in rows})
    breakdown: list[dict[str, Any]] = []
    for seed in seeds:
        seed_rows = [row for row in rows if int(row.get("seed", 0)) == seed]
        breakdown.append(
            {
                "seed": int(seed),
                "trace_row_count": int(len(seed_rows)),
                "availability_rate": _mean([float(row.get("availability_proxy", 0.0)) for row in seed_rows]),
                "collapse_rate": _mean([float(row.get("collapse_pressure_proxy", 0.0)) for row in seed_rows]),
                "mean_projection_quality": _mean([float(row.get("projection_quality_proxy", 0.0)) for row in seed_rows]),
                "mean_wm_context_supply_score": _mean([float(row.get("wm_context_supply_score", 0.0)) for row in seed_rows]),
                "mean_planning_handoff_score": _mean([float(row.get("planning_handoff_score", 0.0)) for row in seed_rows]),
                "mean_selection_score_pre_gate": _mean([float(row.get("selection_score_pre_gate", 0.0)) for row in seed_rows]),
                "status_counts": dict(Counter(str(row.get("status", "unknown")) for row in seed_rows)),
            }
        )
    return breakdown


def _status_breakdown(rows: list[dict[str, Any]]) -> dict[str, Any]:
    breakdown: dict[str, Any] = {}
    for status in sorted({str(row.get("status", "unknown")) for row in rows}):
        status_rows = [row for row in rows if str(row.get("status", "unknown")) == status]
        breakdown[status] = {
            "count": int(len(status_rows)),
            "mean_wm_context_supply_score": _mean([float(row.get("wm_context_supply_score", 0.0)) for row in status_rows]),
            "mean_planning_handoff_score": _mean([float(row.get("planning_handoff_score", 0.0)) for row in status_rows]),
            "mean_projection_quality": _mean([float(row.get("projection_quality_proxy", 0.0)) for row in status_rows]),
            "mean_pred_context_score": _mean([float(row.get("pred_context_score", 0.0)) for row in status_rows]),
            "mean_selection_score_pre_gate": _mean([float(row.get("selection_score_pre_gate", 0.0)) for row in status_rows]),
        }
    return breakdown


def _rank_correlations(rows: list[dict[str, Any]], *, target_key: str, exclude_features: set[str] | None = None) -> list[dict[str, Any]]:
    exclude = set(exclude_features or set())
    target = [float(row.get(target_key, 0.0)) for row in rows]
    ranked: list[dict[str, Any]] = []
    for feature in FEATURE_KEYS:
        if feature in exclude:
            continue
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


def _distinct_information_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    wm_values = [float(row.get("wm_context_supply_score", 0.0)) for row in rows]
    plan_values = [float(row.get("planning_handoff_score", 0.0)) for row in rows]
    availability = [float(row.get("availability_proxy", 0.0)) for row in rows]
    opportunity = [float(row.get("benchmark_like_survival_opportunity_proxy", 0.0)) for row in rows]
    wm_plan_corr = _pearson(wm_values, plan_values)
    wm_availability_corr = _pearson(wm_values, availability)
    plan_availability_corr = _pearson(plan_values, availability)
    wm_opportunity_corr = _pearson(wm_values, opportunity)
    plan_opportunity_corr = _pearson(plan_values, opportunity)
    distinct = bool(
        wm_plan_corr is not None
        and abs(wm_plan_corr) < 0.98
        and (
            abs((plan_availability_corr or 0.0) - (wm_availability_corr or 0.0)) >= 0.05
            or abs((plan_opportunity_corr or 0.0) - (wm_opportunity_corr or 0.0)) >= 0.05
        )
    )
    return {
        "wm_plan_correlation": wm_plan_corr,
        "wm_availability_correlation": wm_availability_corr,
        "plan_availability_correlation": plan_availability_corr,
        "wm_opportunity_correlation": wm_opportunity_corr,
        "plan_opportunity_correlation": plan_opportunity_corr,
        "distinct_information_present": bool(distinct),
        "reason": (
            "planning_handoff_score contributes distinct structure beyond wm_context_supply_score"
            if distinct
            else "planning_handoff_score is effectively collinear with wm_context_supply_score in the current first-branch implementation"
        ),
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    wm_plan_probe_artifact = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_wm_primary_plan_structure_probe_v1"
    )
    wm_plan_entry_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_world_model_planning_context_entry_snapshot_v1"
    )
    loop_surface_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_proposal_learning_loop_context_branch_snapshot_v1"
    )
    architecture_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_architecture_upstream_context_branch_snapshot_v1"
    )
    hardening_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.swap_c_incumbent_hardening_probe_v1"
    )
    frontier_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.false_safe_frontier_control_characterization_snapshot_v1"
    )
    if not all(
        [
            wm_plan_probe_artifact,
            wm_plan_entry_artifact,
            loop_surface_artifact,
            architecture_artifact,
            hardening_artifact,
            frontier_artifact,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: wm/plan trace-quality snapshot requires the carried-forward v4 branch-entry, implementation-probe, and v3 closure artifacts",
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
                "reason": "cannot judge wm/plan trace quality without the prerequisite v4 branch-opening evidence",
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

    per_seed_context_runs: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []
    for seed in sweep_seeds:
        probe_cfg = _clone_cfg(cfg, seed=int(seed), rounds=int(sweep_rounds), probe_enabled=True)
        _, _, history = run_proposal_learning_loop(probe_cfg)
        summary = r._summarize_history(history)
        trace_rows = _extract_trace_rows(history, int(seed))
        all_rows.extend(trace_rows)
        per_seed_context_runs.append(
            {
                "seed": int(seed),
                "history_summary": dict(summary),
                "trace_row_count": int(len(trace_rows)),
                "status_counts": dict(Counter(str(row.get("status", "unknown")) for row in trace_rows)),
            }
        )

    feature_inventory = _feature_inventory(all_rows)
    seed_breakdown = _seed_breakdown(all_rows)
    status_breakdown = _status_breakdown(all_rows)

    availability_ranked = _rank_correlations(all_rows, target_key="availability_proxy")
    collapse_ranked = _rank_correlations(all_rows, target_key="collapse_pressure_proxy")
    projection_quality_ranked = _rank_correlations(
        all_rows,
        target_key="projection_quality_proxy",
        exclude_features={"pred_projection_bad_prob"},
    )
    opportunity_ranked = _rank_correlations(
        all_rows,
        target_key="benchmark_like_survival_opportunity_proxy",
    )
    distinct_info = _distinct_information_report(all_rows)

    provisional_mean = _safe_float(dict(status_breakdown.get("provisional", {})).get("mean_wm_context_supply_score"), None)
    blocked_mean = _safe_float(dict(status_breakdown.get("blocked", {})).get("mean_wm_context_supply_score"), None)
    wm_gap = None if provisional_mean is None or blocked_mean is None else float(provisional_mean - blocked_mean)
    wm_availability_corr = _safe_float(
        dict(availability_ranked[0] if availability_ranked and availability_ranked[0]["feature"] == "wm_context_supply_score" else {}).get("correlation"),
        None,
    )
    if wm_availability_corr is None:
        for row in availability_ranked:
            if str(row.get("feature", "")) == "wm_context_supply_score":
                wm_availability_corr = _safe_float(row.get("correlation"), None)
                break
    traces_good_enough = bool(
        len(all_rows) >= 18
        and (wm_gap is not None and wm_gap >= 0.03)
        and (wm_availability_corr is not None and abs(wm_availability_corr) >= 0.20)
    )

    next_family = "proposal_learning_loop" if traces_good_enough else "memory_summary"
    next_template = (
        "proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1"
        if traces_good_enough
        else "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v2"
    )
    next_rationale = (
        "wm_context_supply_score shows real discriminative separation across provisional vs blocked conditions, while planning_handoff_score is currently redundant, so the next behavior-changing step should stay proposal_learning_loop and target wm-owned context discrimination rather than planning ownership or downstream selection"
        if traces_good_enough
        else "the traces need one more diagnostic pass before a behavior-changing proposal because the current signal does not separate contexts strongly enough"
    )

    comparison_refs = {}
    for artifact in [
        wm_plan_probe_artifact,
        wm_plan_entry_artifact,
        loop_surface_artifact,
        architecture_artifact,
        hardening_artifact,
        frontier_artifact,
    ]:
        proposal_id = str(artifact.get("proposal_id", ""))
        comparison_refs[str(artifact.get("template_name", ""))] = {
            "proposal_id": proposal_id,
            "ledger_revision": int(dict(latest_snapshots.get(proposal_id, {})).get("ledger_revision", 0) or 0),
            "artifact_path": str(artifact.get("_artifact_path", "")),
        }

    strongest_signals = {
        "candidate_availability": availability_ranked[:4],
        "collapse_or_scarcity_pressure": collapse_ranked[:4],
        "projection_quality_non_direct": projection_quality_ranked[:4],
        "benchmark_like_survival_opportunity_proxy": opportunity_ranked[:4],
    }
    weakest_signals = sorted(
        [
            row
            for row in availability_ranked
            if row.get("correlation") is not None
        ],
        key=lambda item: abs(float(item.get("correlation", 0.0))),
    )[:4]

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v1",
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
        "trace_quality_analysis": {
            "seed_sweep_used": list(sweep_seeds),
            "rounds_used_per_seed": int(sweep_rounds),
            "trace_feature_inventory": feature_inventory,
            "seed_context_breakdown": seed_breakdown,
            "status_breakdown": status_breakdown,
            "strongest_signals": strongest_signals,
            "weakest_signals": weakest_signals,
            "wm_signal_diagnostics": {
                "wm_context_supply_gap_provisional_minus_blocked": wm_gap,
                "wm_context_supply_availability_correlation": wm_availability_corr,
                "mean_wm_context_supply_score": _mean([float(row.get("wm_context_supply_score", 0.0)) for row in all_rows]),
                "mean_pred_context_score": _mean([float(row.get("pred_context_score", 0.0)) for row in all_rows]),
                "mean_pred_uncertainty": _mean([float(row.get("pred_uncertainty", 0.0)) for row in all_rows]),
                "signal_quality_label": (
                    "informative"
                    if traces_good_enough
                    else "weak_or_mixed"
                ),
            },
            "wm_plan_distinct_information": distinct_info,
            "benchmark_like_survival_inference_note": "proposal_learning_loop traces do not emit true benchmark-like labels; the reported survival metric is an upstream opportunity proxy based on availability, pre-gate score, and projection quality",
            "per_seed_context_runs": per_seed_context_runs,
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
            "traces_good_enough_for_behavior_change": bool(traces_good_enough),
            "recommended_next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "rationale": str(next_rationale),
        },
        "observability_gain": {
            "passed": bool(len(all_rows) >= 18),
            "reason": "the snapshot gathered enough wm/plan trace rows across multiple seed/context conditions to measure feature quality instead of relying on the single-seed opening probe alone",
            "seed_count": int(len(sweep_seeds)),
            "trace_row_count": int(len(all_rows)),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the snapshot ranks the strongest and weakest wm/plan trace signals and isolates whether planning_handoff_score adds distinct information beyond wm context supply",
            "planning_adds_distinct_information": bool(distinct_info.get("distinct_information_present", False)),
            "wm_signal_quality_label": "",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": float(
                min(
                    1.0,
                    0.42
                    + 0.10 * int(len(sweep_seeds) >= 3)
                    + 0.18 * int(len(all_rows) >= 18)
                    + 0.15 * int(traces_good_enough)
                    + 0.10 * int(not bool(distinct_info.get("distinct_information_present", False))),
                )
            ),
            "reason": "the snapshot resolves whether the new wm->plan traces are strong enough for the next behavior-changing branch step and whether that next step should stay wm-primary",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "diagnostic-only trace-quality snapshot with live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": str(next_template),
            "reason": str(next_rationale),
        },
        "diagnostic_conclusions": {
            "traces_good_enough_for_behavior_change": bool(traces_good_enough),
            "wm_signal_quality_label": "informative" if traces_good_enough else "weak_or_mixed",
            "planning_adds_distinct_information": bool(distinct_info.get("distinct_information_present", False)),
            "recommended_next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "routing_deferred": bool(dict(frontier_artifact.get("diagnostic_conclusions", {})).get("routing_deferred", False)),
        },
    }
    artifact_payload["activation_analysis_usefulness"]["wm_signal_quality_label"] = str(
        artifact_payload["diagnostic_conclusions"]["wm_signal_quality_label"]
    )

    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"memory_summary_v4_wm_plan_context_trace_quality_snapshot_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: wm/plan trace quality was characterized for the first v4 branch",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
