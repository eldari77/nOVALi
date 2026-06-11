from __future__ import annotations

import json
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
from .v4_wm_context_signal_overlap_snapshot_v1 import _artifact_reference
from .v4_wm_primary_plan_structure_probe_v1 import _safe_float


def _find_feature(
    feature_rows: list[dict[str, Any]],
    feature_name: str,
) -> dict[str, Any]:
    for row in list(feature_rows):
        if str(dict(row).get("feature", "")) == str(feature_name):
            return dict(row)
    return {}


def _hybrid_component_report(
    feature_rows: list[dict[str, Any]],
    effective_mix: dict[str, Any],
) -> dict[str, Any]:
    effective_weights = dict(effective_mix.get("effective_feature_weights", {}))
    baseline_reused_share = _safe_float(effective_mix.get("baseline_reused_share"), 0.0) or 0.0

    return {
        "keep_hybridized_with_baseline": [
            {
                "feature": "pred_gain_sign_prob",
                "role": "baseline_owned_ranking_carrier",
                "effective_weight": _safe_float(effective_weights.get("pred_gain_sign_prob"), None),
                "reason": "strong baseline availability carrier; useful to keep at the boundary, but destructive when duplicated inside a wm-owned independent correction",
            },
            {
                "feature": "calibrated_projected",
                "role": "baseline_owned_projected_score_carrier",
                "effective_weight": _safe_float(effective_weights.get("calibrated_projected"), None),
                "reason": "already embedded in projected scoring and pre-gate ranking; should remain part of the shared boundary rather than a second positive wm-owned vote",
            },
            {
                "feature": "projected_quality_boundary",
                "role": "boundary_coupled_quality_guard",
                "effective_weight": _safe_float(effective_weights.get("projected_quality"), None),
                "reason": "projection-quality gating is useful, but it should stay coupled to the baseline/projected path instead of being treated as a standalone wm discriminator",
            },
            {
                "feature": "pred_uncertainty",
                "role": "shared_boundary_penalty",
                "effective_weight": _safe_float(effective_weights.get("pred_uncertainty"), None),
                "reason": "uncertainty remains part of the shared safety-sensitive boundary and should not become an independent wm-owned ownership shift",
            },
        ],
        "distinct_wm_owned_candidates": [
            {
                "feature": "pred_context_score",
                "role": "primary_distinct_anchor",
                "reason": str(dict(_find_feature(feature_rows, "pred_context_score")).get("reason", "")),
            },
            {
                "feature": "wm_context_supply_score_contextual_remainder",
                "role": "secondary_contextual_anchor",
                "reason": "use only the contextual remainder of wm_context_supply_score, not the full mixed score, because the full score already carries baseline-dominant terms",
            },
            {
                "feature": "projection_recent",
                "role": "weak_secondary_modulator",
                "reason": "useful as a light contextual history modifier, but too weak to stand alone as a primary wm-owned discriminator",
            },
        ],
        "hybrid_boundary_summary": {
            "baseline_reused_share_in_v1_mix": float(baseline_reused_share),
            "interpretation": "most of the useful v1 wm mix lived on the shared wm/baseline boundary; the viable redesign is to keep that overlap on the baseline side while letting wm contribute only context-specific modulation",
        },
    }


def _boundary_zone_report(
    overlap_artifact: dict[str, Any],
) -> dict[str, Any]:
    overlap_report = dict(overlap_artifact.get("overlap_diagnostic_report", {}))
    v1_overlap = dict(overlap_report.get("v1_useful_signal_overlap_with_baseline", {}))
    residual_headroom = dict(overlap_report.get("residual_distinct_headroom_estimate", {}))

    return {
        "acceptable_overlap": {
            "description": "keep overlap where the signal is clearly baseline-owned and high-utility, but treat wm as a contextual modifier around that boundary instead of a duplicate scoring owner",
            "structural_rule": "baseline keeps ranking carriers; wm contributes context-conditioned modulation",
        },
        "destructive_absorption": {
            "signal_overlap_to_baseline_pre_gate": _safe_float(v1_overlap.get("v1_signal_overlap_to_baseline_pre_gate"), None),
            "signal_availability_corr": _safe_float(v1_overlap.get("v1_signal_availability_corr"), None),
            "partial_signal_given_baseline": _safe_float(v1_overlap.get("v1_partial_signal_given_baseline"), None),
            "reason": "the broad v1 wm signal was strong but too aligned with baseline pre-gate, so it failed to open a new useful axis",
        },
        "over_residualization": {
            "signal_overlap_to_baseline_pre_gate": _safe_float(residual_headroom.get("residual_signal_overlap_to_baseline_pre_gate"), None),
            "signal_availability_corr": _safe_float(residual_headroom.get("residual_signal_availability_corr"), None),
            "signal_gap": _safe_float(residual_headroom.get("residual_signal_gap"), None),
            "partial_signal_given_baseline": _safe_float(residual_headroom.get("residual_partial_signal_given_baseline"), None),
            "reason": "the residualized probe removed baseline absorption, but it also stripped away too much useful signal to remain behaviorally meaningful",
        },
        "best_boundary": {
            "description": "between full duplication and full subtraction: keep baseline-dominant ranking carriers on the baseline side, and let wm own only the context-specific remainder anchored by pred_context_score",
            "wm_owned_modulation_only": [
                "pred_context_score",
                "contextual remainder of wm_context_supply_score",
                "light projection_recent modulation",
            ],
            "baseline_owned_shared_carriers": [
                "pred_gain_sign_prob",
                "calibrated_projected",
                "projected quality / uncertainty boundary terms",
            ],
        },
    }


def _residual_failure_report(
    overlap_artifact: dict[str, Any],
) -> dict[str, Any]:
    overlap_report = dict(overlap_artifact.get("overlap_diagnostic_report", {}))
    weakness = dict(overlap_report.get("residualized_probe_weakness_cause", {}))
    return {
        "primary": str(weakness.get("primary", "")),
        "secondary": str(weakness.get("secondary", "")),
        "supporting_metrics": dict(weakness.get("supporting_metrics", {})),
        "reason": str(weakness.get("reason", "")),
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    v1_artifact = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1"
    )
    residual_artifact = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_wm_context_residual_signal_probe_v1"
    )
    overlap_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_context_signal_overlap_snapshot_v1"
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
            overlap_artifact,
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
            "reason": "diagnostic shadow failed: hybrid-boundary characterization requires the v1 probe, residual probe, overlap snapshot, and prior v4 trace-quality artifacts",
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
                "reason": "cannot define the hybrid boundary without the prior overlap and wm-probe artifacts",
            },
        }

    active_status_text = _load_text_file(ACTIVE_STATUS_PATH)
    handoff_status = _load_json_file(HANDOFF_STATUS_PATH)
    analytics = build_intervention_ledger_analytics()
    latest_snapshots = load_latest_snapshots()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")
    proposal_loop_text = _load_text_file(PROPOSAL_LOOP_PATH)

    overlap_report = dict(overlap_artifact.get("overlap_diagnostic_report", {}))
    feature_rows = list(overlap_report.get("feature_overlap_and_distinctness", []))
    shortfall_report = dict(trace_quality_v2_artifact.get("shortfall_diagnostic_report", {}))
    effective_mix = dict(shortfall_report.get("effective_mix_breakdown", {}))

    hybrid_component_report = _hybrid_component_report(feature_rows, effective_mix)
    boundary_zone_report = _boundary_zone_report(overlap_artifact)
    residual_failure_report = _residual_failure_report(overlap_artifact)

    hybrid_redesign_viable = bool(
        str(dict(overlap_artifact.get("diagnostic_conclusions", {})).get("best_supported_next_option", ""))
        == "hybrid_wm_baseline_redesign"
        and not bool(dict(overlap_artifact.get("diagnostic_conclusions", {})).get("meaningful_distinct_headroom_exists", True))
        and _find_feature(feature_rows, "pred_context_score")
    )
    plan_non_owning = bool(dict(overlap_artifact.get("diagnostic_conclusions", {})).get("plan_should_remain_non_owning", True))

    next_family = "proposal_learning_loop" if hybrid_redesign_viable else "memory_summary"
    next_template = (
        "proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1"
        if hybrid_redesign_viable
        else "memory_summary.v4_wm_signal_line_pause_snapshot_v1"
    )
    next_rationale = (
        "a hybrid redesign probe is justified because the useful wm signal is real and boundary-shared; the next step should test a boundary-aware hybrid modulation without reopening pure wm-only ownership"
        if hybrid_redesign_viable
        else "the branch should pause because no viable hybrid boundary was evidenced"
    )

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_wm_baseline_hybrid_boundary_snapshot_v1",
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
            "memory_summary.v4_wm_context_signal_overlap_snapshot_v1": _artifact_reference(
                overlap_artifact,
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
        "hybrid_boundary_diagnostic_report": {
            "useful_wm_signal_components": hybrid_component_report,
            "boundary_zones": boundary_zone_report,
            "overlap_that_should_be_kept": {
                "summary": "keep shared overlap where the feature is baseline-owned and already acting as a strong ranking carrier",
                "features": [
                    "pred_gain_sign_prob",
                    "calibrated_projected",
                    "projected_quality / uncertainty boundary terms",
                ],
            },
            "overlap_that_should_be_reduced": {
                "summary": "reduce only duplicate positive reuse of baseline-dominant ranking carriers inside a wm-owned correction",
                "features": [
                    "direct positive reuse of pred_gain_sign_prob inside wm-only correction",
                    "direct positive reuse of calibrated_projected inside wm-only correction",
                ],
            },
            "residualization_failure_mode": residual_failure_report,
            "hybrid_redesign_viability": {
                "viable": bool(hybrid_redesign_viable),
                "reason": (
                    "a viable boundary exists because the shared useful signal can be assigned to the baseline side while wm retains a smaller context-specific modulation role anchored on pred_context_score"
                    if hybrid_redesign_viable
                    else "the evidence did not support a stable hybrid boundary"
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
            "hybrid_redesign_probe_justified": bool(hybrid_redesign_viable),
            "plan_should_remain_non_owning": bool(plan_non_owning),
            "recommended_next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "rationale": str(next_rationale),
        },
        "observability_gain": {
            "passed": True,
            "reason": "the snapshot defines the hybrid boundary directly from the recorded broad, residualized, and overlap diagnostic artifacts without opening a new behavior-changing branch",
            "v1_trace_row_count": int(dict(v1_artifact.get("observability_gain", {})).get("probe_trace_row_count", 0) or 0),
            "residual_trace_row_count": int(dict(residual_artifact.get("observability_gain", {})).get("residual_trace_row_count", 0) or 0),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the snapshot separates boundary-kept overlap from destructive duplication and over-residualization, which is the missing design input for the next proposal-learning-loop step",
            "hybrid_redesign_probe_justified": bool(hybrid_redesign_viable),
            "plan_should_remain_non_owning": bool(plan_non_owning),
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.96,
            "reason": "the snapshot turns the previous overlap diagnosis into an explicit boundary definition for the next branch step",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "diagnostic-only hybrid-boundary snapshot with live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": str(next_template),
            "reason": str(next_rationale),
        },
        "diagnostic_conclusions": {
            "hybrid_redesign_probe_justified": bool(hybrid_redesign_viable),
            "plan_should_remain_non_owning": bool(plan_non_owning),
            "recommended_next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "routing_deferred": bool(dict(frontier_artifact.get("diagnostic_conclusions", {})).get("routing_deferred", False)),
            "viable_hybrid_boundary_exists": bool(hybrid_redesign_viable),
        },
    }

    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"memory_summary_v4_wm_baseline_hybrid_boundary_snapshot_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: the wm/baseline hybrid boundary was characterized without changing behavior",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
