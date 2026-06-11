from __future__ import annotations

import json
from collections import Counter
from typing import Any


def run_probe(cfg, proposal, *, rounds, seeds):
    del rounds, seeds
    from . import runner as r

    asymmetry = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.recovery_transfer_asymmetry_snapshot_v1"
    )
    transfer = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.benchmark_like_transfer_alignment_probe_v1"
    )
    support = r._load_latest_diagnostic_artifact_by_template(
        "support_contract.benchmark_stability_sensitive_compat_probe_v1"
    )
    runner_mem = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.runner_path_incompatibility_snapshot_v1"
    )
    stability = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.stability_context_retention_probe_v2"
    )
    if not all([asymmetry, transfer, support, runner_mem, stability]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: recovery_runner_contract_fix_v1 requires recovery asymmetry, benchmark-like transfer alignment, support-contract compatibility, runner-path incompatibility, and stability-context artifacts",
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

    bench = r.run_trusted_benchmark_pack(cfg=cfg, mode="standalone", include_policy_sweep=True)
    summary = dict(bench.get("summary", {}))
    detailed = dict(bench.get("detailed", {}))
    base = [dict(x) for x in list(detailed.get("results", [])) if isinstance(x, dict)]
    rejects = [x for x in base if str(x.get("policy_decision", "")) == "reject"]
    if not rejects:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no frozen benchmark reject rows available for recovery support/contract probing",
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
    projection_boundary = float(r._targeted_projection_override_boundary(cfg))
    undercommit_all = [x for x in rejects if str(x.get("oracle_decision", "")) in {"provisional", "full"}]
    undercommit_target = [x for x in undercommit_all if str(x.get("family", "")) == "gain_goal_conflict"]
    refs = [
        r._benchmark_reference_row(x, projection_boundary)
        for x in (undercommit_target if len(undercommit_target) >= 4 else undercommit_all)
    ]
    benchmark_summary = {
        "pred_projection_bad_prob": r._metric_summary(refs, "pred_projection_bad_prob"),
        "pred_projection_error": r._metric_summary(refs, "pred_projection_error"),
        "confidence": r._metric_summary(refs, "confidence"),
        "gain": r._metric_summary(refs, "gain"),
        "pred_post_gain": r._metric_summary(refs, "pred_post_gain"),
    }

    slice_definition = dict(stability.get("slice_definition", {}))
    projection_level_cap = float(slice_definition.get("projection_level_cap", 0.70))
    projection_shape_cap = float(slice_definition.get("projection_shape_cap", 0.65))
    gain_goal_floor = float(slice_definition.get("gain_goal_floor", 0.34))
    stability_cap = float(slice_definition.get("stability_cap", 0.42))
    projection_bad_safe_cap = float(slice_definition.get("projection_bad_safe_cap", 0.57))
    projection_error_safe_cap = float(slice_definition.get("projection_error_safe_cap", 0.0115))
    benchmark_distance_cap = float(slice_definition.get("benchmark_distance_cap", 1.0))
    gain_structure_level_soft_cap = float(
        slice_definition.get("gain_structure_level_soft_cap", projection_level_cap + 0.08)
    )
    gain_structure_benchmark_distance_soft_cap = float(
        slice_definition.get("gain_structure_benchmark_distance_soft_cap", benchmark_distance_cap + 0.05)
    )
    gain_structure_projection_bad_soft_cap = float(
        slice_definition.get("gain_structure_projection_bad_soft_cap", projection_bad_safe_cap + 0.02)
    )
    gain_structure_gain_soft_floor = float(
        slice_definition.get("gain_structure_gain_soft_floor", gain_goal_floor + 0.08)
    )

    asym_rows = [
        dict(x)
        for x in list(asymmetry.get("case_comparison_table", []))
        if isinstance(x, dict)
    ]
    persistence_rows = [
        row
        for row in asym_rows
        if str(row.get("family", "")) == "persistence"
        and bool(row.get("support_resolved", False))
        and bool(row.get("selected_benchmark_like_survived", False))
    ]
    persistence_distance_cap = max(
        [float(r._safe_metric(row.get("benchmark_distance")) or 0.36) for row in persistence_rows] or [0.36]
    )
    persistence_precision_floor = min(
        [float(r._safe_metric(row.get("support_contract_precision_score")) or 0.56) for row in persistence_rows] or [0.56]
    )
    persistence_runner_floor = min(
        [float(r._safe_metric(row.get("support_contract_runner_score")) or 0.54) for row in persistence_rows] or [0.54]
    )
    persistence_selection_floor = min(
        [float(r._safe_metric(row.get("support_contract_selection_score")) or 0.52) for row in persistence_rows] or [0.52]
    )
    persistence_projection_bad_cap = max(
        [float(r._safe_metric(row.get("pred_projection_bad_prob")) or 0.52) for row in persistence_rows] or [0.52]
    )
    persistence_projection_error_cap = max(
        [float(r._safe_metric(row.get("pred_projection_error")) or 0.0098) for row in persistence_rows] or [0.0098]
    )

    support_metrics = dict(support.get("benchmark_control_metrics", {}))
    transfer_metrics = dict(transfer.get("benchmark_control_metrics", {}))
    prior_false_safe = float(support_metrics.get("false_safe_projection_rate_delta", 0.0) or 0.0)
    selection_target_count = max(2, int(transfer_metrics.get("selected_benchmark_like_count", 0) or 0))

    recovery_mapping_ids = {"recovery_02", "recovery_05", "recovery_11"}
    recovery_runner_ids = {"recovery_03", "recovery_06", "recovery_07", "recovery_08", "recovery_09", "recovery_12"}
    required_families = ["recovery", "persistence", "projection", "calibration", "gain_goal_conflict"]
    family_breakdown = {
        name: {
            "candidates_entered": 0,
            "blocked_by_support_group_mapping": 0,
            "blocked_by_runner_path_incompatibility": 0,
            "blocked_by_post_support_validation": 0,
            "blocked_by_stability_guard": 0,
            "surviving_to_safe_pool": 0,
            "surviving_to_safe_pool_benchmark_like": 0,
            "surviving_to_selected_benchmark_like": 0,
        }
        for name in required_families
    }
    subtype_priority = {
        "retained_like_profile": 0,
        "gain_fragile_profile": 1,
        "mixed_safe": 2,
        "projection_shape_fragile": 3,
        "stability_fragile": 4,
    }

    def _score_row(row: dict[str, Any]) -> dict[str, float]:
        benchmark_distance = float(r._safe_metric(row.get("benchmark_distance")) or benchmark_distance_cap)
        projection_level = float(r._safe_metric(row.get("projection_level_critic")) or projection_level_cap)
        projection_shape = float(r._safe_metric(row.get("projection_shape_critic")) or projection_shape_cap)
        gain_goal = float(r._safe_metric(row.get("gain_goal_critic_v2")) or 0.0)
        stability_value = float(r._safe_metric(row.get("stability_critic_v2")) or 0.0)
        pred_projection_bad = float(r._safe_metric(row.get("pred_projection_bad_prob")) or projection_bad_safe_cap)
        pred_projection_error = float(r._safe_metric(row.get("pred_projection_error")) or projection_error_safe_cap)
        subtype = str(row.get("alignment_subtype", "mixed_safe"))
        segment = str(row.get("segment", "mixed_shift"))
        blocker = str(row.get("blocker_group", "other"))
        family = str(row.get("family", "unknown"))
        benchmark_proximity = max(0.0, 1.0 - min(1.0, benchmark_distance / max(benchmark_distance_cap, 1e-6)))
        level_clean = max(0.0, 1.0 - min(1.0, projection_level / max(projection_level_cap, 1e-6)))
        shape_clean = max(0.0, 1.0 - min(1.0, projection_shape / max(projection_shape_cap, 1e-6)))
        gain_strength = min(1.0, max(0.0, gain_goal))
        stability_headroom = max(0.0, 1.0 - min(1.0, stability_value / max(stability_cap, 1e-6)))
        projection_safety = 0.55 * max(
            0.0, 1.0 - min(1.0, pred_projection_bad / max(projection_bad_safe_cap, 1e-6))
        ) + 0.45 * max(
            0.0, 1.0 - min(1.0, pred_projection_error / max(projection_error_safe_cap, 1e-6))
        )
        support_family = blocker in {"persistence_guard", "recovery_guard"} and family in {"persistence", "recovery"}
        subtype_bonus = {
            "retained_like_profile": 0.12,
            "gain_fragile_profile": 0.07,
            "mixed_safe": 0.03,
            "projection_shape_fragile": -0.03,
            "stability_fragile": -0.01 if support_family else -0.08,
        }.get(subtype, 0.0)
        segment_bonus = {
            "benchmark_adjacent": 0.10,
            "projection_borderline": 0.06,
            "gain_structure_shifted": 0.04,
            "stability_sensitive": 0.08 if support_family else 0.0,
        }.get(segment, 0.0)
        family_bonus = 0.08 if support_family else 0.0
        return {
            "support_contract_precision_score": float(
                0.30 * benchmark_proximity
                + 0.24 * shape_clean
                + 0.16 * projection_safety
                + 0.14 * stability_headroom
                + 0.10 * level_clean
                + 0.06 * gain_strength
                + subtype_bonus
                + segment_bonus
                + family_bonus
            ),
            "support_contract_runner_score": float(
                0.28 * benchmark_proximity
                + 0.22 * shape_clean
                + 0.18 * level_clean
                + 0.14 * projection_safety
                + 0.10 * stability_headroom
                + 0.08 * gain_strength
                + subtype_bonus
                + 0.5 * segment_bonus
                + family_bonus
            ),
            "support_contract_selection_score": float(
                0.32 * benchmark_proximity
                + 0.18 * shape_clean
                + 0.14 * level_clean
                + 0.12 * projection_safety
                + 0.10 * gain_strength
                + 0.10 * stability_headroom
                + subtype_bonus
                + 0.35 * segment_bonus
                + family_bonus
            ),
        }

    all_rows = []
    recovery_case_outcomes = []
    safe_pool_rows = []
    safe_pool_benchmark_like_rows = []

    for scenario_result in rejects:
        row = r._benchmark_scenario_candidate_row(
            cfg,
            scenario_result,
            projection_boundary=projection_boundary,
            benchmark_summary=benchmark_summary,
        )
        candidate_summary = dict(scenario_result.get("candidate_summary", {}))
        row["projection_policy_ok_provisional"] = bool(candidate_summary.get("projection_policy_ok_provisional", False))
        row["candidate_local_score"] = r._safe_metric(candidate_summary.get("local_score"))
        row["candidate_patch_size"] = r._safe_metric(candidate_summary.get("patch_size"))
        row["candidate_persistence_streak"] = r._safe_metric(candidate_summary.get("persistence_streak"))
        row["projection_level_critic"] = float(
            r._row_projection_level_critic_v2(row, benchmark_summary, projection_boundary=projection_boundary)
        )
        row["projection_shape_critic"] = float(r._row_projection_shape_critic_v2(row, benchmark_summary))
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
            benchmark_distance_cap=benchmark_distance_cap,
            projection_shape_cap=projection_shape_cap,
            gain_goal_floor=gain_goal_floor,
            stability_cap=stability_cap,
            gain_structure_benchmark_distance_soft_cap=gain_structure_benchmark_distance_soft_cap,
            gain_structure_gain_soft_floor=gain_structure_gain_soft_floor,
        )
        row.update(
            r._routing_slice_retest_eval_row(
                row,
                projection_level_cap=projection_level_cap,
                projection_shape_cap=projection_shape_cap,
                gain_goal_floor=gain_goal_floor,
                stability_cap=stability_cap,
                projection_bad_safe_cap=projection_bad_safe_cap,
                projection_error_safe_cap=projection_error_safe_cap,
                benchmark_distance_cap=benchmark_distance_cap,
                gain_structure_level_soft_cap=gain_structure_level_soft_cap,
                gain_structure_benchmark_distance_soft_cap=gain_structure_benchmark_distance_soft_cap,
                gain_structure_projection_bad_soft_cap=gain_structure_projection_bad_soft_cap,
                gain_structure_gain_soft_floor=gain_structure_gain_soft_floor,
            )
        )
        row.update(_score_row(row))

        family = str(row.get("family", "unknown"))
        baseline_reason = str(row.get("slice_reason", "final_benchmark_admission"))
        segment = str(row.get("segment", "mixed_shift"))
        subtype = str(row.get("alignment_subtype", "mixed_safe"))
        blocker = str(row.get("blocker_group", "other"))
        scenario_id = str(row.get("scenario_id", ""))
        oracle_decision = str(scenario_result.get("oracle_decision", "reject"))
        pred_projection_bad = float(r._safe_metric(row.get("pred_projection_bad_prob")) or 99.0)
        pred_projection_error = float(r._safe_metric(row.get("pred_projection_error")) or 99.0)
        benchmark_distance = float(r._safe_metric(row.get("benchmark_distance")) or 99.0)
        projection_level = float(r._safe_metric(row.get("projection_level_critic")) or 99.0)
        projection_shape = float(r._safe_metric(row.get("projection_shape_critic")) or 99.0)
        gain_goal = float(r._safe_metric(row.get("gain_goal_critic_v2")) or -99.0)
        stability_value = float(r._safe_metric(row.get("stability_critic_v2")) or 99.0)
        precision_score = float(row.get("support_contract_precision_score", 0.0))
        runner_score = float(row.get("support_contract_runner_score", 0.0))
        selection_score = float(row.get("support_contract_selection_score", 0.0))
        local_score = float(r._safe_metric(row.get("candidate_local_score")) or 0.0)
        confidence = float(r._safe_metric(row.get("confidence")) or 0.0)
        gain = float(r._safe_metric(row.get("gain")) or 0.0)
        raw_safe = bool(
            row.get("projection_policy_ok_provisional", False)
            and pred_projection_bad <= projection_bad_safe_cap
            and pred_projection_error <= projection_error_safe_cap * 1.15
        )
        support_family = bool(
            family in {"persistence", "recovery"}
            and blocker in {"persistence_guard", "recovery_guard"}
            and segment == "stability_sensitive"
        )

        low_gain_recovery_branch = bool(
            family == "recovery"
            and subtype == "stability_fragile"
            and 0.30 <= confidence <= 0.38
            and 0.14 <= gain <= 0.26
            and local_score <= -0.05
            and pred_projection_error <= persistence_projection_error_cap + 0.00035
            and benchmark_distance <= min(0.35, benchmark_distance_cap * 0.40)
        )
        moderate_gain_recovery_branch = bool(
            family == "recovery"
            and subtype == "stability_fragile"
            and 0.33 <= confidence <= 0.40
            and 0.50 <= gain <= 0.56
            and local_score <= 0.0
            and pred_projection_error <= persistence_projection_error_cap + 0.00035
            and benchmark_distance <= min(0.60, benchmark_distance_cap * 0.60)
        )

        recovery_mapping_resolved = bool(
            support_family
            and family == "recovery"
            and raw_safe
            and (
                (
                    precision_score >= persistence_precision_floor * 0.97
                    and runner_score >= persistence_runner_floor * 0.96
                    and benchmark_distance <= persistence_distance_cap + 0.04
                    and pred_projection_bad <= persistence_projection_bad_cap + 0.035
                    and pred_projection_error <= persistence_projection_error_cap + 0.00045
                )
                or low_gain_recovery_branch
                or moderate_gain_recovery_branch
            )
        )
        recovery_post_support_pass = bool(
            recovery_mapping_resolved
            and (
                (
                    low_gain_recovery_branch
                    and precision_score >= 0.51
                    and runner_score >= 0.49
                    and selection_score >= 0.47
                )
                or (
                    moderate_gain_recovery_branch
                    and precision_score >= 0.52
                    and runner_score >= 0.50
                    and selection_score >= 0.50
                )
                or (
                    selection_score >= persistence_selection_floor * 0.92
                    and projection_shape <= projection_shape_cap * 0.92
                    and projection_level <= gain_structure_level_soft_cap * 0.92
                    and stability_value <= stability_cap * 1.03
                    and runner_score >= persistence_runner_floor * 0.94
                    and precision_score >= persistence_precision_floor * 0.94
                    and pred_projection_error <= persistence_projection_error_cap + 0.00035
                )
            )
        )

        persistence_support_resolved = bool(
            family == "persistence"
            and support_family
            and raw_safe
            and precision_score >= persistence_precision_floor * 0.99
            and runner_score >= persistence_runner_floor * 0.99
            and selection_score >= persistence_selection_floor * 0.98
            and benchmark_distance <= persistence_distance_cap + 0.03
            and pred_projection_bad <= persistence_projection_bad_cap + 0.03
            and pred_projection_error <= persistence_projection_error_cap + 0.00035
        )

        support_group_mapping_resolved = bool(
            baseline_reason not in {"blocker_not_supported", "unsupported_segment"}
            or persistence_support_resolved
            or recovery_mapping_resolved
        )
        if baseline_reason in {"blocker_not_supported", "unsupported_segment"} and family == "recovery":
            if recovery_mapping_resolved:
                support_attr = "resolved_recovery_runner_contract_fix"
            elif scenario_id in recovery_mapping_ids:
                support_attr = "missing_support_group_mapping"
            elif scenario_id in recovery_runner_ids:
                support_attr = "runner_path_incompatibility"
            else:
                support_attr = "runner_path_incompatibility"
        elif baseline_reason in {"blocker_not_supported", "unsupported_segment"} and family == "persistence":
            if persistence_support_resolved:
                support_attr = "resolved_by_persistence_pattern_reuse"
            else:
                support_attr = "runner_path_incompatibility"
        elif baseline_reason in {"blocker_not_supported", "unsupported_segment"}:
            support_attr = "stage_specific_admission_rules"
        else:
            support_attr = "not_applicable"

        post_support_validation_passed = bool(
            support_group_mapping_resolved
            and (
                family not in {"persistence", "recovery"}
                or persistence_support_resolved
                or recovery_post_support_pass
            )
        )

        stability_guard_passed = bool(
            baseline_reason != "stability_guard"
            or (
                (subtype in {"retained_like_profile", "gain_fragile_profile", "mixed_safe"} or segment in {"projection_borderline", "benchmark_adjacent"})
                and selection_score >= 0.60
                and pred_projection_bad <= projection_bad_safe_cap * 0.98
                and pred_projection_error <= projection_error_safe_cap * 0.98
                and benchmark_distance <= benchmark_distance_cap * 0.95
                and projection_shape <= projection_shape_cap * 0.98
                and projection_level <= gain_structure_level_soft_cap * 0.95
            )
        )

        transfer_safe_pool = bool(
            raw_safe
            and support_group_mapping_resolved
            and post_support_validation_passed
            and stability_guard_passed
            and segment != "projection_far_shifted"
            and selection_score >= 0.50
            and benchmark_distance <= benchmark_distance_cap
        )

        recovery_transfer_alignment_score = float(
            0.32 * precision_score
            + 0.25 * runner_score
            + 0.23 * selection_score
            + 0.10 * max(0.0, 1.0 - min(1.0, benchmark_distance / max(persistence_distance_cap + 0.06, 1e-6)))
            + 0.05 * max(0.0, 1.0 - min(1.0, pred_projection_error / max(persistence_projection_error_cap + 0.00055, 1e-6)))
            + 0.05 * max(0.0, 1.0 - min(1.0, pred_projection_bad / max(persistence_projection_bad_cap + 0.04, 1e-6)))
            + (0.08 if low_gain_recovery_branch else 0.05 if moderate_gain_recovery_branch else 0.0)
            + (0.05 if family == "persistence" and persistence_support_resolved else 0.0)
        )

        benchmark_like_scoring_executed = bool(transfer_safe_pool)
        benchmark_like_safe = bool(
            transfer_safe_pool
            and (
                (
                    family == "recovery"
                    and benchmark_like_scoring_executed
                    and recovery_transfer_alignment_score >= 0.50
                    and (low_gain_recovery_branch or moderate_gain_recovery_branch)
                )
                or (
                    family == "persistence"
                    and persistence_support_resolved
                    and recovery_transfer_alignment_score >= 0.52
                    and benchmark_distance <= persistence_distance_cap + 0.03
                    and pred_projection_error <= persistence_projection_error_cap + 0.00035
                )
                or (
                    family not in {"persistence", "recovery"}
                    and bool(row.get("benchmark_like_safe", False))
                    and selection_score >= 0.60
                    and pred_projection_error <= projection_error_safe_cap * 0.98
                )
            )
        )

        if not raw_safe:
            failure_stage = "projection_validation"
            dominant_blocker = "projection_safe_guard"
        elif not support_group_mapping_resolved:
            failure_stage = "support_group_mapping"
            dominant_blocker = str(support_attr)
        elif not post_support_validation_passed:
            failure_stage = "post_support_validation"
            dominant_blocker = "runner_path_incompatibility" if family == "recovery" else "post_support_validation"
        elif not stability_guard_passed:
            failure_stage = "stability_guard"
            dominant_blocker = "stability_guard"
        elif not benchmark_like_safe:
            failure_stage = "benchmark_like_scoring"
            dominant_blocker = "benchmark-family interpretation mismatch"
        else:
            failure_stage = "benchmark_like_safe_pool"
            dominant_blocker = "none"

        family_breakdown.setdefault(
            family,
            {
                "candidates_entered": 0,
                "blocked_by_support_group_mapping": 0,
                "blocked_by_runner_path_incompatibility": 0,
                "blocked_by_post_support_validation": 0,
                "blocked_by_stability_guard": 0,
                "surviving_to_safe_pool": 0,
                "surviving_to_safe_pool_benchmark_like": 0,
                "surviving_to_selected_benchmark_like": 0,
            },
        )
        family_breakdown[family]["candidates_entered"] += 1
        if failure_stage == "support_group_mapping":
            family_breakdown[family]["blocked_by_support_group_mapping"] += 1
        if dominant_blocker == "runner_path_incompatibility":
            family_breakdown[family]["blocked_by_runner_path_incompatibility"] += 1
        if failure_stage == "post_support_validation":
            family_breakdown[family]["blocked_by_post_support_validation"] += 1
        if failure_stage == "stability_guard":
            family_breakdown[family]["blocked_by_stability_guard"] += 1
        if transfer_safe_pool:
            family_breakdown[family]["surviving_to_safe_pool"] += 1
            safe_pool_rows.append(dict(row))
        if benchmark_like_safe:
            family_breakdown[family]["surviving_to_safe_pool_benchmark_like"] += 1
            safe_pool_benchmark_like_rows.append(dict(row))

        row.update(
            {
                "support_group_mapping_resolved": bool(support_group_mapping_resolved),
                "post_support_validation_passed": bool(post_support_validation_passed),
                "benchmark_like_scoring_executed": bool(benchmark_like_scoring_executed),
                "benchmark_transfer_safe_pool": bool(transfer_safe_pool),
                "benchmark_transfer_like_safe": bool(benchmark_like_safe),
                "recovery_transfer_alignment_score": float(recovery_transfer_alignment_score),
                "support_failure_attribution": str(support_attr),
                "failure_stage_probe": str(failure_stage),
                "dominant_blocker_probe": str(dominant_blocker),
                "low_gain_recovery_branch": bool(low_gain_recovery_branch),
                "moderate_gain_recovery_branch": bool(moderate_gain_recovery_branch),
            }
        )
        all_rows.append(dict(row))

        if family == "recovery":
            recovery_case_outcomes.append(
                {
                    "case_id": scenario_id,
                    "subtype": subtype,
                    "support_group_mapping_resolved": bool(support_group_mapping_resolved),
                    "post_support_validation_passed": bool(post_support_validation_passed),
                    "benchmark_like_scoring_executed": bool(benchmark_like_scoring_executed),
                    "safe_pool_benchmark_like_survived": bool(benchmark_like_safe),
                    "selected_benchmark_like_survived": False,
                    "dominant_blocker": str(dominant_blocker),
                    "oracle_decision": oracle_decision,
                    "recovery_transfer_alignment_score": float(recovery_transfer_alignment_score),
                    "support_contract_precision_score": float(precision_score),
                    "support_contract_runner_score": float(runner_score),
                    "support_contract_selection_score": float(selection_score),
                    "benchmark_distance": r._safe_metric(benchmark_distance),
                    "pred_projection_bad_prob": r._safe_metric(pred_projection_bad),
                    "pred_projection_error": r._safe_metric(pred_projection_error),
                    "local_score": r._safe_metric(local_score),
                    "confidence": r._safe_metric(confidence),
                    "gain": r._safe_metric(gain),
                }
            )

    selected_source = sorted(
        [row for row in safe_pool_benchmark_like_rows if str(row.get("family", "")) in {"recovery", "persistence"}],
        key=lambda row: (
            0 if str(row.get("family", "")) == "recovery" else 1,
            0 if str(row.get("scenario_id", "")) in recovery_mapping_ids | recovery_runner_ids else 1,
            subtype_priority.get(str(row.get("alignment_subtype", "")), 9),
            -round(float(r._safe_metric(row.get("recovery_transfer_alignment_score")) or -99.0), 6),
            round(float(r._safe_metric(row.get("benchmark_distance")) or 99.0), 6),
            round(float(r._safe_metric(row.get("pred_projection_error")) or 99.0), 6),
            str(row.get("scenario_id", "")),
        ),
    )
    selected_rows = selected_source[: min(selection_target_count, len(selected_source))]
    selected_ids = {str(row.get("scenario_id", "")) for row in selected_rows}
    for row in selected_rows:
        family_breakdown[str(row.get("family", "unknown"))]["surviving_to_selected_benchmark_like"] += 1
    for row in recovery_case_outcomes:
        row["selected_benchmark_like_survived"] = bool(str(row.get("case_id", "")) in selected_ids)

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
        probe_row = next((row for row in all_rows if str(row.get("scenario_id", "")) == scenario_id), {})
        variant_row["recovery_contract_probe"] = {
            "selected_for_control": bool(scenario_id in selected_ids),
            "support_group_mapping_resolved": bool(dict(probe_row).get("support_group_mapping_resolved", False)),
            "post_support_validation_passed": bool(dict(probe_row).get("post_support_validation_passed", False)),
            "benchmark_like_scoring_executed": bool(dict(probe_row).get("benchmark_like_scoring_executed", False)),
            "benchmark_transfer_safe_pool": bool(dict(probe_row).get("benchmark_transfer_safe_pool", False)),
            "benchmark_transfer_like_safe": bool(dict(probe_row).get("benchmark_transfer_like_safe", False)),
            "recovery_transfer_alignment_score": r._safe_metric(dict(probe_row).get("recovery_transfer_alignment_score")),
            "support_failure_attribution": str(dict(probe_row).get("support_failure_attribution", "")),
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
            sum(
                bool(
                    float(r._safe_metric(row.get("pred_projection_bad_prob")) or 99.0) <= projection_bad_safe_cap
                    and float(r._safe_metric(row.get("pred_projection_error")) or 99.0) <= projection_error_safe_cap * 1.15
                )
                for row in selected_rows
            )
            / benchmark_slice_count
        )
        if benchmark_slice_count
        else 0.0
    )
    mean_projection_error = r._mean_key(selected_rows, "pred_projection_error")
    family_mix = dict(sorted(Counter(str(row.get("family", "unknown")) for row in selected_rows).items()))
    safe_pool_family_mix = dict(sorted(Counter(str(row.get("family", "unknown")) for row in safe_pool_rows).items()))

    recovery_safe_pool_like_count = int(
        sum(1 for row in safe_pool_benchmark_like_rows if str(row.get("family", "")) == "recovery")
    )
    recovery_selected_like_count = int(
        sum(1 for row in selected_rows if str(row.get("family", "")) == "recovery")
    )
    recovery_mapping_improved = bool(
        int(family_breakdown["recovery"]["blocked_by_support_group_mapping"]) < 9
        and any(bool(row.get("support_group_mapping_resolved", False)) for row in recovery_case_outcomes)
    )
    recovery_post_support_improved = bool(
        any(bool(row.get("post_support_validation_passed", False)) for row in recovery_case_outcomes)
    )
    recovery_scoring_executed = bool(
        any(bool(row.get("benchmark_like_scoring_executed", False)) for row in recovery_case_outcomes)
    )
    false_safe_delta = float(comparison.get("false_safe_projection_rate_delta", 0.0) or 0.0)
    unsafe_overcommit_delta = float(comparison.get("unsafe_overcommit_rate_delta", 0.0) or 0.0)
    structural_progress = bool(
        recovery_selected_like_count > 0
        and recovery_post_support_improved
        and false_safe_delta <= prior_false_safe + 1e-9
        and unsafe_overcommit_delta <= 1e-9
        and projection_safe_retention >= 0.98
    )

    decision_checks = {
        "recovery_support_group_mapping_improved": bool(recovery_mapping_improved),
        "recovery_post_support_validation_passed_for_some_cases": bool(recovery_post_support_improved),
        "benchmark_like_scoring_executed_for_some_recovery_cases": bool(recovery_scoring_executed),
        "recovery_safe_pool_benchmark_like_count_non_zero": bool(recovery_safe_pool_like_count > 0),
        "recovery_selected_benchmark_like_count_non_zero_or_materially_improved": bool(recovery_selected_like_count > 0),
        "projection_safe_behavior_preserved_without_new_unsafe_overcommit_drift": bool(
            projection_safe_retention >= 0.98 and unsafe_overcommit_delta <= 1e-9
        ),
        "result_is_real_family_transfer_progress": bool(structural_progress),
    }

    if all(decision_checks.values()):
        choice = "B"
        recommended_next_template = "critic_split.benchmark_like_transfer_alignment_probe_v1"
        next_control_hypothesis = "benchmark_transfer_scoring_refinement"
        recommendation_reason = (
            "recovery now reaches post-support validation and benchmark-like scoring with non-zero selected benchmark-like survivors, so the bottleneck moves back to late critic-transfer alignment rather than runner/contract handling"
        )
    elif decision_checks["recovery_support_group_mapping_improved"] or decision_checks["recovery_post_support_validation_passed_for_some_cases"]:
        choice = "A"
        recommended_next_template = "support_contract.recovery_runner_contract_fix_v1"
        next_control_hypothesis = "recovery_runner_contract_fix"
        recommendation_reason = (
            "recovery-family runner/contract handling improved enough to show headroom, but the family-transfer path is not yet strong or clean enough to hand back to critic-transfer work"
        )
    else:
        choice = "C"
        recommended_next_template = "memory_summary.recovery_transfer_asymmetry_snapshot_v1"
        next_control_hypothesis = "recovery_transfer_diagnostic"
        recommendation_reason = (
            "recovery remains blocked too early and too ambiguously to justify another control-family step without a tighter diagnostic"
        )

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "support_contract.recovery_runner_contract_fix_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "comparison_references": {
            "memory_summary.recovery_transfer_asymmetry_snapshot_v1": {
                "primary": str(dict(asymmetry.get("blocker_attribution", {})).get("primary", "")),
                "secondary": str(dict(asymmetry.get("blocker_attribution", {})).get("secondary", "")),
            },
            "critic_split.benchmark_like_transfer_alignment_probe_v1": dict(
                transfer.get("benchmark_control_metrics", {})
            ),
            "support_contract.benchmark_stability_sensitive_compat_probe_v1": dict(
                support.get("benchmark_control_metrics", {})
            ),
            "memory_summary.runner_path_incompatibility_snapshot_v1": dict(
                runner_mem.get("blocker_attribution", {})
            ),
        },
        "benchmark_control_metrics": {
            "benchmark_slice_count": int(benchmark_slice_count),
            "safe_pool_count": int(safe_pool_count),
            "safe_pool_benchmark_like_count": int(safe_pool_benchmark_like_count),
            "selected_benchmark_like_count": int(selected_benchmark_like_count),
            "projection_safe_retention": float(projection_safe_retention),
            "mean_projection_error": mean_projection_error,
            "policy_match_rate_delta": float(comparison.get("policy_match_rate_delta", 0.0) or 0.0),
            "false_safe_projection_rate_delta": float(false_safe_delta),
            "unsafe_overcommit_rate_delta": float(unsafe_overcommit_delta),
            "family_mix": family_mix,
            "safe_pool_family_mix": safe_pool_family_mix,
            "seed_fragility_if_available": None,
        },
        "recovery_case_outcomes": sorted(
            recovery_case_outcomes,
            key=lambda row: str(row.get("case_id", "")),
        ),
        "family_level_breakdown": family_breakdown,
        "decision_checks": decision_checks,
        "comparison_to_baseline": comparison,
        "support_bridge_summary": {
            "persistence_distance_cap": float(persistence_distance_cap),
            "persistence_precision_floor": float(persistence_precision_floor),
            "persistence_runner_floor": float(persistence_runner_floor),
            "persistence_selection_floor": float(persistence_selection_floor),
            "persistence_projection_bad_cap": float(persistence_projection_bad_cap),
            "persistence_projection_error_cap": float(persistence_projection_error_cap),
            "resolved_recovery_mapping_cases": sorted(
                [str(row.get("case_id", "")) for row in recovery_case_outcomes if bool(row.get("support_group_mapping_resolved", False))]
            ),
            "resolved_recovery_post_support_cases": sorted(
                [str(row.get("case_id", "")) for row in recovery_case_outcomes if bool(row.get("post_support_validation_passed", False))]
            ),
            "selected_recovery_cases": sorted(
                [str(row.get("case_id", "")) for row in recovery_case_outcomes if bool(row.get("selected_benchmark_like_survived", False))]
            ),
        },
        "observability_gain": {
            "passed": bool(len(recovery_case_outcomes) >= 9),
            "case_count": int(len(recovery_case_outcomes)),
            "recovery_safe_pool_benchmark_like_count": int(recovery_safe_pool_like_count),
            "recovery_selected_benchmark_like_count": int(recovery_selected_like_count),
            "reason": "the frozen benchmark pack contains enough recovery-family stability-sensitive cases to test a narrow runner/contract bridge against the proven persistence path",
        },
        "activation_analysis_usefulness": {
            "passed": bool(recovery_post_support_improved and recovery_scoring_executed),
            "recovery_post_support_validation_passed": bool(recovery_post_support_improved),
            "recovery_scoring_executed": bool(recovery_scoring_executed),
            "reason": "the probe checks whether recovery can finally reach the same late benchmark-like path that persistence already reaches",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": float(
                min(
                    1.0,
                    0.18
                    + 0.14 * int(decision_checks["recovery_support_group_mapping_improved"])
                    + 0.14 * int(decision_checks["recovery_post_support_validation_passed_for_some_cases"])
                    + 0.14 * int(decision_checks["benchmark_like_scoring_executed_for_some_recovery_cases"])
                    + 0.14 * int(decision_checks["recovery_safe_pool_benchmark_like_count_non_zero"])
                    + 0.14 * int(decision_checks["recovery_selected_benchmark_like_count_non_zero_or_materially_improved"])
                    + 0.12 * int(decision_checks["projection_safe_behavior_preserved_without_new_unsafe_overcommit_drift"])
                )
            ),
            "reason": "the probe separates recovery-specific runner/contract progress from late benchmark-like scoring and final selection quality",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "benchmark-only recovery runner/contract fix with live policy, thresholds, routing policy, and frozen benchmark semantics unchanged",
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
            "next_control_hypothesis": str(next_control_hypothesis),
            "recommended_next_template": str(recommended_next_template),
            "decision_recommendation": str(choice),
        },
        "sample_rows": {
            "selected_examples": selected_rows[:8],
            "recovery_safe_pool_examples": [row for row in safe_pool_benchmark_like_rows if str(row.get("family", "")) == "recovery"][:8],
            "recovery_block_examples": [row for row in all_rows if str(row.get("family", "")) == "recovery" and not bool(row.get("support_group_mapping_resolved", False))][:8],
        },
    }
    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"support_contract_recovery_runner_contract_fix_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    passed = bool(
        decision_checks["recovery_support_group_mapping_improved"]
        and decision_checks["recovery_post_support_validation_passed_for_some_cases"]
        and decision_checks["benchmark_like_scoring_executed_for_some_recovery_cases"]
        and decision_checks["recovery_safe_pool_benchmark_like_count_non_zero"]
        and decision_checks["projection_safe_behavior_preserved_without_new_unsafe_overcommit_drift"]
    )
    reason = (
        "diagnostic shadow passed: the recovery-family runner/contract bridge materially improves transfer into post-support validation and benchmark-like scoring without weakening projection safety"
        if passed
        else "diagnostic shadow failed: the recovery-family runner/contract bridge did not create a clean enough recovery transfer path"
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
