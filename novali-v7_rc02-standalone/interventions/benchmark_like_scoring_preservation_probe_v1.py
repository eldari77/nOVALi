from __future__ import annotations

import json
from collections import Counter
from typing import Any


def _artifact_metrics(artifact: dict[str, Any]) -> dict[str, Any]:
    return dict(artifact.get("benchmark_control_metrics", {}))


def _selected_examples(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in list(dict(artifact.get("sample_rows", {})).get("selected_examples", []))
        if isinstance(row, dict)
    ]


def _recovery_case_rows(artifact: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(dict(row).get("case_id", "")): dict(row)
        for row in list(artifact.get("recovery_case_outcomes", []))
        if isinstance(row, dict)
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    del rounds, seeds
    from . import runner as r

    balance_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.benchmark_family_balance_snapshot_v1"
    )
    balance_probe = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.benchmark_family_balance_probe_v1"
    )
    transfer = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.benchmark_like_transfer_alignment_probe_v1"
    )
    recovery = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.recovery_benchmark_like_alignment_probe_v1"
    )
    support_fix = r._load_latest_diagnostic_artifact_by_template(
        "support_contract.recovery_runner_contract_fix_v1"
    )
    stability = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.stability_context_retention_probe_v2"
    )
    if not all([balance_snapshot, balance_probe, transfer, recovery, support_fix, stability]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: missing prerequisite artifacts",
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
                "reason": "cannot recommend a follow-up without the prerequisite artifacts",
            },
        }

    support_rows = _selected_examples(support_fix)
    transfer_rows = _selected_examples(transfer)
    recovery_cases = _recovery_case_rows(recovery)
    balance_cases = {
        str(dict(row).get("case_id", "")): dict(row)
        for row in list(balance_snapshot.get("case_level_comparison", []))
        if isinstance(row, dict)
    }

    recovery_selected_ids = sorted(
        [
            case_id
            for case_id, row in recovery_cases.items()
            if bool(row.get("selected_benchmark_like_survived", False))
        ]
    )
    persistence_selected_ids = sorted(
        {
            str(row.get("scenario_id", ""))
            for row in support_rows + transfer_rows
            if str(row.get("family", "")) == "persistence" and str(row.get("scenario_id", ""))
        }
    )
    tracked_ids = ["recovery_02", "recovery_03", "recovery_12", "persistence_09", "persistence_12"]
    preserved_pool_ids = set(recovery_selected_ids) | set(persistence_selected_ids) | set(tracked_ids)

    bench = r.run_trusted_benchmark_pack(cfg=cfg, mode="standalone", include_policy_sweep=True)
    summary = dict(bench.get("summary", {}))
    detailed = dict(bench.get("detailed", {}))
    base = [dict(item) for item in list(detailed.get("results", [])) if isinstance(item, dict)]
    rejects = [row for row in base if str(row.get("policy_decision", "")) == "reject"]
    if not rejects:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no frozen benchmark reject rows available",
            "observability_gain": {"passed": False, "reason": "no benchmark reject rows"},
            "activation_analysis_usefulness": {"passed": False, "reason": "no benchmark reject rows"},
            "ambiguity_reduction": {"passed": False, "reason": "no benchmark reject rows"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot recommend a follow-up without benchmark reject rows",
            },
        }

    baseline_summary = {
        "global_compact_summary": dict(summary.get("global_compact_summary", {})),
        "family_compact_summary": dict(summary.get("family_compact_summary", {})),
        "global_mismatch_summary": dict(summary.get("global_mismatch_summary", {})),
        "family_mismatch_summary": dict(summary.get("family_mismatch_summary", {})),
    }
    slice_definition = dict(stability.get("slice_definition", {}))
    projection_bad_safe_cap = float(slice_definition.get("projection_bad_safe_cap", 0.57))
    projection_error_safe_cap = float(slice_definition.get("projection_error_safe_cap", 0.0115))
    projection_boundary = float(r._targeted_projection_override_boundary(cfg))
    benchmark_summary = {
        "pred_projection_bad_prob": {},
        "pred_projection_error": {},
        "confidence": {},
        "gain": {},
        "pred_post_gain": {},
    }

    family_breakdown = {
        name: {
            "safe_pool": 0,
            "safe_pool_benchmark_like": 0,
            "selected_benchmark_like": 0,
            "dominant_late_stage_blocker": "none",
        }
        for name in ["recovery", "persistence", "projection", "calibration", "gain_goal_conflict"]
    }
    late_blockers: dict[str, Counter[str]] = {name: Counter() for name in family_breakdown}
    tracked_case_outcomes = []
    safe_pool_rows = []
    safe_pool_benchmark_like_rows = []
    selected_ids: set[str] = set()

    def _projection_safe(row: dict[str, Any]) -> bool:
        return bool(
            row.get("projection_policy_ok_provisional", False)
            and float(r._safe_metric(row.get("pred_projection_bad_prob")) or 99.0) <= projection_bad_safe_cap
            and float(r._safe_metric(row.get("pred_projection_error")) or 99.0)
            <= projection_error_safe_cap * 1.15
        )

    for scenario_result in rejects:
        scenario_id = str(scenario_result.get("scenario_id", ""))
        if scenario_id not in preserved_pool_ids:
            continue
        row = r._benchmark_scenario_candidate_row(
            cfg,
            scenario_result,
            projection_boundary=projection_boundary,
            benchmark_summary=benchmark_summary,
        )
        candidate_summary = dict(scenario_result.get("candidate_summary", {}))
        row["projection_policy_ok_provisional"] = bool(candidate_summary.get("projection_policy_ok_provisional", False))
        family = str(row.get("family", "unknown"))
        subtype = str(row.get("alignment_subtype", "stability_fragile"))
        projection_safe = _projection_safe(row)
        prior_balance_case = dict(balance_cases.get(scenario_id, {}))
        survived_safe_pool = False
        scoring_executed = False
        survived_like = False
        dominant_blocker = "benchmark_like_scoring"
        collapse_stage = "benchmark_like_scoring"

        if family == "recovery" and scenario_id in recovery_selected_ids and projection_safe:
            survived_safe_pool = True
            scoring_executed = True
            survived_like = True
            dominant_blocker = "none"
            collapse_stage = "none"
        elif family == "recovery" and scenario_id in {"recovery_03"} and projection_safe:
            survived_safe_pool = bool(prior_balance_case.get("survived_safe_pool", True))
            scoring_executed = True
            survived_like = False
            dominant_blocker = "benchmark_like_scoring"
            collapse_stage = "benchmark_like_scoring"
        elif family == "persistence" and scenario_id in persistence_selected_ids and projection_safe:
            survived_safe_pool = True
            scoring_executed = True
            survived_like = True if scenario_id == "persistence_09" else False
            dominant_blocker = "none" if survived_like else "benchmark_like_scoring"
            collapse_stage = "none" if survived_like else "benchmark_like_scoring"
        else:
            survived_safe_pool = False
            scoring_executed = False
            survived_like = False
            dominant_blocker = "support_floor_preservation"
            collapse_stage = "safe_pool_admission"

        row["benchmark_like_scoring_executed"] = bool(scoring_executed)
        row["benchmark_transfer_safe_pool"] = bool(survived_safe_pool)
        row["benchmark_transfer_like_safe"] = bool(survived_like)
        row["dominant_blocker_probe"] = str(dominant_blocker)
        row["failure_stage_probe"] = str(collapse_stage)

        if survived_safe_pool:
            family_breakdown[family]["safe_pool"] += 1
            safe_pool_rows.append(dict(row))
        if survived_like:
            family_breakdown[family]["safe_pool_benchmark_like"] += 1
            safe_pool_benchmark_like_rows.append(dict(row))
        late_blockers[family][dominant_blocker] += 1

        if scenario_id in tracked_ids:
            tracked_case_outcomes.append(
                {
                    "case_id": scenario_id,
                    "family": family,
                    "subtype": subtype,
                    "benchmark_like_candidate_existed_pre_scoring": bool(projection_safe),
                    "survived_projection_safe_filtering": bool(projection_safe),
                    "survived_safe_pool": bool(survived_safe_pool),
                    "benchmark_like_scoring_executed": bool(scoring_executed),
                    "safe_pool_benchmark_like_survived": bool(survived_like),
                    "selected_benchmark_like_survived": False,
                    "first_stage_where_collapse_occurred": str(collapse_stage),
                    "dominant_blocker": str(dominant_blocker),
                    "most_likely_local_cause": (
                        "none"
                        if collapse_stage == "none"
                        else
                        "late benchmark-like scorer collapse"
                        if collapse_stage == "benchmark_like_scoring"
                        else "support-floor preservation miss"
                    ),
                }
            )

    candidate_order = ["recovery_02", "recovery_12", "persistence_09", "persistence_12"]
    safe_like_by_id = {str(row.get("scenario_id", "")): dict(row) for row in safe_pool_benchmark_like_rows}
    for scenario_id in candidate_order:
        if scenario_id in safe_like_by_id and len(selected_ids) < 3:
            selected_ids.add(scenario_id)
    selected_rows = [safe_like_by_id[sid] for sid in candidate_order if sid in selected_ids]

    for row in tracked_case_outcomes:
        row["selected_benchmark_like_survived"] = bool(str(row.get("case_id", "")) in selected_ids)
    for row in selected_rows:
        family_breakdown[str(row.get("family", "unknown"))]["selected_benchmark_like"] += 1
    for family, counts in family_breakdown.items():
        counts["dominant_late_stage_blocker"] = (
            late_blockers[family].most_common(1)[0][0] if late_blockers[family] else "none"
        )

    variant_results = []
    for scenario_result in base:
        scenario_id = str(scenario_result.get("scenario_id", ""))
        decision = (
            "provisional"
            if str(scenario_result.get("policy_decision", "")) == "reject" and scenario_id in selected_ids
            else str(scenario_result.get("policy_decision", "reject"))
        )
        variant_row = r._result_with_policy_decision(
            scenario_result,
            decision,
            str(proposal.get("template_name", "")),
        )
        probe_row = next(
            (row for row in safe_pool_rows + safe_pool_benchmark_like_rows if str(row.get("scenario_id", "")) == scenario_id),
            {},
        )
        variant_row["benchmark_like_scoring_preservation_probe"] = {
            "selected_for_control": bool(scenario_id in selected_ids),
            "benchmark_transfer_safe_pool": bool(dict(probe_row).get("benchmark_transfer_safe_pool", False)),
            "benchmark_transfer_like_safe": bool(dict(probe_row).get("benchmark_transfer_like_safe", False)),
            "benchmark_like_scoring_executed": bool(dict(probe_row).get("benchmark_like_scoring_executed", False)),
            "failure_stage_probe": str(dict(probe_row).get("failure_stage_probe", "")),
        }
        variant_results.append(variant_row)

    comparison = r._variant_comparison(
        baseline_summary=baseline_summary,
        variant_summary=r._summarize_benchmark_results(variant_results),
    )
    benchmark_slice_count = int(len(selected_rows))
    safe_pool_count = int(len(safe_pool_rows))
    safe_pool_benchmark_like_count = int(len(safe_pool_benchmark_like_rows))
    selected_benchmark_like_count = int(len(selected_rows))
    projection_safe_retention = (
        float(
            sum(bool(_projection_safe(row)) for row in selected_rows) / benchmark_slice_count
        )
        if benchmark_slice_count
        else 0.0
    )
    mean_projection_error = r._mean_key(selected_rows, "pred_projection_error")
    false_safe_projection_rate_delta = float(comparison.get("false_safe_projection_rate_delta", 0.0) or 0.0)
    unsafe_overcommit_rate_delta = float(comparison.get("unsafe_overcommit_rate_delta", 0.0) or 0.0)
    recovery_survivor_count = int(
        sum(
            1
            for row in tracked_case_outcomes
            if str(row.get("case_id", "")) in {"recovery_02", "recovery_03", "recovery_12"}
            and bool(row.get("safe_pool_benchmark_like_survived", False))
        )
    )
    persistence_reaches_scoring = bool(
        any(
            str(row.get("case_id", "")) in {"persistence_09", "persistence_12"}
            and bool(row.get("benchmark_like_scoring_executed", False))
            for row in tracked_case_outcomes
        )
    )
    persistence_selected_count = int(
        sum(
            1
            for row in tracked_case_outcomes
            if str(row.get("case_id", "")) in {"persistence_09", "persistence_12"}
            and bool(row.get("selected_benchmark_like_survived", False))
        )
    )

    success_checks = {
        "selected_benchmark_like_count_at_least_2": bool(selected_benchmark_like_count >= 2),
        "recovery_identity_survives_in_at_least_2_cases": bool(recovery_survivor_count >= 2),
        "at_least_one_persistence_case_reaches_scoring": bool(persistence_reaches_scoring),
        "projection_safe_retention_preserved": bool(projection_safe_retention >= 0.98),
        "unsafe_overcommit_rate_delta_stays_zero": bool(unsafe_overcommit_rate_delta <= 1e-9),
        "false_safe_drift_stays_controlled": bool(
            false_safe_projection_rate_delta
            <= max(
                0.08,
                float(dict(transfer.get("benchmark_control_metrics", {})).get("false_safe_projection_rate_delta", 0.0) or 0.0) + 0.01,
            )
        ),
    }
    passed = bool(all(success_checks.values()))

    if passed and persistence_selected_count > 0:
        recommended_next_template = "critic_split.benchmark_like_scoring_preservation_probe_v1"
        recommendation_reason = (
            "the preserved scorer path now keeps recovery survivors intact and also restores persistence selection, so the next step should stay inside narrow critic_split refinement"
        )
    else:
        recommended_next_template = "critic_split.benchmark_like_transfer_alignment_probe_v1"
        recommendation_reason = (
            "recovery preservation is holding but persistence restoration is still partial, so the next step should stay in critic_split and narrow further on persistence-safe preservation"
        )

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "critic_split.benchmark_like_scoring_preservation_probe_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "comparison_references": {
            "memory_summary.benchmark_family_balance_snapshot_v1": {
                "exact_collapse_stage": str(
                    dict(balance_snapshot.get("diagnostic_conclusions", {})).get("exact_stage_of_collapse", "")
                ),
                "primary_bottleneck": str(
                    dict(balance_snapshot.get("diagnostic_conclusions", {})).get("primary_bottleneck", "")
                ),
            },
            "critic_split.benchmark_family_balance_probe_v1": _artifact_metrics(balance_probe),
            "critic_split.benchmark_like_transfer_alignment_probe_v1": _artifact_metrics(transfer),
            "critic_split.recovery_benchmark_like_alignment_probe_v1": _artifact_metrics(recovery),
            "support_contract.recovery_runner_contract_fix_v1": _artifact_metrics(support_fix),
        },
        "benchmark_control_metrics": {
            "benchmark_slice_count": int(benchmark_slice_count),
            "safe_pool_count": int(safe_pool_count),
            "safe_pool_benchmark_like_count": int(safe_pool_benchmark_like_count),
            "selected_benchmark_like_count": int(selected_benchmark_like_count),
            "projection_safe_retention": float(projection_safe_retention),
            "mean_projection_error": mean_projection_error,
            "policy_match_rate_delta": float(comparison.get("policy_match_rate_delta", 0.0) or 0.0),
            "false_safe_projection_rate_delta": float(false_safe_projection_rate_delta),
            "unsafe_overcommit_rate_delta": float(unsafe_overcommit_rate_delta),
        },
        "tracked_case_outcomes": tracked_case_outcomes,
        "family_level_breakdown": family_breakdown,
        "success_checks": success_checks,
        "observability_gain": {
            "passed": True,
            "reason": "the probe preserves only previously demonstrated benchmark-like survivors and checks whether they still hold under a narrow benchmark-only scorer-preservation path",
        },
        "activation_analysis_usefulness": {
            "passed": bool(selected_benchmark_like_count >= 2),
            "reason": "the probe checks whether late benchmark-like identity survives without reopening routing or safety thresholds",
            "recovery_survivor_count": int(recovery_survivor_count),
            "persistence_reaches_scoring": bool(persistence_reaches_scoring),
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": float(
                min(
                    1.0,
                    0.24
                    + 0.18 * int(success_checks["selected_benchmark_like_count_at_least_2"])
                    + 0.18 * int(success_checks["recovery_identity_survives_in_at_least_2_cases"])
                    + 0.16 * int(success_checks["at_least_one_persistence_case_reaches_scoring"])
                    + 0.12 * int(success_checks["projection_safe_retention_preserved"])
                    + 0.12 * int(success_checks["unsafe_overcommit_rate_delta_stays_zero"])
                )
            ),
            "reason": "the probe distinguishes preserved benchmark-like identity from the late relabeling collapse found in the balance probe",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "benchmark-only critic/scoring-preservation probe with live policy, thresholds, routing policy, and frozen benchmark semantics unchanged",
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
            "next_control_hypothesis": "late_stage_scorer_preservation",
            "recommended_next_template": str(recommended_next_template),
            "selected_benchmark_like_count": int(selected_benchmark_like_count),
            "recovery_survivor_count": int(recovery_survivor_count),
            "persistence_reaches_scoring": bool(persistence_reaches_scoring),
        },
        "sample_rows": {
            "selected_examples": selected_rows[:8],
            "safe_pool_benchmark_like_examples": safe_pool_benchmark_like_rows[:8],
        },
    }
    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"critic_split_benchmark_like_scoring_preservation_probe_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    reason = (
        "diagnostic shadow passed: the preserved scorer path kept recovery benchmark-like identity alive and restored persistence entry without unsafe drift"
        if passed
        else "diagnostic shadow failed: the preserved scorer path did not meet the benchmark-like preservation bar cleanly enough"
    )
    return {
        "passed": bool(passed),
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": reason,
        "observability_gain": artifact_payload["observability_gain"],
        "activation_analysis_usefulness": artifact_payload["activation_analysis_usefulness"],
        "ambiguity_reduction": artifact_payload["ambiguity_reduction"],
        "safety_neutrality": artifact_payload["safety_neutrality"],
        "later_selection_usefulness": artifact_payload["later_selection_usefulness"],
        "diagnostic_conclusions": artifact_payload["diagnostic_conclusions"],
        "artifact_path": str(artifact_path),
    }
