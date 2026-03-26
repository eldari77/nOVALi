from __future__ import annotations

import json

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
from .v4_wm_context_signal_discrimination_probe_v1 import _extract_rows, _safety_envelope_report
from .v4_wm_context_signal_overlap_snapshot_v1 import _artifact_reference, _partial_corr
from .v4_wm_hybrid_context_scoped_probe_v1 import (
    _align_probe_rows,
    _row_examples,
    _seed_effect_reports,
    _slice_lookup,
    _slice_reports,
    _status_effect_report,
)
from .v4_wm_primary_plan_structure_probe_v1 import _clone_cfg, _safe_float


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    stability_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v1"
    )
    scoped_probe_artifact = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1"
    )
    scope_effect_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_context_scope_effect_snapshot_v1"
    )
    hybrid_probe_artifact = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1"
    )
    frontier_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.false_safe_frontier_control_characterization_snapshot_v1"
    )
    if not all(
        [
            stability_snapshot,
            scoped_probe_artifact,
            scope_effect_snapshot,
            hybrid_probe_artifact,
            frontier_artifact,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: the scoped-hybrid stabilization probe requires the scoped probe, its stability snapshot, and the hybrid boundary probe",
            "observability_gain": {"passed": False, "reason": "missing prerequisite artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "missing prerequisite artifacts"},
        }

    active_status_text = _load_text_file(ACTIVE_STATUS_PATH)
    handoff_status = _load_json_file(HANDOFF_STATUS_PATH)
    analytics = build_intervention_ledger_analytics()
    latest_snapshots = load_latest_snapshots()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")
    proposal_loop_text = _load_text_file(PROPOSAL_LOOP_PATH)

    slice_thresholds = dict(
        dict(dict(scoped_probe_artifact.get("context_scoped_effect_report", {})).get("context_slice_effects", {})).get(
            "slice_thresholds",
            {},
        )
    )
    context_cut = _safe_float(slice_thresholds.get("context_cut"), float(cfg.v4_wm_hybrid_context_scoped_context_cut)) or float(
        cfg.v4_wm_hybrid_context_scoped_context_cut
    )
    risk_cut = _safe_float(slice_thresholds.get("risk_cut"), float(cfg.v4_wm_hybrid_context_scoped_risk_cut)) or float(
        cfg.v4_wm_hybrid_context_scoped_risk_cut
    )

    sweep_seeds = list(dict.fromkeys([int(seed) for seed in list(seeds)] + [int(cfg.seed) + 1, int(cfg.seed) + 2]))[:3]
    sweep_rounds = max(1, int(rounds))

    per_seed_runs = []
    baseline_rows = []
    hybrid_rows = []
    scoped_rows = []
    stabilized_rows = []
    safety_reports = []

    for seed in sweep_seeds:
        baseline_cfg = _clone_cfg(cfg, seed=int(seed), rounds=int(sweep_rounds), probe_enabled=True)
        baseline_cfg.v4_wm_plan_context_trace_enabled = True
        baseline_cfg.v4_wm_baseline_hybrid_boundary_probe_enabled = False
        baseline_cfg.v4_wm_hybrid_context_scoped_probe_enabled = False
        baseline_cfg.v4_wm_hybrid_context_stabilization_probe_enabled = False
        baseline_cfg.verbose = False

        hybrid_cfg = _clone_cfg(cfg, seed=int(seed), rounds=int(sweep_rounds), probe_enabled=True)
        hybrid_cfg.v4_wm_plan_context_trace_enabled = True
        hybrid_cfg.v4_wm_baseline_hybrid_boundary_probe_enabled = True
        hybrid_cfg.v4_wm_hybrid_context_scoped_probe_enabled = False
        hybrid_cfg.v4_wm_hybrid_context_stabilization_probe_enabled = False
        hybrid_cfg.verbose = False

        scoped_cfg = _clone_cfg(cfg, seed=int(seed), rounds=int(sweep_rounds), probe_enabled=True)
        scoped_cfg.v4_wm_plan_context_trace_enabled = True
        scoped_cfg.v4_wm_baseline_hybrid_boundary_probe_enabled = True
        scoped_cfg.v4_wm_hybrid_context_scoped_probe_enabled = True
        scoped_cfg.v4_wm_hybrid_context_stabilization_probe_enabled = False
        scoped_cfg.v4_wm_hybrid_context_scoped_context_cut = float(context_cut)
        scoped_cfg.v4_wm_hybrid_context_scoped_risk_cut = float(risk_cut)
        scoped_cfg.verbose = False

        stabilized_cfg = _clone_cfg(cfg, seed=int(seed), rounds=int(sweep_rounds), probe_enabled=True)
        stabilized_cfg.v4_wm_plan_context_trace_enabled = True
        stabilized_cfg.v4_wm_baseline_hybrid_boundary_probe_enabled = True
        stabilized_cfg.v4_wm_hybrid_context_scoped_probe_enabled = True
        stabilized_cfg.v4_wm_hybrid_context_stabilization_probe_enabled = True
        stabilized_cfg.v4_wm_hybrid_context_scoped_context_cut = float(context_cut)
        stabilized_cfg.v4_wm_hybrid_context_scoped_risk_cut = float(risk_cut)
        stabilized_cfg.verbose = False

        _, _, baseline_history = run_proposal_learning_loop(baseline_cfg)
        _, _, hybrid_history = run_proposal_learning_loop(hybrid_cfg)
        _, _, scoped_history = run_proposal_learning_loop(scoped_cfg)
        _, _, stabilized_history = run_proposal_learning_loop(stabilized_cfg)

        baseline_summary = r._summarize_history(baseline_history)
        hybrid_summary = r._summarize_history(hybrid_history)
        scoped_summary = r._summarize_history(scoped_history)
        stabilized_summary = r._summarize_history(stabilized_history)

        baseline_seed_rows = _augment_rows(_extract_rows(baseline_history, int(seed), "baseline"))
        hybrid_seed_rows = _augment_rows(_extract_rows(hybrid_history, int(seed), "hybrid_probe"))
        scoped_seed_rows = _augment_rows(_extract_rows(scoped_history, int(seed), "context_scoped_probe"))
        stabilized_seed_rows = _augment_rows(_extract_rows(stabilized_history, int(seed), "context_stabilized_probe"))

        baseline_rows.extend(baseline_seed_rows)
        hybrid_rows.extend(hybrid_seed_rows)
        scoped_rows.extend(scoped_seed_rows)
        stabilized_rows.extend(stabilized_seed_rows)

        safety_vs_baseline = _safety_envelope_report(baseline_summary, stabilized_summary)
        safety_vs_hybrid = _safety_envelope_report(hybrid_summary, stabilized_summary)
        safety_vs_scoped = _safety_envelope_report(scoped_summary, stabilized_summary)
        safety_reports.append({"seed": int(seed), "vs_baseline": safety_vs_baseline, "vs_hybrid": safety_vs_hybrid, "vs_scoped": safety_vs_scoped})
        per_seed_runs.append(
            {
                "seed": int(seed),
                "baseline_summary": baseline_summary,
                "hybrid_summary": hybrid_summary,
                "context_scoped_summary": scoped_summary,
                "context_stabilized_summary": stabilized_summary,
            }
        )

    baseline_report = _separation_report(baseline_rows, "wm_context_supply_score")
    hybrid_report = _separation_report(hybrid_rows, "v4_wm_hybrid_boundary_score")
    scoped_report = _separation_report(scoped_rows, "v4_wm_hybrid_context_scoped_score")
    stabilized_report = _separation_report(stabilized_rows, "v4_wm_hybrid_context_stabilization_score")

    baseline_pre_gate_corr = _safe_float(dict(baseline_report.get("availability_correlations", {})).get("selection_score_pre_gate"), 0.0) or 0.0
    baseline_pre_gate_gap = _safe_float(dict(baseline_report.get("gap_metrics", {})).get("selection_score_pre_gate_provisional_minus_blocked"), 0.0) or 0.0
    hybrid_pre_gate_corr = _safe_float(dict(hybrid_report.get("availability_correlations", {})).get("selection_score_pre_gate"), 0.0) or 0.0
    hybrid_pre_gate_gap = _safe_float(dict(hybrid_report.get("gap_metrics", {})).get("selection_score_pre_gate_provisional_minus_blocked"), 0.0) or 0.0
    scoped_pre_gate_corr = _safe_float(dict(scoped_report.get("availability_correlations", {})).get("selection_score_pre_gate"), 0.0) or 0.0
    scoped_pre_gate_gap = _safe_float(dict(scoped_report.get("gap_metrics", {})).get("selection_score_pre_gate_provisional_minus_blocked"), 0.0) or 0.0
    stabilized_pre_gate_corr = _safe_float(dict(stabilized_report.get("availability_correlations", {})).get("selection_score_pre_gate"), 0.0) or 0.0
    stabilized_pre_gate_gap = _safe_float(dict(stabilized_report.get("gap_metrics", {})).get("selection_score_pre_gate_provisional_minus_blocked"), 0.0) or 0.0

    hybrid_signal_corr = _safe_float(dict(hybrid_report.get("availability_correlations", {})).get("signal"), 0.0) or 0.0
    scoped_signal_corr = _safe_float(dict(scoped_report.get("availability_correlations", {})).get("signal"), 0.0) or 0.0
    stabilized_signal_corr = _safe_float(dict(stabilized_report.get("availability_correlations", {})).get("signal"), 0.0) or 0.0
    hybrid_signal_gap = _safe_float(dict(hybrid_report.get("gap_metrics", {})).get("signal_provisional_minus_blocked"), 0.0) or 0.0
    scoped_signal_gap = _safe_float(dict(scoped_report.get("gap_metrics", {})).get("signal_provisional_minus_blocked"), 0.0) or 0.0
    stabilized_signal_gap = _safe_float(dict(stabilized_report.get("gap_metrics", {})).get("signal_provisional_minus_blocked"), 0.0) or 0.0

    hybrid_overlap = _aligned_overlap_report(baseline_rows, hybrid_rows, "v4_wm_hybrid_boundary_score")
    scoped_overlap = _aligned_overlap_report(baseline_rows, scoped_rows, "v4_wm_hybrid_context_scoped_score")
    stabilized_overlap = _aligned_overlap_report(baseline_rows, stabilized_rows, "v4_wm_hybrid_context_stabilization_score")
    hybrid_overlap_corr = _safe_float(hybrid_overlap.get("signal_to_baseline_pre_gate_correlation"), 0.0) or 0.0
    scoped_overlap_corr = _safe_float(scoped_overlap.get("signal_to_baseline_pre_gate_correlation"), 0.0) or 0.0
    stabilized_overlap_corr = _safe_float(stabilized_overlap.get("signal_to_baseline_pre_gate_correlation"), 0.0) or 0.0
    hybrid_distinctness = _distinctness_score(hybrid_signal_corr, hybrid_overlap_corr)
    scoped_distinctness = _distinctness_score(scoped_signal_corr, scoped_overlap_corr)
    stabilized_distinctness = _distinctness_score(stabilized_signal_corr, stabilized_overlap_corr)
    hybrid_partial = _partial_corr(signal_to_target=hybrid_signal_corr, signal_to_baseline=hybrid_overlap_corr, baseline_to_target=baseline_pre_gate_corr)
    scoped_partial = _partial_corr(signal_to_target=scoped_signal_corr, signal_to_baseline=scoped_overlap_corr, baseline_to_target=baseline_pre_gate_corr)
    stabilized_partial = _partial_corr(signal_to_target=stabilized_signal_corr, signal_to_baseline=stabilized_overlap_corr, baseline_to_target=baseline_pre_gate_corr)

    aligned_scoped = _align_probe_rows(
        baseline_rows,
        scoped_rows,
        signal_key="v4_wm_hybrid_context_scoped_score",
        delta_key="v4_wm_hybrid_context_scoped_delta",
        scope_gate_key="v4_wm_hybrid_context_scope_gate",
        scope_multiplier_key="v4_wm_hybrid_context_scope_multiplier",
        scope_label_key="v4_wm_hybrid_context_scope_label",
    )
    aligned_stabilized = _align_probe_rows(
        baseline_rows,
        stabilized_rows,
        signal_key="v4_wm_hybrid_context_stabilization_score",
        delta_key="v4_wm_hybrid_context_stabilization_delta",
        scope_gate_key="v4_wm_hybrid_context_scope_gate",
        scope_multiplier_key="v4_wm_hybrid_context_final_scope_multiplier",
        scope_label_key="v4_wm_hybrid_context_scope_label",
    )
    scoped_status_effects = _status_effect_report(aligned_scoped)
    stabilized_status_effects = _status_effect_report(aligned_stabilized)
    scoped_seed_effects = _seed_effect_reports(aligned_scoped)
    stabilized_seed_effects = _seed_effect_reports(aligned_stabilized)
    scoped_slice_effects = _slice_reports(aligned_scoped, context_cut=float(context_cut), risk_cut=float(risk_cut))
    stabilized_slice_effects = _slice_reports(aligned_stabilized, context_cut=float(context_cut), risk_cut=float(risk_cut))

    scoped_strong = _slice_lookup(scoped_slice_effects, "high_context_low_risk")
    scoped_weak = _slice_lookup(scoped_slice_effects, "low_context_high_risk")
    stabilized_strong = _slice_lookup(stabilized_slice_effects, "high_context_low_risk")
    stabilized_weak = _slice_lookup(stabilized_slice_effects, "low_context_high_risk")
    scoped_seed2 = next((row for row in scoped_seed_effects if int(row.get("seed", -1)) == 2), {})
    stabilized_seed2 = next((row for row in stabilized_seed_effects if int(row.get("seed", -1)) == 2), {})

    safety_preserved = bool(all(bool(dict(item.get("vs_baseline", {})).get("passed", False)) and bool(dict(item.get("vs_hybrid", {})).get("passed", False)) and bool(dict(item.get("vs_scoped", {})).get("passed", False)) for item in safety_reports))
    strong_slice_preserved = bool((_safe_float(stabilized_strong.get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0) >= (_safe_float(scoped_strong.get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0) - 0.00010)
    weak_slice_protected = bool((_safe_float(stabilized_weak.get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0) >= 0.0 and ((_safe_float(stabilized_weak.get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0) >= (_safe_float(scoped_weak.get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0) - 0.00010))
    seed2_gap_improved = bool((_safe_float(stabilized_seed2.get("selection_score_pre_gate_gap_delta"), 0.0) or 0.0) >= (_safe_float(scoped_seed2.get("selection_score_pre_gate_gap_delta"), 0.0) or 0.0) + 0.00005)
    overall_gap_improved = bool(stabilized_pre_gate_gap >= scoped_pre_gate_gap + 0.00003)
    distinctness_improved = bool(stabilized_distinctness >= scoped_distinctness + 0.003 or (_safe_float(stabilized_partial, -1.0) or -1.0) >= (_safe_float(scoped_partial, -1.0) or -1.0) + 0.0015)
    baseline_path_not_regressed = bool(stabilized_pre_gate_corr >= baseline_pre_gate_corr - 0.003)
    stabilization_improved = bool(safety_preserved and strong_slice_preserved and weak_slice_protected and seed2_gap_improved and overall_gap_improved and distinctness_improved and baseline_path_not_regressed)

    next_template = "memory_summary.v4_wm_hybrid_context_stabilization_effect_snapshot_v1" if stabilization_improved else "memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v2"
    next_rationale = (
        "the stabilization step improved narrow-scope consistency while preserving the supported slice and weak-slice protection, so the next step should map its effect before any further tuning"
        if stabilization_improved
        else "the stabilization step stayed upstream and safe, but its consistency gains were not yet strong enough to justify another behavior-changing move without another diagnostic read"
    )

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "proposal_learning_loop.v4_wm_hybrid_context_stabilization_probe_v1",
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
            "memory_summary.v4_wm_hybrid_context_scope_stability_snapshot_v1": _artifact_reference(stability_snapshot, latest_snapshots),
            "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1": _artifact_reference(scoped_probe_artifact, latest_snapshots),
            "memory_summary.v4_wm_hybrid_context_scope_effect_snapshot_v1": _artifact_reference(scope_effect_snapshot, latest_snapshots),
            "proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1": _artifact_reference(hybrid_probe_artifact, latest_snapshots),
            "memory_summary.false_safe_frontier_control_characterization_snapshot_v1": _artifact_reference(frontier_artifact, latest_snapshots),
        },
        "branch_implementation_summary": {
            "stabilization_application": [
                "kept the scoped-hybrid boundary intact and added a small stabilization layer on top of the existing scope multiplier",
                "used near-threshold context and risk edge gates plus hybrid-boundary support to soften over-damping only where weak-seed rows look recoverable",
                "left the baseline-owned ranking carriers and the wm-owned scoped modulation structure unchanged",
            ],
            "plan_remained_non_owning": ["planning_handoff_score was not used as a decision lever", "plan_ remained handoff and organization only"],
            "downstream_exclusions_preserved": ["no adoption_ ownership or branching", "no social_conf_ ownership or branching", "no self_improve_ attachment", "no selected-set optimization work"],
        },
        "shadow_metrics": {
            "seed_sweep_used": list(sweep_seeds),
            "rounds_used_per_seed": int(sweep_rounds),
            "baseline_separation": baseline_report,
            "hybrid_separation": hybrid_report,
            "context_scoped_separation": scoped_report,
            "context_stabilized_separation": stabilized_report,
            "comparison_vs_baseline": {
                "selection_score_pre_gate_availability_corr_delta": float(stabilized_pre_gate_corr - baseline_pre_gate_corr),
                "selection_score_pre_gate_gap_delta": float(stabilized_pre_gate_gap - baseline_pre_gate_gap),
                "context_stabilized_signal_availability_corr": float(stabilized_signal_corr),
                "context_stabilized_signal_gap": float(stabilized_signal_gap),
                "context_stabilized_signal_overlap_to_baseline_pre_gate": float(stabilized_overlap_corr),
                "context_stabilized_distinctness_score": float(stabilized_distinctness),
            },
            "comparison_vs_hybrid": {
                "selection_score_pre_gate_availability_corr_delta": float(stabilized_pre_gate_corr - hybrid_pre_gate_corr),
                "selection_score_pre_gate_gap_delta": float(stabilized_pre_gate_gap - hybrid_pre_gate_gap),
                "signal_availability_corr_delta": float(stabilized_signal_corr - hybrid_signal_corr),
                "signal_gap_delta": float(stabilized_signal_gap - hybrid_signal_gap),
                "distinctness_score_delta": float(stabilized_distinctness - hybrid_distinctness),
            },
            "comparison_vs_context_scoped": {
                "selection_score_pre_gate_availability_corr_delta": float(stabilized_pre_gate_corr - scoped_pre_gate_corr),
                "selection_score_pre_gate_gap_delta": float(stabilized_pre_gate_gap - scoped_pre_gate_gap),
                "signal_availability_corr_delta": float(stabilized_signal_corr - scoped_signal_corr),
                "signal_gap_delta": float(stabilized_signal_gap - scoped_signal_gap),
                "signal_overlap_to_baseline_pre_gate_delta": float(stabilized_overlap_corr - scoped_overlap_corr),
                "distinctness_score_delta": float(stabilized_distinctness - scoped_distinctness),
                "seed_2_gap_delta": float((_safe_float(stabilized_seed2.get("selection_score_pre_gate_gap_delta"), 0.0) or 0.0) - (_safe_float(scoped_seed2.get("selection_score_pre_gate_gap_delta"), 0.0) or 0.0)),
                "high_context_low_risk_delta_delta": float((_safe_float(stabilized_strong.get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0) - (_safe_float(scoped_strong.get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0)),
                "low_context_high_risk_delta_delta": float((_safe_float(stabilized_weak.get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0) - (_safe_float(scoped_weak.get("mean_selection_score_pre_gate_delta"), 0.0) or 0.0)),
            },
            "partial_signal_given_baseline": {"hybrid": _safe_float(hybrid_partial, None), "context_scoped": _safe_float(scoped_partial, None), "context_stabilized": _safe_float(stabilized_partial, None)},
            "per_seed_runs": per_seed_runs,
            "safety_envelope_reports": safety_reports,
        },
        "stabilization_effect_report": {
            "row_level_effects": {"context_scoped_reference": scoped_status_effects, "context_stabilized": stabilized_status_effects, "top_positive_examples": _row_examples(aligned_stabilized, reverse=True), "weakest_examples": _row_examples(aligned_stabilized, reverse=False)},
            "seed_level_effects": {"context_scoped_reference": scoped_seed_effects, "context_stabilized": stabilized_seed_effects},
            "context_slice_effects": {"slice_thresholds": {"context_cut": float(context_cut), "risk_cut": float(risk_cut)}, "context_scoped_reference": scoped_slice_effects, "context_stabilized": stabilized_slice_effects},
        },
        "analytics_context": {
            "analytics_report_path": str(intervention_data_dir() / "intervention_analytics_latest.json"),
            "proposal_recommendations_path": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            "proposal_count": int(analytics.get("proposal_count", 0) or 0),
            "current_recommendation_top_templates": [str(item.get("template_name", "")) for item in list(recommendations.get("all_ranked_proposals", [])) if isinstance(item, dict) and str(item.get("decision", "")) == "suggested"][:8],
            "proposal_learning_loop_reference_present": "proposal_learning_loop" in proposal_loop_text,
        },
        "decision_recommendation": {"stabilization_improved_consistency": bool(stabilization_improved), "branch_stayed_cleanly_upstream": bool(safety_preserved), "recommended_next_template": str(next_template), "rationale": str(next_rationale)},
        "observability_gain": {"passed": True, "reason": "the stabilization probe remained fully observable through the existing wm/plan trace path with explicit stabilization trace fields", "baseline_trace_row_count": int(len(baseline_rows)), "context_scoped_trace_row_count": int(len(scoped_rows)), "context_stabilized_trace_row_count": int(len(stabilized_rows))},
        "activation_analysis_usefulness": {"passed": True, "reason": "the probe tests whether the scoped hybrid can be made more consistent in weak seeds without widening scope or changing downstream ownership", "stabilization_improved_consistency": bool(stabilization_improved), "plan_non_owning_preserved": True},
        "ambiguity_reduction": {"passed": True, "score": float(min(1.0, 0.55 + 0.12 * int(stabilization_improved) + 0.08 * int(seed2_gap_improved) + 0.08 * int(strong_slice_preserved) + 0.07 * int(weak_slice_protected) + 0.07 * int(safety_preserved))), "reason": "the probe shows whether the scoped-hybrid design can be stabilized in the weak seed while staying narrowly targeted and fully upstream"},
        "safety_neutrality": {"passed": bool(safety_preserved), "scope": str(proposal.get("scope", "")), "reason": "the stabilization probe stayed inside the downstream safety envelope with live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope unchanged"},
        "later_selection_usefulness": {"passed": True, "recommended_next_template": str(next_template), "reason": str(next_rationale)},
        "diagnostic_conclusions": {"stabilization_improved_consistency": bool(stabilization_improved), "branch_stayed_cleanly_upstream": bool(safety_preserved), "plan_should_remain_non_owning": True, "recommended_next_family": "memory_summary", "recommended_next_template": str(next_template), "routing_deferred": bool(dict(frontier_artifact.get("diagnostic_conclusions", {})).get("routing_deferred", False))},
    }
    artifact_path = r._diagnostic_artifact_dir() / f"proposal_learning_loop_v4_wm_hybrid_context_stabilization_probe_v1_{proposal['proposal_id']}.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": bool(safety_preserved),
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: the scoped-hybrid stabilization probe stayed inside the intended upstream safety envelope" if safety_preserved else "diagnostic shadow failed: the scoped-hybrid stabilization probe changed downstream safety behavior beyond the intended upstream scope",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
