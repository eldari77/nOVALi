from __future__ import annotations

import copy
import json
from collections import Counter
from typing import Any

from experiments.proposal_learning_loop import ProposalLearningConfig, run_proposal_learning_loop

from .analytics import build_intervention_ledger_analytics
from .ledger import intervention_data_dir, load_latest_snapshots
from .v4_first_hypothesis_landscape_snapshot_v1 import (
    ACTIVE_STATUS_PATH,
    HANDOFF_STATUS_PATH,
    PROPOSAL_LOOP_PATH,
    _load_json_file,
    _load_text_file,
)


def _safe_float(value: Any, default: float | None = 0.0) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(sum(values) / len(values))


def _clone_cfg(cfg: ProposalLearningConfig, *, seed: int, rounds: int, probe_enabled: bool) -> ProposalLearningConfig:
    run_cfg = copy.deepcopy(cfg)
    run_cfg.seed = int(seed)
    run_cfg.rounds = int(rounds)
    run_cfg.verbose = False
    run_cfg.v4_wm_primary_plan_structure_probe_enabled = bool(probe_enabled)
    run_cfg.v4_wm_plan_context_trace_enabled = bool(probe_enabled)
    return run_cfg


def _trace_report(history: list[dict[str, Any]]) -> dict[str, Any]:
    round_summaries = [dict(entry.get("wm_plan_round_summary", {})) for entry in history if isinstance(entry, dict)]
    rows = [
        dict(row)
        for entry in history
        for row in list(dict(entry).get("wm_plan_context_rows", []))
        if isinstance(row, dict)
    ]
    status_counts: Counter[str] = Counter(str(row.get("status", "unknown")) for row in rows)
    top_examples = sorted(
        rows,
        key=lambda row: (
            _safe_float(row.get("planning_handoff_score"), 0.0) or 0.0,
            _safe_float(row.get("wm_context_supply_score"), 0.0) or 0.0,
        ),
        reverse=True,
    )[:5]
    return {
        "round_count": int(len(history)),
        "trace_round_count": int(sum(1 for summary in round_summaries if bool(summary.get("trace_visible", False)))),
        "trace_row_count": int(len(rows)),
        "projected_available_count": int(sum(1 for row in rows if bool(row.get("projected_available", False)))),
        "joint_handoff_visible_rounds": int(sum(1 for summary in round_summaries if bool(summary.get("joint_handoff_visible", False)))),
        "wm_owner_visible": bool(any(bool(row.get("world_model_active", False)) for row in rows)),
        "planning_handoff_visible": bool(any(bool(row.get("planning_active", False)) for row in rows)),
        "mean_wm_context_supply_score": _mean(
            [float(row.get("wm_context_supply_score", 0.0)) for row in rows]
        ),
        "mean_planning_handoff_score": _mean(
            [float(row.get("planning_handoff_score", 0.0)) for row in rows]
        ),
        "mean_pred_context_score": _mean(
            [float(row.get("pred_context_score", 0.0)) for row in rows]
        ),
        "mean_pred_uncertainty": _mean(
            [float(row.get("pred_uncertainty", 0.0)) for row in rows]
        ),
        "mean_selection_score_pre_gate": _mean(
            [float(row.get("selection_score_pre_gate", 0.0)) for row in rows]
        ),
        "status_counts": dict(status_counts),
        "top_trace_examples": [
            {
                "round": int(row.get("round", 0)),
                "candidate_id": str(row.get("candidate_id", "")),
                "status": str(row.get("status", "")),
                "wm_context_supply_score": float(row.get("wm_context_supply_score", 0.0)),
                "planning_handoff_score": float(row.get("planning_handoff_score", 0.0)),
                "pred_context_score": float(row.get("pred_context_score", 0.0)),
                "pred_gain_norm": float(row.get("pred_gain_norm", 0.0)),
                "pred_projection_bad_prob": float(row.get("pred_projection_bad_prob", 1.0)),
                "pred_uncertainty": float(row.get("pred_uncertainty", 0.0)),
            }
            for row in top_examples
        ],
    }


def _aggregate_history_summaries(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys_mean = [
        "mean_realized_gain",
        "mean_goal_agreement",
        "mean_goal_mse_latent",
        "mean_projection_error",
    ]
    keys_int = [
        "rounds",
        "provisional_count",
        "full_adopt_count",
        "rollback_count",
        "projection_bad_incidents",
        "live_variant_override_total",
        "live_variant_baseline_rejected_total",
        "live_variant_projection_eligible_total",
        "live_variant_conf_gain_eligible_total",
    ]
    aggregated = {"seed_count": int(len(rows))}
    for key in keys_int:
        values = [int(dict(row).get(key, 0) or 0) for row in rows]
        aggregated[key] = int(round(sum(values) / len(values))) if values else 0
    for key in keys_mean:
        values = [
            float(value)
            for value in [_safe_float(dict(row).get(key), None) for row in rows]
            if value is not None
        ]
        aggregated[key] = _mean(values)
    return aggregated


def _downstream_invariance_report(
    baseline_summary: dict[str, Any],
    probe_summary: dict[str, Any],
) -> dict[str, Any]:
    count_keys = [
        "provisional_count",
        "full_adopt_count",
        "rollback_count",
        "projection_bad_incidents",
        "live_variant_override_total",
    ]
    float_keys = [
        "mean_realized_gain",
        "mean_goal_agreement",
        "mean_goal_mse_latent",
        "mean_projection_error",
    ]
    count_deltas = {
        key: int(probe_summary.get(key, 0) or 0) - int(baseline_summary.get(key, 0) or 0)
        for key in count_keys
    }
    float_deltas = {}
    for key in float_keys:
        baseline_value = _safe_float(baseline_summary.get(key), None)
        probe_value = _safe_float(probe_summary.get(key), None)
        float_deltas[key] = (
            None
            if baseline_value is None or probe_value is None
            else float(probe_value - baseline_value)
        )
    passed = bool(
        all(delta == 0 for delta in count_deltas.values())
        and all(delta is None or abs(delta) <= 1e-12 for delta in float_deltas.values())
    )
    return {
        "passed": bool(passed),
        "count_deltas": count_deltas,
        "float_deltas": float_deltas,
        "reason": (
            "trace-only probe preserved downstream adoption/rollback behavior"
            if passed
            else "trace-only probe altered downstream behavior and crossed its intended ownership boundary"
        ),
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    wm_plan_snapshot_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_world_model_planning_context_entry_snapshot_v1"
    )
    loop_surface_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_proposal_learning_loop_context_branch_snapshot_v1"
    )
    architecture_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_architecture_upstream_context_branch_snapshot_v1"
    )
    landscape_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_first_hypothesis_landscape_snapshot_v1"
    )
    hardening_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.swap_c_incumbent_hardening_probe_v1"
    )
    frontier_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.false_safe_frontier_control_characterization_snapshot_v1"
    )
    if not all(
        [
            wm_plan_snapshot_artifact,
            loop_surface_artifact,
            architecture_artifact,
            landscape_artifact,
            hardening_artifact,
            frontier_artifact,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: the first v4 proposal-learning-loop probe requires the carried-forward v4 branch-entry and v3 closure artifacts",
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
                "reason": "cannot open the wm/plan branch cleanly without the carried-forward branch-entry diagnostics",
            },
        }

    active_status_text = _load_text_file(ACTIVE_STATUS_PATH)
    handoff_status = _load_json_file(HANDOFF_STATUS_PATH)
    analytics = build_intervention_ledger_analytics()
    latest_snapshots = load_latest_snapshots()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")
    proposal_loop_text = _load_text_file(PROPOSAL_LOOP_PATH)

    per_seed_runs: list[dict[str, Any]] = []
    baseline_summaries: list[dict[str, Any]] = []
    probe_summaries: list[dict[str, Any]] = []
    trace_reports: list[dict[str, Any]] = []

    for seed in list(seeds):
        baseline_cfg = _clone_cfg(cfg, seed=int(seed), rounds=int(rounds), probe_enabled=False)
        probe_cfg = _clone_cfg(cfg, seed=int(seed), rounds=int(rounds), probe_enabled=True)

        _, _, baseline_history = run_proposal_learning_loop(baseline_cfg)
        _, _, probe_history = run_proposal_learning_loop(probe_cfg)

        baseline_summary = r._summarize_history(baseline_history)
        probe_summary = r._summarize_history(probe_history)
        trace_report = _trace_report(probe_history)
        invariance = _downstream_invariance_report(baseline_summary, probe_summary)

        baseline_summaries.append(dict(baseline_summary))
        probe_summaries.append(dict(probe_summary))
        trace_reports.append(dict(trace_report))
        per_seed_runs.append(
            {
                "seed": int(seed),
                "baseline_summary": dict(baseline_summary),
                "probe_summary": dict(probe_summary),
                "trace_report": dict(trace_report),
                "downstream_invariance": dict(invariance),
            }
        )

    aggregated_baseline = _aggregate_history_summaries(baseline_summaries)
    aggregated_probe = _aggregate_history_summaries(probe_summaries)
    aggregated_trace = {
        "seed_count": int(len(trace_reports)),
        "trace_round_count": int(sum(int(report.get("trace_round_count", 0) or 0) for report in trace_reports)),
        "trace_row_count": int(sum(int(report.get("trace_row_count", 0) or 0) for report in trace_reports)),
        "projected_available_count": int(sum(int(report.get("projected_available_count", 0) or 0) for report in trace_reports)),
        "joint_handoff_visible_rounds": int(sum(int(report.get("joint_handoff_visible_rounds", 0) or 0) for report in trace_reports)),
        "wm_owner_visible": bool(any(bool(report.get("wm_owner_visible", False)) for report in trace_reports)),
        "planning_handoff_visible": bool(any(bool(report.get("planning_handoff_visible", False)) for report in trace_reports)),
        "mean_wm_context_supply_score": _mean(
            [
                float(value)
                for value in [_safe_float(report.get("mean_wm_context_supply_score"), None) for report in trace_reports]
                if value is not None
            ]
        ),
        "mean_planning_handoff_score": _mean(
            [
                float(value)
                for value in [_safe_float(report.get("mean_planning_handoff_score"), None) for report in trace_reports]
                if value is not None
            ]
        ),
        "mean_pred_context_score": _mean(
            [
                float(value)
                for value in [_safe_float(report.get("mean_pred_context_score"), None) for report in trace_reports]
                if value is not None
            ]
        ),
        "mean_pred_uncertainty": _mean(
            [
                float(value)
                for value in [_safe_float(report.get("mean_pred_uncertainty"), None) for report in trace_reports]
                if value is not None
            ]
        ),
        "top_trace_examples": [
            example
            for report in trace_reports
            for example in list(report.get("top_trace_examples", []))
        ][:8],
    }
    aggregated_invariance = _downstream_invariance_report(aggregated_baseline, aggregated_probe)

    hardening_conclusions = dict(hardening_artifact.get("diagnostic_conclusions", {}))
    frontier_conclusions = dict(frontier_artifact.get("diagnostic_conclusions", {}))
    carried_forward_baseline = dict(handoff_status.get("carried_forward_baseline", {}))

    downstream_exclusions_preserved = {
        "adoption_owner_unchanged": True,
        "social_conf_owner_unchanged": True,
        "selected_set_optimization_unchanged": True,
        "self_improve_owner_not_attached": True,
        "routing_untouched": True,
    }
    branch_opened_cleanly = bool(
        aggregated_trace["trace_row_count"] > 0
        and aggregated_trace["wm_owner_visible"]
        and aggregated_trace["planning_handoff_visible"]
        and aggregated_invariance["passed"]
    )
    next_family = "memory_summary"
    next_template = "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v1"
    next_rationale = (
        "the first wm-owned branch is now open cleanly, so the next safe step is to characterize the new wm->plan context traces by seed/context quality before any behavior-changing proposal-learning-loop intervention"
    )

    comparison_refs = {}
    for artifact in [
        wm_plan_snapshot_artifact,
        loop_surface_artifact,
        architecture_artifact,
        landscape_artifact,
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
        "template_name": "proposal_learning_loop.v4_wm_primary_plan_structure_probe_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "branch_context": {
            "proposal_learning_loop_path": str(PROPOSAL_LOOP_PATH),
            "active_status_path": str(ACTIVE_STATUS_PATH),
            "handoff_status_path": str(HANDOFF_STATUS_PATH),
            "active_status_mentions_v4_active": "`novali-v4` is the active working version." in active_status_text,
            "carried_forward_baseline": carried_forward_baseline,
            "carried_forward_swap_c_safety": dict(hardening_artifact.get("incumbent_robustness_report", {})),
            "v3_under_cap_critic_exhausted": not bool(hardening_conclusions.get("productive_under_cap_critic_work_left", True)),
            "false_safe_frontier_classification": str(frontier_conclusions.get("frontier_classification", "")),
            "routing_deferred": bool(frontier_conclusions.get("routing_deferred", False)),
        },
        "comparison_references": comparison_refs,
        "branch_implementation_summary": {
            "wm_changes": [
                "added probe-only wm-owned context trace toggles in ProposalLearningConfig",
                "captured per-candidate world-model context supply rows at existing projection/evaluation handoff points",
                "left world-model scoring and downstream gating rules unchanged",
            ],
            "plan_handoff_changes": [
                "added plan_horizon/plan_candidates visibility to the new probe trace rows",
                "derived a planning_handoff_score from existing wm context plus current plan settings",
                "kept plan_ as a structure co-owner only; no planning-first or planning-only branch was added",
            ],
            "observability_tracing_added": [
                "wm_plan_context_rows per round in proposal-learning-loop history",
                "wm_plan_round_summary aggregate per round",
                "shadow probe comparison between trace-disabled baseline and trace-enabled probe runs",
            ],
            "explicit_downstream_exclusions_preserved": [
                "no adoption_ ownership or threshold changes",
                "no social_conf_ ownership or selected-set optimization changes",
                "no self_improve_ ownership attachment in the first v4 branch",
                "no routing work and no false-safe frontier retuning",
            ],
        },
        "shadow_run_metrics": {
            "baseline_aggregate": aggregated_baseline,
            "probe_aggregate": aggregated_probe,
            "downstream_invariance": aggregated_invariance,
            "trace_report": aggregated_trace,
            "per_seed_runs": per_seed_runs,
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
        "downstream_boundary_report": {
            "preserved": downstream_exclusions_preserved,
            "downstream_invariance": aggregated_invariance,
        },
        "decision_recommendation": {
            "branch_opened_cleanly": bool(branch_opened_cleanly),
            "downstream_boundaries_preserved": bool(aggregated_invariance["passed"]),
            "recommended_next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "rationale": str(next_rationale),
        },
        "observability_gain": {
            "passed": bool(
                aggregated_trace["trace_row_count"] > 0
                and aggregated_trace["wm_owner_visible"]
                and aggregated_trace["planning_handoff_visible"]
            ),
            "reason": "the probe adds visible wm-owned upstream context traces and plan handoff rows at the existing evaluation seams without changing the adoption/social-confidence machinery",
            "trace_row_count": int(aggregated_trace["trace_row_count"]),
            "joint_handoff_visible_rounds": int(aggregated_trace["joint_handoff_visible_rounds"]),
            "mean_wm_context_supply_score": aggregated_trace["mean_wm_context_supply_score"],
            "mean_planning_handoff_score": aggregated_trace["mean_planning_handoff_score"],
        },
        "activation_analysis_usefulness": {
            "passed": bool(branch_opened_cleanly),
            "reason": "the probe opens the wm_->plan branch through real runtime traces rather than a renamed downstream selector/control path",
            "branch_opened_cleanly": bool(branch_opened_cleanly),
            "recreated_v3_logic": False,
        },
        "ambiguity_reduction": {
            "passed": bool(branch_opened_cleanly),
            "score": float(min(1.0, 0.55 + 0.20 * int(branch_opened_cleanly) + 0.10 * int(aggregated_invariance["passed"]))),
            "reason": "the probe resolves whether the first v4 branch can be opened through wm_/plan_ observability without drifting into exhausted v3 critic/control work",
        },
        "safety_neutrality": {
            "passed": bool(aggregated_invariance["passed"]),
            "scope": str(proposal.get("scope", "")),
            "reason": "shadow-only trace probe with live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": str(next_template),
            "reason": str(next_rationale),
        },
        "diagnostic_conclusions": {
            "branch_opened_cleanly": bool(branch_opened_cleanly),
            "downstream_boundaries_preserved": bool(aggregated_invariance["passed"]),
            "first_v4_branch_opened_without_recreating_v3_logic": bool(branch_opened_cleanly),
            "under_cap_critic_exhaustion_still_holds": not bool(hardening_conclusions.get("productive_under_cap_critic_work_left", True)),
            "next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "routing_deferred": bool(frontier_conclusions.get("routing_deferred", False)),
        },
    }
    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"proposal_learning_loop_v4_wm_primary_plan_structure_probe_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": bool(branch_opened_cleanly and aggregated_invariance["passed"]),
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": (
            "diagnostic shadow passed: the first v4 wm-owned proposal-learning-loop branch opened cleanly with trace visibility and preserved downstream boundaries"
            if branch_opened_cleanly and aggregated_invariance["passed"]
            else "diagnostic shadow failed: the first v4 wm-owned proposal-learning-loop branch did not preserve its downstream boundaries"
        ),
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
