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


def _architecture_plane_report(surface: dict[str, Any]) -> dict[str, Any]:
    prefix_counts = dict(surface.get("prefix_counts", {}))
    toggles = dict(surface.get("toggles", {}))
    adoption_count = int(prefix_counts.get("adoption_", 0) or 0)
    social_conf_count = int(prefix_counts.get("social_conf_", 0) or 0)
    planes = {
        "world_model_context_supply": {
            "open": bool(int(prefix_counts.get("wm_", 0) or 0) > 0 and toggles.get("use_world_model")),
            "surface_count": int(prefix_counts.get("wm_", 0) or 0),
            "why": "proposal_learning_loop exposes world-model controls and keeps world-model execution enabled",
        },
        "planning_context_shaping": {
            "open": bool(int(prefix_counts.get("plan_", 0) or 0) > 0 and toggles.get("use_planning")),
            "surface_count": int(prefix_counts.get("plan_", 0) or 0),
            "why": "planning controls remain available and active in the proposal-learning loop",
        },
        "self_improvement_context_adaptation": {
            "open": bool(int(prefix_counts.get("self_improve_", 0) or 0) > 0 and toggles.get("enable_self_improvement")),
            "surface_count": int(prefix_counts.get("self_improve_", 0) or 0),
            "why": "self-improvement controls remain available and active in the proposal-learning loop",
        },
        "adoption_social_governance": {
            "open": bool(adoption_count > 0 and social_conf_count > 0),
            "surface_count": int(adoption_count + social_conf_count),
            "why": "adoption and social-confidence surfaces are both present, so branch governance can be architecture-owned rather than critic-owned",
        },
    }
    return {
        "planes": planes,
        "all_core_planes_open": bool(all(bool(dict(info).get("open", False)) for info in planes.values())),
        "open_plane_count": int(sum(1 for info in planes.values() if bool(dict(info).get("open", False)))),
        "total_surface_count": int(sum(int(dict(info).get("surface_count", 0) or 0) for info in planes.values())),
    }


def _top_recommendation_templates(recommendations: dict[str, Any], *, decision: str, limit: int = 8) -> list[str]:
    rows = []
    for item in list(recommendations.get("all_ranked_proposals", [])):
        if not isinstance(item, dict):
            continue
        if str(item.get("decision", "")) != str(decision):
            continue
        rows.append(str(item.get("template_name", "")))
    return rows[: int(limit)]


def run_probe(cfg, proposal, *, rounds, seeds):
    del cfg, rounds, seeds
    from . import runner as r

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
    seed_context_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.seed_context_shift_snapshot"
    )
    benchmark_context_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.benchmark_context_availability_snapshot"
    )
    routing_artifact = r._load_latest_diagnostic_artifact_by_template(
        "routing_rule.slice_targeted_benchmark_sweep_v1"
    )
    if not all(
        [
            landscape_artifact,
            hardening_artifact,
            frontier_artifact,
            invariance_artifact,
            coverage_artifact,
            seed_context_artifact,
            benchmark_context_artifact,
            routing_artifact,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: v4 architecture snapshot requires the prior v4 landscape plus carried-forward frontier, hardening, coverage, context, and routing reference artifacts",
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
                "reason": "cannot rank the first architecture-level v4 branch without the carried-forward diagnostic set",
            },
        }

    active_status_text = _load_text_file(ACTIVE_STATUS_PATH)
    handoff_status = _load_json_file(HANDOFF_STATUS_PATH)
    analytics = build_intervention_ledger_analytics()
    analytics_report = _load_json_file(intervention_data_dir() / "intervention_analytics_latest.json")
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")
    latest_snapshots = load_latest_snapshots()
    proposal_loop_text = _load_text_file(PROPOSAL_LOOP_PATH)
    architecture_surface = _count_config_prefixes(proposal_loop_text)
    architecture_planes = _architecture_plane_report(architecture_surface)
    benchmark_pack = _benchmark_pack_summary(BENCHMARK_PACK_ROOT)

    landscape_conclusions = dict(landscape_artifact.get("diagnostic_conclusions", {}))
    hardening_conclusions = dict(hardening_artifact.get("diagnostic_conclusions", {}))
    frontier_conclusions = dict(frontier_artifact.get("diagnostic_conclusions", {}))
    invariance_conclusions = dict(invariance_artifact.get("diagnostic_conclusions", {}))
    coverage_conclusions = dict(coverage_artifact.get("diagnostic_conclusions", {}))
    seed_context_conclusions = dict(seed_context_artifact.get("diagnostic_conclusions", {}))
    benchmark_context_conclusions = dict(benchmark_context_artifact.get("diagnostic_conclusions", {}))
    routing_conclusions = dict(routing_artifact.get("diagnostic_conclusions", {}))

    persistence_family = dict(dict(coverage_artifact.get("family_coverage_report", {})).get("persistence", {}))
    carried_forward_baseline = dict(handoff_status.get("carried_forward_baseline", {}))

    under_cap_critic_exhausted = not bool(hardening_conclusions.get("productive_under_cap_critic_work_left", True))
    hard_discrete_frontier = (
        str(frontier_conclusions.get("frontier_classification", "")) == "hard_discrete_accounting_boundary"
    )
    no_control_headroom = not bool(frontier_conclusions.get("benchmark_only_control_headroom_exists", True))
    routing_deferred = bool(frontier_conclusions.get("routing_deferred", False))
    upstream_context_signal_open = bool(
        str(seed_context_conclusions.get("collapse_driver", "")) == "low_candidate_count"
        and str(benchmark_context_conclusions.get("availability_driver", "")) == "scarcity"
    )
    persistence_upstream_healthy = bool(int(persistence_family.get("safe_pool_benchmark_like_count", 0) or 0) > 0)
    persistence_excluded_only_at_selection = (
        str(persistence_family.get("absence_stage", "")) == "absent_only_at_selection"
    )
    architecture_surface_open = bool(architecture_planes.get("all_core_planes_open", False))
    legacy_recommender_bias = bool(
        _top_recommendation_templates(recommendations, decision="suggested", limit=5)
        and not any(
            name.startswith("memory_summary.v4_")
            for name in _top_recommendation_templates(recommendations, decision="suggested", limit=5)
        )
    )

    candidate_rows = [
        {
            "rank": 1,
            "candidate_branch": "proposal-learning-loop architecture/context leverage path",
            "state": "open" if architecture_surface_open and under_cap_critic_exhausted and hard_discrete_frontier and no_control_headroom else "closed",
            "reason": (
                "open because proposal_learning_loop exposes active world-model, planning, self-improvement, adoption, and social-confidence surfaces, so upstream context formation can be opened as a new architecture-owned branch rather than as renamed critic/control tuning"
                if architecture_surface_open and under_cap_critic_exhausted and hard_discrete_frontier and no_control_headroom
                else "closed because the repo does not expose enough active proposal-learning-loop architecture surface to justify an architecture-owned v4 branch"
            ),
            "dependency_on_carried_forward_v3_evidence": [
                "swap_C is the stable carried-forward baseline",
                "under-cap critic_split work is exhausted",
                "the false-safe frontier is a hard discrete accounting boundary",
                "benchmark-only control headroom is not evidenced",
            ],
            "projected_value": {"label": "high", "score": 0.96},
            "projected_risk": {"label": "medium", "score": 0.44},
            "reversibility": {"label": "high", "score": 0.84},
            "projected_priority": _projected_score(
                "open" if architecture_surface_open and under_cap_critic_exhausted and hard_discrete_frontier and no_control_headroom else "closed",
                0.96,
                0.44,
                0.84,
            ),
            "ownership_note": "This is the strongest repo-supported alternative to the generic branch-structure path, but it still needs to be owned first by memory_summary because no dedicated architecture proposal family exists yet.",
        },
        {
            "rank": 2,
            "candidate_branch": "architecture / branch-structure path",
            "state": "open" if under_cap_critic_exhausted and hard_discrete_frontier and no_control_headroom else "closed",
            "reason": (
                "open because novali-v4 needs a clean architecture-owned branch boundary above the exhausted v3 critic/control line"
                if under_cap_critic_exhausted and hard_discrete_frontier and no_control_headroom
                else "closed because the carried-forward v3 evidence does not force a new branch boundary yet"
            ),
            "dependency_on_carried_forward_v3_evidence": [
                "novali-v3 is paused",
                "continued under-cap critic_split is closed",
                "benchmark/control retest remains closed",
            ],
            "projected_value": {"label": "high", "score": 0.89},
            "projected_risk": {"label": "medium", "score": 0.41},
            "reversibility": {"label": "high", "score": 0.91},
            "projected_priority": _projected_score(
                "open" if under_cap_critic_exhausted and hard_discrete_frontier and no_control_headroom else "closed",
                0.89,
                0.41,
                0.91,
            ),
            "ownership_note": "This is the structural framing branch, but by itself it is still less specific than the proposal-learning-loop architecture/context path.",
        },
        {
            "rank": 3,
            "candidate_branch": "diagnostic / memory / governance support path",
            "state": "open",
            "reason": "open because memory_summary is still the safest currently ownable family in the repo and the recommender remains legacy-v3 dominated rather than branch-aware",
            "dependency_on_carried_forward_v3_evidence": [
                "branch pause and carry-forward baseline are already formalized",
                "the current recommendations do not yet express the v4 architecture opening cleanly",
            ],
            "projected_value": {"label": "medium", "score": 0.73},
            "projected_risk": {"label": "low", "score": 0.16},
            "reversibility": {"label": "high", "score": 0.98},
            "projected_priority": _projected_score("open", 0.73, 0.16, 0.98),
            "ownership_note": "Best owner family for the next move, but not the substantive architecture hypothesis itself.",
        },
        {
            "rank": 4,
            "candidate_branch": "upstream context-formation path",
            "state": "open_secondary" if upstream_context_signal_open else "closed",
            "reason": (
                "open only as a secondary branch because scarcity/context evidence remains real, but a pure context-formation retry would collapse back into renamed v3 work unless it is explicitly opened through a new architecture surface"
                if upstream_context_signal_open
                else "closed because current evidence no longer supports upstream context scarcity as a live branch"
            ),
            "dependency_on_carried_forward_v3_evidence": [
                "seed-context diagnostics tied earlier collapse to low candidate count and scarcity",
                "swap_C family coverage showed persistence healthy upstream and compressed only at final selection",
            ],
            "projected_value": {"label": "medium", "score": 0.72},
            "projected_risk": {"label": "medium_high", "score": 0.58},
            "reversibility": {"label": "medium", "score": 0.71},
            "projected_priority": _projected_score(
                "open_secondary" if upstream_context_signal_open else "closed",
                0.72,
                0.58,
                0.71,
            ),
            "ownership_note": "This remains open only if treated as an architecture-level context-formation branch rather than as a direct continuation of v3 tuning.",
        },
        {
            "rank": 5,
            "candidate_branch": "benchmark/control retest branch",
            "state": "closed",
            "reason": "closed because benchmark-only control characterization found no safe headroom and the prior routing/control retest produced zero benchmark slice and zero safe pool",
            "dependency_on_carried_forward_v3_evidence": [
                "false_safe_frontier_control_characterization_snapshot_v1 found benchmark-only control headroom does not exist",
                "routing_rule.slice_targeted_benchmark_sweep_v1 collapsed to a zero benchmark slice",
            ],
            "projected_value": {"label": "low", "score": 0.14},
            "projected_risk": {"label": "medium", "score": 0.57},
            "reversibility": {"label": "high", "score": 0.9},
            "projected_priority": _projected_score("closed", 0.14, 0.57, 0.9),
            "ownership_note": "This is still just a renamed v3 line and remains closed unless new frontier evidence appears.",
        },
        {
            "rank": 6,
            "candidate_branch": "continued under-cap critic_split branch",
            "state": "closed",
            "reason": "closed because swap_C hardening and frontier characterization jointly showed no productive under-cap critic work remains in novali-v3 or its carried-forward v4 baseline",
            "dependency_on_carried_forward_v3_evidence": [
                "swap_c_incumbent_hardening_probe_v1 found productive_under_cap_critic_work_left = false",
                "safe_trio_false_safe_invariance_snapshot_v1 found no measurable headroom under the cap",
            ],
            "projected_value": {"label": "low", "score": 0.08},
            "projected_risk": {"label": "medium", "score": 0.52},
            "reversibility": {"label": "high", "score": 0.88},
            "projected_priority": _projected_score("closed", 0.08, 0.52, 0.88),
            "ownership_note": "This is the exhausted novali-v3 line and should stay closed in v4.",
        },
    ]

    best_first_hypothesis = (
        "open a proposal-learning-loop architecture/context branch that treats upstream context formation as a world-model/planning/self-improvement/adoption branch-design problem rather than as continued critic/control tuning"
    )
    recommended_next_family = "memory_summary"
    recommended_next_template = "memory_summary.v4_proposal_learning_loop_context_branch_snapshot_v1"
    recommended_next_rationale = (
        "the strongest open v4 branch is the repo-native proposal-learning-loop architecture/context path, and the safest first ownable move is a memory_summary snapshot that maps how world-model, planning, self-improvement, and adoption surfaces should own upstream context formation before any new intervention family is introduced"
    )

    latest_snapshot_refs = {}
    for artifact in [
        landscape_artifact,
        hardening_artifact,
        frontier_artifact,
        invariance_artifact,
        coverage_artifact,
        seed_context_artifact,
        benchmark_context_artifact,
        routing_artifact,
    ]:
        proposal_id = str(artifact.get("proposal_id", ""))
        latest_snapshot_refs[str(artifact.get("template_name", ""))] = {
            "proposal_id": proposal_id,
            "ledger_revision": int(dict(latest_snapshots.get(proposal_id, {})).get("ledger_revision", 0) or 0),
        }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_architecture_upstream_context_branch_snapshot_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "branch_context": {
            "active_status_path": str(ACTIVE_STATUS_PATH),
            "handoff_status_path": str(HANDOFF_STATUS_PATH),
            "active_status_mentions_v4_active": "`novali-v4` is the active working version." in active_status_text,
            "handoff_active_version": str(handoff_status.get("active_working_version", "")),
            "handoff_frozen_version": str(handoff_status.get("frozen_fallback_reference_version", "")),
            "carried_forward_baseline": carried_forward_baseline,
        },
        "architecture_surface_report": {
            "proposal_learning_loop_path": str(PROPOSAL_LOOP_PATH),
            "proposal_learning_loop_surface": architecture_surface,
            "architecture_plane_report": architecture_planes,
            "benchmark_pack_summary": benchmark_pack,
        },
        "comparison_references": {
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
                "frontier_characterization_report": dict(frontier_artifact.get("frontier_characterization_report", {})),
            },
            "memory_summary.safe_trio_false_safe_invariance_snapshot_v1": {
                "diagnostic_conclusions": invariance_conclusions,
                "structural_conclusion": dict(invariance_artifact.get("structural_conclusion", {})),
            },
            "memory_summary.swap_c_family_coverage_snapshot_v1": {
                "diagnostic_conclusions": coverage_conclusions,
                "family_coverage_report": dict(coverage_artifact.get("family_coverage_report", {})),
            },
            "memory_summary.seed_context_shift_snapshot": {
                "diagnostic_conclusions": seed_context_conclusions,
            },
            "memory_summary.benchmark_context_availability_snapshot": {
                "diagnostic_conclusions": benchmark_context_conclusions,
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
            "top_failure_tags": list(analytics.get("top_failure_tags", []))[:5],
            "current_recommendation_top_templates": _top_recommendation_templates(recommendations, decision="suggested", limit=8),
            "legacy_recommender_bias_detected": bool(legacy_recommender_bias),
            "analytics_report_generated_at": str(analytics_report.get("generated_at", "")),
        },
        "ranked_architecture_upstream_branch_landscape": candidate_rows,
        "decision_recommendation": {
            "best_first_architecture_hypothesis": str(best_first_hypothesis),
            "recommended_next_family": str(recommended_next_family),
            "recommended_next_template": str(recommended_next_template),
            "rationale": str(recommended_next_rationale),
        },
        "branch_snapshot_refs": latest_snapshot_refs,
        "observability_gain": {
            "passed": True,
            "reason": "the snapshot combines carried-forward v3 closure evidence, the prior v4 landscape, proposal-learning-loop architecture surface, benchmark pack structure, and current recommendation state to rank only architecture-level v4 openings",
            "candidate_branch_count": int(len(candidate_rows)),
            "architecture_surface_open": bool(architecture_surface_open),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the snapshot distinguishes a repo-native architecture/context branch from open-secondary support branches and from closed v3 continuation lines",
            "under_cap_critic_exhausted": bool(under_cap_critic_exhausted),
            "benchmark_control_retest_closed": bool(no_control_headroom),
            "proposal_learning_loop_architecture_open": bool(architecture_surface_open),
            "legacy_recommender_bias_detected": bool(legacy_recommender_bias),
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": float(
                min(
                    1.0,
                    0.42
                    + 0.18 * int(under_cap_critic_exhausted)
                    + 0.14 * int(hard_discrete_frontier)
                    + 0.12 * int(no_control_headroom)
                    + 0.08 * int(architecture_surface_open)
                    + 0.06 * int(persistence_upstream_healthy and persistence_excluded_only_at_selection)
                )
            ),
            "reason": "the snapshot cleanly separates architecture-owned v4 openings from renamed v3 continuation lines and from secondary support-only branches",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "diagnostic-only architecture/context branch snapshot with live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": str(recommended_next_template),
            "reason": str(recommended_next_rationale),
        },
        "diagnostic_conclusions": {
            "best_first_architecture_hypothesis": str(best_first_hypothesis),
            "proposal_learning_loop_architecture_branch_open": bool(architecture_surface_open),
            "architecture_branch_structure_open": bool(
                under_cap_critic_exhausted and hard_discrete_frontier and no_control_headroom
            ),
            "upstream_context_branch_open": bool(upstream_context_signal_open),
            "diagnostic_memory_support_branch_open": True,
            "benchmark_control_retest_open": False,
            "continued_under_cap_critic_split_open": False,
            "recommended_next_family": str(recommended_next_family),
            "recommended_next_template": str(recommended_next_template),
            "routing_deferred": bool(routing_deferred),
        },
    }
    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"memory_summary_v4_architecture_upstream_context_branch_snapshot_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: the first architecture-level novali-v4 branch landscape was ranked outside the exhausted novali-v3 critic/control line",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
