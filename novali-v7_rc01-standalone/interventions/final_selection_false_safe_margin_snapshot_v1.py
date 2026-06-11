from __future__ import annotations

import json
from typing import Any


TRACKED_CASE_IDS = [
    "recovery_02",
    "recovery_03",
    "recovery_12",
    "persistence_09",
    "persistence_12",
]
CURRENT_SURVIVOR_IDS = ["persistence_09", "recovery_02", "recovery_12"]
RESIDUAL_IDS = ["recovery_03", "persistence_12"]
REPORTED_FAMILIES = ["recovery", "persistence", "projection", "calibration", "gain_goal_conflict"]


def _artifact_metrics(artifact: dict[str, Any]) -> dict[str, Any]:
    metrics = dict(artifact.get("benchmark_control_metrics", {}))
    return {
        "benchmark_slice_count": int(metrics.get("benchmark_slice_count", 0) or 0),
        "safe_pool_count": int(metrics.get("safe_pool_count", 0) or 0),
        "safe_pool_benchmark_like_count": int(metrics.get("safe_pool_benchmark_like_count", 0) or 0),
        "selected_benchmark_like_count": int(metrics.get("selected_benchmark_like_count", 0) or 0),
        "projection_safe_retention": float(metrics.get("projection_safe_retention", 0.0) or 0.0),
        "mean_projection_error": metrics.get("mean_projection_error"),
        "policy_match_rate_delta": metrics.get("policy_match_rate_delta"),
        "false_safe_projection_rate_delta": metrics.get("false_safe_projection_rate_delta"),
        "unsafe_overcommit_rate_delta": metrics.get("unsafe_overcommit_rate_delta"),
        "family_mix": {
            str(name): int(count)
            for name, count in sorted(
                dict(metrics.get("family_mix", {})).items(),
                key=lambda item: str(item[0]),
            )
        },
    }


def _rows_from_artifact(artifact: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in list(dict(artifact.get("sample_rows", {})).get(key, []))
        if isinstance(row, dict)
    ]


def _tracked_case_map(artifact: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(dict(row).get("case_id", "")): dict(row)
        for row in list(artifact.get("tracked_case_outcomes", []))
        if isinstance(row, dict) and str(dict(row).get("case_id", ""))
    }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _context_robustness_sum(case_ids: list[str], tracked_case_map: dict[str, dict[str, Any]]) -> float:
    return float(
        sum(_safe_float(dict(tracked_case_map.get(case_id, {})).get("context_pressure_score")) for case_id in case_ids)
    )


def _build_variant_results(runner_mod, proposal: dict[str, Any], base_rows: list[dict[str, Any]], selected_ids: set[str]) -> list[dict[str, Any]]:
    variant_results: list[dict[str, Any]] = []
    for scenario_result in base_rows:
        scenario_id = str(scenario_result.get("scenario_id", ""))
        decision = (
            "provisional"
            if str(scenario_result.get("policy_decision", "")) == "reject" and scenario_id in selected_ids
            else str(scenario_result.get("policy_decision", "reject"))
        )
        variant_results.append(
            runner_mod._result_with_policy_decision(
                scenario_result,
                decision,
                str(proposal.get("template_name", "")),
            )
        )
    return variant_results


def run_probe(cfg, proposal, *, rounds, seeds):
    del rounds, seeds
    from . import runner as r

    stability_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.stability_context_retention_probe_v2"
    )
    scorer_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.benchmark_like_scoring_preservation_probe_v2"
    )
    balance_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.benchmark_family_balance_snapshot_v1"
    )
    balance_probe = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.benchmark_family_balance_probe_v1"
    )
    transfer_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.benchmark_like_transfer_alignment_probe_v1"
    )
    recovery_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.recovery_benchmark_like_alignment_probe_v1"
    )
    if not all(
        [
            stability_artifact,
            scorer_artifact,
            balance_snapshot,
            balance_probe,
            transfer_artifact,
            recovery_artifact,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: stability/scorer/balance artifacts are required for final_selection_false_safe_margin_snapshot_v1",
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
                "reason": "cannot recommend a follow-up without the prerequisite final-selection artifacts",
            },
        }

    tracked_case_map = _tracked_case_map(stability_artifact)
    safe_pool_like_rows = _rows_from_artifact(stability_artifact, "safe_pool_benchmark_like_examples")
    selected_rows = _rows_from_artifact(stability_artifact, "selected_examples")
    safe_pool_like_by_id = {
        str(row.get("scenario_id", "")): dict(row)
        for row in safe_pool_like_rows
        if str(row.get("scenario_id", ""))
    }
    selected_by_id = {
        str(row.get("scenario_id", "")): dict(row)
        for row in selected_rows
        if str(row.get("scenario_id", ""))
    }
    if not selected_by_id:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no selected benchmark-like slice available to inspect",
            "observability_gain": {"passed": False, "reason": "missing selected benchmark-like slice"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing selected benchmark-like slice"},
            "ambiguity_reduction": {"passed": False, "reason": "missing selected benchmark-like slice"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot inspect final-selection margins without the selected slice",
            },
        }

    stored_baseline_metrics = _artifact_metrics(stability_artifact)
    false_safe_cap = _safe_float(stored_baseline_metrics.get("false_safe_projection_rate_delta"))
    unsafe_overcommit_cap = _safe_float(stored_baseline_metrics.get("unsafe_overcommit_rate_delta"))
    stored_add_evals = {
        str(item.get("case_id", "")): dict(item)
        for item in list(
            dict(stability_artifact.get("stability_context_probe_summary", {})).get(
                "candidate_evaluations", []
            )
        )
        if isinstance(item, dict) and str(item.get("case_id", ""))
    }

    selected_scores = {
        scenario_id: _safe_float(row.get("critic_split_score"))
        for scenario_id, row in selected_by_id.items()
    }
    weakest_selected_id = min(
        selected_scores,
        key=lambda scenario_id: (selected_scores[scenario_id], scenario_id),
    )
    weakest_selected_score = selected_scores[weakest_selected_id]

    benchmark_run = r.run_trusted_benchmark_pack(cfg=cfg, mode="standalone", include_policy_sweep=True)
    summary = dict(benchmark_run.get("summary", {}))
    detailed = dict(benchmark_run.get("detailed", {}))
    base_rows = [dict(item) for item in list(detailed.get("results", [])) if isinstance(item, dict)]
    baseline_summary = {
        "global_compact_summary": dict(summary.get("global_compact_summary", {})),
        "family_compact_summary": dict(summary.get("family_compact_summary", {})),
        "global_mismatch_summary": dict(summary.get("global_mismatch_summary", {})),
        "family_mismatch_summary": dict(summary.get("family_mismatch_summary", {})),
    }

    def _comparison_for(selected_ids: set[str]) -> dict[str, Any]:
        comparison = r._variant_comparison(
            baseline_summary=baseline_summary,
            variant_summary=r._summarize_benchmark_results(
                _build_variant_results(r, proposal, base_rows, selected_ids)
            ),
        )
        return {
            "policy_match_rate_delta": _safe_float(comparison.get("policy_match_rate_delta")),
            "false_safe_projection_rate_delta": _safe_float(
                comparison.get("false_safe_projection_rate_delta")
            ),
            "unsafe_overcommit_rate_delta": _safe_float(
                comparison.get("unsafe_overcommit_rate_delta")
            ),
        }

    current_selected_ids = set(selected_by_id)
    replacement_trials: list[dict[str, Any]] = []
    safe_replacements: list[dict[str, Any]] = []
    for residual_id in RESIDUAL_IDS:
        for survivor_id in CURRENT_SURVIVOR_IDS:
            selected_ids = set(current_selected_ids)
            if survivor_id not in selected_ids:
                continue
            selected_ids.remove(survivor_id)
            selected_ids.add(residual_id)
            trial_metrics = _comparison_for(selected_ids)
            safe_within_cap = bool(
                trial_metrics["false_safe_projection_rate_delta"] <= false_safe_cap + 1e-12
                and trial_metrics["unsafe_overcommit_rate_delta"] <= unsafe_overcommit_cap + 1e-12
            )
            trial_row = {
                "trial_type": "replace",
                "residual_case_id": residual_id,
                "removed_survivor_id": survivor_id,
                "selected_set": sorted(selected_ids),
                "context_robustness_sum": _context_robustness_sum(sorted(selected_ids), tracked_case_map),
                "policy_match_rate_delta": float(trial_metrics["policy_match_rate_delta"]),
                "false_safe_projection_rate_delta": float(
                    trial_metrics["false_safe_projection_rate_delta"]
                ),
                "unsafe_overcommit_rate_delta": float(
                    trial_metrics["unsafe_overcommit_rate_delta"]
                ),
                "false_safe_margin_vs_cap": float(
                    false_safe_cap - trial_metrics["false_safe_projection_rate_delta"]
                ),
                "unsafe_margin_vs_cap": float(
                    unsafe_overcommit_cap - trial_metrics["unsafe_overcommit_rate_delta"]
                ),
                "safe_within_cap": bool(safe_within_cap),
            }
            replacement_trials.append(trial_row)
            if safe_within_cap:
                safe_replacements.append(trial_row)

    incumbent_policy_match_rate_delta = _safe_float(stored_baseline_metrics.get("policy_match_rate_delta"))
    best_safe_replacement_overall = None
    if safe_replacements:
        best_safe_replacement_overall = sorted(
            safe_replacements,
            key=lambda trial: (
                -float(trial.get("policy_match_rate_delta", 0.0)),
                -float(trial.get("context_robustness_sum", 0.0)),
                str(trial.get("residual_case_id", "")),
                str(trial.get("removed_survivor_id", "")),
            ),
        )[0]

    per_case_margin_report = []
    for case_id in TRACKED_CASE_IDS:
        tracked = dict(tracked_case_map.get(case_id, {}))
        safe_row = dict(safe_pool_like_by_id.get(case_id, {}))
        row = dict(safe_row or selected_by_id.get(case_id, {}))
        score = _safe_float(row.get("critic_split_score"))
        score_margin_vs_frontier = float(score - weakest_selected_score) if row else None
        add_trial = dict(stored_add_evals.get(case_id, {}))
        safe_replace_options = [
            dict(trial)
            for trial in safe_replacements
            if str(trial.get("residual_case_id")) == case_id
        ]
        best_safe_replace = None
        if safe_replace_options:
            best_safe_replace = sorted(
                safe_replace_options,
                key=lambda trial: (
                    -float(trial.get("false_safe_margin_vs_cap", 0.0)),
                    -float(trial.get("policy_match_rate_delta", 0.0)),
                    str(trial.get("removed_survivor_id", "")),
                ),
            )[0]
        current_selected = bool(case_id in current_selected_ids)
        first_collapse_stage = str(
            tracked.get(
                "first_stage_where_collapse_occurred",
                "none" if current_selected else "final_selection",
            )
        )
        dominant_blocker = str(
            tracked.get(
                "dominant_blocker",
                "none" if current_selected else "selection_budget_hold_for_drift_control",
            )
        )
        if add_trial:
            likely_local_cause = "shared false-safe guardrail frontier"
        elif current_selected:
            likely_local_cause = "current survivor inside accepted cap"
        else:
            likely_local_cause = str(
                tracked.get("most_likely_local_cause", "not part of the late benchmark-like safe slice")
            )
        add_trial_margin_vs_cap = (
            float(false_safe_cap - _safe_float(add_trial.get("trial_false_safe_projection_rate_delta")))
            if add_trial
            else None
        )
        additive_budget_label = (
            "blocked_by_additive_budget"
            if add_trial_margin_vs_cap is not None and add_trial_margin_vs_cap < 0.0
            else ""
        )
        replacement_policy_delta_vs_incumbent = (
            float(_safe_float(best_safe_replace.get("policy_match_rate_delta")) - incumbent_policy_match_rate_delta)
            if best_safe_replace
            else None
        )
        replacement_context_tiebreak_delta_vs_best_safe = (
            float(
                _safe_float(best_safe_replace.get("context_robustness_sum"))
                - _safe_float(dict(best_safe_replacement_overall or {}).get("context_robustness_sum"))
            )
            if best_safe_replace and best_safe_replacement_overall
            else None
        )
        replacement_attribution_label = ""
        if best_safe_replace:
            if _safe_float(best_safe_replace.get("policy_match_rate_delta")) < incumbent_policy_match_rate_delta - 1e-12:
                replacement_attribution_label = "replacement_safe_but_ranked_below_incumbent"
            elif (
                best_safe_replacement_overall
                and abs(
                    _safe_float(best_safe_replace.get("policy_match_rate_delta"))
                    - _safe_float(dict(best_safe_replacement_overall).get("policy_match_rate_delta"))
                )
                <= 1e-12
                and _safe_float(best_safe_replace.get("context_robustness_sum"))
                < _safe_float(dict(best_safe_replacement_overall).get("context_robustness_sum")) - 1e-12
            ):
                replacement_attribution_label = "replacement_safe_and_policy_tied_but_lost_context_tiebreak"
        if current_selected:
            selector_frontier_attribution_label = ""
            final_selection_split_stage = ""
        elif additive_budget_label:
            selector_frontier_attribution_label = "blocked_by_additive_budget"
            final_selection_split_stage = "budget_eligibility_under_frozen_cap"
        elif replacement_attribution_label:
            selector_frontier_attribution_label = replacement_attribution_label
            final_selection_split_stage = "within_cap_ordering_and_tiebreak"
        else:
            selector_frontier_attribution_label = "unexplained_coupled_selector_effect"
            final_selection_split_stage = "still_genuinely_coupled"
        per_case_margin_report.append(
            {
                "case_id": case_id,
                "family": str(row.get("family", tracked.get("family", "unknown"))),
                "current_selected_benchmark_like": bool(current_selected),
                "safe_pool_benchmark_like_survived": bool(
                    tracked.get("safe_pool_benchmark_like_survived", bool(row))
                ),
                "benchmark_like_scoring_executed": bool(
                    tracked.get("benchmark_like_scoring_executed", bool(row))
                ),
                "first_stage_where_collapse_occurred": first_collapse_stage,
                "dominant_blocker": dominant_blocker,
                "critic_split_score": score if row else None,
                "score_margin_vs_weakest_selected": score_margin_vs_frontier,
                "context_pressure_score": _safe_float(
                    tracked.get("context_pressure_score", 0.0)
                )
                if tracked
                else None,
                "add_trial_false_safe_projection_rate_delta": (
                    float(add_trial.get("trial_false_safe_projection_rate_delta"))
                    if add_trial
                    else None
                ),
                "add_trial_false_safe_margin_vs_cap": add_trial_margin_vs_cap,
                "add_trial_unsafe_overcommit_rate_delta": (
                    float(add_trial.get("trial_unsafe_overcommit_rate_delta"))
                    if add_trial
                    else None
                ),
                "best_safe_replace": best_safe_replace,
                "additive_budget_label": str(additive_budget_label),
                "replacement_attribution_label": str(replacement_attribution_label),
                "selector_frontier_attribution_label": str(selector_frontier_attribution_label),
                "replacement_policy_delta_vs_incumbent": replacement_policy_delta_vs_incumbent,
                "replacement_context_tiebreak_delta_vs_best_safe": replacement_context_tiebreak_delta_vs_best_safe,
                "final_selection_split_stage": str(final_selection_split_stage),
                "most_likely_local_cause": likely_local_cause,
            }
        )

    family_level_breakdown = {
        family: {
            "safe_pool_count": 0,
            "safe_pool_benchmark_like_count": 0,
            "scoring_executed_count": 0,
            "selected_benchmark_like_count": 0,
            "dominant_late_blocker": "none",
            "comparison_vs_baseline": {},
        }
        for family in REPORTED_FAMILIES
    }
    family_blockers: dict[str, dict[str, int]] = {family: {} for family in REPORTED_FAMILIES}
    for case_id in TRACKED_CASE_IDS:
        tracked = dict(tracked_case_map.get(case_id, {}))
        family = str(tracked.get("family", safe_pool_like_by_id.get(case_id, {}).get("family", "unknown")))
        if family not in family_level_breakdown:
            continue
        if bool(tracked.get("survived_safe_pool", False)):
            family_level_breakdown[family]["safe_pool_count"] += 1
        if bool(tracked.get("safe_pool_benchmark_like_survived", False)):
            family_level_breakdown[family]["safe_pool_benchmark_like_count"] += 1
        if bool(tracked.get("benchmark_like_scoring_executed", False)):
            family_level_breakdown[family]["scoring_executed_count"] += 1
        if bool(tracked.get("selected_benchmark_like_survived", False)):
            family_level_breakdown[family]["selected_benchmark_like_count"] += 1
        blocker = str(tracked.get("dominant_blocker", "none"))
        family_blockers[family][blocker] = family_blockers[family].get(blocker, 0) + 1
    baseline_reference = {
        "critic_split.benchmark_like_scoring_preservation_probe_v2": _artifact_metrics(scorer_artifact),
        "critic_split.recovery_benchmark_like_alignment_probe_v1": _artifact_metrics(recovery_artifact),
        "critic_split.benchmark_like_transfer_alignment_probe_v1": _artifact_metrics(transfer_artifact),
    }
    for family in REPORTED_FAMILIES:
        dominant = "none"
        if family_blockers[family]:
            dominant = sorted(
                family_blockers[family].items(),
                key=lambda item: (-int(item[1]), str(item[0])),
            )[0][0]
        family_level_breakdown[family]["dominant_late_blocker"] = str(dominant)
        family_level_breakdown[family]["comparison_vs_baseline"] = {
            "current_selected_benchmark_like": int(family_level_breakdown[family]["selected_benchmark_like_count"]),
            "scorer_preservation_v2_selected": int(
                dict(scorer_artifact.get("family_level_breakdown", {}))
                .get(family, {})
                .get("selected_benchmark_like", 0)
            ),
            "recovery_alignment_selected": int(
                dict(recovery_artifact.get("family_level_breakdown", {}))
                .get(family, {})
                .get("selected_benchmark_like", 0)
            ),
            "transfer_alignment_selected": int(
                dict(transfer_artifact.get("family_level_breakdown", {}))
                .get(family, {})
                .get("selected_benchmark_like", 0)
            ),
        }

    safe_replace_by_residual = {
        residual_id: [
            dict(trial)
            for trial in safe_replacements
            if str(trial.get("residual_case_id")) == residual_id
        ]
        for residual_id in RESIDUAL_IDS
    }
    shared_frontier_anchor = ""
    if safe_replacements:
        replacement_counts: dict[str, int] = {}
        for trial in safe_replacements:
            removed = str(trial.get("removed_survivor_id", ""))
            replacement_counts[removed] = replacement_counts.get(removed, 0) + 1
        shared_frontier_anchor = sorted(
            replacement_counts.items(),
            key=lambda item: (-int(item[1]), str(item[0])),
        )[0][0]

    blocked_residual_reports = [
        dict(row)
        for row in per_case_margin_report
        if bool(row.get("safe_pool_benchmark_like_survived", False))
        and bool(row.get("benchmark_like_scoring_executed", False))
        and not bool(row.get("current_selected_benchmark_like", False))
    ]
    ordering_stage_evidence_present = any(
        bool(row.get("best_safe_replace")) or bool(str(row.get("replacement_attribution_label", "")))
        for row in blocked_residual_reports
    )
    final_selection_split_assessment = (
        "serial_budget_then_ordering"
        if blocked_residual_reports
        and ordering_stage_evidence_present
        and all(
            str(row.get("selector_frontier_attribution_label", "")) != "unexplained_coupled_selector_effect"
            for row in blocked_residual_reports
        )
        else "still_genuinely_coupled"
    )
    if final_selection_split_assessment == "serial_budget_then_ordering":
        primary_blocker = "budget_eligibility_under_frozen_cap"
        secondary_blocker = "within_cap_ordering_and_tiebreak"
        first_safe_next_critic_lever = (
            "selector-frontier attribution complete; additive budget is the first gate and within-cap ordering is the second gate under unchanged settings"
        )
        recommended_next_action = "hold_and_consolidate"
        recommended_next_template = ""
        slice_health = "structurally_healthy_but_serially_budget_then_ordering_limited"
    elif not safe_replacements:
        primary_blocker = "guardrail_coupled_shared_selected_set_frontier"
        secondary_blocker = "rank_margin_compression"
        first_safe_next_critic_lever = "narrow late-stage scorer preservation remains the first safe lever"
        recommended_next_action = "critic_refinement_next"
        recommended_next_template = "critic_split.benchmark_like_scoring_preservation_probe_v2"
        slice_health = "healthy_upstream_but_final_selection_frozen"
    else:
        primary_blocker = "guardrail_coupled_shared_selected_set_frontier"
        secondary_blocker = "rank_margin_compression"
        first_safe_next_critic_lever = "swap-aware final-selection guardrail correction"
        recommended_next_action = "critic_refinement_next"
        recommended_next_template = "critic_split.benchmark_like_scoring_preservation_probe_v2"
        slice_health = "structurally_healthy_but_selection_frontier_limited"

    selected_set_interaction_report = {
        "baseline_selected_ids": sorted(current_selected_ids),
        "baseline_false_safe_projection_rate_delta_cap": float(false_safe_cap),
        "baseline_unsafe_overcommit_rate_delta_cap": float(unsafe_overcommit_cap),
        "stored_add_trials": {
            residual_id: dict(stored_add_evals.get(residual_id, {}))
            for residual_id in RESIDUAL_IDS
        },
        "replacement_trials": replacement_trials,
        "safe_replacements": safe_replacements,
        "shared_frontier_anchor": str(shared_frontier_anchor),
        "primary_interaction_mode": str(primary_blocker),
        "slice_health": str(slice_health),
    }

    observability_gain = {
        "passed": True,
        "reason": "the snapshot localizes the final-selection false-safe frontier after scorer preservation succeeded upstream",
    }
    activation_analysis = {
        "passed": True,
        "reason": "the snapshot distinguishes add-vs-replace behavior for the two residual benchmark-like candidates",
        "safe_replacement_exists": bool(safe_replacements),
    }
    ambiguity_reduction = {
        "passed": True,
        "score": float(
            min(
                1.0,
                0.34
                + 0.22 * int(bool(stored_add_evals))
                + 0.18 * int(bool(safe_replacements))
                + 0.14 * int(bool(shared_frontier_anchor))
                + 0.12 * int(primary_blocker == "guardrail_coupled_shared_selected_set_frontier"),
            )
        ),
        "reason": "the snapshot separates additive false-safe cap breach from replacement-safe frontier swaps",
    }
    safety_neutrality = {
        "passed": True,
        "scope": str(proposal.get("scope", "")),
        "reason": "diagnostic-only benchmark snapshot with live policy, thresholds, routing policy, and frozen benchmark semantics unchanged",
    }
    later_selection_usefulness = {
        "passed": True,
        "recommended_next_action": str(recommended_next_action),
        "recommended_next_template": str(recommended_next_template),
        "reason": str(first_safe_next_critic_lever),
    }
    operator_readable_conclusion = (
        "final selection is now better explained as a serial selector-frontier failure: blocked residuals first fail budget eligibility under the frozen cap, and any within-cap replacement then resolves through ordering and context tie-breaks without changing routing, thresholds, or policy"
        if final_selection_split_assessment == "serial_budget_then_ordering"
        else "the snapshot still cannot fully separate additive budget failure from downstream ordering, so the selector-frontier remains genuinely coupled under the current evidence"
    )

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.final_selection_false_safe_margin_snapshot_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "comparison_references": {
            "critic_split.stability_context_retention_probe_v2": _artifact_metrics(stability_artifact),
            "critic_split.benchmark_like_scoring_preservation_probe_v2": _artifact_metrics(
                scorer_artifact
            ),
            "memory_summary.benchmark_family_balance_snapshot_v1": {
                "exact_collapse_stage": str(
                    dict(balance_snapshot.get("diagnostic_conclusions", {})).get(
                        "exact_stage_of_collapse", "benchmark_like_scoring"
                    )
                ),
                "primary_bottleneck": str(
                    dict(balance_snapshot.get("diagnostic_conclusions", {})).get(
                        "primary_bottleneck", "scoring-collapse"
                    )
                ),
            },
            "critic_split.benchmark_family_balance_probe_v1": _artifact_metrics(balance_probe),
            "critic_split.recovery_benchmark_like_alignment_probe_v1": _artifact_metrics(
                recovery_artifact
            ),
            "critic_split.benchmark_like_transfer_alignment_probe_v1": _artifact_metrics(
                transfer_artifact
            ),
        },
        "per_case_final_selection_margin_report": per_case_margin_report,
        "selected_set_interaction_report": selected_set_interaction_report,
        "final_selection_split_assessment": str(final_selection_split_assessment),
        "family_level_breakdown": family_level_breakdown,
        "bottleneck_ranking": [
            str(primary_blocker),
            str(secondary_blocker),
            "family_specific_final_selection_penalty" if not safe_replacements else "selection_budget_competition",
        ],
        "first_safe_next_critic_lever": str(first_safe_next_critic_lever),
        "recommended_next_action": str(recommended_next_action),
        "decision_recommendation": {
            "recommended_next_action": str(recommended_next_action),
            "recommended_next_template": str(recommended_next_template),
            "rationale": str(first_safe_next_critic_lever),
        },
        "diagnostic_conclusions": {
            "primary_bottleneck": str(primary_blocker),
            "secondary_bottleneck": str(secondary_blocker),
            "final_selection_split_assessment": str(final_selection_split_assessment),
            "shared_frontier_anchor": str(shared_frontier_anchor),
            "safe_replacement_exists": bool(safe_replacements),
            "slice_health": str(slice_health),
            "recommended_next_action": str(recommended_next_action),
            "recommended_next_template": str(recommended_next_template),
            "routing_deferred": True,
        },
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "operator_readable_conclusion": str(operator_readable_conclusion),
    }
    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"memory_summary_final_selection_false_safe_margin_snapshot_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: final-selection false-safe margins were localized and add-vs-replace behavior was explained",
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
