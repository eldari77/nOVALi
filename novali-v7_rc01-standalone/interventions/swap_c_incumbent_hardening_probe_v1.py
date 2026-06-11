from __future__ import annotations

import json
from typing import Any


INCUMBENT_SWAP_C = ["recovery_02", "recovery_03", "recovery_12"]
TRACKED_RECOVERY = ["recovery_02", "recovery_03", "recovery_12"]
TRACKED_RESIDUAL = ["persistence_09", "persistence_12"]
TRACKED_CASES = TRACKED_RECOVERY + TRACKED_RESIDUAL


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
        "projection_safe_retention": _safe_float(metrics.get("projection_safe_retention")),
        "mean_projection_error": metrics.get("mean_projection_error"),
        "policy_match_rate_delta": metrics.get("policy_match_rate_delta"),
        "false_safe_projection_rate_delta": metrics.get("false_safe_projection_rate_delta"),
        "unsafe_overcommit_rate_delta": metrics.get("unsafe_overcommit_rate_delta"),
    }


def _tracked_case_map(artifact: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(dict(row).get("case_id", "")): dict(row)
        for row in list(artifact.get("tracked_case_outcomes", []))
        if isinstance(row, dict) and str(dict(row).get("case_id", ""))
    }


def _rows_from_artifact(artifact: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in list(dict(artifact.get("sample_rows", {})).get(key, []))
        if isinstance(row, dict)
    ]


def _build_variant_results(
    runner_mod, proposal: dict[str, Any], base_rows: list[dict[str, Any]], selected_ids: set[str]
) -> list[dict[str, Any]]:
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


def _context_robustness(ids: list[str], case_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    scores = [_safe_float(dict(case_rows.get(case_id, {})).get("context_pressure_score")) for case_id in ids]
    return {
        "sum": float(sum(scores)),
        "mean": float(sum(scores) / len(scores)) if scores else 0.0,
        "min": float(min(scores)) if scores else 0.0,
        "max": float(max(scores)) if scores else 0.0,
    }


def _swap_c_row_from_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    for row in list(artifact.get("old_incumbent_vs_swap_c", [])):
        if isinstance(row, dict) and str(dict(row).get("trio_name", "")) == "swap_C":
            return dict(row)
    for row in list(artifact.get("frontier_analysis_table", [])):
        if isinstance(row, dict) and str(dict(row).get("source_trio_name", "")) == "swap_C":
            return dict(row)
    for row in list(artifact.get("trio_comparison_table", [])):
        if isinstance(row, dict) and str(dict(row).get("trio_name", "")) == "incumbent_swap_c":
            return dict(row)
    best = dict(artifact.get("best_safe_trio", {}))
    if best and set(list(best.get("selected_ids", []))) == set(INCUMBENT_SWAP_C):
        return best
    return {}


def _normalize_swap_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "selected_ids": [str(item) for item in list(row.get("selected_ids", []))],
        "selected_benchmark_like_count": int(row.get("selected_benchmark_like_count", 0) or 0),
        "projection_safe_retention": _safe_float(row.get("projection_safe_retention")),
        "unsafe_overcommit_rate_delta": _safe_float(row.get("unsafe_overcommit_rate_delta")),
        "false_safe_projection_rate_delta": _safe_float(row.get("false_safe_projection_rate_delta")),
        "false_safe_margin_vs_cap": _safe_float(row.get("false_safe_margin_vs_cap")),
        "policy_match_rate_delta": _safe_float(row.get("policy_match_rate_delta")),
        "mean_projection_error": row.get("mean_projection_error"),
        "context_robustness_sum": _safe_float(
            row.get(
                "context_robustness_sum",
                dict(row.get("context_robustness_signal", {})).get("sum"),
            )
        ),
    }


def _normalize_family_candidate_row(row: dict[str, Any]) -> dict[str, Any]:
    context_signal = dict(row.get("context_robustness_signal", {}))
    return {
        "trio_name": str(row.get("trio_name", row.get("source_trio_name", ""))),
        "selected_ids": [str(item) for item in list(row.get("selected_ids", []))],
        "selected_benchmark_like_count": int(row.get("selected_benchmark_like_count", 0) or 0),
        "projection_safe_retention": _safe_float(row.get("projection_safe_retention", 1.0)),
        "unsafe_overcommit_rate_delta": _safe_float(row.get("unsafe_overcommit_rate_delta")),
        "false_safe_projection_rate_delta": _safe_float(row.get("false_safe_projection_rate_delta")),
        "false_safe_margin_vs_cap": _safe_float(row.get("false_safe_margin_vs_cap")),
        "policy_match_rate_delta": _safe_float(row.get("policy_match_rate_delta")),
        "mean_projection_error": row.get("mean_projection_error"),
        "context_robustness_sum": _safe_float(
            row.get("context_robustness_sum", context_signal.get("sum"))
        ),
        "safe_within_cap": bool(row.get("safe_within_cap", row.get("safe", False))),
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    del rounds, seeds
    from . import runner as r

    confirmation_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.safe_trio_incumbent_confirmation_probe_v1"
    )
    guardrail_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.final_selection_false_safe_guardrail_probe_v1"
    )
    invariance_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.safe_trio_false_safe_invariance_snapshot_v1"
    )
    coverage_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.swap_c_family_coverage_snapshot_v1"
    )
    scorer_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.benchmark_like_scoring_preservation_probe_v2"
    )
    persistence_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.persistence_balanced_safe_trio_probe_v1"
    )
    if not all(
        [
            confirmation_artifact,
            guardrail_artifact,
            invariance_artifact,
            coverage_artifact,
            scorer_artifact,
            persistence_artifact,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: incumbent confirmation, guardrail, invariance, coverage, scorer-preservation, and persistence-balance artifacts are required",
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
                "reason": "cannot harden the incumbent without the prerequisite trio and frontier artifacts",
            },
        }

    tracked_case_rows = _tracked_case_map(confirmation_artifact)
    case_row_lookup = {
        str(row.get("scenario_id", "")): dict(row)
        for row in _rows_from_artifact(scorer_artifact, "selected_examples")
        + _rows_from_artifact(scorer_artifact, "safe_pool_benchmark_like_examples")
        if str(row.get("scenario_id", ""))
    }
    false_safe_cap = _safe_float(
        dict(scorer_artifact.get("benchmark_control_metrics", {})).get("false_safe_projection_rate_delta")
    )

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
    comparison = r._variant_comparison(
        baseline_summary=baseline_summary,
        variant_summary=r._summarize_benchmark_results(
            _build_variant_results(r, proposal, base_rows, set(INCUMBENT_SWAP_C))
        ),
    )

    direct_swap_c = {
        "selected_ids": list(INCUMBENT_SWAP_C),
        "selected_benchmark_like_count": int(len(INCUMBENT_SWAP_C)),
        "projection_safe_retention": 1.0,
        "unsafe_overcommit_rate_delta": _safe_float(comparison.get("unsafe_overcommit_rate_delta")),
        "false_safe_projection_rate_delta": _safe_float(comparison.get("false_safe_projection_rate_delta")),
        "false_safe_margin_vs_cap": float(false_safe_cap - _safe_float(comparison.get("false_safe_projection_rate_delta"))),
        "policy_match_rate_delta": _safe_float(comparison.get("policy_match_rate_delta")),
        "mean_projection_error": r._mean_key(
            [case_row_lookup[case_id] for case_id in INCUMBENT_SWAP_C if case_id in case_row_lookup],
            "pred_projection_error",
        ),
        "context_robustness_signal": _context_robustness(INCUMBENT_SWAP_C, tracked_case_rows),
        "safe_within_cap": True,
        "trio_name": "swap_C_direct_replay",
    }
    direct_swap_c_review = _normalize_family_candidate_row(direct_swap_c)

    historical_rows = {
        "safe_trio_confirmation": _normalize_swap_row(_swap_c_row_from_artifact(confirmation_artifact)),
        "final_selection_guardrail": _normalize_swap_row(_swap_c_row_from_artifact(guardrail_artifact)),
        "false_safe_invariance_snapshot": _normalize_swap_row(_swap_c_row_from_artifact(invariance_artifact)),
        "persistence_balance_comparison": _normalize_swap_row(_swap_c_row_from_artifact(persistence_artifact)),
        "direct_replay": _normalize_swap_row(direct_swap_c),
    }
    comparable_history = [row for row in historical_rows.values() if row]
    identical_safety_profile = bool(
        comparable_history
        and all(int(row.get("selected_benchmark_like_count", 0)) == 3 for row in comparable_history)
        and all(abs(_safe_float(row.get("projection_safe_retention")) - 1.0) <= 1e-12 for row in comparable_history)
        and all(_safe_float(row.get("unsafe_overcommit_rate_delta")) <= 1e-12 for row in comparable_history)
        and all(abs(_safe_float(row.get("false_safe_projection_rate_delta")) - false_safe_cap) <= 1e-12 for row in comparable_history)
    )
    consistent_policy = len({_safe_float(row.get("policy_match_rate_delta")) for row in comparable_history}) == 1
    consistent_context = len({_safe_float(row.get("context_robustness_sum")) for row in comparable_history}) == 1
    incumbent_instability_detected = not bool(identical_safety_profile and consistent_policy and consistent_context)
    under_cap_hardening_improvement_found = bool(
        _safe_float(direct_swap_c_review.get("false_safe_margin_vs_cap")) > 1e-12
        or _safe_float(direct_swap_c_review.get("policy_match_rate_delta"))
        > max(
            (
                _safe_float(row.get("policy_match_rate_delta"))
                for name, row in historical_rows.items()
                if name != "direct_replay"
            ),
            default=0.0,
        )
        + 1e-12
    )

    incumbent_reviewed = _normalize_family_candidate_row(dict(confirmation_artifact.get("incumbent_trio_reviewed", {})))
    swap_c_reviewed = _normalize_family_candidate_row(dict(confirmation_artifact.get("swap_C_reviewed", {})))
    coverage_inventory = [
        _normalize_family_candidate_row(dict(row))
        for row in list(coverage_artifact.get("family_candidate_inventory", []))
        if isinstance(row, dict)
    ]
    if not incumbent_reviewed.get("selected_ids"):
        for row in coverage_inventory:
            if str(row.get("trio_name", "")) == "baseline":
                incumbent_reviewed = dict(row)
                break
    if not swap_c_reviewed.get("selected_ids"):
        for row in coverage_inventory:
            if str(row.get("trio_name", "")) == "swap_C":
                swap_c_reviewed = dict(row)
                break

    strongest_neighboring_family_candidates = sorted(
        [
            dict(row)
            for row in coverage_inventory
            if str(row.get("trio_name", "")) not in {"swap_C", "baseline"}
        ],
        key=lambda row: (
            _safe_float(row.get("policy_match_rate_delta")),
            _safe_float(row.get("context_robustness_sum")),
            -_safe_float(row.get("mean_projection_error"), 0.0),
        ),
        reverse=True,
    )[:3]
    top_neighbor = dict(strongest_neighboring_family_candidates[0]) if strongest_neighboring_family_candidates else {}

    swap_c_beats_incumbent = bool(
        _safe_float(direct_swap_c_review.get("policy_match_rate_delta"))
        > _safe_float(incumbent_reviewed.get("policy_match_rate_delta")) + 1e-12
        or (
            abs(
                _safe_float(direct_swap_c_review.get("policy_match_rate_delta"))
                - _safe_float(incumbent_reviewed.get("policy_match_rate_delta"))
            )
            <= 1e-12
            and _safe_float(direct_swap_c_review.get("context_robustness_sum"))
            > _safe_float(incumbent_reviewed.get("context_robustness_sum")) + 1e-12
        )
    )
    if top_neighbor:
        policy_gap_vs_neighbor = float(
            _safe_float(direct_swap_c_review.get("policy_match_rate_delta"))
            - _safe_float(top_neighbor.get("policy_match_rate_delta"))
        )
        context_gap_vs_neighbor = float(
            _safe_float(direct_swap_c_review.get("context_robustness_sum"))
            - _safe_float(top_neighbor.get("context_robustness_sum"))
        )
        if policy_gap_vs_neighbor > 1e-12:
            swap_vs_neighbor_status = "swap_C_still_best"
        elif abs(policy_gap_vs_neighbor) <= 1e-12:
            if context_gap_vs_neighbor > 1e-12:
                swap_vs_neighbor_status = "swap_C_still_best"
            elif abs(context_gap_vs_neighbor) <= 1e-12:
                swap_vs_neighbor_status = "swap_C_ties_best"
            else:
                swap_vs_neighbor_status = "swap_C_not_best"
        else:
            swap_vs_neighbor_status = "swap_C_not_best"
    else:
        policy_gap_vs_neighbor = 0.0
        context_gap_vs_neighbor = 0.0
        swap_vs_neighbor_status = "swap_C_still_best"

    swap_c_hardening_safety_assessment = (
        "swap_C_hardened_safe"
        if identical_safety_profile
        and _safe_float(direct_swap_c_review.get("projection_safe_retention")) >= 1.0 - 1e-12
        and _safe_float(direct_swap_c_review.get("unsafe_overcommit_rate_delta")) <= 1e-12
        and _safe_float(direct_swap_c_review.get("false_safe_margin_vs_cap")) >= -1e-12
        else "swap_C_safety_fragile"
    )
    swap_c_hardening_utility_assessment = str(swap_vs_neighbor_status)
    if swap_c_hardening_safety_assessment == "swap_C_hardened_safe" and swap_vs_neighbor_status == "swap_C_still_best":
        hardening_robustness_assessment = "hardened_incumbent_quality_candidate"
    elif swap_c_hardening_safety_assessment == "swap_C_hardened_safe":
        hardening_robustness_assessment = "promising_but_composition_sensitive_leader"
    else:
        hardening_robustness_assessment = "too_fragile_to_promote"

    structural_vs_local_assessment = str(hardening_robustness_assessment)
    exploitation_bottleneck_relation_assessment = (
        "final_selection_exploitation_bottleneck_confirmed"
        if str(dict(coverage_artifact.get("diagnostic_conclusions", {})).get("exploitation_bottleneck_relation_assessment", ""))
        == "final_selection_exploitation_bottleneck_confirmed"
        or str(dict(invariance_artifact.get("diagnostic_conclusions", {})).get("exploitation_bottleneck_relation_assessment", ""))
        == "final_selection_exploitation_bottleneck_confirmed"
        else "still_unclear"
    )

    recovery_case_report = {}
    for case_id in TRACKED_RECOVERY:
        base = dict(tracked_case_rows.get(case_id, {}))
        recovery_case_report[case_id] = {
            "survives_projection_safe_filtering": bool(base.get("survived_projection_safe_filtering", False)),
            "survives_safe_pool_admission": bool(base.get("survived_safe_pool", False)),
            "benchmark_like_scoring_survived": bool(base.get("safe_pool_benchmark_like_survived", False)),
            "selected_under_swap_c": True,
            "context_pressure_score": _safe_float(base.get("context_pressure_score")),
            "dominant_blocker": "none",
            "stability_note": (
                "protected anchor" if case_id == "recovery_02" else "selected in incumbent under flat frontier"
            ),
        }

    persistence_specific = {
        str(name): dict(payload)
        for name, payload in dict(coverage_artifact.get("persistence_specific_analysis", {})).items()
        if isinstance(payload, dict)
    }
    residual_watch_report = {}
    for case_id in TRACKED_RESIDUAL:
        base = dict(tracked_case_rows.get(case_id, {}))
        diag = dict(persistence_specific.get(case_id, {}))
        residual_watch_report[case_id] = {
            "survives_projection_safe_filtering": bool(
                diag.get("survives_projection_safe_filtering", base.get("survived_projection_safe_filtering", False))
            ),
            "survives_safe_pool_admission": bool(
                diag.get("survives_safe_pool_admission", base.get("survived_safe_pool", False))
            ),
            "survives_benchmark_like_scoring": bool(
                diag.get("survives_benchmark_like_scoring", base.get("safe_pool_benchmark_like_survived", False))
            ),
            "selected_under_swap_c": False,
            "blocked_at_final_selection_under_swap_c": bool(diag.get("blocked_at_final_selection_under_swap_c", True)),
            "best_local_reason": str(diag.get("best_local_reason", "excluded downstream under the fixed cap")),
        }

    if hardening_robustness_assessment == "hardened_incumbent_quality_candidate":
        recommended_next_action = "hold_and_consolidate"
        next_template = "memory_summary.false_safe_frontier_control_characterization_snapshot_v1"
        recommendation_reason = (
            "swap_C replays cleanly as the best safe trio under the frozen cap and still beats both the old incumbent and the strongest neighboring safe variants, so the next bounded step is to consolidate the frontier characterization rather than reopen another critic loop"
        )
        next_hypothesis = "confirmed_hardened_swap_c_incumbent"
    elif hardening_robustness_assessment == "promising_but_composition_sensitive_leader":
        recommended_next_action = "benchmark_only_control_exploration_next"
        next_template = "memory_summary.false_safe_frontier_control_characterization_snapshot_v1"
        recommendation_reason = (
            "swap_C remains promising and safe, but lingering composition sensitivity still warrants one consolidation pass on the frontier interpretation before treating it as fully hardened"
        )
        next_hypothesis = "composition_sensitive_swap_c_leader"
    else:
        recommended_next_action = "critic_refinement_next"
        next_template = "critic_split.final_selection_false_safe_guardrail_probe_v1"
        recommendation_reason = (
            "swap_C no longer looks stable enough to keep promoting as the incumbent, so the line should fall back to critic/frontier diagnosis under the same frozen envelope"
        )
        next_hypothesis = "swap_c_hardening_failed"

    operator_readable_conclusion = (
        "swap_C remains safely admissible under the frozen false-safe envelope, still beats the old incumbent, and also stays ahead of the strongest safe neighboring variants; composition sensitivity remains visible across the family, but not strongly enough to dislodge swap_C as the current hardened benchmark-only control candidate"
        if hardening_robustness_assessment == "hardened_incumbent_quality_candidate"
        else (
            "swap_C stays safe and useful, but the neighboring safe family remains close enough that the result is better read as a promising composition-sensitive leader than a fully hardened incumbent"
            if hardening_robustness_assessment == "promising_but_composition_sensitive_leader"
            else "swap_C does not hold a stable enough lead under hardening review to promote beyond provisional status"
        )
    )

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "critic_split.swap_c_incumbent_hardening_probe_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "probe_identity_context": {
            "phase": "benchmark_only_control_hardening_review",
            "probe_line": "critic_split.swap_c_incumbent_hardening_probe_v1",
            "protected_anchor_case_id": "recovery_02",
            "frozen_false_safe_projection_rate_delta_cap": float(false_safe_cap),
            "reviewed_safe_family_count": int(
                len([row for row in coverage_inventory if bool(row.get("safe_within_cap", False))])
            ),
        },
        "evidence_inputs_used": [
            "critic_split.safe_trio_incumbent_confirmation_probe_v1",
            "memory_summary.swap_c_family_coverage_snapshot_v1",
            "memory_summary.safe_trio_false_safe_invariance_snapshot_v1",
            "critic_split.final_selection_false_safe_guardrail_probe_v1",
            "critic_split.persistence_balanced_safe_trio_probe_v1",
            "critic_split.benchmark_like_scoring_preservation_probe_v2",
            "trusted_benchmark_pack_v1",
        ],
        "comparison_references": {
            "critic_split.safe_trio_incumbent_confirmation_probe_v1": {
                "swap_c_confirmed_as_new_incumbent_baseline": bool(
                    dict(confirmation_artifact.get("diagnostic_conclusions", {})).get(
                        "swap_c_confirmed_as_new_incumbent_baseline", False
                    )
                ),
                "best_safe_trio_name": str(
                    dict(confirmation_artifact.get("diagnostic_conclusions", {})).get("best_safe_trio_name", "")
                ),
            },
            "critic_split.final_selection_false_safe_guardrail_probe_v1": {
                "best_safe_trio_name": str(
                    dict(guardrail_artifact.get("diagnostic_conclusions", {})).get("best_safe_trio_name", "")
                ),
                "swap_beats_incumbent": bool(
                    dict(guardrail_artifact.get("diagnostic_conclusions", {})).get("swap_beats_incumbent", False)
                ),
            },
            "memory_summary.safe_trio_false_safe_invariance_snapshot_v1": {
                "false_safe_frontier_classification": str(
                    dict(invariance_artifact.get("diagnostic_conclusions", {})).get(
                        "false_safe_frontier_classification", ""
                    )
                ),
                "invariance_assessment": str(
                    dict(invariance_artifact.get("diagnostic_conclusions", {})).get("invariance_assessment", "")
                ),
                "measurable_headroom_under_cap": bool(
                    dict(invariance_artifact.get("diagnostic_conclusions", {})).get("measurable_headroom_under_cap", False)
                ),
            },
            "memory_summary.swap_c_family_coverage_snapshot_v1": {
                "classification": str(dict(coverage_artifact.get("diagnostic_conclusions", {})).get("classification", "")),
                "family_safe_candidate_count": int(
                    dict(coverage_artifact.get("diagnostic_conclusions", {})).get("family_safe_candidate_count", 0) or 0
                ),
                "family_outperforming_candidate_count": int(
                    dict(coverage_artifact.get("diagnostic_conclusions", {})).get("family_outperforming_candidate_count", 0) or 0
                ),
            },
            "critic_split.benchmark_like_scoring_preservation_probe_v2": _artifact_metrics(scorer_artifact),
        },
        "incumbent_reviewed": dict(incumbent_reviewed),
        "swap_C_reviewed": dict(direct_swap_c_review),
        "strongest_neighboring_family_candidates_reviewed": strongest_neighboring_family_candidates,
        "swap_C_hardening_safety_assessment": str(swap_c_hardening_safety_assessment),
        "swap_C_hardening_utility_assessment": str(swap_c_hardening_utility_assessment),
        "incumbent_vs_swap_hardening_comparison": {
            "swap_c_selected_ids": list(direct_swap_c_review.get("selected_ids", [])),
            "old_incumbent_selected_ids": list(incumbent_reviewed.get("selected_ids", [])),
            "policy_match_rate_delta_gap": float(
                _safe_float(direct_swap_c_review.get("policy_match_rate_delta"))
                - _safe_float(incumbent_reviewed.get("policy_match_rate_delta"))
            ),
            "context_robustness_sum_gap": float(
                _safe_float(direct_swap_c_review.get("context_robustness_sum"))
                - _safe_float(incumbent_reviewed.get("context_robustness_sum"))
            ),
            "false_safe_margin_gap": float(
                _safe_float(direct_swap_c_review.get("false_safe_margin_vs_cap"))
                - _safe_float(incumbent_reviewed.get("false_safe_margin_vs_cap"))
            ),
            "mean_projection_error_gap": float(
                _safe_float(direct_swap_c_review.get("mean_projection_error"))
                - _safe_float(incumbent_reviewed.get("mean_projection_error"))
            ),
            "swap_c_beats_incumbent": bool(swap_c_beats_incumbent),
        },
        "swap_vs_neighbor_comparison": {
            "top_neighbor_trio_name": str(top_neighbor.get("trio_name", "")),
            "top_neighbor_selected_ids": list(top_neighbor.get("selected_ids", [])),
            "policy_match_rate_delta_gap_vs_top_neighbor": float(policy_gap_vs_neighbor),
            "context_robustness_sum_gap_vs_top_neighbor": float(context_gap_vs_neighbor),
            "false_safe_margin_gap_vs_top_neighbor": float(
                _safe_float(direct_swap_c_review.get("false_safe_margin_vs_cap"))
                - _safe_float(top_neighbor.get("false_safe_margin_vs_cap"))
            ),
            "swap_c_neighbor_status": str(swap_vs_neighbor_status),
        },
        "hardening_robustness_assessment": str(hardening_robustness_assessment),
        "structural_vs_local_assessment": str(structural_vs_local_assessment),
        "exploitation_bottleneck_relation_assessment": str(exploitation_bottleneck_relation_assessment),
        "routing_status": "routing_deferred",
        "incumbent_robustness_report": {
            "selected_ids": list(direct_swap_c_review.get("selected_ids", [])),
            "selected_benchmark_like_count": int(direct_swap_c_review.get("selected_benchmark_like_count", 0)),
            "projection_safe_retention": _safe_float(direct_swap_c_review.get("projection_safe_retention")),
            "unsafe_overcommit_rate_delta": _safe_float(direct_swap_c_review.get("unsafe_overcommit_rate_delta")),
            "false_safe_projection_rate_delta": _safe_float(direct_swap_c_review.get("false_safe_projection_rate_delta")),
            "policy_match_rate_delta": _safe_float(direct_swap_c_review.get("policy_match_rate_delta")),
            "mean_projection_error": direct_swap_c_review.get("mean_projection_error"),
            "context_robustness_sum": _safe_float(direct_swap_c_review.get("context_robustness_sum")),
            "false_safe_margin_vs_cap": _safe_float(direct_swap_c_review.get("false_safe_margin_vs_cap")),
        },
        "historical_consistency_table": historical_rows,
        "recovery_case_stability_report": recovery_case_report,
        "residual_watch_report": residual_watch_report,
        "hardening_findings": {
            "swap_c_shows_instability_across_evaluated_contexts": bool(incumbent_instability_detected),
            "under_cap_hardening_improvement_found": bool(under_cap_hardening_improvement_found),
            "identical_safety_profile_across_replays": bool(identical_safety_profile),
            "policy_match_stable_across_replays": bool(consistent_policy),
            "context_robustness_stable_across_replays": bool(consistent_context),
            "productive_under_cap_critic_work_left": bool(under_cap_hardening_improvement_found),
            "baseline_should_remain_unchanged": bool(
                not incumbent_instability_detected and not under_cap_hardening_improvement_found
            ),
        },
        "observability_gain": {
            "passed": True,
            "reason": "the probe directly replays swap_C and checks it against the current confirmation, family coverage, balancing, and invariance artifacts",
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the probe determines whether swap_C still behaves like the strongest admissible control incumbent under the unchanged frozen cap",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": float(
                min(
                    1.0,
                    0.34
                    + 0.18 * int(identical_safety_profile)
                    + 0.12 * int(consistent_policy)
                    + 0.12 * int(consistent_context)
                    + 0.12 * int(swap_vs_neighbor_status == "swap_C_still_best")
                    + 0.08 * int(not under_cap_hardening_improvement_found)
                )
            ),
            "reason": "the probe separates true incumbent hardening from a merely local family advantage under the same flat false-safe frontier",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "benchmark-only incumbent-hardening probe with live policy, thresholds, routing policy, and frozen benchmark semantics unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_action": str(recommended_next_action),
            "recommended_next_template": str(next_template),
            "reason": str(recommendation_reason),
        },
        "decision_recommendation": {
            "recommended_next_action": str(recommended_next_action),
            "recommended_next_template": str(next_template),
            "rationale": str(recommendation_reason),
        },
        "recommended_next_action": str(recommended_next_action),
        "recommended_next_template": str(next_template),
        "review_rollback_deprecation_trigger_status": {
            "review_triggered": False,
            "rollback_triggered": False,
            "deprecation_triggered": False,
        },
        "resource_trust_accounting": {
            "network_mode": "none",
            "routing_changed": False,
            "thresholds_relaxed": False,
            "live_policy_changed": False,
            "projection_safe_envelope_changed": False,
            "trusted_input_sources": [
                "local novali-v4 diagnostic artifacts",
                "trusted benchmark pack",
                "local intervention analytics",
            ],
            "write_root": "novali-v4/data/diagnostic_memory",
        },
        "operator_readable_conclusion": str(operator_readable_conclusion),
        "diagnostic_conclusions": {
            "swap_c_remains_best_working_incumbent": bool(swap_vs_neighbor_status != "swap_C_not_best"),
            "swap_c_shows_instability": bool(incumbent_instability_detected),
            "under_cap_hardening_improvement_found": bool(under_cap_hardening_improvement_found),
            "baseline_should_remain_unchanged": bool(
                not incumbent_instability_detected and not under_cap_hardening_improvement_found
            ),
            "productive_under_cap_critic_work_left": bool(under_cap_hardening_improvement_found),
            "swap_C_hardening_safety_assessment": str(swap_c_hardening_safety_assessment),
            "swap_C_hardening_utility_assessment": str(swap_c_hardening_utility_assessment),
            "hardening_robustness_assessment": str(hardening_robustness_assessment),
            "structural_vs_local_assessment": str(structural_vs_local_assessment),
            "exploitation_bottleneck_relation_assessment": str(exploitation_bottleneck_relation_assessment),
            "next_control_hypothesis": str(next_hypothesis),
            "recommended_next_action": str(recommended_next_action),
            "recommended_next_template": str(next_template),
            "routing_deferred": True,
            "routing_status": "routing_deferred",
        },
    }
    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"critic_split_swap_c_incumbent_hardening_probe_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: swap_C incumbent hardening was replayed against the current safe-family frontier without changing routing, thresholds, or policy",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
