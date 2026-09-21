from __future__ import annotations

import json
from typing import Any

from .analytics import build_intervention_ledger_analytics
from .ledger import intervention_data_dir, load_latest_snapshots
from .v4_first_hypothesis_landscape_snapshot_v1 import (
    ACTIVE_STATUS_PATH,
    BENCHMARK_PACK_ROOT,
    HANDOFF_STATUS_PATH,
    PROPOSAL_LOOP_PATH,
    _benchmark_pack_summary,
    _count_config_prefixes,
    _load_json_file,
    _load_text_file,
    _projected_score,
)


def _surface_signal_report(source_text: str, surface_counts: dict[str, Any]) -> dict[str, Any]:
    prefix_counts = dict(surface_counts.get("prefix_counts", {}))
    toggles = dict(surface_counts.get("toggles", {}))
    return {
        "wm_": {
            "prefix_count": int(prefix_counts.get("wm_", 0) or 0),
            "toggle_enabled": bool(toggles.get("use_world_model")),
            "marker_counts": {
                "shadow_rollout": int(source_text.count("_world_model_shadow_rollout(")),
                "candidate_projection": int(source_text.count("wm_candidate_projection_enabled")),
                "world_model_eval_call": int(source_text.count("world_model=world_model")),
            },
        },
        "plan_": {
            "prefix_count": int(prefix_counts.get("plan_", 0) or 0),
            "toggle_enabled": bool(toggles.get("use_planning")),
            "marker_counts": {
                "planning_eval_call": int(source_text.count("use_planning=cfg.use_planning")),
                "plan_horizon_pass": int(source_text.count("plan_horizon=cfg.plan_horizon")),
                "plan_candidates_pass": int(source_text.count("plan_candidates=cfg.plan_candidates")),
            },
        },
        "self_improve_": {
            "prefix_count": int(prefix_counts.get("self_improve_", 0) or 0),
            "toggle_enabled": bool(toggles.get("enable_self_improvement")),
            "marker_counts": {
                "personal_dummy_probe": int(source_text.count("triad_propose_test_personal_dummies(")),
                "outcome_recording": int(source_text.count("record_self_improvement_outcome(")),
                "self_improve_adopt_threshold": int(source_text.count("self_improve_adopt_threshold")),
            },
        },
        "adoption_": {
            "prefix_count": int(prefix_counts.get("adoption_", 0) or 0),
            "toggle_enabled": True,
            "marker_counts": {
                "selected_set_adoption": int(source_text.count("adopted_meta")),
                "adoption_thresholds": int(source_text.count("adoption_score_threshold")),
                "adaptive_patch_scale": int(source_text.count("adaptive_patch_scale")),
            },
        },
        "social_conf_": {
            "prefix_count": int(prefix_counts.get("social_conf_", 0) or 0),
            "toggle_enabled": True,
            "marker_counts": {
                "social_confidence_fn": int(source_text.count("_compute_social_confidence(")),
                "provisional_decay": int(source_text.count("social_conf_provisional_decay")),
                "selection_score_usage": int(source_text.count("selection_score")),
            },
        },
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    del cfg, rounds, seeds
    from . import runner as r

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
    invariance_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.safe_trio_false_safe_invariance_snapshot_v1"
    )
    coverage_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.swap_c_family_coverage_snapshot_v1"
    )
    routing_artifact = r._load_latest_diagnostic_artifact_by_template(
        "routing_rule.slice_targeted_benchmark_sweep_v1"
    )
    if not all(
        [
            architecture_artifact,
            landscape_artifact,
            hardening_artifact,
            frontier_artifact,
            invariance_artifact,
            coverage_artifact,
            routing_artifact,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: v4 proposal-learning-loop context snapshot requires the architecture-opening, frontier, hardening, coverage, and routing reference artifacts",
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
                "reason": "cannot rank the proposal-learning-loop entry surfaces without the carried-forward diagnostic set",
            },
        }

    active_status_text = _load_text_file(ACTIVE_STATUS_PATH)
    handoff_status = _load_json_file(HANDOFF_STATUS_PATH)
    analytics = build_intervention_ledger_analytics()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")
    latest_snapshots = load_latest_snapshots()
    proposal_loop_text = _load_text_file(PROPOSAL_LOOP_PATH)
    surface_counts = _count_config_prefixes(proposal_loop_text)
    surface_signals = _surface_signal_report(proposal_loop_text, surface_counts)
    benchmark_pack = _benchmark_pack_summary(BENCHMARK_PACK_ROOT)

    architecture_conclusions = dict(architecture_artifact.get("diagnostic_conclusions", {}))
    landscape_conclusions = dict(landscape_artifact.get("diagnostic_conclusions", {}))
    hardening_conclusions = dict(hardening_artifact.get("diagnostic_conclusions", {}))
    frontier_conclusions = dict(frontier_artifact.get("diagnostic_conclusions", {}))
    invariance_conclusions = dict(invariance_artifact.get("diagnostic_conclusions", {}))
    coverage_conclusions = dict(coverage_artifact.get("diagnostic_conclusions", {}))
    routing_conclusions = dict(routing_artifact.get("diagnostic_conclusions", {}))
    carried_forward_baseline = dict(handoff_status.get("carried_forward_baseline", {}))

    under_cap_critic_exhausted = not bool(hardening_conclusions.get("productive_under_cap_critic_work_left", True))
    hard_discrete_frontier = (
        str(frontier_conclusions.get("frontier_classification", "")) == "hard_discrete_accounting_boundary"
    )
    no_control_headroom = not bool(frontier_conclusions.get("benchmark_only_control_headroom_exists", True))
    routing_deferred = bool(frontier_conclusions.get("routing_deferred", False))

    candidate_rows = [
        {
            "rank": 1,
            "surface": "wm_ + plan_ combined entry",
            "state": "open",
            "reason": "best first entry because world-model supplies upstream context/forecast structure and planning is already passed alongside it in evaluation calls, so this pair can open a real context-formation branch instead of re-entering downstream selected-set tuning",
            "dependence_on_carried_forward_v3_evidence": [
                "under-cap critic_split work is exhausted",
                "false-safe frontier is hard discrete",
                "benchmark-only control headroom is not evidenced",
                "routing remains deferred",
            ],
            "projected_value": {"label": "high", "score": 0.97},
            "projected_risk": {"label": "medium", "score": 0.42},
            "reversibility": {"label": "high", "score": 0.82},
            "projected_priority": _projected_score("open", 0.97, 0.42, 0.82),
            "surface_evidence": {
                "wm_prefix_count": int(dict(surface_signals.get("wm_", {})).get("prefix_count", 0)),
                "plan_prefix_count": int(dict(surface_signals.get("plan_", {})).get("prefix_count", 0)),
                "joint_eval_calls": int(proposal_loop_text.count("world_model=world_model") and proposal_loop_text.count("use_planning=cfg.use_planning")),
            },
        },
        {
            "rank": 2,
            "surface": "wm_",
            "state": "open",
            "reason": "clean upstream context-formation surface with the richest config footprint, explicit shadow rollout logic, candidate projection, uncertainty/context weighting, and active runtime use",
            "dependence_on_carried_forward_v3_evidence": [
                "v3 closed downstream final-selection and control lines, so an upstream forecasting surface is still open",
                "persistence remained healthy upstream under swap_C, which supports moving the next branch above final selection",
            ],
            "projected_value": {"label": "high", "score": 0.92},
            "projected_risk": {"label": "medium", "score": 0.46},
            "reversibility": {"label": "high", "score": 0.79},
            "projected_priority": _projected_score("open", 0.92, 0.46, 0.79),
            "surface_evidence": dict(surface_signals.get("wm_", {})),
        },
        {
            "rank": 3,
            "surface": "plan_",
            "state": "open_secondary",
            "reason": "open as structure support, but weaker than wm_ because planning appears as a thin steering surface and would risk becoming search-only reshaping unless paired with new world-model context supply",
            "dependence_on_carried_forward_v3_evidence": [
                "v3 failures were not caused by lack of downstream ranking pressure",
                "a planning-only branch could drift back toward local optimization without changing the exhausted frontier diagnosis",
            ],
            "projected_value": {"label": "medium", "score": 0.74},
            "projected_risk": {"label": "medium", "score": 0.43},
            "reversibility": {"label": "high", "score": 0.86},
            "projected_priority": _projected_score("open_secondary", 0.74, 0.43, 0.86),
            "surface_evidence": dict(surface_signals.get("plan_", {})),
        },
        {
            "rank": 4,
            "surface": "self_improve_",
            "state": "open_secondary",
            "reason": "open only as a later support surface because it adapts agents internally, but a naive first move would mostly re-enter patch/adoption dynamics that v3 already exhausted under the current cap",
            "dependence_on_carried_forward_v3_evidence": [
                "swap_C hardening found no productive under-cap critic work left",
                "frontier characterization ruled out more downstream selected-set improvement under the current cap",
            ],
            "projected_value": {"label": "medium", "score": 0.58},
            "projected_risk": {"label": "medium_high", "score": 0.61},
            "reversibility": {"label": "medium", "score": 0.74},
            "projected_priority": _projected_score("open_secondary", 0.58, 0.61, 0.74),
            "surface_evidence": dict(surface_signals.get("self_improve_", {})),
        },
        {
            "rank": 5,
            "surface": "adoption_",
            "state": "closed",
            "reason": "closed as a first branch entry because it is downstream selected-set acceptance and patch-scaling logic; used naively, it would just recreate the exhausted v3 final-selection frontier under a new name",
            "dependence_on_carried_forward_v3_evidence": [
                "swap_C is already the best safe trio under the flat frontier",
                "no productive under-cap hardening remains",
                "persistence exclusion is downstream under the fixed cap rather than upstream scarcity",
            ],
            "projected_value": {"label": "low", "score": 0.22},
            "projected_risk": {"label": "high", "score": 0.69},
            "reversibility": {"label": "high", "score": 0.83},
            "projected_priority": _projected_score("closed", 0.22, 0.69, 0.83),
            "surface_evidence": dict(surface_signals.get("adoption_", {})),
        },
        {
            "rank": 6,
            "surface": "social_conf_",
            "state": "closed",
            "reason": "closed as a first branch entry because it is coordination/provisional gating and selection-score logic; used naively, it would re-open the same downstream composition and tie-break problems already flattened by the v3 frontier diagnosis",
            "dependence_on_carried_forward_v3_evidence": [
                "safe-trio invariance showed composition changes utility but not false-safe occupancy",
                "swap_C family coverage showed persistence is excluded only at final selection",
            ],
            "projected_value": {"label": "low", "score": 0.20},
            "projected_risk": {"label": "high", "score": 0.67},
            "reversibility": {"label": "high", "score": 0.82},
            "projected_priority": _projected_score("closed", 0.20, 0.67, 0.82),
            "surface_evidence": dict(surface_signals.get("social_conf_", {})),
        },
    ]

    best_first_entry = "wm_ + plan_ combined entry, with wm_ as the primary owner and plan_ as the structure co-owner"
    recommended_next_family = "memory_summary"
    recommended_next_template = "memory_summary.v4_world_model_planning_context_entry_snapshot_v1"
    recommended_next_rationale = (
        "the cleanest first v4 branch entry is the combined world-model/planning surface, because it is the only clearly upstream context-forming path that is already wired into evaluation without collapsing back into exhausted downstream selection/control logic"
    )

    latest_snapshot_refs = {}
    for artifact in [
        architecture_artifact,
        landscape_artifact,
        hardening_artifact,
        frontier_artifact,
        invariance_artifact,
        coverage_artifact,
        routing_artifact,
    ]:
        proposal_id = str(artifact.get("proposal_id", ""))
        latest_snapshot_refs[str(artifact.get("template_name", ""))] = {
            "proposal_id": proposal_id,
            "ledger_revision": int(dict(latest_snapshots.get(proposal_id, {})).get("ledger_revision", 0) or 0),
        }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_proposal_learning_loop_context_branch_snapshot_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "branch_context": {
            "active_status_path": str(ACTIVE_STATUS_PATH),
            "handoff_status_path": str(HANDOFF_STATUS_PATH),
            "active_status_mentions_v4_active": "`novali-v4` is the active working version." in active_status_text,
            "carried_forward_baseline": carried_forward_baseline,
        },
        "proposal_learning_loop_context_surface_report": {
            "proposal_learning_loop_path": str(PROPOSAL_LOOP_PATH),
            "surface_counts": surface_counts,
            "surface_signal_report": surface_signals,
            "benchmark_pack_summary": benchmark_pack,
        },
        "comparison_references": {
            "memory_summary.v4_architecture_upstream_context_branch_snapshot_v1": {
                "decision_recommendation": dict(architecture_artifact.get("decision_recommendation", {})),
                "diagnostic_conclusions": architecture_conclusions,
            },
            "memory_summary.v4_first_hypothesis_landscape_snapshot_v1": {
                "decision_recommendation": dict(landscape_artifact.get("decision_recommendation", {})),
                "diagnostic_conclusions": landscape_conclusions,
            },
            "critic_split.swap_c_incumbent_hardening_probe_v1": {
                "diagnostic_conclusions": hardening_conclusions,
                "incumbent_robustness_report": dict(hardening_artifact.get("incumbent_robustness_report", {})),
            },
            "memory_summary.false_safe_frontier_control_characterization_snapshot_v1": {
                "diagnostic_conclusions": frontier_conclusions,
            },
            "memory_summary.safe_trio_false_safe_invariance_snapshot_v1": {
                "diagnostic_conclusions": invariance_conclusions,
            },
            "memory_summary.swap_c_family_coverage_snapshot_v1": {
                "diagnostic_conclusions": coverage_conclusions,
                "family_coverage_report": dict(coverage_artifact.get("family_coverage_report", {})),
            },
            "routing_rule.slice_targeted_benchmark_sweep_v1": {
                "diagnostic_conclusions": routing_conclusions,
                "benchmark_control_metrics": dict(routing_artifact.get("benchmark_control_metrics", {})),
            },
        },
        "analytics_context": {
            "analytics_report_path": str(intervention_data_dir() / "intervention_analytics_latest.json"),
            "proposal_recommendations_path": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            "proposal_count": int(analytics.get("proposal_count", 0) or 0),
            "current_recommendation_top_templates": [
                str(item.get("template_name", ""))
                for item in list(recommendations.get("suggested_proposals", []))
            ][:8],
        },
        "ranked_proposal_learning_loop_surface_map": candidate_rows,
        "surface_separation_report": {
            "world_model_context_formation": "upstream forecasting, candidate projection, uncertainty/context weighting, and shadow rollout support",
            "planning_structure": "trajectory/action-search shaping passed alongside evaluation rather than downstream acceptance logic",
            "self_improvement_structure": "within-agent patch generation and self-adaptation layer",
            "adoption_logic": "downstream selected-set acceptance, scaling, cooldown, and rollback-sensitive patch application",
            "social_confidence_coordination_logic": "downstream coordination, provisional evidence decay, and selection-score gating",
        },
        "decision_recommendation": {
            "best_first_entry_point": str(best_first_entry),
            "recommended_next_family": str(recommended_next_family),
            "recommended_next_template": str(recommended_next_template),
            "rationale": str(recommended_next_rationale),
        },
        "branch_snapshot_refs": latest_snapshot_refs,
        "observability_gain": {
            "passed": True,
            "reason": "the snapshot combines proposal-learning-loop surface signals with carried-forward v3 closure evidence to rank the first real v4 entry surfaces",
            "surface_count": int(len(candidate_rows)),
            "joint_wm_plan_entry_open": True,
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the snapshot distinguishes truly upstream architecture surfaces from downstream governance surfaces that would recreate exhausted v3 logic",
            "under_cap_critic_exhausted": bool(under_cap_critic_exhausted),
            "hard_discrete_frontier": bool(hard_discrete_frontier),
            "benchmark_control_headroom_exists": bool(not no_control_headroom),
            "routing_deferred": bool(routing_deferred),
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": float(
                min(
                    1.0,
                    0.46
                    + 0.16 * int(under_cap_critic_exhausted)
                    + 0.14 * int(hard_discrete_frontier)
                    + 0.10 * int(no_control_headroom)
                    + 0.08 * int(bool(dict(surface_signals.get("wm_", {})).get("toggle_enabled", False)))
                    + 0.06 * int(bool(dict(surface_signals.get("plan_", {})).get("toggle_enabled", False)))
                )
            ),
            "reason": "the snapshot cleanly ranks the proposal-learning-loop surfaces and identifies which ones would just recreate exhausted v3 logic if used naively",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "diagnostic-only proposal-learning-loop surface snapshot with live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": str(recommended_next_template),
            "reason": str(recommended_next_rationale),
        },
        "diagnostic_conclusions": {
            "best_first_entry_point": str(best_first_entry),
            "world_model_surface_open": bool(dict(surface_signals.get("wm_", {})).get("toggle_enabled", False)),
            "planning_surface_open": bool(dict(surface_signals.get("plan_", {})).get("toggle_enabled", False)),
            "self_improvement_surface_open_as_secondary": True,
            "adoption_surface_open_as_first_move": False,
            "social_conf_surface_open_as_first_move": False,
            "recommended_next_family": str(recommended_next_family),
            "recommended_next_template": str(recommended_next_template),
            "routing_deferred": bool(routing_deferred),
        },
    }
    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"memory_summary_v4_proposal_learning_loop_context_branch_snapshot_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: the proposal-learning-loop architecture surfaces were ranked and the first real v4 branch entry point was localized",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
