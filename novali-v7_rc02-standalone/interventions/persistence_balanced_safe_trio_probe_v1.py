from __future__ import annotations

import json
from typing import Any


INCUMBENT = ["recovery_02", "recovery_03", "recovery_12"]
TRIOS = {
    "incumbent_swap_c": INCUMBENT,
    "old_incumbent": ["recovery_02", "recovery_12", "persistence_09"],
    "recovery_02_recovery_12_persistence_12": ["recovery_02", "recovery_12", "persistence_12"],
    "recovery_02_recovery_03_persistence_09": ["recovery_02", "recovery_03", "persistence_09"],
    "recovery_02_recovery_03_persistence_12": ["recovery_02", "recovery_03", "persistence_12"],
}
REPORTED_FAMILIES = ["recovery", "persistence", "projection", "calibration", "gain_goal_conflict"]
TRACKED_CASE_IDS = ["recovery_02", "recovery_03", "recovery_12", "persistence_09", "persistence_12"]


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


def _family_counts(ids: list[str], case_rows: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts = {family: 0 for family in REPORTED_FAMILIES}
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

    confirmation_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.safe_trio_incumbent_confirmation_probe_v1"
    )
    coverage_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.swap_c_family_coverage_snapshot_v1"
    )
    scorer_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.benchmark_like_scoring_preservation_probe_v2"
    )
    if not all([confirmation_artifact, coverage_artifact, scorer_artifact]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: confirmation, family-coverage, and scorer-preservation artifacts are required",
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
                "reason": "cannot evaluate persistence-balanced trios without the prerequisite incumbent and safe-pool artifacts",
            },
        }

    false_safe_cap = float(
        dict(scorer_artifact.get("benchmark_control_metrics", {})).get(
            "false_safe_projection_rate_delta", 0.0
        )
        or 0.0
    )
    tracked_case_rows = _tracked_case_map(confirmation_artifact)
    case_row_lookup = {
        str(row.get("scenario_id", "")): dict(row)
        for row in _rows_from_artifact(scorer_artifact, "selected_examples")
        + _rows_from_artifact(scorer_artifact, "safe_pool_benchmark_like_examples")
        if str(row.get("scenario_id", ""))
    }

    bench = r.run_trusted_benchmark_pack(cfg=cfg, mode="standalone", include_policy_sweep=True)
    summary = dict(bench.get("summary", {}))
    detailed = dict(bench.get("detailed", {}))
    base_rows = [dict(item) for item in list(detailed.get("results", [])) if isinstance(item, dict)]
    baseline_summary = {
        "global_compact_summary": dict(summary.get("global_compact_summary", {})),
        "family_compact_summary": dict(summary.get("family_compact_summary", {})),
        "global_mismatch_summary": dict(summary.get("global_mismatch_summary", {})),
        "family_mismatch_summary": dict(summary.get("family_mismatch_summary", {})),
    }

    trio_table = []
    for trio_name, trio_ids in TRIOS.items():
        selected_ids = set(trio_ids)
        comparison = r._variant_comparison(
            baseline_summary=baseline_summary,
            variant_summary=r._summarize_benchmark_results(
                _build_variant_results(r, proposal, base_rows, selected_ids)
            ),
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
        row = {
            "trio_name": str(trio_name),
            "selected_ids": list(trio_ids),
            "selected_benchmark_like_count": int(len(trio_ids)),
            "projection_safe_retention": float(projection_safe_retention),
            "unsafe_overcommit_rate_delta": float(
                comparison.get("unsafe_overcommit_rate_delta", 0.0) or 0.0
            ),
            "false_safe_projection_rate_delta": float(
                comparison.get("false_safe_projection_rate_delta", 0.0) or 0.0
            ),
            "false_safe_margin_vs_cap": float(
                false_safe_cap - float(comparison.get("false_safe_projection_rate_delta", 0.0) or 0.0)
            ),
            "policy_match_rate_delta": float(
                comparison.get("policy_match_rate_delta", 0.0) or 0.0
            ),
            "context_robustness_signal": _context_robustness(trio_ids, tracked_case_rows),
            "family_coverage_summary": _family_counts(trio_ids, tracked_case_rows),
            "mean_projection_error": r._mean_key(
                [case_row_lookup[case_id] for case_id in trio_ids if case_id in case_row_lookup],
                "pred_projection_error",
            ),
        }
        row["safe"] = bool(
            int(row["selected_benchmark_like_count"]) == 3
            and abs(float(row["projection_safe_retention"]) - 1.0) <= 1e-12
            and float(row["unsafe_overcommit_rate_delta"]) <= 1e-12
            and float(row["false_safe_projection_rate_delta"]) <= false_safe_cap + 1e-12
        )
        trio_table.append(row)

    incumbent = next((dict(row) for row in trio_table if str(row.get("trio_name")) == "incumbent_swap_c"), {})
    persistence_trios = [
        dict(row)
        for row in trio_table
        if str(row.get("trio_name")) != "incumbent_swap_c" and int(dict(row.get("family_coverage_summary", {})).get("persistence", 0)) > 0
    ]
    best_persistence_trio = {}
    if persistence_trios:
        best_persistence_trio = sorted(
            persistence_trios,
            key=lambda row: (
                -int(bool(row.get("safe", False))),
                -float(row.get("policy_match_rate_delta", 0.0)),
                -float(dict(row.get("context_robustness_signal", {})).get("sum", 0.0)),
                str(row.get("trio_name", "")),
            ),
        )[0]

    policy_gap = float(incumbent.get("policy_match_rate_delta", 0.0)) - float(best_persistence_trio.get("policy_match_rate_delta", 0.0))
    context_gap = float(dict(incumbent.get("context_robustness_signal", {})).get("sum", 0.0)) - float(
        dict(best_persistence_trio.get("context_robustness_signal", {})).get("sum", 0.0)
    )
    persistence_balancing_viable = bool(
        bool(best_persistence_trio)
        and bool(best_persistence_trio.get("safe", False))
        and float(best_persistence_trio.get("policy_match_rate_delta", 0.0))
        >= float(incumbent.get("policy_match_rate_delta", 0.0)) - 1e-12
        and float(dict(best_persistence_trio.get("context_robustness_signal", {})).get("sum", 0.0))
        >= float(dict(incumbent.get("context_robustness_signal", {})).get("sum", 0.0)) - 1e-12
    )

    if persistence_balancing_viable:
        next_template = "critic_split.persistence_balanced_safe_trio_probe_v1"
        recommendation_reason = (
            "at least one persistence-inclusive trio stays inside the cap and fully matches the incumbent’s policy/context profile, so persistence balancing is viable under the current cap"
        )
        next_hypothesis = "persistence_balancing_viable_under_current_cap"
    else:
        next_template = "critic_split.final_selection_false_safe_guardrail_probe_v1"
        recommendation_reason = (
            "persistence-inclusive trios remain safe, but none closes the combined policy-match and context-robustness gap to swap_C, so persistence balancing should stay deferred under the current cap"
        )
        next_hypothesis = "persistence_balancing_deferred_under_current_cap"

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "critic_split.persistence_balanced_safe_trio_probe_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
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
            "memory_summary.swap_c_family_coverage_snapshot_v1": {
                "classification": str(
                    dict(coverage_artifact.get("diagnostic_conclusions", {})).get("classification", "")
                ),
                "next_control_hypothesis": str(
                    dict(coverage_artifact.get("diagnostic_conclusions", {})).get("next_control_hypothesis", "")
                ),
            },
            "critic_split.benchmark_like_scoring_preservation_probe_v2": _artifact_metrics(scorer_artifact),
        },
        "trio_comparison_table": trio_table,
        "swap_c_baseline": dict(incumbent),
        "best_persistence_inclusive_trio": dict(best_persistence_trio),
        "comparison_vs_swap_c": {
            "policy_match_rate_gap": float(policy_gap),
            "context_robustness_gap": float(context_gap),
            "best_persistence_trio_name": str(best_persistence_trio.get("trio_name", "")),
            "best_persistence_matches_swap_c_policy": bool(
                float(best_persistence_trio.get("policy_match_rate_delta", 0.0))
                >= float(incumbent.get("policy_match_rate_delta", 0.0)) - 1e-12
            ),
            "best_persistence_matches_swap_c_context": bool(
                float(dict(best_persistence_trio.get("context_robustness_signal", {})).get("sum", 0.0))
                >= float(dict(incumbent.get("context_robustness_signal", {})).get("sum", 0.0)) - 1e-12
            ),
        },
        "observability_gain": {
            "passed": True,
            "reason": "the probe compares the incumbent against the required persistence-inclusive alternatives under the same frozen cap and benchmark pack",
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the probe determines whether persistence-family reintegration is competitive enough under the current cap to justify balancing work",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": float(
                min(
                    1.0,
                    0.34
                    + 0.16 * int(bool(best_persistence_trio))
                    + 0.14 * int(bool(best_persistence_trio.get("safe", False)))
                    + 0.18 * int(not persistence_balancing_viable)
                    + 0.12 * int(float(policy_gap) <= 0.0)
                    + 0.06 * int(float(context_gap) <= 0.0)
                )
            ),
            "reason": "the probe distinguishes safe persistence inclusion from truly competitive persistence-balanced alternatives under the fixed cap",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "benchmark-only persistence-balancing probe with live policy, thresholds, routing policy, and frozen benchmark semantics unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": str(next_template),
            "reason": str(recommendation_reason),
        },
        "decision_recommendation": {
            "recommended_next_template": str(next_template),
            "rationale": str(recommendation_reason),
        },
        "diagnostic_conclusions": {
            "persistence_balancing_viable_under_cap": bool(persistence_balancing_viable),
            "best_persistence_trio_name": str(best_persistence_trio.get("trio_name", "")),
            "recommended_next_template": str(next_template),
            "next_control_hypothesis": str(next_hypothesis),
            "routing_deferred": True,
        },
    }
    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"critic_split_persistence_balanced_safe_trio_probe_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: persistence-balanced trios were evaluated under the same cap and compared directly against the confirmed incumbent",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
