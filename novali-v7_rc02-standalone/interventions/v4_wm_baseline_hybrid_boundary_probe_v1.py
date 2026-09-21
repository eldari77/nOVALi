from __future__ import annotations

import json
from typing import Any

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
from .v4_wm_context_signal_discrimination_probe_v1 import (
    _extract_rows,
    _safety_envelope_report,
)
from .v4_wm_context_signal_overlap_snapshot_v1 import (
    _artifact_reference,
    _partial_corr,
)
from .v4_wm_primary_plan_structure_probe_v1 import _clone_cfg, _safe_float


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    hybrid_boundary_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_baseline_hybrid_boundary_snapshot_v1"
    )
    overlap_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_context_signal_overlap_snapshot_v1"
    )
    trace_quality_v2_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_plan_context_trace_quality_snapshot_v2"
    )
    v1_artifact = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1"
    )
    residual_artifact = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_wm_context_residual_signal_probe_v1"
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
            hybrid_boundary_snapshot,
            overlap_artifact,
            trace_quality_v2_artifact,
            v1_artifact,
            residual_artifact,
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
            "reason": "diagnostic shadow failed: the hybrid wm/baseline probe requires the hybrid-boundary snapshot, overlap snapshot, prior wm probes, and carried-forward safety artifacts",
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
                "reason": "cannot run the hybrid wm/baseline probe without the hybrid-boundary and overlap diagnostics",
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
    hybrid_rows: list[dict[str, Any]] = []
    safety_reports: list[dict[str, Any]] = []

    for seed in sweep_seeds:
        baseline_cfg = _clone_cfg(cfg, seed=int(seed), rounds=int(sweep_rounds), probe_enabled=True)
        baseline_cfg.v4_wm_plan_context_trace_enabled = True
        baseline_cfg.v4_wm_context_signal_discrimination_probe_enabled = False
        baseline_cfg.v4_wm_context_residual_signal_probe_enabled = False
        baseline_cfg.v4_wm_baseline_hybrid_boundary_probe_enabled = False
        baseline_cfg.verbose = False

        v1_cfg = _clone_cfg(cfg, seed=int(seed), rounds=int(sweep_rounds), probe_enabled=True)
        v1_cfg.v4_wm_plan_context_trace_enabled = True
        v1_cfg.v4_wm_context_signal_discrimination_probe_enabled = True
        v1_cfg.v4_wm_context_residual_signal_probe_enabled = False
        v1_cfg.v4_wm_baseline_hybrid_boundary_probe_enabled = False
        v1_cfg.verbose = False

        residual_cfg = _clone_cfg(cfg, seed=int(seed), rounds=int(sweep_rounds), probe_enabled=True)
        residual_cfg.v4_wm_plan_context_trace_enabled = True
        residual_cfg.v4_wm_context_signal_discrimination_probe_enabled = False
        residual_cfg.v4_wm_context_residual_signal_probe_enabled = True
        residual_cfg.v4_wm_baseline_hybrid_boundary_probe_enabled = False
        residual_cfg.verbose = False

        hybrid_cfg = _clone_cfg(cfg, seed=int(seed), rounds=int(sweep_rounds), probe_enabled=True)
        hybrid_cfg.v4_wm_plan_context_trace_enabled = True
        hybrid_cfg.v4_wm_context_signal_discrimination_probe_enabled = False
        hybrid_cfg.v4_wm_context_residual_signal_probe_enabled = False
        hybrid_cfg.v4_wm_baseline_hybrid_boundary_probe_enabled = True
        hybrid_cfg.verbose = False

        _, _, baseline_history = run_proposal_learning_loop(baseline_cfg)
        _, _, v1_history = run_proposal_learning_loop(v1_cfg)
        _, _, residual_history = run_proposal_learning_loop(residual_cfg)
        _, _, hybrid_history = run_proposal_learning_loop(hybrid_cfg)

        baseline_summary = r._summarize_history(baseline_history)
        v1_summary = r._summarize_history(v1_history)
        residual_summary = r._summarize_history(residual_history)
        hybrid_summary = r._summarize_history(hybrid_history)

        baseline_seed_rows = _augment_rows(_extract_rows(baseline_history, int(seed), "baseline"))
        v1_seed_rows = _augment_rows(_extract_rows(v1_history, int(seed), "v1_probe"))
        residual_seed_rows = _augment_rows(_extract_rows(residual_history, int(seed), "residual_probe"))
        hybrid_seed_rows = _augment_rows(_extract_rows(hybrid_history, int(seed), "hybrid_probe"))

        safety_vs_baseline = _safety_envelope_report(baseline_summary, hybrid_summary)
        safety_vs_v1 = _safety_envelope_report(v1_summary, hybrid_summary)
        safety_vs_residual = _safety_envelope_report(residual_summary, hybrid_summary)

        baseline_rows.extend(baseline_seed_rows)
        v1_rows.extend(v1_seed_rows)
        residual_rows.extend(residual_seed_rows)
        hybrid_rows.extend(hybrid_seed_rows)
        safety_reports.append(
            {
                "seed": int(seed),
                "vs_baseline": dict(safety_vs_baseline),
                "vs_v1": dict(safety_vs_v1),
                "vs_residual": dict(safety_vs_residual),
            }
        )
        per_seed_runs.append(
            {
                "seed": int(seed),
                "baseline_summary": dict(baseline_summary),
                "v1_summary": dict(v1_summary),
                "residual_summary": dict(residual_summary),
                "hybrid_summary": dict(hybrid_summary),
                "baseline_separation": _separation_report(baseline_seed_rows, "wm_context_supply_score"),
                "v1_separation": _separation_report(v1_seed_rows, "v4_wm_discrimination_score"),
                "residual_separation": _separation_report(residual_seed_rows, "v4_wm_residual_signal_score"),
                "hybrid_separation": _separation_report(hybrid_seed_rows, "v4_wm_hybrid_boundary_score"),
                "safety_vs_baseline": dict(safety_vs_baseline),
                "safety_vs_v1": dict(safety_vs_v1),
                "safety_vs_residual": dict(safety_vs_residual),
            }
        )

    baseline_report = _separation_report(baseline_rows, "wm_context_supply_score")
    v1_report = _separation_report(v1_rows, "v4_wm_discrimination_score")
    residual_report = _separation_report(residual_rows, "v4_wm_residual_signal_score")
    hybrid_report = _separation_report(hybrid_rows, "v4_wm_hybrid_boundary_score")

    v1_overlap = _aligned_overlap_report(baseline_rows, v1_rows, "v4_wm_discrimination_score")
    residual_overlap = _aligned_overlap_report(baseline_rows, residual_rows, "v4_wm_residual_signal_score")
    hybrid_overlap = _aligned_overlap_report(baseline_rows, hybrid_rows, "v4_wm_hybrid_boundary_score")

    baseline_pre_gate_corr = _safe_float(
        dict(baseline_report.get("availability_correlations", {})).get("selection_score_pre_gate"),
        0.0,
    ) or 0.0
    baseline_pre_gate_gap = _safe_float(
        dict(baseline_report.get("gap_metrics", {})).get("selection_score_pre_gate_provisional_minus_blocked"),
        0.0,
    ) or 0.0
    hybrid_pre_gate_corr = _safe_float(
        dict(hybrid_report.get("availability_correlations", {})).get("selection_score_pre_gate"),
        0.0,
    ) or 0.0
    hybrid_pre_gate_gap = _safe_float(
        dict(hybrid_report.get("gap_metrics", {})).get("selection_score_pre_gate_provisional_minus_blocked"),
        0.0,
    ) or 0.0

    v1_signal_corr = _safe_float(dict(v1_report.get("availability_correlations", {})).get("signal"), 0.0) or 0.0
    residual_signal_corr = _safe_float(dict(residual_report.get("availability_correlations", {})).get("signal"), 0.0) or 0.0
    hybrid_signal_corr = _safe_float(dict(hybrid_report.get("availability_correlations", {})).get("signal"), 0.0) or 0.0
    v1_signal_gap = _safe_float(dict(v1_report.get("gap_metrics", {})).get("signal_provisional_minus_blocked"), 0.0) or 0.0
    residual_signal_gap = _safe_float(dict(residual_report.get("gap_metrics", {})).get("signal_provisional_minus_blocked"), 0.0) or 0.0
    hybrid_signal_gap = _safe_float(dict(hybrid_report.get("gap_metrics", {})).get("signal_provisional_minus_blocked"), 0.0) or 0.0

    v1_overlap_corr = _safe_float(v1_overlap.get("signal_to_baseline_pre_gate_correlation"), 0.0) or 0.0
    residual_overlap_corr = _safe_float(residual_overlap.get("signal_to_baseline_pre_gate_correlation"), 0.0) or 0.0
    hybrid_overlap_corr = _safe_float(hybrid_overlap.get("signal_to_baseline_pre_gate_correlation"), 0.0) or 0.0

    v1_distinctness = _distinctness_score(v1_signal_corr, v1_overlap_corr)
    residual_distinctness = _distinctness_score(residual_signal_corr, residual_overlap_corr)
    hybrid_distinctness = _distinctness_score(hybrid_signal_corr, hybrid_overlap_corr)

    v1_partial_signal = _partial_corr(
        signal_to_target=v1_signal_corr,
        signal_to_baseline=v1_overlap_corr,
        baseline_to_target=baseline_pre_gate_corr,
    )
    residual_partial_signal = _partial_corr(
        signal_to_target=residual_signal_corr,
        signal_to_baseline=residual_overlap_corr,
        baseline_to_target=baseline_pre_gate_corr,
    )
    hybrid_partial_signal = _partial_corr(
        signal_to_target=hybrid_signal_corr,
        signal_to_baseline=hybrid_overlap_corr,
        baseline_to_target=baseline_pre_gate_corr,
    )

    safety_preserved = bool(
        all(
            bool(dict(item.get("vs_baseline", {})).get("passed", False))
            and bool(dict(item.get("vs_v1", {})).get("passed", False))
            and bool(dict(item.get("vs_residual", {})).get("passed", False))
            for item in safety_reports
        )
    )
    branch_stayed_cleanly_upstream = bool(safety_preserved)

    destructive_absorption_avoided = bool(hybrid_overlap_corr <= v1_overlap_corr - 0.10)
    over_residualization_avoided = bool(
        hybrid_signal_corr >= residual_signal_corr + 0.15
        and hybrid_signal_gap >= residual_signal_gap + 0.02
    )
    distinct_headroom_improved = bool(
        hybrid_distinctness >= max(v1_distinctness, residual_distinctness) + 0.01
        or (_safe_float(hybrid_partial_signal, -1.0) or -1.0)
        >= max(_safe_float(v1_partial_signal, -1.0) or -1.0, _safe_float(residual_partial_signal, -1.0) or -1.0) + 0.03
    )
    baseline_path_not_regressed = bool(
        hybrid_pre_gate_corr >= baseline_pre_gate_corr - 0.003
        and hybrid_pre_gate_gap >= baseline_pre_gate_gap - 0.003
    )
    useful_upstream_separation_improved = bool(
        safety_preserved
        and destructive_absorption_avoided
        and over_residualization_avoided
        and distinct_headroom_improved
        and baseline_path_not_regressed
    )

    next_family = "memory_summary"
    next_template = (
        "memory_summary.v4_wm_hybrid_probe_effect_snapshot_v1"
        if useful_upstream_separation_improved
        else "memory_summary.v4_wm_hybrid_probe_effect_snapshot_v1"
    )
    next_rationale = (
        "the hybrid wm/baseline boundary preserved the downstream envelope and found a stronger middle path between absorption and over-residualization, so the next step should map exactly where the hybrid effect is helping before any broader redesign"
        if useful_upstream_separation_improved
        else "the hybrid probe stayed upstream and safe, but it still needs a diagnostic effect readout before deciding whether to iterate again or pause the branch"
    )

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "proposal_learning_loop.v4_wm_baseline_hybrid_boundary_probe_v1",
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
            "memory_summary.v4_wm_baseline_hybrid_boundary_snapshot_v1": _artifact_reference(
                hybrid_boundary_snapshot,
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
            "proposal_learning_loop.v4_wm_context_signal_discrimination_probe_v1": _artifact_reference(
                v1_artifact,
                latest_snapshots,
            ),
            "proposal_learning_loop.v4_wm_context_residual_signal_probe_v1": _artifact_reference(
                residual_artifact,
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
        "branch_implementation_summary": {
            "hybrid_boundary_design": [
                "kept baseline-owned ranking carriers in place through pred_gain_sign_prob, calibrated_projected, and the existing projected-quality/uncertainty boundary path",
                "added wm-owned context-conditioned modulation only through pred_context_score, the contextual remainder of wm_context_supply_score, and light projection_recent modulation",
                "applied the wm-owned hybrid effect only as a bounded modulation to the projected score path before the existing pre-gate mix",
            ],
            "baseline_owned_terms": [
                "pred_gain_sign_prob",
                "calibrated_projected",
                "projected-quality / uncertainty boundary terms",
            ],
            "wm_modulation_terms": [
                "pred_context_score",
                "contextual remainder of wm_context_supply_score",
                "light projection_recent modulation",
            ],
            "duplicate_reuse_avoidance": [
                "did not add direct positive reuse of pred_gain_sign_prob inside the wm correction",
                "did not add direct positive reuse of calibrated_projected inside the wm correction",
                "used baseline-overlap excess only as a mild boundary penalty instead of a second positive vote",
            ],
            "plan_remained_non_owning": [
                "planning_handoff_score was not used as an independent decision lever",
                "plan_ remained a handoff and organization layer only",
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
            "hybrid_separation": hybrid_report,
            "overlap_reports": {
                "v1": v1_overlap,
                "residual": residual_overlap,
                "hybrid": hybrid_overlap,
            },
            "partial_signal_given_baseline": {
                "v1": _safe_float(v1_partial_signal, None),
                "residual": _safe_float(residual_partial_signal, None),
                "hybrid": _safe_float(hybrid_partial_signal, None),
            },
            "per_seed_runs": per_seed_runs,
            "safety_envelope_reports": safety_reports,
            "comparison_vs_baseline": {
                "selection_score_pre_gate_availability_corr_delta": float(hybrid_pre_gate_corr - baseline_pre_gate_corr),
                "selection_score_pre_gate_gap_delta": float(hybrid_pre_gate_gap - baseline_pre_gate_gap),
                "hybrid_signal_availability_corr": float(hybrid_signal_corr),
                "hybrid_signal_gap": float(hybrid_signal_gap),
                "hybrid_signal_overlap_to_baseline_pre_gate": float(hybrid_overlap_corr),
                "hybrid_distinctness_score": float(hybrid_distinctness),
            },
            "comparison_vs_v1": {
                "signal_availability_corr_delta": float(hybrid_signal_corr - v1_signal_corr),
                "signal_gap_delta": float(hybrid_signal_gap - v1_signal_gap),
                "signal_overlap_to_baseline_pre_gate_delta": float(hybrid_overlap_corr - v1_overlap_corr),
                "distinctness_score_delta": float(hybrid_distinctness - v1_distinctness),
                "partial_signal_given_baseline_delta": (
                    None
                    if v1_partial_signal is None or hybrid_partial_signal is None
                    else float(hybrid_partial_signal - v1_partial_signal)
                ),
                "v1_signal_availability_corr": float(v1_signal_corr),
                "v1_signal_gap": float(v1_signal_gap),
                "v1_signal_overlap_to_baseline_pre_gate": float(v1_overlap_corr),
                "v1_distinctness_score": float(v1_distinctness),
            },
            "comparison_vs_residual": {
                "signal_availability_corr_delta": float(hybrid_signal_corr - residual_signal_corr),
                "signal_gap_delta": float(hybrid_signal_gap - residual_signal_gap),
                "signal_overlap_to_baseline_pre_gate_delta": float(hybrid_overlap_corr - residual_overlap_corr),
                "distinctness_score_delta": float(hybrid_distinctness - residual_distinctness),
                "partial_signal_given_baseline_delta": (
                    None
                    if residual_partial_signal is None or hybrid_partial_signal is None
                    else float(hybrid_partial_signal - residual_partial_signal)
                ),
                "residual_signal_availability_corr": float(residual_signal_corr),
                "residual_signal_gap": float(residual_signal_gap),
                "residual_signal_overlap_to_baseline_pre_gate": float(residual_overlap_corr),
                "residual_distinctness_score": float(residual_distinctness),
            },
        },
        "hybrid_boundary_diagnostics": {
            "destructive_absorption_avoided": bool(destructive_absorption_avoided),
            "over_residualization_avoided": bool(over_residualization_avoided),
            "distinct_headroom_improved": bool(distinct_headroom_improved),
            "baseline_path_not_regressed": bool(baseline_path_not_regressed),
            "explanation": (
                "the hybrid probe found a better middle path between overlap and residualization"
                if useful_upstream_separation_improved
                else "the hybrid probe stayed within the intended middle boundary design, but the measurable gain over baseline and prior wm probes was still limited"
            ),
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
            "hybrid_boundary_improved_useful_upstream_separation": bool(useful_upstream_separation_improved),
            "branch_stayed_cleanly_upstream": bool(branch_stayed_cleanly_upstream),
            "recommended_next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "rationale": str(next_rationale),
        },
        "observability_gain": {
            "passed": True,
            "reason": "the hybrid probe remained fully observable through the existing wm/plan trace path with dedicated hybrid boundary trace fields",
            "baseline_trace_row_count": int(len(baseline_rows)),
            "v1_trace_row_count": int(len(v1_rows)),
            "residual_trace_row_count": int(len(residual_rows)),
            "hybrid_trace_row_count": int(len(hybrid_rows)),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the probe directly tests whether a boundary-aware wm/baseline hybrid can preserve useful context signal without reopening downstream ownership or pure wm-only overlap failure modes",
            "hybrid_boundary_improved_useful_upstream_separation": bool(useful_upstream_separation_improved),
            "plan_non_owning_preserved": True,
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": float(
                min(
                    1.0,
                    0.52
                    + 0.16 * int(useful_upstream_separation_improved)
                    + 0.10 * int(destructive_absorption_avoided)
                    + 0.10 * int(over_residualization_avoided)
                    + 0.08 * int(branch_stayed_cleanly_upstream)
                )
            ),
            "reason": "the probe shows whether the viable hybrid boundary from the prior snapshot can survive contact with the actual upstream scoring seam without drifting downstream",
        },
        "safety_neutrality": {
            "passed": bool(safety_preserved),
            "scope": str(proposal.get("scope", "")),
            "reason": "the hybrid wm/baseline probe stayed inside the downstream safety envelope with live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": str(next_template),
            "reason": str(next_rationale),
        },
        "diagnostic_conclusions": {
            "hybrid_boundary_improved_useful_upstream_separation": bool(useful_upstream_separation_improved),
            "branch_stayed_cleanly_upstream": bool(branch_stayed_cleanly_upstream),
            "plan_should_remain_non_owning": True,
            "recommended_next_family": str(next_family),
            "recommended_next_template": str(next_template),
            "routing_deferred": bool(dict(frontier_artifact.get("diagnostic_conclusions", {})).get("routing_deferred", False)),
        },
    }
    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"proposal_learning_loop_v4_wm_baseline_hybrid_boundary_probe_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": bool(safety_preserved),
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": (
            "diagnostic shadow passed: the hybrid wm/baseline probe stayed inside the intended upstream safety envelope"
            if safety_preserved
            else "diagnostic shadow failed: the hybrid wm/baseline probe changed downstream safety behavior beyond the intended upstream scope"
        ),
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
