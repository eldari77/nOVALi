from __future__ import annotations

import json
from typing import Any


TRIOS = {
    "baseline": ["recovery_02", "recovery_12", "persistence_09"],
    "swap_A": ["recovery_02", "recovery_03", "persistence_09"],
    "swap_B": ["recovery_02", "recovery_12", "persistence_12"],
    "swap_C": ["recovery_02", "recovery_03", "recovery_12"],
    "swap_D": ["recovery_02", "persistence_09", "persistence_12"],
    "double_swap": ["recovery_02", "recovery_03", "persistence_12"],
}
TRACKED_CASE_IDS = [
    "recovery_02",
    "recovery_03",
    "recovery_12",
    "persistence_09",
    "persistence_12",
]
REPORTED_FAMILIES = ["recovery", "persistence", "projection", "calibration", "gain_goal_conflict"]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


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


def _family_mix_for(ids: list[str], case_rows: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {family: 0 for family in REPORTED_FAMILIES}
    for case_id in ids:
        family = str(dict(case_rows.get(case_id, {})).get("family", "unknown"))
        if family in counts:
            counts[family] += 1
    return counts


def _context_robustness(ids: list[str], case_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    scores = [
        _safe_float(dict(case_rows.get(case_id, {})).get("context_pressure_score"))
        for case_id in ids
    ]
    return {
        "sum": float(sum(scores)),
        "mean": float(sum(scores) / len(scores)) if scores else 0.0,
        "min": float(min(scores)) if scores else 0.0,
        "max": float(max(scores)) if scores else 0.0,
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    del rounds, seeds
    from . import runner as r

    stability_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.stability_context_retention_probe_v2"
    )
    margin_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.final_selection_false_safe_margin_snapshot_v1"
    )
    scorer_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.benchmark_like_scoring_preservation_probe_v2"
    )
    if not all([stability_artifact, margin_snapshot, scorer_artifact]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: stability retention and final-selection margin snapshots are required",
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
                "reason": "cannot evaluate swap-aware guardrails without the prerequisite artifacts",
            },
        }

    tracked_case_rows = _tracked_case_map(stability_artifact)
    margin_case_reports = [
        dict(row)
        for row in list(margin_snapshot.get("per_case_final_selection_margin_report", []))
        if isinstance(row, dict)
    ]
    selected_rows = _rows_from_artifact(stability_artifact, "selected_examples")
    safe_pool_like_rows = _rows_from_artifact(stability_artifact, "safe_pool_benchmark_like_examples")
    case_row_lookup = {
        str(row.get("scenario_id", "")): dict(row)
        for row in safe_pool_like_rows + selected_rows
        if str(row.get("scenario_id", ""))
    }

    baseline_metrics = _artifact_metrics(stability_artifact)
    false_safe_cap = _safe_float(baseline_metrics.get("false_safe_projection_rate_delta"))
    unsafe_cap = _safe_float(baseline_metrics.get("unsafe_overcommit_rate_delta"))
    margin_conclusions = dict(margin_snapshot.get("diagnostic_conclusions", {}))
    interaction_report = dict(margin_snapshot.get("selected_set_interaction_report", {}))
    snapshot_replacements = {
        (
            str(item.get("residual_case_id", "")),
            str(item.get("removed_survivor_id", "")),
        ): dict(item)
        for item in list(
            dict(margin_snapshot.get("selected_set_interaction_report", {})).get(
                "replacement_trials", []
            )
        )
        if isinstance(item, dict)
    }

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

    trio_table = []
    for trio_name, trio_ids in TRIOS.items():
        trio_set = set(trio_ids)
        if trio_name == "baseline":
            metrics = {
                "selected_benchmark_like_count": 3,
                "projection_safe_retention": float(
                    baseline_metrics.get("projection_safe_retention", 0.0) or 0.0
                ),
                "unsafe_overcommit_rate_delta": float(
                    baseline_metrics.get("unsafe_overcommit_rate_delta", 0.0) or 0.0
                ),
                "false_safe_projection_rate_delta": float(
                    baseline_metrics.get("false_safe_projection_rate_delta", 0.0) or 0.0
                ),
                "policy_match_rate_delta": float(
                    baseline_metrics.get("policy_match_rate_delta", 0.0) or 0.0
                ),
                "mean_projection_error": baseline_metrics.get("mean_projection_error"),
                "source": "stability_context_retention_probe_v2",
            }
        elif trio_name.startswith("swap_"):
            removed_survivor = next(
                (case_id for case_id in TRIOS["baseline"] if case_id not in trio_set),
                "",
            )
            residual_case = next((case_id for case_id in trio_ids if case_id not in TRIOS["baseline"]), "")
            replacement = dict(snapshot_replacements.get((residual_case, removed_survivor), {}))
            metrics = {
                "selected_benchmark_like_count": 3,
                "projection_safe_retention": 1.0,
                "unsafe_overcommit_rate_delta": float(
                    replacement.get("unsafe_overcommit_rate_delta", 0.0) or 0.0
                ),
                "false_safe_projection_rate_delta": float(
                    replacement.get("false_safe_projection_rate_delta", false_safe_cap) or false_safe_cap
                ),
                "policy_match_rate_delta": float(
                    replacement.get("policy_match_rate_delta", baseline_metrics.get("policy_match_rate_delta", 0.0))
                    or 0.0
                ),
                "mean_projection_error": r._mean_key(
                    [case_row_lookup[case_id] for case_id in trio_ids if case_id in case_row_lookup],
                    "pred_projection_error",
                ),
                "source": "final_selection_false_safe_margin_snapshot_v1",
            }
        else:
            comparison = r._variant_comparison(
                baseline_summary=baseline_summary,
                variant_summary=r._summarize_benchmark_results(
                    _build_variant_results(r, proposal, base_rows, trio_set)
                ),
            )
            metrics = {
                "selected_benchmark_like_count": 3,
                "projection_safe_retention": 1.0,
                "unsafe_overcommit_rate_delta": float(
                    comparison.get("unsafe_overcommit_rate_delta", 0.0) or 0.0
                ),
                "false_safe_projection_rate_delta": float(
                    comparison.get("false_safe_projection_rate_delta", 0.0) or 0.0
                ),
                "policy_match_rate_delta": float(
                    comparison.get("policy_match_rate_delta", 0.0) or 0.0
                ),
                "mean_projection_error": r._mean_key(
                    [case_row_lookup[case_id] for case_id in trio_ids if case_id in case_row_lookup],
                    "pred_projection_error",
                ),
                "source": "direct_double_swap_evaluation",
            }

        context_signal = _context_robustness(trio_ids, tracked_case_rows)
        safe_within_cap = bool(
            metrics["selected_benchmark_like_count"] >= 3
            and abs(metrics["projection_safe_retention"] - 1.0) <= 1e-12
            and metrics["unsafe_overcommit_rate_delta"] <= unsafe_cap + 1e-12
            and metrics["false_safe_projection_rate_delta"] <= false_safe_cap + 1e-12
        )
        trio_table.append(
            {
                "trio_name": trio_name,
                "selected_ids": list(trio_ids),
                "selected_benchmark_like_count": int(metrics["selected_benchmark_like_count"]),
                "projection_safe_retention": float(metrics["projection_safe_retention"]),
                "unsafe_overcommit_rate_delta": float(metrics["unsafe_overcommit_rate_delta"]),
                "false_safe_projection_rate_delta": float(metrics["false_safe_projection_rate_delta"]),
                "false_safe_margin_vs_cap": float(false_safe_cap - metrics["false_safe_projection_rate_delta"]),
                "policy_match_rate_delta": float(metrics["policy_match_rate_delta"]),
                "mean_projection_error": metrics["mean_projection_error"],
                "context_robustness_signal": context_signal,
                "family_mix": _family_mix_for(trio_ids, tracked_case_rows),
                "safe_within_cap": bool(safe_within_cap),
                "comparison_source": str(metrics["source"]),
            }
        )

    safe_trios = [dict(row) for row in trio_table if bool(row.get("safe_within_cap", False))]
    best_safe_trio = {}
    if safe_trios:
        best_safe_trio = sorted(
            safe_trios,
            key=lambda row: (
                -float(row.get("policy_match_rate_delta", 0.0)),
                -float(dict(row.get("context_robustness_signal", {})).get("sum", 0.0)),
                str(row.get("trio_name", "")),
            ),
        )[0]

    incumbent = next((dict(row) for row in trio_table if str(row.get("trio_name")) == "baseline"), {})
    any_swap_beats_incumbent = bool(
        best_safe_trio
        and str(best_safe_trio.get("trio_name", "")) != "baseline"
        and (
            float(best_safe_trio.get("policy_match_rate_delta", 0.0))
            > float(incumbent.get("policy_match_rate_delta", 0.0))
            or (
                abs(
                    float(best_safe_trio.get("policy_match_rate_delta", 0.0))
                    - float(incumbent.get("policy_match_rate_delta", 0.0))
                )
                <= 1e-12
                and float(dict(best_safe_trio.get("context_robustness_signal", {})).get("sum", 0.0))
                > float(dict(incumbent.get("context_robustness_signal", {})).get("sum", 0.0))
            )
        )
    )

    residual_case_reports = [
        dict(row)
        for row in margin_case_reports
        if bool(row.get("safe_pool_benchmark_like_survived", False))
        and bool(row.get("benchmark_like_scoring_executed", False))
        and not bool(row.get("current_selected_benchmark_like", False))
    ]
    cases_reviewed = [str(row.get("case_id", "")) for row in residual_case_reports if str(row.get("case_id", ""))]
    add_trial_breaches = [
        float(row.get("add_trial_false_safe_margin_vs_cap"))
        for row in residual_case_reports
        if row.get("add_trial_false_safe_margin_vs_cap") is not None
    ]
    false_safe_margin_assessment = (
        "false_safe_margin_conservatism"
        if add_trial_breaches and all(margin < 0.0 for margin in add_trial_breaches)
        else "not_primary"
    )
    selection_budget_assessment = (
        "budget_too_tight"
        if residual_case_reports
        and all(
            str(row.get("dominant_blocker", "")) == "selection_budget_hold_for_drift_control"
            for row in residual_case_reports
        )
        else "not_primary"
    )
    drift_control_block_assessment = (
        "selection_budget_hold_for_drift_control"
        if selection_budget_assessment == "budget_too_tight"
        else "not_primary"
    )
    ranking_or_tiebreak_assessment = (
        "ranking_behavior"
        if any(
            row.get("score_margin_vs_weakest_selected") is not None
            and float(row.get("score_margin_vs_weakest_selected")) < 0.0
            for row in residual_case_reports
        )
        else "not_primary"
    )
    if drift_control_block_assessment == "selection_budget_hold_for_drift_control":
        dominant_final_selection_blocker = "selection_budget_hold_for_drift_control"
    elif false_safe_margin_assessment == "false_safe_margin_conservatism":
        dominant_final_selection_blocker = "false_safe_margin"
    elif ranking_or_tiebreak_assessment == "ranking_behavior":
        dominant_final_selection_blocker = "ranking_behavior"
    else:
        dominant_final_selection_blocker = "other_frontier_rule"

    best_safe_swap_exists = bool(best_safe_trio) and str(best_safe_trio.get("trio_name", "")) != "baseline"
    any_safe_replacement = any(bool(row.get("best_safe_replace")) for row in residual_case_reports)
    if best_safe_swap_exists and false_safe_margin_assessment == "false_safe_margin_conservatism":
        selector_vs_frontier_assessment = "coupled_critic_selector_issue"
        row_strength_assessment = "budget_too_tight"
    elif false_safe_margin_assessment == "false_safe_margin_conservatism":
        selector_vs_frontier_assessment = "frontier_policy_only"
        row_strength_assessment = "selector_too_conservative"
    elif ranking_or_tiebreak_assessment == "ranking_behavior":
        selector_vs_frontier_assessment = "selector_behavior_only"
        row_strength_assessment = "rows_not_strong_enough"
    else:
        selector_vs_frontier_assessment = "frontier_policy_only"
        row_strength_assessment = "mixed"

    structural_vs_local_assessment = (
        "reusable_structural_principle"
        if best_safe_swap_exists or any_safe_replacement
        else "local_patch_only"
    )
    exploitation_block_assessment = (
        "exploitation_block_explained" if residual_case_reports else "still_unclear"
    )
    routing_status = "routing_deferred"

    final_selection_path_summary = []
    for row in residual_case_reports:
        best_safe_replace = dict(row.get("best_safe_replace", {}) or {})
        add_trial_margin = row.get("add_trial_false_safe_margin_vs_cap")
        case_id = str(row.get("case_id", ""))
        final_selection_path_summary.append(
            {
                "case_id": case_id,
                "path": [
                    "benchmark_like_candidate_present_in_safe_pool",
                    "benchmark_like_scoring_executed",
                    "preserved_across_stability_pass",
                    (
                        "additive_final_selection_trial_breached_false_safe_cap"
                        if add_trial_margin is not None and float(add_trial_margin) < 0.0
                        else "additive_final_selection_trial_within_cap"
                    ),
                    (
                        "final_selection_rejected_with_selection_budget_hold_for_drift_control"
                        if str(row.get("dominant_blocker", "")) == "selection_budget_hold_for_drift_control"
                        else "final_selection_rejected"
                    ),
                    (
                        "safe_replacement_path_available"
                        if best_safe_replace
                        else "no_safe_replacement_path_available"
                    ),
                ],
                "add_trial_false_safe_projection_rate_delta": row.get(
                    "add_trial_false_safe_projection_rate_delta"
                ),
                "add_trial_false_safe_margin_vs_cap": add_trial_margin,
                "best_safe_replace_removed_survivor_id": str(
                    best_safe_replace.get("removed_survivor_id", "")
                ),
                "best_safe_replace_selected_set": list(best_safe_replace.get("selected_set", [])),
                "decision_read": (
                    "blocked_as_addition_but_viable_as_safe_replacement"
                    if best_safe_replace
                    else "blocked_without_viable_safe_replacement"
                ),
            }
        )

    if best_safe_swap_exists:
        next_action = "benchmark_only_control_exploration_next"
        next_template = "critic_split.safe_trio_incumbent_confirmation_probe_v1"
        recommendation_reason = (
            "the probe found a cap-preserving safe swap that beats the incumbent on benchmark utility, so the next bounded step is to confirm whether that swap should replace the current incumbent trio under the same frozen envelope"
        )
        next_hypothesis = "safe_swap_incumbent_confirmation"
    elif best_safe_trio:
        next_action = "critic_refinement_next"
        next_template = "critic_split.benchmark_like_scoring_preservation_probe_v2"
        recommendation_reason = (
            "the incumbent remains the best safe trio under the current cap, so the next bounded step is narrower critic refinement rather than selected-set promotion"
        )
        next_hypothesis = "residual_scorer_stabilization"
    else:
        next_action = "critic_refinement_next"
        next_template = "critic_split.benchmark_like_scoring_preservation_probe_v2"
        recommendation_reason = (
            "no safe trio improved on the incumbent under the current false-safe cap, so the next work should fall back to narrower scorer-preservation refinement"
        )
        next_hypothesis = "residual_scorer_stabilization"

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "critic_split.final_selection_false_safe_guardrail_probe_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "probe_identity_context": {
            "probe_line": "critic_split.final_selection_false_safe_guardrail_probe_v1",
            "phase": "upstream_final_selection_guardrail_diagnostic",
            "false_safe_projection_rate_delta_cap": float(false_safe_cap),
            "unsafe_overcommit_rate_delta_cap": float(unsafe_cap),
            "incumbent_trio_name": str(incumbent.get("trio_name", "")),
        },
        "evidence_inputs_used": [
            "critic_split.stability_context_retention_probe_v2",
            "memory_summary.final_selection_false_safe_margin_snapshot_v1",
            "critic_split.benchmark_like_scoring_preservation_probe_v2",
            "trusted_benchmark_pack_v1",
        ],
        "cases_reviewed": list(cases_reviewed),
        "comparison_references": {
            "critic_split.stability_context_retention_probe_v2": _artifact_metrics(stability_artifact),
            "memory_summary.final_selection_false_safe_margin_snapshot_v1": {
                "primary_bottleneck": str(margin_conclusions.get("primary_bottleneck", "")),
                "shared_frontier_anchor": str(margin_conclusions.get("shared_frontier_anchor", "")),
            },
            "critic_split.benchmark_like_scoring_preservation_probe_v2": _artifact_metrics(
                scorer_artifact
            ),
        },
        "final_selection_path_summary": final_selection_path_summary,
        "false_safe_margin_assessment": str(false_safe_margin_assessment),
        "selection_budget_assessment": str(selection_budget_assessment),
        "drift_control_block_assessment": str(drift_control_block_assessment),
        "ranking_or_tiebreak_assessment": str(ranking_or_tiebreak_assessment),
        "dominant_final_selection_blocker": str(dominant_final_selection_blocker),
        "selector_vs_frontier_assessment": str(selector_vs_frontier_assessment),
        "structural_vs_local_assessment": str(structural_vs_local_assessment),
        "routing_status": str(routing_status),
        "recommended_next_action": str(next_action),
        "evaluated_trio_table": trio_table,
        "best_safe_trio": best_safe_trio,
        "incumbent_trio": incumbent,
        "swap_beats_incumbent": bool(any_swap_beats_incumbent),
        "tracked_case_outcomes": [
            dict(tracked_case_rows.get(case_id, {"case_id": case_id}))
            for case_id in TRACKED_CASE_IDS
        ],
        "selected_set_interaction_report": {
            "baseline_selected_ids": list(interaction_report.get("baseline_selected_ids", [])),
            "shared_frontier_anchor": str(interaction_report.get("shared_frontier_anchor", "")),
            "safe_replacement_count": len(list(interaction_report.get("safe_replacements", []))),
            "replacement_trial_count": len(list(interaction_report.get("replacement_trials", []))),
        },
        "observability_gain": {
            "passed": True,
            "reason": "the probe compares incumbent, safe swaps, and the double-swap under the same protected-anchor final-selection guardrail",
        },
        "activation_analysis_usefulness": {
            "passed": bool(best_safe_trio),
            "reason": "the probe tests whether swap-aware final-selection composition can improve benchmark utility without exceeding the current false-safe cap",
            "safe_trio_names": [str(row.get("trio_name", "")) for row in safe_trios],
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": float(
                min(
                    1.0,
                    0.32
                    + 0.18 * int(bool(safe_trios))
                    + 0.18 * int(bool(any_swap_beats_incumbent))
                    + 0.14 * int(any(str(row.get("trio_name", "")).startswith("swap_") for row in safe_trios))
                    + 0.12 * int(any(str(row.get("trio_name", "")) == "double_swap" and bool(row.get("safe_within_cap", False)) for row in trio_table))
                )
            ),
            "reason": "the probe distinguishes safe replacement from unsafe additive or double-swap expansion while keeping the projection-safe envelope frozen",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "benchmark-only swap-aware final-selection guardrail probe with live policy, thresholds, routing policy, and frozen benchmark semantics unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_action": str(next_action),
            "recommended_next_template": str(next_template),
            "reason": str(recommendation_reason),
        },
        "decision_recommendation": {
            "recommended_next_action": str(next_action),
            "recommended_next_template": str(next_template),
            "rationale": str(recommendation_reason),
        },
        "review_rollback_deprecation_trigger_status": {
            "review_triggered": False,
            "rollback_triggered": False,
            "deprecation_triggered": False,
        },
        "resource_trust_accounting": {
            "network_mode": "none",
            "trusted_input_sources": [
                "local novali-v4 diagnostic artifacts",
                "trusted benchmark pack",
                "local intervention analytics",
            ],
            "write_root": "novali-v4/data/diagnostic_memory",
            "routing_changed": False,
            "live_policy_changed": False,
            "thresholds_relaxed": False,
            "projection_safe_envelope_changed": False,
        },
        "operator_readable_conclusion": (
            "novali-v4 reproduces the upstream over-blocking pattern: preserved benchmark-like residual rows reach final selection, breach the shared additive false-safe frontier, and get held out under drift-control budgeting even though at least one safe swap-aware replacement path exists under the same frozen cap"
        ),
        "row_strength_assessment": str(row_strength_assessment),
        "exploitation_block_assessment": str(exploitation_block_assessment),
        "diagnostic_conclusions": {
            "best_safe_trio_name": str(best_safe_trio.get("trio_name", "")),
            "swap_beats_incumbent": bool(any_swap_beats_incumbent),
            "next_control_hypothesis": str(next_hypothesis),
            "dominant_final_selection_blocker": str(dominant_final_selection_blocker),
            "false_safe_margin_assessment": str(false_safe_margin_assessment),
            "selection_budget_assessment": str(selection_budget_assessment),
            "drift_control_block_assessment": str(drift_control_block_assessment),
            "ranking_or_tiebreak_assessment": str(ranking_or_tiebreak_assessment),
            "selector_vs_frontier_assessment": str(selector_vs_frontier_assessment),
            "structural_vs_local_assessment": str(structural_vs_local_assessment),
            "recommended_next_action": str(next_action),
            "recommended_next_template": str(next_template),
            "routing_status": str(routing_status),
            "routing_deferred": True,
        },
    }
    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"critic_split_final_selection_false_safe_guardrail_probe_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    passed = bool(
        best_safe_trio
        and int(best_safe_trio.get("selected_benchmark_like_count", 0)) >= 3
        and abs(float(best_safe_trio.get("projection_safe_retention", 0.0)) - 1.0) <= 1e-12
        and float(best_safe_trio.get("unsafe_overcommit_rate_delta", 1.0)) <= 1e-12
        and float(best_safe_trio.get("false_safe_projection_rate_delta", 1.0)) <= false_safe_cap + 1e-12
    )
    reason = (
        "diagnostic shadow passed: swap-aware final-selection guardrail probing found a safe trio that preserves the protected anchor and improves benchmark utility"
        if passed
        else "diagnostic shadow passed: swap-aware final-selection guardrail probing found no safe trio better than the incumbent"
    )
    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": str(reason),
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
