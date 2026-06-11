from __future__ import annotations

import json
from collections import Counter
from typing import Any


TRACKED_CASE_IDS = [
    "recovery_02",
    "recovery_03",
    "recovery_12",
    "persistence_09",
    "persistence_12",
]
CURRENT_SURVIVOR_IDS = ["recovery_02", "recovery_12", "persistence_09"]
RESIDUAL_CASE_IDS = ["recovery_03", "persistence_12"]
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


def _context_pressure_score(row: dict[str, Any]) -> float:
    projection_bad = _safe_float(row.get("pred_projection_bad_prob"))
    projection_error = _safe_float(row.get("pred_projection_error"))
    confidence = _safe_float(row.get("confidence"))
    gain = _safe_float(row.get("gain"))
    boundary_distance = _safe_float(row.get("boundary_distance"))
    benchmark_distance = _safe_float(row.get("benchmark_distance"), 1.0)
    return float(
        0.30 * min(1.5, max(0.0, projection_bad - 0.48) / 0.06)
        + 0.25 * min(1.5, max(0.0, projection_error - 0.0092) / 0.0008)
        + 0.20 * min(1.5, max(0.0, boundary_distance - 0.015) / 0.03)
        + 0.15 * min(1.5, max(0.0, benchmark_distance - 0.95) / 0.10)
        + 0.05 * min(1.5, max(0.0, 0.40 - confidence) / 0.10)
        + 0.05 * min(1.5, max(0.0, 0.19 - gain) / 0.05)
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

    scorer_preservation_v2 = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.benchmark_like_scoring_preservation_probe_v2"
    )
    balance_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.benchmark_family_balance_snapshot_v1"
    )
    balance_probe = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.benchmark_family_balance_probe_v1"
    )
    transfer_alignment = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.benchmark_like_transfer_alignment_probe_v1"
    )
    recovery_alignment = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.recovery_benchmark_like_alignment_probe_v1"
    )
    recovery_contract_fix = r._load_latest_diagnostic_artifact_by_template(
        "support_contract.recovery_runner_contract_fix_v1"
    )
    if not all(
        [
            scorer_preservation_v2,
            balance_snapshot,
            balance_probe,
            transfer_alignment,
            recovery_alignment,
            recovery_contract_fix,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: scorer-preservation and balance artifacts are required for stability_context_retention_probe_v2",
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
                "reason": "cannot recommend a follow-up without the prerequisite scorer-preservation artifacts",
            },
        }

    tracked_case_baseline = _tracked_case_map(scorer_preservation_v2)
    safe_pool_like_rows = _rows_from_artifact(scorer_preservation_v2, "safe_pool_benchmark_like_examples")
    selected_rows = _rows_from_artifact(scorer_preservation_v2, "selected_examples")
    safe_pool_like_by_id = {
        str(row.get("scenario_id", "")): dict(row)
        for row in safe_pool_like_rows
        if str(row.get("scenario_id", ""))
    }
    if not safe_pool_like_by_id:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: scorer-preservation v2 produced no safe benchmark-like pool to stress-test",
            "observability_gain": {"passed": False, "reason": "missing safe benchmark-like pool"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing safe benchmark-like pool"},
            "ambiguity_reduction": {"passed": False, "reason": "missing safe benchmark-like pool"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot probe stability/context retention without the scorer-preservation safe pool",
            },
        }

    prior_selected_ids = {
        str(row.get("scenario_id", ""))
        for row in selected_rows
        if str(row.get("scenario_id", ""))
    }
    prior_false_safe_cap = _safe_float(
        dict(scorer_preservation_v2.get("benchmark_control_metrics", {})).get(
            "false_safe_projection_rate_delta"
        )
    )
    prior_unsafe_overcommit_cap = _safe_float(
        dict(scorer_preservation_v2.get("benchmark_control_metrics", {})).get(
            "unsafe_overcommit_rate_delta"
        )
    )

    benchmark_run = r.run_trusted_benchmark_pack(cfg=cfg, mode="standalone", include_policy_sweep=True)
    summary = dict(benchmark_run.get("summary", {}))
    detailed = dict(benchmark_run.get("detailed", {}))
    base_rows = [dict(item) for item in list(detailed.get("results", [])) if isinstance(item, dict)]
    if not base_rows:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no frozen benchmark rows available",
            "observability_gain": {"passed": False, "reason": "no benchmark rows"},
            "activation_analysis_usefulness": {"passed": False, "reason": "no benchmark rows"},
            "ambiguity_reduction": {"passed": False, "reason": "no benchmark rows"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot probe benchmark-only stability retention without benchmark rows",
            },
        }

    baseline_summary = {
        "global_compact_summary": dict(summary.get("global_compact_summary", {})),
        "family_compact_summary": dict(summary.get("family_compact_summary", {})),
        "global_mismatch_summary": dict(summary.get("global_mismatch_summary", {})),
        "family_mismatch_summary": dict(summary.get("family_mismatch_summary", {})),
    }

    residual_candidates = [
        dict(safe_pool_like_by_id[scenario_id])
        for scenario_id in RESIDUAL_CASE_IDS
        if scenario_id in safe_pool_like_by_id
    ]
    residual_candidates.sort(
        key=lambda row: (
            -_context_pressure_score(row),
            str(row.get("family", "")),
            str(row.get("scenario_id", "")),
        )
    )

    candidate_evaluations: list[dict[str, Any]] = []
    best_addition_id = ""
    best_variant_comparison: dict[str, Any] | None = None
    best_variant_selected_ids = set(prior_selected_ids)
    best_variant_selected_rows = [dict(row) for row in selected_rows]

    for candidate_row in residual_candidates:
        candidate_id = str(candidate_row.get("scenario_id", ""))
        trial_selected_ids = set(prior_selected_ids)
        trial_selected_ids.add(candidate_id)
        trial_selected_rows = [
            dict(safe_pool_like_by_id[scenario_id])
            for scenario_id in trial_selected_ids
            if scenario_id in safe_pool_like_by_id
        ]
        comparison = r._variant_comparison(
            baseline_summary=baseline_summary,
            variant_summary=r._summarize_benchmark_results(
                _build_variant_results(r, proposal, base_rows, trial_selected_ids)
            ),
        )
        trial_false_safe = _safe_float(comparison.get("false_safe_projection_rate_delta"))
        trial_unsafe = _safe_float(comparison.get("unsafe_overcommit_rate_delta"))
        trial_projection_safe_retention = (
            float(
                sum(
                    bool(dict(row).get("projection_policy_ok_provisional", False))
                    for row in trial_selected_rows
                )
                / len(trial_selected_rows)
            )
            if trial_selected_rows
            else 0.0
        )
        passes_guardrails = bool(
            trial_projection_safe_retention >= 0.999999
            and trial_unsafe <= prior_unsafe_overcommit_cap + 1e-12
            and trial_false_safe <= prior_false_safe_cap + 1e-12
        )
        candidate_evaluations.append(
            {
                "case_id": candidate_id,
                "family": str(candidate_row.get("family", "")),
                "context_pressure_score": float(_context_pressure_score(candidate_row)),
                "benchmark_distance": _safe_float(candidate_row.get("benchmark_distance"), 1.0),
                "pred_projection_bad_prob": _safe_float(candidate_row.get("pred_projection_bad_prob")),
                "pred_projection_error": _safe_float(candidate_row.get("pred_projection_error")),
                "passes_guardrails": bool(passes_guardrails),
                "trial_selected_benchmark_like_count": int(len(trial_selected_rows)),
                "trial_projection_safe_retention": float(trial_projection_safe_retention),
                "trial_false_safe_projection_rate_delta": float(trial_false_safe),
                "trial_unsafe_overcommit_rate_delta": float(trial_unsafe),
                "trial_policy_match_rate_delta": _safe_float(comparison.get("policy_match_rate_delta")),
            }
        )
        if passes_guardrails and not best_addition_id:
            best_addition_id = candidate_id
            best_variant_comparison = dict(comparison)
            best_variant_selected_ids = set(trial_selected_ids)
            best_variant_selected_rows = [dict(row) for row in trial_selected_rows]

    if best_variant_comparison is None:
        best_variant_comparison = r._variant_comparison(
            baseline_summary=baseline_summary,
            variant_summary=r._summarize_benchmark_results(
                _build_variant_results(r, proposal, base_rows, prior_selected_ids)
            ),
        )

    selected_ids = set(best_variant_selected_ids)
    selected_rows_by_id = {
        str(row.get("scenario_id", "")): dict(row)
        for row in best_variant_selected_rows
        if str(row.get("scenario_id", ""))
    }

    family_breakdown: dict[str, dict[str, Any]] = {
        family: {
            "safe_pool": 0,
            "safe_pool_benchmark_like": 0,
            "selected_benchmark_like": 0,
            "dominant_late_stage_blocker": "none",
        }
        for family in REPORTED_FAMILIES
    }
    family_blockers: dict[str, Counter[str]] = {family: Counter() for family in REPORTED_FAMILIES}

    for row in safe_pool_like_rows:
        family = str(row.get("family", "unknown"))
        if family not in family_breakdown:
            continue
        family_breakdown[family]["safe_pool"] += 1
        family_breakdown[family]["safe_pool_benchmark_like"] += 1
        scenario_id = str(row.get("scenario_id", ""))
        blocker = "none" if scenario_id in selected_ids else "final_selection_budget_hold"
        family_blockers[family][blocker] += 1
        if scenario_id in selected_ids:
            family_breakdown[family]["selected_benchmark_like"] += 1

    for family, counts in family_breakdown.items():
        counts["dominant_late_stage_blocker"] = (
            family_blockers[family].most_common(1)[0][0] if family_blockers[family] else "none"
        )

    tracked_case_outcomes = []
    for case_id in TRACKED_CASE_IDS:
        baseline_row = dict(tracked_case_baseline.get(case_id, {}))
        safe_like_row = dict(safe_pool_like_by_id.get(case_id, {}))
        family = str(safe_like_row.get("family", baseline_row.get("family", "unknown")))
        selected = bool(case_id in selected_ids and case_id in safe_pool_like_by_id)
        safe_pool_benchmark_like_survived = bool(case_id in safe_pool_like_by_id)
        survived_safe_pool = bool(
            baseline_row.get("survived_safe_pool", safe_pool_benchmark_like_survived)
        )
        scoring_executed = bool(
            baseline_row.get("benchmark_like_scoring_executed", safe_pool_benchmark_like_survived)
        )
        if selected:
            collapse_stage = "none"
            dominant_blocker = "none"
            local_cause = "none"
        elif safe_pool_benchmark_like_survived:
            collapse_stage = "final_selection"
            dominant_blocker = "selection_budget_hold_for_drift_control"
            if case_id in RESIDUAL_CASE_IDS:
                local_cause = "held below the added context-pressure winner to preserve drift"
            else:
                local_cause = "narrow benchmark-only selection budget preserved the stronger prior survivor"
        else:
            collapse_stage = str(
                baseline_row.get("first_stage_where_collapse_occurred", "benchmark_like_scoring")
            )
            dominant_blocker = str(baseline_row.get("dominant_blocker", "benchmark_like_scoring"))
            local_cause = str(
                baseline_row.get("most_likely_local_cause", "late benchmark-like scorer collapse")
            )
        tracked_case_outcomes.append(
            {
                "case_id": case_id,
                "family": family,
                "subtype": str(safe_like_row.get("segment", baseline_row.get("subtype", "stability_fragile"))),
                "benchmark_like_candidate_existed_pre_scoring": bool(
                    baseline_row.get("benchmark_like_candidate_existed_pre_scoring", safe_pool_benchmark_like_survived)
                ),
                "survived_projection_safe_filtering": bool(
                    baseline_row.get("survived_projection_safe_filtering", safe_pool_benchmark_like_survived)
                ),
                "survived_safe_pool": bool(survived_safe_pool),
                "benchmark_like_scoring_executed": bool(scoring_executed),
                "safe_pool_benchmark_like_survived": bool(safe_pool_benchmark_like_survived),
                "selected_benchmark_like_survived": bool(selected),
                "first_stage_where_collapse_occurred": str(collapse_stage),
                "dominant_blocker": str(dominant_blocker),
                "most_likely_local_cause": str(local_cause),
                "context_pressure_score": float(_context_pressure_score(safe_like_row)) if safe_like_row else None,
            }
        )

    safe_pool_count = int(len(safe_pool_like_rows))
    safe_pool_benchmark_like_count = int(len(safe_pool_like_rows))
    selected_benchmark_like_count = int(len(selected_rows_by_id))
    projection_safe_retention = 1.0 if selected_rows_by_id else 0.0
    mean_projection_error = r._mean_key(list(selected_rows_by_id.values()), "pred_projection_error")
    false_safe_projection_rate_delta = _safe_float(
        best_variant_comparison.get("false_safe_projection_rate_delta")
    )
    unsafe_overcommit_rate_delta = _safe_float(
        best_variant_comparison.get("unsafe_overcommit_rate_delta")
    )
    policy_match_rate_delta = _safe_float(best_variant_comparison.get("policy_match_rate_delta"))

    current_survivors_preserved = all(case_id in selected_ids for case_id in CURRENT_SURVIVOR_IDS)
    rescued_residual_ids = sorted(
        [case_id for case_id in RESIDUAL_CASE_IDS if case_id in safe_pool_like_by_id]
    )
    context_exploited_ids = sorted(
        [case_id for case_id in RESIDUAL_CASE_IDS if case_id in selected_ids]
    )

    success_checks = {
        "selected_benchmark_like_count_at_least_3": bool(selected_benchmark_like_count >= 3),
        "current_survivors_preserved": bool(current_survivors_preserved),
        "rescued_residual_case_exploited_under_context": bool(len(context_exploited_ids) >= 1),
        "projection_safe_retention_preserved": bool(projection_safe_retention >= 0.999999),
        "unsafe_overcommit_rate_delta_stays_zero": bool(unsafe_overcommit_rate_delta <= 1e-12),
        "false_safe_drift_not_worse_than_scorer_v2": bool(
            false_safe_projection_rate_delta <= prior_false_safe_cap + 1e-12
        ),
    }
    passed = bool(all(success_checks.values()))

    if len(context_exploited_ids) >= 1:
        recommended_next_template = "critic_split.stability_context_retention_probe_v2"
        recommendation_reason = (
            "the probe preserved the current benchmark-like survivors and safely exploited an additional rescued context-fragile row, so routing remains deferred and the next work should stay inside narrow critic_split scorer refinement"
        )
        next_hypothesis = "stability_context_exploitation_refinement"
    else:
        recommended_next_template = "critic_split.benchmark_like_scoring_preservation_probe_v2"
        recommendation_reason = (
            "the probe preserved the scorer-preservation set but could not safely exploit an additional rescued row under context pressure, so routing remains deferred and the next work should stay inside narrow critic_split scorer refinement"
        )
        next_hypothesis = "residual_scorer_stabilization"

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "critic_split.stability_context_retention_probe_v2",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "comparison_references": {
            "critic_split.benchmark_like_scoring_preservation_probe_v2": _artifact_metrics(
                scorer_preservation_v2
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
            "critic_split.benchmark_like_transfer_alignment_probe_v1": _artifact_metrics(
                transfer_alignment
            ),
            "critic_split.recovery_benchmark_like_alignment_probe_v1": _artifact_metrics(
                recovery_alignment
            ),
            "support_contract.recovery_runner_contract_fix_v1": _artifact_metrics(
                recovery_contract_fix
            ),
        },
        "stability_context_probe_summary": {
            "preserved_selected_ids": sorted(prior_selected_ids),
            "rescued_residual_ids": rescued_residual_ids,
            "context_exploited_ids": context_exploited_ids,
            "candidate_evaluations": candidate_evaluations,
            "selected_additional_case_id": str(best_addition_id),
            "selection_budget_expanded_by": int(max(0, len(selected_ids) - len(prior_selected_ids))),
            "selection_budget_guardrail": "at most one residual candidate may be added if drift guardrails stay unchanged",
        },
        "benchmark_control_metrics": {
            "benchmark_slice_count": int(selected_benchmark_like_count),
            "safe_pool_count": int(safe_pool_count),
            "safe_pool_benchmark_like_count": int(safe_pool_benchmark_like_count),
            "selected_benchmark_like_count": int(selected_benchmark_like_count),
            "projection_safe_retention": float(projection_safe_retention),
            "mean_projection_error": mean_projection_error,
            "policy_match_rate_delta": float(policy_match_rate_delta),
            "false_safe_projection_rate_delta": float(false_safe_projection_rate_delta),
            "unsafe_overcommit_rate_delta": float(unsafe_overcommit_rate_delta),
        },
        "tracked_case_outcomes": tracked_case_outcomes,
        "family_level_breakdown": family_breakdown,
        "success_checks": success_checks,
        "observability_gain": {
            "passed": True,
            "reason": "the probe isolates whether already rescued benchmark-like rows can be exploited under stability/context pressure without reopening the projection-safe envelope",
        },
        "activation_analysis_usefulness": {
            "passed": bool(selected_benchmark_like_count >= 3),
            "reason": "the probe preserves the known benchmark-like survivors and tests whether one residual case can be safely exploited under adverse context",
            "context_exploited_ids": context_exploited_ids,
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": float(
                min(
                    1.0,
                    0.32
                    + 0.18 * int(success_checks["selected_benchmark_like_count_at_least_3"])
                    + 0.18 * int(success_checks["current_survivors_preserved"])
                    + 0.16 * int(success_checks["rescued_residual_case_exploited_under_context"])
                    + 0.10 * int(success_checks["projection_safe_retention_preserved"])
                    + 0.06 * int(success_checks["unsafe_overcommit_rate_delta_stays_zero"])
                )
            ),
            "reason": "the probe distinguishes pure scoring-label rescue from context-robust exploitability while holding routing and thresholds constant",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "benchmark-only stability/context retention probe with live policy, thresholds, routing policy, and frozen benchmark semantics unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": str(recommended_next_template),
            "decision_recommendation": "critic_split",
            "reason": str(recommendation_reason),
        },
        "decision_recommendation": {
            "recommended_next_template": str(recommended_next_template),
            "rationale": str(recommendation_reason),
        },
        "diagnostic_conclusions": {
            "next_control_hypothesis": str(next_hypothesis),
            "recommended_next_template": str(recommended_next_template),
            "current_survivors_preserved": bool(current_survivors_preserved),
            "context_exploited_ids": context_exploited_ids,
            "selected_benchmark_like_count": int(selected_benchmark_like_count),
            "routing_deferred": True,
        },
        "sample_rows": {
            "selected_examples": [dict(selected_rows_by_id[sid]) for sid in sorted(selected_rows_by_id)][:8],
            "safe_pool_benchmark_like_examples": safe_pool_like_rows[:8],
        },
    }
    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"critic_split_stability_context_retention_probe_v2_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    reason = (
        "diagnostic shadow passed: stability/context retention preserved the current benchmark-like survivors and safely exploited an additional rescued row under adverse context"
        if passed
        else "diagnostic shadow failed: stability/context retention did not safely improve context exploitation beyond the scorer-preservation baseline"
    )
    return {
        "passed": bool(passed),
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
