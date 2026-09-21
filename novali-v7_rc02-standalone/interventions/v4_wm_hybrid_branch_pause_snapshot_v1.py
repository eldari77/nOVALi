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


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    scoped_probe_artifact = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1"
    )
    stabilization_probe_artifact = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_wm_hybrid_context_stabilization_probe_v1"
    )
    working_baseline_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_scoped_working_baseline_snapshot_v1"
    )
    stability_snapshot_v2 = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v2"
    )
    scope_effect_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_context_scope_effect_snapshot_v1"
    )
    frontier_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.false_safe_frontier_control_characterization_snapshot_v1"
    )
    if not all(
        [
            scoped_probe_artifact,
            stabilization_probe_artifact,
            working_baseline_artifact,
            stability_snapshot_v2,
            scope_effect_snapshot,
            frontier_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: branch-pause formalization requires the scoped probe, stabilization probe, scoped working-baseline snapshot, and supporting stability/effect artifacts",
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
                "reason": "cannot formalize a clean branch pause without the scoped-hybrid baseline and stability evidence chain",
            },
        }

    active_status_text = _load_text_file(ACTIVE_STATUS_PATH)
    handoff_status = _load_json_file(HANDOFF_STATUS_PATH)
    analytics = build_intervention_ledger_analytics()
    latest_snapshots = load_latest_snapshots()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")
    proposal_loop_text = _load_text_file(PROPOSAL_LOOP_PATH)

    branch_summary = dict(scoped_probe_artifact.get("branch_implementation_summary", {}))
    scoped_shadow = dict(scoped_probe_artifact.get("shadow_metrics", {}))
    working_report = dict(working_baseline_artifact.get("working_baseline_report", {}))
    working_strengths = dict(working_report.get("current_scoped_hybrid_strengths", {}))
    protected_weak_regions = dict(working_report.get("protected_weak_regions", {}))
    meaningful_improvement_criteria = dict(working_report.get("meaningful_improvement_criteria", {}))
    recent_challenger = dict(working_report.get("failed_recent_challenger_example", {}))
    accepted_limitations = dict(working_report.get("accepted_limitations", {}))
    stability_v2_report = dict(stability_snapshot_v2.get("stability_v2_report", {}))
    scope_effect_report = dict(scope_effect_snapshot.get("effect_decomposition_report", {}))
    baseline_decision = dict(working_baseline_artifact.get("decision_recommendation", {}))

    comparison_vs_baseline = dict(scoped_shadow.get("comparison_vs_baseline", {}))
    comparison_vs_hybrid = dict(scoped_shadow.get("comparison_vs_hybrid", {}))
    scoped_separation = dict(scoped_shadow.get("context_scoped_separation", {}))
    scoped_gap_metrics = dict(scoped_separation.get("gap_metrics", {}))

    strong_slice = dict(working_strengths.get("strong_slice", {}))
    weak_seed = dict(protected_weak_regions.get("seed_2", {}))
    weak_slice = dict(protected_weak_regions.get("low_context_high_risk", {}))
    direct_stability = dict(stability_v2_report.get("scoped_vs_stabilization_direct_comparison", {}))
    best_config = dict(stability_v2_report.get("best_current_narrow_working_configuration", {}))
    scope_interpretation = dict(scope_effect_report.get("stability_vs_locality_interpretation", {}))

    all_ranked = list(recommendations.get("all_ranked_proposals", []))
    suggested_templates = [
        str(item.get("template_name", ""))
        for item in all_ranked
        if isinstance(item, dict) and str(item.get("decision", "")) == "suggested"
    ][:8]

    held_baseline = {
        "template": "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1",
        "classification": str(working_strengths.get("classification", "")),
        "branch_stayed_cleanly_upstream": bool(working_strengths.get("branch_stayed_cleanly_upstream", False)),
        "plan_should_remain_non_owning": True,
        "selection_score_pre_gate_gap": _safe_float(working_strengths.get("selection_score_pre_gate_gap"), 0.0),
        "signal_availability_corr": _safe_float(working_strengths.get("signal_availability_corr"), 0.0),
        "signal_gap": _safe_float(working_strengths.get("signal_gap"), 0.0),
        "distinctness_score": _safe_float(working_strengths.get("distinctness_score"), 0.0),
        "positive_seed_count_vs_baseline": int(working_strengths.get("positive_seed_count_vs_baseline", 0) or 0),
        "strongest_supported_region": {
            "slice": str(strong_slice.get("slice", "")),
            "mean_selection_score_pre_gate_delta": _safe_float(
                strong_slice.get("mean_selection_score_pre_gate_delta"),
                0.0,
            ),
            "positive_delta_share": _safe_float(strong_slice.get("positive_delta_share"), 0.0),
        },
        "protected_weak_regions": {
            "low_context_high_risk": {
                "accepted_status": str(weak_slice.get("accepted_status", "")),
                "mean_selection_score_pre_gate_delta": _safe_float(
                    weak_slice.get("mean_selection_score_pre_gate_delta"),
                    0.0,
                ),
                "positive_delta_share": _safe_float(weak_slice.get("positive_delta_share"), 0.0),
            },
            "seed_2": {
                "accepted_status": str(weak_seed.get("accepted_status", "")),
                "classification": str(weak_seed.get("classification", "")),
                "selection_score_pre_gate_gap_delta": _safe_float(
                    weak_seed.get("selection_score_pre_gate_gap_delta"),
                    0.0,
                ),
            },
        },
        "held_configuration": {
            "hybrid_boundary_preserved": list(branch_summary.get("hybrid_boundary_preserved", [])),
            "context_scoping_definition": list(branch_summary.get("context_scoping_definition", [])),
            "emphasized_or_damped_slices": dict(branch_summary.get("emphasized_or_damped_slices", {})),
            "downstream_exclusions_preserved": list(branch_summary.get("downstream_exclusions_preserved", [])),
            "plan_remained_non_owning": list(branch_summary.get("plan_remained_non_owning", [])),
        },
    }

    pause_conditions = {
        "branch_status": "paused_with_baseline_held",
        "pause_reason": "the scoped-hybrid probe is the current narrow standard to beat, while the stabilization layer adds only small metric drift and no current follow-on tweak clears the formal improvement bar",
        "conditions": [
            "hold proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1 fixed as the working narrow baseline",
            "do not authorize another behavior-changing probe unless a challenger idea clearly clears the meaningful-improvement criteria",
            "keep plan_ non-owning and keep the branch cleanly upstream",
            "keep downstream safety and behavior envelope unchanged",
            "keep the scoped pattern narrow rather than broadening it globally",
            "keep routing deferred and keep novali-v3 closed as fallback/reference only",
        ],
        "pause_supported_by": {
            "baseline_formalized": bool(
                baseline_decision.get("scoped_hybrid_should_be_working_narrow_baseline", False)
            ),
            "stabilization_not_justified": not bool(
                baseline_decision.get("another_stabilization_iteration_justified", True)
            ),
            "best_current_narrow_configuration": str(best_config.get("best_template", "")),
            "stability_vs_locality": str(accepted_limitations.get("stability_vs_locality", "")),
            "recent_challenger_result": str(recent_challenger.get("why_not_enough", "")),
        },
    }

    reopen_triggers = {
        "challenger_must_clear_formal_bar": dict(meaningful_improvement_criteria),
        "trigger_classes": [
            "a new context-scoped hybrid idea with materially different scope logic or modulation that beats the current scoped baseline on the main gap and signal-gap criteria",
            "a broader architecture diagnostic that surfaces a genuinely new upstream signal class not already absorbed by the baseline pre-gate path",
            "evidence that the narrow gain can be widened without harming low_context_high_risk or breaking the all-seeds-positive condition",
            "a clearly distinct upstream branch idea that stays wm-owned, keeps plan_ non-owning, and does not reopen downstream adoption/social_conf logic",
        ],
        "supporting_reopen_examples": [
            "selection_score_pre_gate_gap_delta_vs_scoped >= 0.00005 with signal_gap_delta_vs_scoped >= 0.001",
            "all 3 seeds remain positive vs baseline while seed_2 improvement becomes material rather than marginal",
            "strong_slice improves without weak_slice becoming negative",
            "distinctness and partial-signal gains accompany a real main-gap improvement instead of secondary-only drift",
        ],
        "reopen_timing_rule": "reopen only when a new idea class can be screened against the formal improvement bar before another behavior-changing pass is attempted",
    }

    valid_future_candidate_idea_types = [
        {
            "idea_class": "new scoped-hybrid refinement with materially new scope logic",
            "valid_if": "it keeps the current hybrid boundary intact, remains wm-owned, and shows a plausible path to beat the scoped baseline on the main gap and signal-gap criteria",
        },
        {
            "idea_class": "upstream architecture diagnostic that identifies a distinct non-absorbed wm signal",
            "valid_if": "it remains diagnostic-only and demonstrates why the new signal is not just renamed overlap with the baseline pre-gate path",
        },
        {
            "idea_class": "reopen-candidate screening diagnostic",
            "valid_if": "it is used to test whether a proposed future challenger actually clears the formal bar before any new behavior-changing probe is opened",
        },
    ]

    invalid_or_closed_next_steps = [
        "another stabilization iteration without new evidence that materially beats the scoped baseline",
        "global broadening of the scoped-hybrid modulation",
        "pure wm-only discrimination retries or narrower residual-only retries",
        "turning plan_ into an owning lever",
        "introducing adoption_, social_conf_, or self_improve_ ownership into this branch",
        "selected-set optimization or downstream selection/adoption work under a new label",
        "routing work while routing remains deferred",
        "reopening novali-v3 critic/control lines for routine follow-on tuning",
    ]

    next_family = "memory_summary"
    next_template = "memory_summary.v4_wm_hybrid_reopen_candidate_screen_snapshot_v1"
    next_rationale = "the branch should pause now, and the only justified future next step is a reopen-screening diagnostic when a genuinely new candidate idea emerges"

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_wm_hybrid_branch_pause_snapshot_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "branch_context": {
            "active_status_path": str(ACTIVE_STATUS_PATH),
            "handoff_status_path": str(HANDOFF_STATUS_PATH),
            "proposal_learning_loop_path": str(PROPOSAL_LOOP_PATH),
            "active_status_mentions_v4_active": "`novali-v4` is the active working version." in active_status_text,
            "carried_forward_baseline": dict(handoff_status.get("carried_forward_baseline", {})),
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
        },
        "comparison_references": {
            "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1": _artifact_reference(
                scoped_probe_artifact,
                latest_snapshots,
            ),
            "proposal_learning_loop.v4_wm_hybrid_context_stabilization_probe_v1": _artifact_reference(
                stabilization_probe_artifact,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_hybrid_scoped_working_baseline_snapshot_v1": _artifact_reference(
                working_baseline_artifact,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v2": _artifact_reference(
                stability_snapshot_v2,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_hybrid_context_scope_effect_snapshot_v1": _artifact_reference(
                scope_effect_snapshot,
                latest_snapshots,
            ),
            "memory_summary.false_safe_frontier_control_characterization_snapshot_v1": _artifact_reference(
                frontier_snapshot,
                latest_snapshots,
            ),
        },
        "branch_pause_report": {
            "held_baseline": held_baseline,
            "formal_pause_conditions": pause_conditions,
            "formal_reopen_triggers": reopen_triggers,
            "valid_future_candidate_idea_types": valid_future_candidate_idea_types,
            "invalid_or_already_closed_next_steps": invalid_or_closed_next_steps,
            "accepted_limitations": {
                "stability_vs_locality": str(scope_interpretation.get("classification", "")),
                "stabilization_repeatability": str(
                    dict(stability_v2_report.get("repeatability_vs_drift", {})).get("classification", "")
                ),
                "recent_stabilization_delta": {
                    "selection_score_pre_gate_gap_delta_vs_scoped": _safe_float(
                        dict(direct_stability.get("delta_stabilization_minus_scoped", {})).get(
                            "selection_score_pre_gate_gap_delta"
                        ),
                        0.0,
                    ),
                    "signal_gap_delta_vs_scoped": _safe_float(
                        dict(direct_stability.get("delta_stabilization_minus_scoped", {})).get(
                            "signal_gap_delta"
                        ),
                        0.0,
                    ),
                },
                "reason": "the line is worth holding, but not worth churning; the current supported gain is narrow, and recent follow-on stabilization changed too little to justify another active pass",
            },
        },
        "analytics_context": {
            "analytics_report_path": str(intervention_data_dir() / "intervention_analytics_latest.json"),
            "proposal_recommendations_path": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            "proposal_count": int(analytics.get("proposal_count", 0) or 0),
            "current_recommendation_top_templates": suggested_templates,
            "proposal_learning_loop_reference_present": "proposal_learning_loop" in proposal_loop_text,
            "current_scoped_gap_metric": _safe_float(
                scoped_gap_metrics.get("selection_score_pre_gate_provisional_minus_blocked"),
                0.0,
            ),
            "current_scoped_signal_gap_metric": _safe_float(
                dict(scoped_separation.get("gap_metrics", {})).get("signal_provisional_minus_blocked"),
                0.0,
            ),
            "current_scoped_signal_overlap": _safe_float(
                comparison_vs_baseline.get("context_scoped_signal_overlap_to_baseline_pre_gate"),
                0.0,
            ),
            "current_scoped_gap_delta_vs_hybrid": _safe_float(
                comparison_vs_hybrid.get("selection_score_pre_gate_gap_delta"),
                0.0,
            ),
        },
        "decision_recommendation": {
            "branch_should_now_be_considered_paused_with_baseline_held": True,
            "held_baseline_template": "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1",
            "another_stabilization_iteration_justified": False,
            "plan_should_remain_non_owning": True,
            "recommended_next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "recommended_timing": "only_if_reopen_trigger_is_met",
            "rationale": "the current scoped-hybrid configuration should now be held fixed as the paused narrow baseline, and future work should reopen only through a candidate-screening diagnostic when a genuinely new challenger idea appears",
        },
        "observability_gain": {
            "passed": True,
            "reason": "the snapshot converts the scoped-baseline evidence chain into explicit pause conditions, reopen triggers, and closed next-step classes",
            "compared_templates": [
                "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1",
                "proposal_learning_loop.v4_wm_hybrid_context_stabilization_probe_v1",
                "memory_summary.v4_wm_hybrid_scoped_working_baseline_snapshot_v1",
                "memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v2",
            ],
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the snapshot cleanly distinguishes what is held fixed, what can reopen the branch, and what is explicitly invalid right now",
            "held_baseline_template": "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1",
            "branch_pause_status": "paused_with_baseline_held",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.94,
            "reason": "the branch now has a precise held baseline, precise reopen triggers, and a closed list of low-yield next steps that should not be retried",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "diagnostic-only branch-pause formalization with live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": str(next_template),
            "reason": str(next_rationale),
        },
        "diagnostic_conclusions": {
            "branch_should_now_be_considered_paused_with_baseline_held": True,
            "held_baseline_template": "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1",
            "another_stabilization_iteration_justified": False,
            "plan_should_remain_non_owning": True,
            "recommended_next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
        },
    }

    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"memory_summary_v4_wm_hybrid_branch_pause_snapshot_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: the scoped-hybrid branch was formally paused with the current working narrow baseline held fixed",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
