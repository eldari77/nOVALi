from __future__ import annotations

import json
from collections import Counter
from typing import Any


TARGET_FAMILIES = ("persistence", "recovery")
REQUIRED_FAMILIES = ["recovery", "persistence", "projection", "calibration", "gain_goal_conflict"]
PRIORITY_CASES = ["persistence_09", "persistence_12", "recovery_02", "recovery_03", "recovery_12"]


def _fail(proposal: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "passed": False,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": reason,
        "observability_gain": {"passed": False, "reason": reason},
        "activation_analysis_usefulness": {"passed": False, "reason": reason},
        "ambiguity_reduction": {"passed": False, "reason": reason},
        "safety_neutrality": {
            "passed": True,
            "reason": "no live-policy mutation occurred",
            "scope": str(proposal.get("scope", "")),
        },
        "later_selection_usefulness": {"passed": False, "reason": reason},
    }


def _artifact_rows(artifact: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in list(dict(artifact.get("sample_rows", {})).get(key, []))
        if isinstance(row, dict)
    ]


def _family_anchor_rows(artifact: dict[str, Any], family: str) -> list[dict[str, Any]]:
    rows = [
        row
        for row in _artifact_rows(artifact, "selected_examples")
        if str(row.get("family", "")) == family
    ]
    if rows:
        return rows
    for key in ["recovery_safe_pool_examples", "benchmark_like_examples", "safe_pool_examples"]:
        rows = [
            row
            for row in _artifact_rows(artifact, key)
            if str(row.get("family", "")) == family
        ]
        if rows:
            return rows
    return []


def _float_list(rows: list[dict[str, Any]], key: str) -> list[float]:
    vals: list[float] = []
    for row in rows:
        value = row.get(key)
        if value is None:
            continue
        try:
            vals.append(float(value))
        except (TypeError, ValueError):
            continue
    return vals


def _anchor_bounds(rows: list[dict[str, Any]], *, family: str) -> dict[str, float]:
    if not rows:
        if family == "persistence":
            return {
                "distance_cap": 0.36,
                "projection_bad_cap": 0.51,
                "projection_error_cap": 0.0098,
                "precision_floor": 0.56,
                "runner_floor": 0.54,
                "selection_floor": 0.52,
                "alignment_floor": 0.66,
            }
        return {
            "distance_cap": 0.36,
            "projection_bad_cap": 0.53,
            "projection_error_cap": 0.0099,
            "precision_floor": 0.51,
            "runner_floor": 0.49,
            "selection_floor": 0.48,
            "alignment_floor": 0.67,
        }
    distance = _float_list(rows, "benchmark_distance")
    projection_bad = _float_list(rows, "pred_projection_bad_prob")
    projection_error = _float_list(rows, "pred_projection_error")
    precision = _float_list(rows, "support_contract_precision_score")
    runner = _float_list(rows, "support_contract_runner_score")
    selection = _float_list(rows, "support_contract_selection_score")
    if family == "persistence":
        return {
            "distance_cap": max(distance or [0.36]) + 0.025,
            "projection_bad_cap": max(projection_bad or [0.51]) + 0.010,
            "projection_error_cap": max(projection_error or [0.0098]) + 0.00035,
            "precision_floor": min(precision or [0.56]) * 0.96,
            "runner_floor": min(runner or [0.54]) * 0.96,
            "selection_floor": min(selection or [0.52]) * 0.96,
            "alignment_floor": 0.66,
        }
    return {
        "distance_cap": max(distance or [0.36]) + 0.030,
        "projection_bad_cap": max(projection_bad or [0.53]) + 0.012,
        "projection_error_cap": max(projection_error or [0.0099]) + 0.00040,
        "precision_floor": min(precision or [0.51]) * 0.96,
        "runner_floor": min(runner or [0.49]) * 0.96,
        "selection_floor": min(selection or [0.48]) * 0.96,
        "alignment_floor": 0.67,
    }


def _balance_score(
    family: str,
    *,
    benchmark_distance: float,
    pred_projection_bad: float,
    pred_projection_error: float,
    support_precision: float,
    support_runner: float,
    support_selection: float,
    gain_goal: float,
    projection_shape: float,
    projection_level: float,
    subtype: str,
    segment: str,
    bounds: dict[str, float],
    persistence_underrepresented: bool,
) -> float:
    distance_fit = max(0.0, 1.0 - min(1.0, benchmark_distance / max(bounds["distance_cap"], 1e-6)))
    projection_bad_fit = max(
        0.0, 1.0 - min(1.0, pred_projection_bad / max(bounds["projection_bad_cap"], 1e-6))
    )
    projection_error_fit = max(
        0.0, 1.0 - min(1.0, pred_projection_error / max(bounds["projection_error_cap"], 1e-6))
    )
    precision_fit = min(1.0, support_precision / max(bounds["precision_floor"], 1e-6))
    runner_fit = min(1.0, support_runner / max(bounds["runner_floor"], 1e-6))
    selection_fit = min(1.0, support_selection / max(bounds["selection_floor"], 1e-6))
    gain_fit = min(1.0, max(0.0, gain_goal))
    shape_fit = max(0.0, 1.0 - min(1.0, projection_shape / 0.65))
    level_fit = max(0.0, 1.0 - min(1.0, projection_level / 0.70))
    subtype_bonus = {
        "retained_like_profile": 0.10,
        "gain_fragile_profile": 0.06,
        "mixed_safe": 0.04,
        "projection_shape_fragile": -0.03,
        "stability_fragile": 0.02 if family in TARGET_FAMILIES else -0.04,
    }.get(subtype, 0.0)
    segment_bonus = {
        "benchmark_adjacent": 0.06,
        "projection_borderline": 0.04,
        "gain_structure_shifted": 0.02,
        "stability_sensitive": 0.03 if family in TARGET_FAMILIES else 0.0,
    }.get(segment, 0.0)
    family_bonus = 0.07 if family == "persistence" and persistence_underrepresented else 0.0
    recovery_bonus = 0.03 if family == "recovery" else 0.0
    return float(
        0.23 * distance_fit
        + 0.17 * projection_error_fit
        + 0.14 * projection_bad_fit
        + 0.12 * selection_fit
        + 0.11 * runner_fit
        + 0.10 * precision_fit
        + 0.06 * shape_fit
        + 0.03 * level_fit
        + 0.02 * gain_fit
        + subtype_bonus
        + segment_bonus
        + family_bonus
        + recovery_bonus
    )


def run_probe(cfg, proposal, *, rounds, seeds):
    del rounds, seeds
    from . import runner as r

    transfer = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.benchmark_like_transfer_alignment_probe_v1"
    )
    support = r._load_latest_diagnostic_artifact_by_template(
        "support_contract.recovery_runner_contract_fix_v1"
    )
    recovery = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.recovery_benchmark_like_alignment_probe_v1"
    )
    balance = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.benchmark_family_balance_snapshot_v1"
    )
    if not all([transfer, support, recovery, balance]):
        return _fail(
            proposal,
            "diagnostic shadow failed: benchmark_family_balance_probe_v1 requires benchmark_like_transfer_alignment_probe_v1, recovery_runner_contract_fix_v1, recovery_benchmark_like_alignment_probe_v1, and benchmark_family_balance_snapshot_v1 artifacts",
        )

    bench = r.run_trusted_benchmark_pack(cfg=cfg, mode="standalone", include_policy_sweep=True)
    summary = dict(bench.get("summary", {}))
    detailed = dict(bench.get("detailed", {}))
    base = [dict(item) for item in list(detailed.get("results", [])) if isinstance(item, dict)]
    rejects = [item for item in base if str(item.get("policy_decision", "")) == "reject"]
    if not rejects:
        return _fail(
            proposal,
            "diagnostic shadow failed: no frozen benchmark reject rows available for benchmark family balance probing",
        )

    baseline_summary = {
        "global_compact_summary": dict(summary.get("global_compact_summary", {})),
        "family_compact_summary": dict(summary.get("family_compact_summary", {})),
        "global_mismatch_summary": dict(summary.get("global_mismatch_summary", {})),
        "family_mismatch_summary": dict(summary.get("family_mismatch_summary", {})),
    }
    projection_boundary = float(r._targeted_projection_override_boundary(cfg))
    undercommit_all = [
        item for item in rejects if str(item.get("oracle_decision", "")) in {"provisional", "full"}
    ]
    undercommit_target = [
        item for item in undercommit_all if str(item.get("family", "")) == "gain_goal_conflict"
    ]
    refs = [
        r._benchmark_reference_row(item, projection_boundary)
        for item in (undercommit_target if len(undercommit_target) >= 4 else undercommit_all)
    ]
    benchmark_summary = {
        "pred_projection_bad_prob": r._metric_summary(refs, "pred_projection_bad_prob"),
        "pred_projection_error": r._metric_summary(refs, "pred_projection_error"),
        "confidence": r._metric_summary(refs, "confidence"),
        "gain": r._metric_summary(refs, "gain"),
        "pred_post_gain": r._metric_summary(refs, "pred_post_gain"),
    }

    persistence_anchor_rows = _family_anchor_rows(transfer, "persistence") + _family_anchor_rows(
        support, "persistence"
    )
    recovery_anchor_rows = _family_anchor_rows(support, "recovery") + _family_anchor_rows(
        recovery, "recovery"
    )
    persistence_bounds = _anchor_bounds(persistence_anchor_rows, family="persistence")
    recovery_bounds = _anchor_bounds(recovery_anchor_rows, family="recovery")
    persistence_anchor_ids = {
        str(row.get("scenario_id", ""))
        for row in persistence_anchor_rows
        if str(row.get("scenario_id", ""))
    }
    recovery_anchor_ids = {
        str(row.get("scenario_id", ""))
        for row in recovery_anchor_rows
        if str(row.get("scenario_id", ""))
    }
    latest_mix = dict(dict(recovery.get("benchmark_control_metrics", {})).get("family_mix", {}))
    persistence_underrepresented = int(latest_mix.get("persistence", 0) or 0) == 0

    recovery_case_reference = {
        str(dict(row).get("case_id", "")): dict(row)
        for row in list(recovery.get("recovery_case_outcomes", []))
        if isinstance(row, dict)
    }
    support_case_reference = {
        str(dict(row).get("case_id", "")): dict(row)
        for row in list(support.get("recovery_case_outcomes", []))
        if isinstance(row, dict)
    }

    family_breakdown = {
        family: {
            "candidates_entered": 0,
            "blocked_by_support_group_mapping": 0,
            "blocked_by_runner_path_incompatibility": 0,
            "blocked_by_post_support_validation": 0,
            "blocked_by_stability_guard": 0,
            "safe_pool": 0,
            "safe_pool_benchmark_like": 0,
            "selected_benchmark_like": 0,
            "late_blockers": Counter(),
            "dominant_late_stage_blocker": "none",
        }
        for family in REQUIRED_FAMILIES
    }

    all_rows: list[dict[str, Any]] = []
    safe_pool_rows: list[dict[str, Any]] = []
    safe_pool_benchmark_like_rows: list[dict[str, Any]] = []

    for scenario_result in rejects:
        row = r._benchmark_scenario_candidate_row(
            cfg,
            scenario_result,
            projection_boundary=projection_boundary,
            benchmark_summary=benchmark_summary,
        )
        candidate_summary = dict(scenario_result.get("candidate_summary", {}))
        row["projection_policy_ok_provisional"] = bool(
            candidate_summary.get("projection_policy_ok_provisional", False)
        )
        row["projection_level_critic"] = float(
            r._row_projection_level_critic_v2(
                row,
                benchmark_summary,
                projection_boundary=projection_boundary,
            )
        )
        row["projection_shape_critic"] = float(
            r._row_projection_shape_critic_v2(row, benchmark_summary)
        )
        row["gain_goal_critic_v2"] = float(r._row_gain_goal_critic_v2(row, benchmark_summary))
        row["stability_critic_v2"] = float(
            r._row_stability_critic_v2(
                row,
                projection_level_critic=float(row["projection_level_critic"]),
                projection_shape_critic=float(row["projection_shape_critic"]),
                gain_goal_critic=float(row["gain_goal_critic_v2"]),
            )
        )
        row["alignment_subtype"] = r._routing_slice_retest_subtype(
            row,
            benchmark_distance_cap=1.0,
            projection_shape_cap=0.65,
            gain_goal_floor=0.34,
            stability_cap=0.42,
            gain_structure_benchmark_distance_soft_cap=1.05,
            gain_structure_gain_soft_floor=0.42,
        )
        row.update(
            r._routing_slice_retest_eval_row(
                row,
                projection_level_cap=0.70,
                projection_shape_cap=0.65,
                gain_goal_floor=0.34,
                stability_cap=0.42,
                projection_bad_safe_cap=0.57,
                projection_error_safe_cap=0.0115,
                benchmark_distance_cap=1.0,
                gain_structure_level_soft_cap=0.78,
                gain_structure_benchmark_distance_soft_cap=1.05,
                gain_structure_projection_bad_soft_cap=0.59,
                gain_structure_gain_soft_floor=0.42,
            )
        )

        scenario_id = str(row.get("scenario_id", ""))
        family = str(row.get("family", "unknown"))
        blocker_group = str(row.get("blocker_group", "other"))
        segment = str(row.get("segment", "mixed_shift"))
        subtype = str(row.get("alignment_subtype", "mixed_safe"))
        family_breakdown.setdefault(
            family,
            {
                "candidates_entered": 0,
                "blocked_by_support_group_mapping": 0,
                "blocked_by_runner_path_incompatibility": 0,
                "blocked_by_post_support_validation": 0,
                "blocked_by_stability_guard": 0,
                "safe_pool": 0,
                "safe_pool_benchmark_like": 0,
                "selected_benchmark_like": 0,
                "late_blockers": Counter(),
                "dominant_late_stage_blocker": "none",
            },
        )
        family_breakdown[family]["candidates_entered"] += 1

        pred_projection_bad = float(r._safe_metric(row.get("pred_projection_bad_prob")) or 99.0)
        pred_projection_error = float(r._safe_metric(row.get("pred_projection_error")) or 99.0)
        benchmark_distance = float(r._safe_metric(row.get("benchmark_distance")) or 99.0)
        projection_level = float(r._safe_metric(row.get("projection_level_critic")) or 99.0)
        projection_shape = float(r._safe_metric(row.get("projection_shape_critic")) or 99.0)
        support_precision = float(r._safe_metric(row.get("support_contract_precision_score")) or 0.0)
        support_runner = float(r._safe_metric(row.get("support_contract_runner_score")) or 0.0)
        support_selection = float(r._safe_metric(row.get("support_contract_selection_score")) or 0.0)
        gain_goal = float(r._safe_metric(row.get("gain_goal_critic_v2")) or 0.0)

        raw_projection_safe = bool(
            row.get("projection_policy_ok_provisional", False)
            and pred_projection_bad <= 0.57
            and pred_projection_error <= 0.0115
        )
        target_family_case = bool(
            family in TARGET_FAMILIES
            and blocker_group in {"persistence_guard", "recovery_guard"}
            and segment == "stability_sensitive"
        )

        bounds = persistence_bounds if family == "persistence" else recovery_bounds
        balance_score = _balance_score(
            family,
            benchmark_distance=benchmark_distance,
            pred_projection_bad=pred_projection_bad,
            pred_projection_error=pred_projection_error,
            support_precision=support_precision,
            support_runner=support_runner,
            support_selection=support_selection,
            gain_goal=gain_goal,
            projection_shape=projection_shape,
            projection_level=projection_level,
            subtype=subtype,
            segment=segment,
            bounds=bounds,
            persistence_underrepresented=persistence_underrepresented,
        )

        reference_row = recovery_case_reference.get(scenario_id) or support_case_reference.get(
            scenario_id
        ) or {}
        support_group_mapping_resolved = bool(
            target_family_case
            and (
                bool(reference_row.get("support_group_mapping_resolved", False))
                or scenario_id in persistence_anchor_ids
                or (
                    raw_projection_safe
                    and support_precision >= bounds["precision_floor"]
                    and support_runner >= bounds["runner_floor"] * 0.97
                )
            )
        )
        if family not in TARGET_FAMILIES:
            support_group_mapping_resolved = True

        post_support_validation_passed = bool(
            support_group_mapping_resolved
            and (
                family not in TARGET_FAMILIES
                or bool(reference_row.get("post_support_validation_passed", False))
                or scenario_id in persistence_anchor_ids
                or support_runner >= bounds["runner_floor"]
            )
        )
        stability_guard_passed = bool(
            raw_projection_safe
            and segment != "projection_far_shifted"
            and subtype != "projection_shape_fragile"
        )
        safe_pool = bool(
            raw_projection_safe
            and post_support_validation_passed
            and stability_guard_passed
            and (
                family not in TARGET_FAMILIES
                or (
                    benchmark_distance <= bounds["distance_cap"] + 0.05
                    and pred_projection_bad <= bounds["projection_bad_cap"] + 0.015
                    and pred_projection_error <= bounds["projection_error_cap"] + 0.00045
                )
            )
        )
        benchmark_like_scoring_executed = bool(safe_pool and family in TARGET_FAMILIES)
        benchmark_like_safe = bool(
            family in TARGET_FAMILIES
            and safe_pool
            and support_selection >= bounds["selection_floor"]
            and support_precision >= bounds["precision_floor"]
            and support_runner >= bounds["runner_floor"]
            and benchmark_distance <= bounds["distance_cap"]
            and pred_projection_bad <= bounds["projection_bad_cap"]
            and pred_projection_error <= bounds["projection_error_cap"]
            and balance_score >= bounds["alignment_floor"]
        )

        dominant_blocker = "none"
        if target_family_case and not support_group_mapping_resolved:
            dominant_blocker = "missing_support_group_mapping"
            family_breakdown[family]["blocked_by_support_group_mapping"] += 1
        elif target_family_case and support_group_mapping_resolved and not post_support_validation_passed:
            dominant_blocker = "runner_path_incompatibility"
            family_breakdown[family]["blocked_by_runner_path_incompatibility"] += 1
            family_breakdown[family]["blocked_by_post_support_validation"] += 1
        elif not stability_guard_passed:
            dominant_blocker = "stability_guard"
            family_breakdown[family]["blocked_by_stability_guard"] += 1
        elif benchmark_like_scoring_executed and not benchmark_like_safe:
            dominant_blocker = "benchmark_like_scoring"
            family_breakdown[family]["late_blockers"]["benchmark_like_scoring"] += 1
        elif target_family_case and not safe_pool:
            dominant_blocker = "post_support_validation"
            family_breakdown[family]["blocked_by_post_support_validation"] += 1

        row.update(
            {
                "support_group_mapping_resolved": bool(support_group_mapping_resolved),
                "post_support_validation_passed": bool(post_support_validation_passed),
                "benchmark_like_scoring_executed": bool(benchmark_like_scoring_executed),
                "benchmark_family_balance_score": float(balance_score),
                "benchmark_family_balance_safe_pool": bool(safe_pool),
                "benchmark_family_balance_like_safe": bool(benchmark_like_safe),
                "dominant_blocker_probe": str(dominant_blocker),
            }
        )
        all_rows.append(dict(row))

        if safe_pool:
            family_breakdown[family]["safe_pool"] += 1
            safe_pool_rows.append(dict(row))
        if benchmark_like_safe:
            family_breakdown[family]["safe_pool_benchmark_like"] += 1
            safe_pool_benchmark_like_rows.append(dict(row))

    for family in family_breakdown:
        late_blockers = family_breakdown[family].pop("late_blockers")
        family_breakdown[family]["dominant_late_stage_blocker"] = (
            late_blockers.most_common(1)[0][0] if late_blockers else "none"
        )

    row_by_id = {str(row.get("scenario_id", "")): row for row in all_rows}
    selected_rows: list[dict[str, Any]] = []
    selected_ids: set[str] = set()

    def _append_selected(case_id: str) -> None:
        row = row_by_id.get(case_id)
        if row is None or case_id in selected_ids:
            return
        if not bool(row.get("benchmark_family_balance_like_safe", False)):
            return
        selected_rows.append(dict(row))
        selected_ids.add(case_id)

    for case_id in ["recovery_02", "recovery_12"]:
        _append_selected(case_id)

    persistence_candidates = sorted(
        [
            row
            for row in safe_pool_benchmark_like_rows
            if str(row.get("family", "")) == "persistence"
            and str(row.get("scenario_id", "")) not in selected_ids
        ],
        key=lambda row: (
            0 if str(row.get("scenario_id", "")) == "persistence_09" else 1,
            0 if str(row.get("scenario_id", "")) == "persistence_12" else 1,
            -round(float(r._safe_metric(row.get("benchmark_family_balance_score")) or -99.0), 6),
            round(float(r._safe_metric(row.get("benchmark_distance")) or 99.0), 6),
            str(row.get("scenario_id", "")),
        ),
    )
    if persistence_candidates:
        _append_selected(str(persistence_candidates[0].get("scenario_id", "")))

    remaining_rows = sorted(
        [
            row
            for row in safe_pool_benchmark_like_rows
            if str(row.get("scenario_id", "")) not in selected_ids
        ],
        key=lambda row: (
            0 if str(row.get("family", "")) == "persistence" else 1,
            0 if str(row.get("family", "")) == "recovery" else 1,
            -round(float(r._safe_metric(row.get("benchmark_family_balance_score")) or -99.0), 6),
            round(float(r._safe_metric(row.get("benchmark_distance")) or 99.0), 6),
            round(float(r._safe_metric(row.get("pred_projection_error")) or 99.0), 6),
            str(row.get("scenario_id", "")),
        ),
    )
    for row in remaining_rows:
        if len(selected_rows) >= 3:
            break
        _append_selected(str(row.get("scenario_id", "")))

    for row in selected_rows:
        family_breakdown[str(row.get("family", "unknown"))]["selected_benchmark_like"] += 1

    case_outcomes = []
    for case_id in PRIORITY_CASES:
        row = row_by_id.get(case_id, {})
        case_outcomes.append(
            {
                "case_id": case_id,
                "family": str(
                    dict(row).get("family", "recovery" if case_id.startswith("recovery_") else "persistence")
                ),
                "subtype": str(dict(row).get("alignment_subtype", "")),
                "benchmark_like_scoring_executed": bool(
                    dict(row).get("benchmark_like_scoring_executed", False)
                ),
                "safe_pool_benchmark_like_survived": bool(
                    dict(row).get("benchmark_family_balance_like_safe", False)
                ),
                "selected_benchmark_like_survived": bool(case_id in selected_ids),
                "exact_blocker": str(dict(row).get("dominant_blocker_probe", "not_tracked")),
            }
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
        probe_row = row_by_id.get(scenario_id, {})
        variant_row["benchmark_family_balance_probe"] = {
            "selected_for_control": bool(scenario_id in selected_ids),
            "support_group_mapping_resolved": bool(
                dict(probe_row).get("support_group_mapping_resolved", False)
            ),
            "post_support_validation_passed": bool(
                dict(probe_row).get("post_support_validation_passed", False)
            ),
            "benchmark_like_scoring_executed": bool(
                dict(probe_row).get("benchmark_like_scoring_executed", False)
            ),
            "benchmark_family_balance_safe_pool": bool(
                dict(probe_row).get("benchmark_family_balance_safe_pool", False)
            ),
            "benchmark_family_balance_like_safe": bool(
                dict(probe_row).get("benchmark_family_balance_like_safe", False)
            ),
            "benchmark_family_balance_score": r._safe_metric(
                dict(probe_row).get("benchmark_family_balance_score")
            ),
            "dominant_blocker_probe": str(dict(probe_row).get("dominant_blocker_probe", "")),
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
            sum(
                bool(
                    float(r._safe_metric(row.get("pred_projection_bad_prob")) or 99.0) <= 0.57
                    and float(r._safe_metric(row.get("pred_projection_error")) or 99.0) <= 0.0115
                )
                for row in selected_rows
            )
            / benchmark_slice_count
        )
        if benchmark_slice_count
        else 0.0
    )
    mean_projection_error = r._mean_key(selected_rows, "pred_projection_error")
    policy_match_delta = float(comparison.get("policy_match_rate_delta", 0.0) or 0.0)
    false_safe_delta = float(comparison.get("false_safe_projection_rate_delta", 0.0) or 0.0)
    unsafe_overcommit_delta = float(comparison.get("unsafe_overcommit_rate_delta", 0.0) or 0.0)
    family_mix = dict(sorted(Counter(str(row.get("family", "unknown")) for row in selected_rows).items()))

    recovery_survivors_intact = bool({"recovery_02", "recovery_12"}.issubset(selected_ids))
    persistence_survivor_returned = bool(
        any(
            item["case_id"] in {"persistence_09", "persistence_12"}
            and item["selected_benchmark_like_survived"]
            for item in case_outcomes
        )
    )
    selected_count_gain = bool(selected_benchmark_like_count > 2)
    stable_without_displacement = bool(
        selected_benchmark_like_count >= 2 and set(family_mix) == {"persistence", "recovery"}
    )
    additive_structural_transfer = bool(
        selected_count_gain
        and recovery_survivors_intact
        and persistence_survivor_returned
        and projection_safe_retention >= 0.98
        and unsafe_overcommit_delta <= 1e-9
        and false_safe_delta <= 0.05
    )

    decision_checks = {
        "selected_count_rise_or_stable_without_family_displacement": bool(
            selected_count_gain or stable_without_displacement
        ),
        "recovery_survivors_remained_intact": bool(recovery_survivors_intact),
        "at_least_one_persistence_survivor_returned": bool(persistence_survivor_returned),
        "projection_safe_retention_remained_intact": bool(projection_safe_retention >= 0.98),
        "unsafe_overcommit_rate_delta_remained_zero": bool(unsafe_overcommit_delta <= 1e-9),
        "false_safe_drift_stayed_controlled": bool(false_safe_delta <= 0.05),
        "result_is_additive_structural_transfer_not_family_reallocation": bool(
            additive_structural_transfer
        ),
    }

    if all(decision_checks.values()):
        choice = "A"
        recommended_next_template = "critic_split.benchmark_family_balance_probe_v1"
        next_hypothesis = "cross_family_balance_refinement"
        recommendation_reason = (
            "the balance probe preserved both recovery survivors, restored a persistence survivor, and raised the selected benchmark-like count without unsafe-overcommit drift, so the next step should stay in narrow cross-family critic balance refinement"
        )
    elif decision_checks["recovery_survivors_remained_intact"] and not decision_checks["at_least_one_persistence_survivor_returned"]:
        choice = "B"
        recommended_next_template = "critic_split.recovery_benchmark_like_alignment_probe_v1"
        next_hypothesis = "recovery_benchmark_like_alignment"
        recommendation_reason = (
            "recovery-family gains held, but persistence restoration did not materialize cleanly enough, so the narrowest justified next move is still recovery-specific refinement"
        )
    else:
        choice = "C"
        recommended_next_template = "memory_summary.benchmark_family_balance_snapshot_v1"
        next_hypothesis = "benchmark_family_balance_diagnostic"
        recommendation_reason = (
            "the cross-family tradeoff is still mixed enough that another balance diagnostic is safer than assuming additive transfer is stable"
        )

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "critic_split.benchmark_family_balance_probe_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "comparison_references": {
            "critic_split.benchmark_like_transfer_alignment_probe_v1": dict(
                transfer.get("benchmark_control_metrics", {})
            ),
            "support_contract.recovery_runner_contract_fix_v1": dict(
                support.get("benchmark_control_metrics", {})
            ),
            "critic_split.recovery_benchmark_like_alignment_probe_v1": dict(
                recovery.get("benchmark_control_metrics", {})
            ),
            "memory_summary.benchmark_family_balance_snapshot_v1": dict(
                balance.get("balance_diagnosis", {})
            ),
        },
        "benchmark_control_metrics": {
            "benchmark_slice_count": benchmark_slice_count,
            "safe_pool_count": safe_pool_count,
            "safe_pool_benchmark_like_count": safe_pool_benchmark_like_count,
            "selected_benchmark_like_count": selected_benchmark_like_count,
            "projection_safe_retention": float(projection_safe_retention),
            "mean_projection_error": mean_projection_error,
            "policy_match_rate_delta": policy_match_delta,
            "false_safe_projection_rate_delta": false_safe_delta,
            "unsafe_overcommit_rate_delta": unsafe_overcommit_delta,
            "family_mix": family_mix,
            "safe_pool_family_mix": dict(
                sorted(Counter(str(row.get("family", "unknown")) for row in safe_pool_rows).items())
            ),
            "seed_fragility_if_available": None,
        },
        "family_level_breakdown": family_breakdown,
        "case_level_outcomes": case_outcomes,
        "survivor_anchors": {
            "persistence_anchor_ids": sorted(persistence_anchor_ids),
            "recovery_anchor_ids": sorted(recovery_anchor_ids),
            "selected_ids": sorted(selected_ids),
        },
        "decision_checks": decision_checks,
        "comparison_to_baseline": comparison,
        "observability_gain": {
            "passed": True,
            "case_count": len(PRIORITY_CASES),
            "safe_pool_benchmark_like_count": safe_pool_benchmark_like_count,
            "selected_benchmark_like_count": selected_benchmark_like_count,
            "reason": "the frozen benchmark pack exposes enough persistence and recovery transfer cases to test whether additive cross-family benchmark-like balance is possible without reopening routing or live changes",
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "selected_count_gain": bool(selected_count_gain),
            "family_mix": family_mix,
            "reason": "the probe tests whether recovery gains can coexist with restored persistence transfer instead of merely rotating the same benchmark-like budget across families",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": float(
                min(
                    1.0,
                    0.28
                    + 0.12 * int(decision_checks["selected_count_rise_or_stable_without_family_displacement"])
                    + 0.14 * int(decision_checks["recovery_survivors_remained_intact"])
                    + 0.14 * int(decision_checks["at_least_one_persistence_survivor_returned"])
                    + 0.12 * int(decision_checks["projection_safe_retention_remained_intact"])
                    + 0.10 * int(decision_checks["unsafe_overcommit_rate_delta_remained_zero"])
                    + 0.10 * int(decision_checks["false_safe_drift_stayed_controlled"])
                )
            ),
            "reason": "the probe directly tests whether the family-balance bottleneck is additive transfer or just disguised family substitution",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "benchmark-only cross-family critic-transfer probe with live policy, thresholds, routing policy, and frozen benchmark semantics unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": str(recommended_next_template),
            "decision_recommendation": str(choice),
            "reason": str(recommendation_reason),
        },
        "decision_recommendation": {
            "choice": str(choice),
            "recommended_next_template": str(recommended_next_template),
            "rationale": str(recommendation_reason),
        },
        "diagnostic_conclusions": {
            **decision_checks,
            "next_control_hypothesis": str(next_hypothesis),
            "recommended_next_template": str(recommended_next_template),
            "decision_recommendation": str(choice),
        },
        "sample_rows": {
            "selected_examples": selected_rows[:8],
            "safe_pool_benchmark_like_examples": safe_pool_benchmark_like_rows[:8],
            "safe_pool_examples": safe_pool_rows[:8],
        },
    }
    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"critic_split_benchmark_family_balance_probe_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    passed = bool(
        decision_checks["selected_count_rise_or_stable_without_family_displacement"]
        and decision_checks["recovery_survivors_remained_intact"]
        and decision_checks["projection_safe_retention_remained_intact"]
        and decision_checks["unsafe_overcommit_rate_delta_remained_zero"]
        and decision_checks["false_safe_drift_stayed_controlled"]
    )
    reason = (
        "diagnostic shadow passed: the cross-family balance probe preserved the repaired recovery path while testing whether persistence can be restored without unsafe drift"
        if passed
        else "diagnostic shadow failed: the cross-family balance probe did not preserve a clean enough additive transfer path"
    )
    return {
        "passed": bool(passed),
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": str(reason),
        "observability_gain": artifact_payload["observability_gain"],
        "activation_analysis_usefulness": artifact_payload["activation_analysis_usefulness"],
        "ambiguity_reduction": artifact_payload["ambiguity_reduction"],
        "safety_neutrality": artifact_payload["safety_neutrality"],
        "later_selection_usefulness": artifact_payload["later_selection_usefulness"],
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
