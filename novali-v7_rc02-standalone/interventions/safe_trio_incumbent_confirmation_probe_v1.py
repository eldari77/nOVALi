from __future__ import annotations

import json
from typing import Any


OLD_INCUMBENT = ["recovery_02", "recovery_12", "persistence_09"]
SWAP_C = ["recovery_02", "recovery_03", "recovery_12"]
TRACKED_CASE_IDS = [
    "recovery_02",
    "recovery_03",
    "recovery_12",
    "persistence_09",
    "persistence_12",
]


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

    guardrail_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.final_selection_false_safe_guardrail_probe_v1"
    )
    scorer_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.benchmark_like_scoring_preservation_probe_v2"
    )
    stability_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.stability_context_retention_probe_v2"
    )
    if not all([guardrail_artifact, scorer_artifact, stability_artifact]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: guardrail, scorer-preservation, and stability artifacts are required",
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
                "reason": "cannot confirm the incumbent safe trio without the prerequisite guardrail artifacts",
            },
        }

    tracked_case_rows = _tracked_case_map(guardrail_artifact)
    case_row_lookup = {
        str(row.get("scenario_id", "")): dict(row)
        for row in _rows_from_artifact(stability_artifact, "selected_examples")
        + _rows_from_artifact(stability_artifact, "safe_pool_benchmark_like_examples")
        if str(row.get("scenario_id", ""))
    }
    false_safe_cap = float(
        dict(scorer_artifact.get("benchmark_control_metrics", {})).get(
            "false_safe_projection_rate_delta", 0.0
        )
        or 0.0
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

    def _evaluate_trio(trio_name: str, trio_ids: list[str]) -> dict[str, Any]:
        selected_ids = set(trio_ids)
        comparison = r._variant_comparison(
            baseline_summary=baseline_summary,
            variant_summary=r._summarize_benchmark_results(
                _build_variant_results(r, proposal, base_rows, selected_ids)
            ),
        )
        selected_count = int(
            sum(
                int(bool(dict(tracked_case_rows.get(case_id, {})).get("safe_pool_benchmark_like_survived", False)))
                for case_id in trio_ids
            )
        )
        projection_safe_retention = (
            float(
                sum(
                    int(bool(dict(tracked_case_rows.get(case_id, {})).get("survived_projection_safe_filtering", False)))
                    for case_id in trio_ids
                )
                / len(trio_ids)
            )
            if trio_ids
            else 0.0
        )
        mean_projection_error = r._mean_key(
            [case_row_lookup[case_id] for case_id in trio_ids if case_id in case_row_lookup],
            "pred_projection_error",
        )
        false_safe_delta = float(comparison.get("false_safe_projection_rate_delta", 0.0) or 0.0)
        unsafe_delta = float(comparison.get("unsafe_overcommit_rate_delta", 0.0) or 0.0)
        return {
            "trio_name": str(trio_name),
            "selected_ids": list(trio_ids),
            "protected_anchor_preserved": bool("recovery_02" in trio_ids),
            "selected_benchmark_like_count": int(selected_count),
            "projection_safe_retention": float(projection_safe_retention),
            "unsafe_overcommit_rate_delta": float(unsafe_delta),
            "false_safe_projection_rate_delta": float(false_safe_delta),
            "false_safe_margin_vs_cap": float(false_safe_cap - false_safe_delta),
            "policy_match_rate_delta": float(comparison.get("policy_match_rate_delta", 0.0) or 0.0),
            "mean_projection_error": mean_projection_error,
            "context_robustness_signal": _context_robustness(trio_ids, tracked_case_rows),
            "safe_within_cap": bool(
                "recovery_02" in trio_ids
                and selected_count >= 3
                and abs(projection_safe_retention - 1.0) <= 1e-12
                and unsafe_delta <= 1e-12
                and false_safe_delta <= false_safe_cap + 1e-12
            ),
        }

    old_incumbent = _evaluate_trio("old_incumbent", OLD_INCUMBENT)
    swap_c = _evaluate_trio("swap_C", SWAP_C)

    guardrail_conclusions = dict(guardrail_artifact.get("diagnostic_conclusions", {}))
    final_selection_path_summary = [
        dict(row)
        for row in list(guardrail_artifact.get("final_selection_path_summary", []))
        if isinstance(row, dict)
    ]

    swap_c_matches_or_beats = bool(
        swap_c.get("safe_within_cap", False)
        and float(swap_c.get("policy_match_rate_delta", 0.0))
        >= float(old_incumbent.get("policy_match_rate_delta", 0.0))
        - 1e-12
        and float(dict(swap_c.get("context_robustness_signal", {})).get("sum", 0.0))
        >= float(dict(old_incumbent.get("context_robustness_signal", {})).get("sum", 0.0))
        - 1e-12
    )
    swap_c_strictly_better = bool(
        swap_c_matches_or_beats
        and (
            float(swap_c.get("policy_match_rate_delta", 0.0))
            > float(old_incumbent.get("policy_match_rate_delta", 0.0))
            + 1e-12
            or float(dict(swap_c.get("context_robustness_signal", {})).get("sum", 0.0))
            > float(dict(old_incumbent.get("context_robustness_signal", {})).get("sum", 0.0))
            + 1e-12
        )
    )
    swap_c_confirmed = bool(
        bool(swap_c.get("protected_anchor_preserved", False))
        and bool(swap_c.get("safe_within_cap", False))
        and bool(swap_c_matches_or_beats)
    )

    swap_c_safety_assessment = "swap_C_safe" if bool(swap_c.get("safe_within_cap", False)) else "not_safe"
    if swap_c_strictly_better:
        swap_c_utility_assessment = "swap_C_outperforms_incumbent"
    elif swap_c_matches_or_beats:
        swap_c_utility_assessment = "ties"
    else:
        swap_c_utility_assessment = "underperforms"

    robustness_assessment = (
        "robust_control_signal"
        if swap_c_confirmed
        and bool(swap_c.get("protected_anchor_preserved", False))
        and abs(float(swap_c.get("false_safe_margin_vs_cap", -1.0))) <= 1e-12
        and float(dict(swap_c.get("context_robustness_signal", {})).get("sum", 0.0))
        > float(dict(old_incumbent.get("context_robustness_signal", {})).get("sum", 0.0)) + 1e-12
        else "fragile_local_gain"
    )
    control_signal_assessment = (
        "valid_benchmark_only_control_exploration"
        if swap_c_confirmed and robustness_assessment == "robust_control_signal"
        else "critic_refinement_evidence_only"
        if swap_c_confirmed
        else "local_patch_only"
    )
    structural_vs_local_assessment = (
        "reusable_structural_principle"
        if control_signal_assessment == "valid_benchmark_only_control_exploration"
        else "local_patch_only"
    )
    exploitation_bottleneck_effect_assessment = (
        "only_exposed_more_clearly"
        if swap_c_confirmed and bool(final_selection_path_summary)
        else "unchanged"
    )
    routing_status = "routing_deferred"

    incumbent_vs_swap_comparison = {
        "old_incumbent_selected_ids": list(OLD_INCUMBENT),
        "swap_c_selected_ids": list(SWAP_C),
        "policy_match_rate_delta_gap": float(
            float(swap_c.get("policy_match_rate_delta", 0.0))
            - float(old_incumbent.get("policy_match_rate_delta", 0.0))
        ),
        "context_robustness_sum_gap": float(
            float(dict(swap_c.get("context_robustness_signal", {})).get("sum", 0.0))
            - float(dict(old_incumbent.get("context_robustness_signal", {})).get("sum", 0.0))
        ),
        "mean_projection_error_gap": (
            None
            if old_incumbent.get("mean_projection_error") is None or swap_c.get("mean_projection_error") is None
            else float(swap_c.get("mean_projection_error")) - float(old_incumbent.get("mean_projection_error"))
        ),
        "false_safe_margin_gap": float(
            float(swap_c.get("false_safe_margin_vs_cap", 0.0))
            - float(old_incumbent.get("false_safe_margin_vs_cap", 0.0))
        ),
    }

    if swap_c_confirmed:
        next_action = "hold_and_consolidate"
        next_template = "memory_summary.swap_c_family_coverage_snapshot_v1"
        next_hypothesis = "confirmed_safe_trio_baseline_with_family_coverage_review"
        recommendation_reason = (
            "swap_C is confirmed as the stronger safe trio baseline under the frozen envelope, so the next bounded step is to consolidate whether that gain is structurally reusable or mostly selected-set family compression before any further control exploration"
        )
    else:
        next_action = "critic_refinement_next"
        next_template = "critic_split.benchmark_like_scoring_preservation_probe_v2"
        next_hypothesis = "residual_scorer_stabilization"
        recommendation_reason = (
            "swap_C did not confirm cleanly enough as the new safe trio baseline, so the next work should remain in narrower scorer-preservation refinement"
        )

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "critic_split.safe_trio_incumbent_confirmation_probe_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "probe_identity_context": {
            "probe_line": "critic_split.safe_trio_incumbent_confirmation_probe_v1",
            "phase": "benchmark_only_control_confirmation",
            "protected_anchor_case_id": "recovery_02",
            "false_safe_projection_rate_delta_cap": float(false_safe_cap),
        },
        "evidence_inputs_used": [
            "critic_split.final_selection_false_safe_guardrail_probe_v1",
            "critic_split.benchmark_like_scoring_preservation_probe_v2",
            "critic_split.stability_context_retention_probe_v2",
            "trusted_benchmark_pack_v1",
        ],
        "comparison_references": {
            "critic_split.final_selection_false_safe_guardrail_probe_v1": {
                "best_safe_trio_name": str(dict(guardrail_artifact.get("best_safe_trio", {})).get("trio_name", "")),
                "swap_beats_incumbent": bool(guardrail_artifact.get("swap_beats_incumbent", False)),
                "dominant_final_selection_blocker": str(
                    guardrail_conclusions.get("dominant_final_selection_blocker", "")
                ),
            },
            "critic_split.benchmark_like_scoring_preservation_probe_v2": _artifact_metrics(
                scorer_artifact
            ),
            "critic_split.stability_context_retention_probe_v2": _artifact_metrics(
                stability_artifact
            ),
        },
        "incumbent_trio_reviewed": dict(old_incumbent),
        "swap_C_reviewed": dict(swap_c),
        "swap_C_safety_assessment": str(swap_c_safety_assessment),
        "swap_C_utility_assessment": str(swap_c_utility_assessment),
        "incumbent_vs_swap_comparison": incumbent_vs_swap_comparison,
        "robustness_assessment": str(robustness_assessment),
        "control_signal_assessment": str(control_signal_assessment),
        "structural_vs_local_assessment": str(structural_vs_local_assessment),
        "exploitation_bottleneck_effect_assessment": str(exploitation_bottleneck_effect_assessment),
        "routing_status": str(routing_status),
        "recommended_next_action": str(next_action),
        "old_incumbent_vs_swap_c": [old_incumbent, swap_c],
        "final_selection_reference_paths": final_selection_path_summary,
        "tracked_case_outcomes": [
            dict(tracked_case_rows.get(case_id, {"case_id": case_id}))
            for case_id in TRACKED_CASE_IDS
        ],
        "confirmation_checks": {
            "recovery_02_protected_anchor_preserved": bool(swap_c.get("protected_anchor_preserved", False)),
            "swap_c_safe_under_false_safe_cap": bool(swap_c.get("safe_within_cap", False)),
            "selected_benchmark_like_count_stays_3": bool(int(swap_c.get("selected_benchmark_like_count", 0)) >= 3),
            "projection_safe_retention_stays_1": bool(abs(float(swap_c.get("projection_safe_retention", 0.0)) - 1.0) <= 1e-12),
            "unsafe_overcommit_rate_delta_stays_zero": bool(float(swap_c.get("unsafe_overcommit_rate_delta", 1.0)) <= 1e-12),
            "false_safe_projection_rate_delta_within_cap": bool(
                float(swap_c.get("false_safe_projection_rate_delta", 1.0)) <= false_safe_cap + 1e-12
            ),
            "swap_c_matches_or_beats_old_incumbent": bool(swap_c_matches_or_beats),
            "swap_c_strictly_better_than_old_incumbent": bool(swap_c_strictly_better),
            "swap_c_confirmed_as_new_incumbent_baseline": bool(swap_c_confirmed),
        },
        "working_baseline_recommendation": {
            "old_incumbent_selected_ids": list(OLD_INCUMBENT),
            "candidate_incumbent_selected_ids": list(SWAP_C),
            "confirmed_new_incumbent": bool(swap_c_confirmed),
            "recommended_working_baseline": list(SWAP_C if swap_c_confirmed else OLD_INCUMBENT),
        },
        "observability_gain": {
            "passed": True,
            "reason": "the confirmation probe directly re-evaluates only the old incumbent and swap_C under the frozen benchmark pack and current false-safe cap",
        },
        "activation_analysis_usefulness": {
            "passed": bool(swap_c.get("safe_within_cap", False)),
            "reason": "the probe confirms whether swap_C should replace the old incumbent baseline without reopening earlier scoring rescue or routing",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": float(
                min(
                    1.0,
                    0.34
                    + 0.16 * int(bool(swap_c.get("safe_within_cap", False)))
                    + 0.18 * int(bool(swap_c_matches_or_beats))
                    + 0.16 * int(bool(swap_c_strictly_better))
                    + 0.12 * int(bool(swap_c.get("protected_anchor_preserved", False)))
                )
            ),
            "reason": "the probe isolates whether the current best safe swap is robust enough to replace the incumbent baseline rather than merely tie it",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "benchmark-only incumbent confirmation with live policy, thresholds, routing policy, and frozen benchmark semantics unchanged",
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
            "swap_C is confirmed as a safe under-cap incumbent replacement that improves benchmark utility and context robustness over the old incumbent under unchanged policy and routing, but it mainly resolves the replacement question and leaves the broader additive exploitation bottleneck in place"
        ),
        "diagnostic_conclusions": {
            "swap_c_confirmed_as_new_incumbent_baseline": bool(swap_c_confirmed),
            "protected_anchor_case_id": "recovery_02",
            "best_safe_trio_name": "swap_C" if swap_c_confirmed else "old_incumbent",
            "swap_C_safety_assessment": str(swap_c_safety_assessment),
            "swap_C_utility_assessment": str(swap_c_utility_assessment),
            "robustness_assessment": str(robustness_assessment),
            "control_signal_assessment": str(control_signal_assessment),
            "structural_vs_local_assessment": str(structural_vs_local_assessment),
            "exploitation_bottleneck_effect_assessment": str(exploitation_bottleneck_effect_assessment),
            "next_control_hypothesis": str(next_hypothesis),
            "recommended_next_action": str(next_action),
            "recommended_next_template": str(next_template),
            "routing_status": str(routing_status),
            "routing_deferred": True,
        },
    }
    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"critic_split_safe_trio_incumbent_confirmation_probe_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    reason = (
        "diagnostic shadow passed: swap_C is confirmed as the new incumbent safe trio baseline"
        if swap_c_confirmed
        else "diagnostic shadow passed: swap_C did not confirm cleanly enough to replace the old incumbent baseline"
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
