from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .analytics import build_intervention_ledger_analytics
from .governance_memory_execution_gate_v1 import build_execution_permission
from .ledger import intervention_data_dir
from .taxonomy import build_proposal_template, list_available_proposal_templates


def proposal_recommendations_report_path() -> Path:
    return intervention_data_dir() / "proposal_recommendations_latest.json"


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_diagnostic_memory_artifacts() -> List[Dict[str, Any]]:
    artifact_dir = intervention_data_dir() / "diagnostic_memory"
    if not artifact_dir.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for path in sorted(artifact_dir.glob("*.json"), key=lambda item: (item.stat().st_mtime, item.name)):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        payload["_artifact_path"] = str(path)
        payload["_artifact_mtime"] = float(path.stat().st_mtime)
        rows.append(payload)
    return rows


def _artifact_passed(artifact: Dict[str, Any]) -> bool:
    return bool(
        dict(artifact.get("observability_gain", {})).get("passed")
        and dict(artifact.get("activation_analysis_usefulness", {})).get("passed")
        and dict(artifact.get("ambiguity_reduction", {})).get("passed")
        and dict(artifact.get("safety_neutrality", {})).get("passed")
        and dict(artifact.get("later_selection_usefulness", {})).get("passed")
    )


def _aggregate_blocker_counts(artifacts: List[Dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for artifact in artifacts:
        blocker_counts = dict(artifact.get("blocker_counts", {}))
        for name, count in blocker_counts.items():
            counts[str(name)] += int(count)
    return counts


def _distribution_distance(left: Dict[str, Any], right: Dict[str, Any]) -> float:
    names = set(left.keys()) | set(right.keys())
    left_total = float(sum(float(left.get(name, 0.0)) for name in names))
    right_total = float(sum(float(right.get(name, 0.0)) for name in names))
    if left_total <= 0.0 or right_total <= 0.0:
        return 0.0
    return float(
        sum(
            abs(float(left.get(name, 0.0)) / left_total - float(right.get(name, 0.0)) / right_total)
            for name in names
        )
        / 2.0
    )


def build_memory_guidance_index() -> Dict[str, Any]:
    analytics = build_intervention_ledger_analytics()
    artifacts = _load_diagnostic_memory_artifacts()
    successful_artifacts = [artifact for artifact in artifacts if _artifact_passed(artifact)]
    aggregate_blockers = _aggregate_blocker_counts(successful_artifacts)
    dominant_blocker = aggregate_blockers.most_common(1)[0][0] if aggregate_blockers else "none"
    dominant_blocker_count = int(aggregate_blockers.most_common(1)[0][1]) if aggregate_blockers else 0
    total_blockers = int(sum(aggregate_blockers.values()))
    dominant_blocker_share = float(dominant_blocker_count / total_blockers) if total_blockers > 0 else 0.0

    latest_successful = successful_artifacts[-1] if successful_artifacts else {}
    previous_successful = successful_artifacts[-2] if len(successful_artifacts) >= 2 else {}
    latest_diagnostic_artifact = next(
        (
            artifact
            for artifact in reversed(successful_artifacts)
            if dict(artifact.get("diagnostic_conclusions", {}))
        ),
        {},
    )
    latest_diagnostic_conclusions = dict(latest_diagnostic_artifact.get("diagnostic_conclusions", {}))
    latest_diagnostic_followup_template = str(
        dict(latest_diagnostic_artifact.get("later_selection_usefulness", {})).get("recommended_next_template", "")
    )
    latest_gap_artifact = next(
        (
            artifact
            for artifact in reversed(successful_artifacts)
            if str(artifact.get("template_name")) == "memory_summary.live_distribution_gap_snapshot"
        ),
        {},
    )
    latest_gap_conclusions = dict(latest_gap_artifact.get("diagnostic_conclusions", {}))
    latest_gap_followup_template = str(
        dict(latest_gap_artifact.get("later_selection_usefulness", {})).get("recommended_next_template", "")
    )
    blocker_profile_shift = _distribution_distance(
        dict(previous_successful.get("blocker_counts", {})),
        dict(latest_successful.get("blocker_counts", {})),
    )
    blocker_profile_changed = bool(len(successful_artifacts) >= 2 and blocker_profile_shift >= 0.25)

    template_summary = dict(analytics.get("template_outcome_summary", {}))
    benchmark_safe_but_dormant: List[Dict[str, Any]] = []
    under_served_families: List[Dict[str, Any]] = []
    for template_name, summary in sorted(template_summary.items(), key=lambda item: str(item[0])):
        benchmark_rate = _safe_float(dict(summary).get("benchmark_pass_rate")) or 0.0
        dormant_rate = _safe_float(dict(summary).get("dormant_live_override_rate")) or 0.0
        if benchmark_rate > 0.0 and dormant_rate > 0.0:
            entry = {
                "template_name": str(template_name),
                "proposal_type": str(dict(summary).get("proposal_type", "unknown")),
                "target_family": str(dict(summary).get("primary_target_family", "unknown")),
                "benchmark_pass_rate": float(benchmark_rate),
                "dormant_live_override_rate": float(dormant_rate),
            }
            benchmark_safe_but_dormant.append(entry)
            under_served_families.append(
                {
                    "target_family": str(entry["target_family"]),
                    "reason": "benchmark_safe_but_live_dormant",
                    "source_template": str(template_name),
                }
            )

    failure_tags = list(analytics.get("top_failure_tags", []))
    dominant_failure_tags = [item for item in failure_tags if str(item.get("name")) != "contract_mismatch_legacy"]
    compact = dict(analytics.get("compact_summary", {}))
    recommendations = dict(compact.get("recommendations", {}))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analytics": analytics,
        "diagnostic_artifact_count": int(len(artifacts)),
        "successful_diagnostic_artifact_count": int(len(successful_artifacts)),
        "latest_successful_artifact_path": str(latest_successful.get("_artifact_path", "")),
        "latest_diagnostic_artifact_path": str(latest_diagnostic_artifact.get("_artifact_path", "")),
        "latest_diagnostic_conclusions": latest_diagnostic_conclusions,
        "latest_diagnostic_followup_template": str(latest_diagnostic_followup_template),
        "latest_gap_artifact_path": str(latest_gap_artifact.get("_artifact_path", "")),
        "latest_gap_conclusions": latest_gap_conclusions,
        "latest_gap_followup_template": str(latest_gap_followup_template),
        "dominant_failure_tags": dominant_failure_tags[:5],
        "dominant_blocker": {
            "name": str(dominant_blocker),
            "count": int(dominant_blocker_count),
            "share": float(dominant_blocker_share),
            "source": "diagnostic_memory" if dominant_blocker != "none" else "none",
        },
        "blocker_counts": {
            str(name): int(count)
            for name, count in sorted(aggregate_blockers.items(), key=lambda item: (-int(item[1]), str(item[0])))
        },
        "blocker_profile_changed": bool(blocker_profile_changed),
        "blocker_profile_shift": float(blocker_profile_shift),
        "benchmark_safe_but_dormant": benchmark_safe_but_dormant,
        "under_served_families": under_served_families,
        "suggested_templates_from_analytics": list(recommendations.get("suggested_next_templates", [])),
        "deprioritized_templates_from_analytics": list(recommendations.get("deprioritized_templates", [])),
        "artifacts": successful_artifacts,
    }


def _memory_dependencies_status(memory_index: Dict[str, Any], dependencies: List[str]) -> Dict[str, Any]:
    satisfied: List[str] = []
    missing: List[str] = []
    latest_artifact = dict(memory_index.get("artifacts", [])[-1] if memory_index.get("artifacts") else {})
    analytics = dict(memory_index.get("analytics", {}))
    blocker_name = str(dict(memory_index.get("dominant_blocker", {})).get("name", "none"))

    for dependency in dependencies:
        dep = str(dependency)
        ok = False
        if dep == "intervention_ledger":
            ok = int(analytics.get("proposal_count", 0)) > 0
        elif dep == "intervention_analytics":
            ok = bool(analytics)
        elif dep == "benchmark_policy_sweep_summary":
            ok = bool(dict(analytics.get("target_family_outcome_summary", {})))
        elif dep == "ledger_routing_history":
            ok = any(str(item.get("proposal_type")) == "routing_rule" for item in list(dict(analytics.get("template_outcome_summary", {})).values()))
        elif dep == "diagnostic_memory.override_dormancy_snapshot":
            ok = any(str(item.get("template_name")) == "memory_summary.override_dormancy_snapshot" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.live_distribution_gap_snapshot":
            ok = any(str(item.get("template_name")) == "memory_summary.live_distribution_gap_snapshot" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.seed_context_shift_snapshot":
            ok = any(str(item.get("template_name")) == "memory_summary.seed_context_shift_snapshot" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.benchmark_context_availability_snapshot":
            ok = any(str(item.get("template_name")) == "memory_summary.benchmark_context_availability_snapshot" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.safe_slice_selection_gap_snapshot":
            ok = any(str(item.get("template_name")) == "memory_summary.safe_slice_selection_gap_snapshot" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.memory_summary.benchmark_transfer_blocker_snapshot_v1":
            ok = any(str(item.get("template_name")) == "memory_summary.benchmark_transfer_blocker_snapshot_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.support_contract.benchmark_stability_sensitive_compat_probe_v1":
            ok = any(str(item.get("template_name")) == "support_contract.benchmark_stability_sensitive_compat_probe_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.routing_rule.candidate_distribution_aware_probe":
            ok = any(str(item.get("template_name")) == "routing_rule.candidate_distribution_aware_probe" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.score_reweight.blocker_sensitive_projection_probe":
            ok = any(str(item.get("template_name")) == "score_reweight.blocker_sensitive_projection_probe" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.routing_rule.activation_window_probe":
            ok = any(str(item.get("template_name")) == "routing_rule.activation_window_probe" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.critic_split.projection_gain_goal_v1":
            ok = any(str(item.get("template_name")) == "critic_split.projection_gain_goal_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.critic_split.projection_gain_goal_v2":
            ok = any(str(item.get("template_name")) == "critic_split.projection_gain_goal_v2" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.critic_split.safe_slice_purity_probe_v1":
            ok = any(str(item.get("template_name")) == "critic_split.safe_slice_purity_probe_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.critic_split.benchmark_distance_retention_probe_v1":
            ok = any(str(item.get("template_name")) == "critic_split.benchmark_distance_retention_probe_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.critic_split.benchmark_alignment_critic_v1":
            ok = any(str(item.get("template_name")) == "critic_split.benchmark_alignment_critic_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.critic_split.benchmark_alignment_critic_v2":
            ok = any(str(item.get("template_name")) == "critic_split.benchmark_alignment_critic_v2" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.critic_split.benchmark_transfer_alignment_probe_v1":
            ok = any(str(item.get("template_name")) == "critic_split.benchmark_transfer_alignment_probe_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.critic_split.benchmark_like_scoring_preservation_probe_v1":
            ok = any(str(item.get("template_name")) == "critic_split.benchmark_like_scoring_preservation_probe_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.critic_split.benchmark_like_scoring_preservation_probe_v2":
            ok = any(str(item.get("template_name")) == "critic_split.benchmark_like_scoring_preservation_probe_v2" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.critic_split.stability_context_retention_probe_v1":
            ok = any(str(item.get("template_name")) == "critic_split.stability_context_retention_probe_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.critic_split.stability_context_retention_probe_v2":
            ok = any(str(item.get("template_name")) == "critic_split.stability_context_retention_probe_v2" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.critic_split.safe_slice_selection_reliability_probe_v1":
            ok = any(str(item.get("template_name")) == "critic_split.safe_slice_selection_reliability_probe_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.support_contract.recovery_runner_contract_fix_v1":
            ok = any(str(item.get("template_name")) == "support_contract.recovery_runner_contract_fix_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.critic_split.recovery_benchmark_like_alignment_probe_v1":
            ok = any(str(item.get("template_name")) == "critic_split.recovery_benchmark_like_alignment_probe_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.critic_split.benchmark_family_balance_probe_v1":
            ok = any(str(item.get("template_name")) == "critic_split.benchmark_family_balance_probe_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.memory_summary.runner_path_incompatibility_snapshot_v1":
            ok = any(str(item.get("template_name")) == "memory_summary.runner_path_incompatibility_snapshot_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.memory_summary.recovery_transfer_asymmetry_snapshot_v1":
            ok = any(str(item.get("template_name")) == "memory_summary.recovery_transfer_asymmetry_snapshot_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.memory_summary.benchmark_family_balance_snapshot_v1":
            ok = any(str(item.get("template_name")) == "memory_summary.benchmark_family_balance_snapshot_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.memory_summary.final_selection_false_safe_margin_snapshot_v1":
            ok = any(str(item.get("template_name")) == "memory_summary.final_selection_false_safe_margin_snapshot_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.memory_summary.swap_c_family_coverage_snapshot_v1":
            ok = any(str(item.get("template_name")) == "memory_summary.swap_c_family_coverage_snapshot_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.memory_summary.safe_trio_false_safe_invariance_snapshot_v1":
            ok = any(str(item.get("template_name")) == "memory_summary.safe_trio_false_safe_invariance_snapshot_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.memory_summary.false_safe_frontier_control_characterization_snapshot_v1":
            ok = any(str(item.get("template_name")) == "memory_summary.false_safe_frontier_control_characterization_snapshot_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.score_reweight.gain_goal_conflict_probe":
            ok = any(str(item.get("template_name")) == "score_reweight.gain_goal_conflict_probe" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.routing_rule.slice_targeted_benchmark_sweep_v1":
            ok = any(str(item.get("template_name")) == "routing_rule.slice_targeted_benchmark_sweep_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.critic_split.final_selection_false_safe_guardrail_probe_v1":
            ok = any(str(item.get("template_name")) == "critic_split.final_selection_false_safe_guardrail_probe_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.critic_split.safe_trio_incumbent_confirmation_probe_v1":
            ok = any(str(item.get("template_name")) == "critic_split.safe_trio_incumbent_confirmation_probe_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.critic_split.persistence_balanced_safe_trio_probe_v1":
            ok = any(str(item.get("template_name")) == "critic_split.persistence_balanced_safe_trio_probe_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.critic_split.swap_c_incumbent_hardening_probe_v1":
            ok = any(str(item.get("template_name")) == "critic_split.swap_c_incumbent_hardening_probe_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.memory_summary.v4_first_hypothesis_landscape_snapshot_v1":
            ok = any(str(item.get("template_name")) == "memory_summary.v4_first_hypothesis_landscape_snapshot_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.memory_summary.v4_architecture_upstream_context_branch_snapshot_v1":
            ok = any(str(item.get("template_name")) == "memory_summary.v4_architecture_upstream_context_branch_snapshot_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.memory_summary.v4_proposal_learning_loop_context_branch_snapshot_v1":
            ok = any(str(item.get("template_name")) == "memory_summary.v4_proposal_learning_loop_context_branch_snapshot_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.memory_summary.v4_world_model_planning_context_entry_snapshot_v1":
            ok = any(str(item.get("template_name")) == "memory_summary.v4_world_model_planning_context_entry_snapshot_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.proposal_learning_loop.v4_wm_primary_plan_structure_probe_v1":
            ok = any(str(item.get("template_name")) == "proposal_learning_loop.v4_wm_primary_plan_structure_probe_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.memory_summary.v4_wm_plan_context_trace_quality_snapshot_v1":
            ok = any(str(item.get("template_name")) == "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.memory_summary.v4_wm_plan_context_trace_quality_snapshot_v2":
            ok = any(str(item.get("template_name")) == "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v2" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1":
            ok = any(str(item.get("template_name")) == "proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.proposal_learning_loop.v4_wm_context_residual_signal_probe_v1":
            ok = any(str(item.get("template_name")) == "proposal_learning_loop.v4_wm_context_residual_signal_probe_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.memory_summary.v4_wm_context_signal_overlap_snapshot_v1":
            ok = any(str(item.get("template_name")) == "memory_summary.v4_wm_context_signal_overlap_snapshot_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.memory_summary.v4_wm_baseline_hybrid_boundary_snapshot_v1":
            ok = any(str(item.get("template_name")) == "memory_summary.v4_wm_baseline_hybrid_boundary_snapshot_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1":
            ok = any(str(item.get("template_name")) == "proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.memory_summary.v4_wm_hybrid_probe_effect_snapshot_v1":
            ok = any(str(item.get("template_name")) == "memory_summary.v4_wm_hybrid_probe_effect_snapshot_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1":
            ok = any(str(item.get("template_name")) == "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1" for item in list(memory_index.get("artifacts", [])))
        elif dep == "diagnostic_memory.current_projection_guard":
            ok = blocker_name == "projection_guard"
        else:
            ok = bool(dep and latest_artifact)
        (satisfied if ok else missing).append(dep)

    ratio = float(len(satisfied) / len(dependencies)) if dependencies else 1.0
    return {
        "satisfied": satisfied,
        "missing": missing,
        "ratio": ratio,
    }


def _template_history(analytics: Dict[str, Any], template_name: str) -> Dict[str, Any]:
    return dict(dict(analytics.get("template_outcome_summary", {})).get(str(template_name), {}))


def _preferred_templates_for_blocker(blocker_name: str) -> Dict[str, float]:
    blocker = str(blocker_name)
    if blocker == "projection_guard":
        return {
            "memory_summary.live_distribution_gap_snapshot": 2.2,
            "routing_rule.activation_window_probe": 1.3,
            "routing_rule.candidate_distribution_aware_probe": 1.1,
            "score_reweight.blocker_sensitive_projection_probe": 0.9,
        }
    if blocker == "confidence_gain_precondition":
        return {
            "score_reweight.gain_goal_conflict_probe": 1.8,
            "memory_summary.live_distribution_gap_snapshot": 1.0,
        }
    return {
        "critic_split.projection_gain_goal_v1": 0.8,
    }


def _preferred_templates_for_gap_hypothesis(hypothesis: str) -> Dict[str, float]:
    name = str(hypothesis)
    if name == "projection_probe":
        return {
            "routing_rule.activation_window_probe": 2.4,
            "score_reweight.blocker_sensitive_projection_probe": 0.8,
        }
    if name == "gain_probe":
        return {
            "score_reweight.gain_goal_conflict_probe": 2.2,
            "score_reweight.blocker_sensitive_projection_probe": 0.7,
        }
    if name == "benchmark_alignment_probe":
        return {
            "routing_rule.candidate_distribution_aware_probe": 2.5,
            "critic_split.projection_gain_goal_v1": 0.7,
        }
    if name == "score_refinement":
        return {
            "critic_split.projection_gain_goal_v2": 2.5,
            "critic_split.projection_gain_goal_v1": 0.8,
            "score_reweight.gain_goal_conflict_probe": 0.6,
        }
    if name == "routing_retry":
        return {
            "routing_rule.activation_window_probe": 2.4,
        }
    if name == "narrow_routing_sweep":
        return {
            "routing_rule.slice_targeted_benchmark_sweep_v1": 2.8,
        }
    if name == "selection_reliability_refinement":
        return {
            "critic_split.safe_slice_selection_reliability_probe_v1": 3.0,
            "critic_split.benchmark_alignment_critic_v2": 0.8,
            "memory_summary.safe_slice_selection_gap_snapshot": 0.2,
        }
    if name == "slice_stability_probe":
        return {
            "critic_split.projection_gain_goal_v2": 2.1,
            "critic_split.projection_gain_goal_v1": 0.6,
            "score_reweight.gain_goal_conflict_probe": 0.5,
        }
    if name == "benchmark_alignment_followup":
        return {
            "critic_split.projection_gain_goal_v2": 2.2,
            "critic_split.projection_gain_goal_v1": 0.5,
            "memory_summary.live_distribution_gap_snapshot": 0.4,
        }
    if name == "benchmark_alignment_critic":
        return {
            "critic_split.projection_gain_goal_v2": 2.5,
            "critic_split.safe_slice_purity_probe_v1": 0.9,
            "memory_summary.live_distribution_gap_snapshot": 0.3,
        }
    if name == "stability_context_retention_probe":
        return {
            "critic_split.stability_context_retention_probe_v2": 2.9,
            "critic_split.stability_context_retention_probe_v1": 1.2,
            "memory_summary.seed_context_shift_snapshot": 0.6,
            "critic_split.benchmark_alignment_critic_v2": 0.8,
        }
    if name == "subtype_conditioned_critic":
        return {
            "critic_split.stability_context_retention_probe_v2": 1.6,
            "critic_split.stability_context_retention_probe_v1": 0.5,
            "critic_split.benchmark_alignment_critic_v2": 0.9,
            "memory_summary.seed_context_shift_snapshot": 0.4,
        }
    if name == "stability_context_retention_continue":
        return {
            "critic_split.stability_context_retention_probe_v2": 2.8,
            "critic_split.benchmark_alignment_critic_v2": 1.4,
            "critic_split.projection_gain_goal_v2": 0.5,
        }
    if name == "benchmark_alignment_model":
        return {
            "critic_split.benchmark_alignment_critic_v1": 2.8,
            "critic_split.projection_gain_goal_v2": 0.9,
            "memory_summary.seed_context_shift_snapshot": 0.3,
        }
    if name == "benchmark_alignment_critic_v2":
        return {
            "critic_split.benchmark_alignment_critic_v2": 3.2,
            "critic_split.benchmark_alignment_critic_v1": 0.8,
            "memory_summary.benchmark_context_availability_snapshot": 0.3,
        }
    if name == "benchmark_alignment_critic_continue":
        return {
            "critic_split.benchmark_alignment_critic_v2": 2.8,
            "critic_split.stability_context_retention_probe_v2": 1.8,
            "critic_split.stability_context_retention_probe_v1": 0.4,
            "memory_summary.benchmark_context_availability_snapshot": 0.3,
        }
    if name == "support_runner_compatibility_fix":
        return {
            "support_contract.benchmark_stability_sensitive_compat_probe_v1": 3.2,
            "critic_split.benchmark_alignment_critic_v2": 0.9,
            "memory_summary.benchmark_transfer_blocker_snapshot_v1": 0.4,
        }
    if name == "recovery_runner_contract_fix":
        return {
            "support_contract.recovery_runner_contract_fix_v1": 3.2,
            "support_contract.benchmark_stability_sensitive_compat_probe_v1": 0.8,
            "memory_summary.recovery_transfer_asymmetry_snapshot_v1": 0.2,
        }
    if name == "recovery_benchmark_like_alignment":
        return {
            "critic_split.recovery_benchmark_like_alignment_probe_v1": 3.2,
            "critic_split.benchmark_like_transfer_alignment_probe_v1": 1.6,
            "support_contract.recovery_runner_contract_fix_v1": 0.5,
        }
    if name == "late_stage_scorer_preservation":
        return {
            "critic_split.benchmark_like_scoring_preservation_probe_v2": 3.4,
            "critic_split.benchmark_like_scoring_preservation_probe_v1": 3.2,
            "critic_split.benchmark_like_transfer_alignment_probe_v1": 1.4,
            "critic_split.recovery_benchmark_like_alignment_probe_v1": 1.0,
        }
    if name == "residual_scorer_stabilization":
        return {
            "critic_split.benchmark_like_scoring_preservation_probe_v2": 3.4,
            "critic_split.benchmark_like_scoring_preservation_probe_v1": 1.8,
            "critic_split.benchmark_like_transfer_alignment_probe_v1": 1.0,
        }
    if name == "swap_aware_final_selection_guardrail_refinement":
        return {
            "critic_split.final_selection_false_safe_guardrail_probe_v1": 3.4,
            "critic_split.benchmark_like_scoring_preservation_probe_v2": 2.4,
            "memory_summary.final_selection_false_safe_margin_snapshot_v1": 0.4,
        }
    if name == "confirmed_safe_trio_baseline":
        return {
            "critic_split.final_selection_false_safe_guardrail_probe_v1": 3.6,
            "critic_split.safe_trio_incumbent_confirmation_probe_v1": 3.2,
            "critic_split.benchmark_like_scoring_preservation_probe_v2": 1.4,
        }
    if name == "critic_split_continue":
        return {
            "critic_split.benchmark_like_scoring_preservation_probe_v2": 3.2,
            "critic_split.benchmark_like_scoring_preservation_probe_v1": 3.0,
            "critic_split.benchmark_like_transfer_alignment_probe_v1": 1.2,
        }
    if name == "persistence_targeted_followup":
        return {
            "critic_split.benchmark_like_scoring_preservation_probe_v2": 2.2,
            "critic_split.benchmark_like_scoring_preservation_probe_v1": 1.8,
            "critic_split.benchmark_like_transfer_alignment_probe_v1": 1.4,
        }
    if name == "cross_family_balance_refinement":
        return {
            "critic_split.benchmark_family_balance_probe_v1": 3.2,
            "critic_split.recovery_benchmark_like_alignment_probe_v1": 1.4,
            "memory_summary.benchmark_family_balance_snapshot_v1": 0.3,
        }
    if name == "narrow_benchmark_routing_revisit":
        return {
            "routing_rule.slice_targeted_benchmark_sweep_v1": 3.0,
            "critic_split.stability_context_retention_probe_v2": 0.5,
        }
    if name == "no_routing_yet":
        return {
            "critic_split.projection_gain_goal_v2": 2.4,
            "critic_split.projection_gain_goal_v1": 0.4,
            "score_reweight.gain_goal_conflict_probe": 0.4,
        }
    if name == "further_slice_refinement":
        return {
            "critic_split.projection_gain_goal_v2": 2.5,
            "score_reweight.gain_goal_conflict_probe": 2.0,
            "critic_split.projection_gain_goal_v1": 0.3,
        }
    if name == "more_critic_work":
        return {
            "critic_split.projection_gain_goal_v2": 2.6,
            "critic_split.projection_gain_goal_v1": 0.4,
            "score_reweight.gain_goal_conflict_probe": 0.7,
        }
    return {}


def build_proposal_recommendations() -> Dict[str, Any]:
    governance_execution_contract = build_execution_permission(action_kind="proposal_recommend")
    memory_index = build_memory_guidance_index()
    analytics = dict(memory_index.get("analytics", {}))
    dominant_blocker = str(dict(memory_index.get("dominant_blocker", {})).get("name", "none"))
    preferred_for_blocker = _preferred_templates_for_blocker(dominant_blocker)
    diagnostic_conclusions = dict(memory_index.get("latest_diagnostic_conclusions", {}))
    gap_conclusions = dict(memory_index.get("latest_gap_conclusions", {}))
    next_control_hypothesis = str(
        diagnostic_conclusions.get("next_control_hypothesis")
        or gap_conclusions.get("next_control_hypothesis", "")
    )
    preferred_for_gap = _preferred_templates_for_gap_hypothesis(next_control_hypothesis)
    latest_diagnostic_followup_template = str(
        memory_index.get("latest_diagnostic_followup_template")
        or memory_index.get("latest_gap_followup_template", "")
    )
    has_benchmark_like_live_segment = bool(diagnostic_conclusions.get("has_benchmark_like_live_segment"))
    dominant_mismatch_axis = str(diagnostic_conclusions.get("dominant_mismatch_axis", ""))
    suggested_from_analytics = {
        str(item.get("template_name")): dict(item)
        for item in list(memory_index.get("suggested_templates_from_analytics", []))
        if isinstance(item, dict)
    }
    deprioritized_from_analytics = {
        str(item.get("template_name")): dict(item)
        for item in list(memory_index.get("deprioritized_templates_from_analytics", []))
        if isinstance(item, dict)
    }
    under_served_families = {
        str(item.get("target_family")): dict(item)
        for item in list(memory_index.get("under_served_families", []))
        if isinstance(item, dict)
    }
    benchmark_safe_but_dormant_names = {
        str(item.get("template_name"))
        for item in list(memory_index.get("benchmark_safe_but_dormant", []))
        if isinstance(item, dict)
    }

    rows: List[Dict[str, Any]] = []
    for template_name in list_available_proposal_templates():
        proposal = build_proposal_template(template_name)
        template_history = _template_history(analytics, template_name)
        dependencies = _memory_dependencies_status(memory_index, list(proposal.get("memory_dependencies", [])))
        target_family = str(dict(proposal.get("intended_benefit", {})).get("target_family", "unknown"))
        blocker_targets = set(str(name) for name in list(proposal.get("targets_blockers", [])))
        semantics = str(proposal.get("evaluation_semantics", "control_changing"))

        score = 0.0
        evidence: List[str] = []
        supporting: Dict[str, Any] = {
            "dominant_blocker": dominant_blocker,
            "under_served_family": dict(under_served_families.get(target_family, {})),
            "memory_dependencies": dependencies,
            "template_history": template_history,
        }
        driver_scores: Counter[str] = Counter()
        suppressed = False

        if template_name in preferred_for_blocker:
            boost = float(preferred_for_blocker[template_name])
            score += boost
            driver_scores["diagnostic_memory"] += boost
            evidence.append(f"targets dominant blocker {dominant_blocker}")
        if template_name in preferred_for_gap:
            boost = float(preferred_for_gap[template_name])
            score += boost
            driver_scores["diagnostic_memory"] += boost
            evidence.append(f"matches current gap hypothesis {next_control_hypothesis}")
        if latest_diagnostic_followup_template and template_name == latest_diagnostic_followup_template:
            score += 2.6
            driver_scores["diagnostic_memory"] += 2.6
            evidence.append("recommended by latest diagnostic artifact")
        if dominant_blocker in blocker_targets:
            score += 0.9
            driver_scores["diagnostic_memory"] += 0.9
            evidence.append(f"explicitly targets blocker {dominant_blocker}")
        if target_family in under_served_families:
            score += 1.0
            driver_scores["family_undercommitment"] += 1.0
            evidence.append(f"targets under-served family {target_family}")

        dependency_ratio = float(dependencies.get("ratio", 0.0))
        if dependency_ratio > 0.0:
            boost = 0.6 * dependency_ratio
            score += boost
            driver_scores["diagnostic_memory"] += boost
            if dependencies.get("missing"):
                evidence.append(f"partial memory coverage ({len(dependencies['satisfied'])}/{len(proposal.get('memory_dependencies', []))})")
            else:
                evidence.append("all required diagnostic memory available")
        else:
            if proposal.get("memory_dependencies"):
                score -= 0.75
                driver_scores["diagnostic_memory"] += 0.75
                evidence.append("required diagnostic memory missing")

        shadow_pass_rate = _safe_float(template_history.get("shadow_pass_rate")) or 0.0
        if shadow_pass_rate > 0.0:
            score += 0.5 * shadow_pass_rate
            driver_scores["diagnostic_memory"] += 0.5 * shadow_pass_rate
            evidence.append("previous intended-stage shadow pass")

        harmful_rate = _safe_float(template_history.get("harmful_failure_rate")) or 0.0
        if harmful_rate > 0.0:
            penalty = 2.0 * harmful_rate
            score -= penalty
            driver_scores["benchmark_regression"] += penalty
            evidence.append("harmful failure history")

        if template_name in suggested_from_analytics:
            score += 0.5
            evidence.append("already suggested by analytics")

        if template_name in deprioritized_from_analytics:
            score -= 0.75
            driver_scores["retry_policy"] += 0.75
            evidence.append(str(deprioritized_from_analytics[template_name].get("reason", "analytics deprioritized this template")))

        if template_name in benchmark_safe_but_dormant_names:
            if not bool(memory_index.get("blocker_profile_changed", False)):
                score -= 3.0
                driver_scores["dormancy"] += 3.0
                suppressed = True
                evidence.append("suppressed: benchmark-safe but repeatedly live-dormant and blocker profile unchanged")
            else:
                score += 0.25
                evidence.append("retry allowed because blocker profile changed materially")

        if template_name == "memory_summary.override_dormancy_snapshot" and shadow_pass_rate > 0.0:
            if not bool(memory_index.get("blocker_profile_changed", False)):
                score -= 1.25
                driver_scores["retry_policy"] += 1.25
                evidence.append("suppressed: dormant blocker snapshot already captured and blocker profile unchanged")

        if template_name == "memory_summary.live_distribution_gap_snapshot":
            if gap_conclusions and not bool(memory_index.get("blocker_profile_changed", False)):
                score -= 1.75
                driver_scores["retry_policy"] += 1.75
                evidence.append("suppressed: live-distribution gap snapshot already captured and remains current")
            if diagnostic_conclusions:
                score -= 3.25
                driver_scores["retry_policy"] += 3.25
                evidence.append("suppressed: newer segment-level diagnostic supersedes this broader gap snapshot")
        if template_name == "memory_summary.seed_context_shift_snapshot":
            if diagnostic_conclusions and str(diagnostic_conclusions.get("collapse_driver", "")):
                score -= 2.75
                driver_scores["retry_policy"] += 2.75
                evidence.append("suppressed: seed-context collapse snapshot already captured and remains current")
        if template_name == "memory_summary.benchmark_context_availability_snapshot":
            if diagnostic_conclusions and str(diagnostic_conclusions.get("availability_driver", "")):
                score -= 2.75
                driver_scores["retry_policy"] += 2.75
                evidence.append("suppressed: benchmark-context availability snapshot already captured and remains current")
        if template_name == "routing_rule.candidate_distribution_aware_probe" and diagnostic_conclusions:
            score -= 4.00
            driver_scores["retry_policy"] += 4.00
            evidence.append("suppressed: candidate-distribution probe already captured and remains current")
        if template_name == "score_reweight.blocker_sensitive_projection_probe" and "score_probe_effect" in diagnostic_conclusions:
            score -= 3.60
            driver_scores["retry_policy"] += 3.60
            evidence.append("suppressed: blocker-sensitive score probe already captured and remains current")
        if template_name == "routing_rule.activation_window_probe" and "slice_activation_observed" in diagnostic_conclusions:
            score -= 3.60
            driver_scores["retry_policy"] += 3.60
            evidence.append("suppressed: activation-window probe already captured and remains current")

        if not has_benchmark_like_live_segment and template_name in {"routing_rule.activation_window_probe", "routing_rule.targeted_gain_goal_proj_margin_01"}:
            score -= 1.60
            driver_scores["retry_policy"] += 1.60
            evidence.append("suppressed: latest segment probe found no benchmark-like live segment for routing activation")
        if not has_benchmark_like_live_segment and template_name == "routing_rule.targeted_gain_goal_proj_margin_01":
            score -= 2.25
            driver_scores["retry_policy"] += 2.25
            evidence.append("suppressed: dormant routing retry is not justified after segment probe found no benchmark-like live segment")
        if dominant_mismatch_axis in {"projection_level", "projection_shape"} and template_name == "score_reweight.blocker_sensitive_projection_probe":
            score += 1.10
            driver_scores["diagnostic_memory"] += 1.10
            evidence.append(f"latest segment probe says mismatch axis is {dominant_mismatch_axis}")
        if dominant_mismatch_axis == "gain_structure" and template_name == "score_reweight.gain_goal_conflict_probe":
            score += 1.10
            driver_scores["diagnostic_memory"] += 1.10
            evidence.append("latest segment probe says mismatch axis is gain_structure")

        if semantics == "control_changing" and dependencies.get("missing"):
            missing_penalty = 0.5 * len(list(dependencies.get("missing", [])))
            score -= missing_penalty
            driver_scores["retry_policy"] += missing_penalty
            evidence.append("control-changing probe missing some prerequisite diagnostic memory")

        if semantics == "diagnostic" and template_name == "memory_summary.live_distribution_gap_snapshot":
            score += 1.25
            driver_scores["diagnostic_memory"] += 1.25
            evidence.append("best next safe diagnostic to explain live-vs-benchmark activation gap")
        if semantics == "diagnostic" and template_name == "memory_summary.seed_context_shift_snapshot":
            score += 1.10
            driver_scores["diagnostic_memory"] += 1.10
            evidence.append("diagnostic memory can clarify safe-slice collapse and seed-context instability")
        if semantics == "diagnostic" and template_name == "memory_summary.benchmark_context_availability_snapshot":
            score += 1.15
            driver_scores["diagnostic_memory"] += 1.15
            evidence.append("diagnostic memory can clarify benchmark-like candidate availability inside the safe pool")

        if semantics == "control_changing" and template_name == "routing_rule.activation_window_probe":
            score += 0.4
            driver_scores["family_undercommitment"] += 0.4
            evidence.append("targeted probe preferred over blunt retry of dormant routing rule")

        primary_driver = "none"
        if driver_scores:
            primary_driver = max(driver_scores.items(), key=lambda item: float(item[1]))[0]

        if suppressed or score <= -0.5:
            decision = "deprioritized"
        elif score >= 1.25:
            decision = "suggested"
        else:
            decision = "neutral"

        rows.append(
            {
                "template_name": str(template_name),
                "proposal_type": str(proposal.get("proposal_type")),
                "target_family": str(target_family),
                "recommended_priority": float(round(score, 4)),
                "decision": str(decision),
                "primary_driver": str(primary_driver),
                "reason_summary": "; ".join(evidence[:4]) if evidence else "no strong memory signal yet",
                "supporting_evidence": {
                    "analytics": {
                        "template_history": template_history,
                        "under_served_family": dict(under_served_families.get(target_family, {})),
                    },
                    "diagnostic_memory": {
                        "dominant_blocker": dict(memory_index.get("dominant_blocker", {})),
                        "memory_dependencies": dependencies,
                    },
                    "retry_policy": {
                        "suppressed": bool(suppressed),
                        "blocker_profile_changed": bool(memory_index.get("blocker_profile_changed", False)),
                        "deprioritized_analytics_reason": (
                            None if template_name not in deprioritized_from_analytics
                            else str(deprioritized_from_analytics[template_name].get("reason"))
                        ),
                    },
                },
            }
        )

    suggested = [
        row for row in sorted(rows, key=lambda item: (-float(item["recommended_priority"]), str(item["template_name"])))
        if str(row.get("decision")) == "suggested"
    ]
    deprioritized = [
        row for row in sorted(rows, key=lambda item: (float(item["recommended_priority"]), str(item["template_name"])))
        if str(row.get("decision")) == "deprioritized"
    ]
    neutral = [
        row for row in sorted(rows, key=lambda item: (-float(item["recommended_priority"]), str(item["template_name"])))
        if str(row.get("decision")) == "neutral"
    ]

    dominant_failure = list(memory_index.get("dominant_failure_tags", []))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "governance_execution_contract": governance_execution_contract,
        "memory_index": memory_index,
        "global_summary": {
            "dominant_blocker": dict(memory_index.get("dominant_blocker", {})),
            "dominant_failure_mode": dominant_failure[0] if dominant_failure else None,
            "dominant_under_served_family": next(iter(under_served_families.values()), None),
            "latest_diagnostic_conclusions": diagnostic_conclusions,
            "latest_gap_conclusions": gap_conclusions,
            "recommendation_drivers": {
                "dormancy": any(row["primary_driver"] == "dormancy" for row in rows),
                "benchmark_regression": any(row["primary_driver"] == "benchmark_regression" for row in rows),
                "diagnostic_memory": any(row["primary_driver"] == "diagnostic_memory" for row in rows),
                "family_undercommitment": any(row["primary_driver"] == "family_undercommitment" for row in rows),
            },
        },
        "suggested_proposals": suggested[:5],
        "deprioritized_proposals": deprioritized[:5],
        "neutral_proposals": neutral[:5],
        "all_ranked_proposals": rows,
    }


def write_proposal_recommendations_report() -> Dict[str, Any]:
    report = build_proposal_recommendations()
    path = proposal_recommendations_report_path()
    report["report_path"] = str(path)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report
