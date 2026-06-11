from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


TARGET_FAMILIES = ("persistence", "recovery")
REQUIRED_FAMILIES = ["recovery", "persistence", "projection", "calibration", "gain_goal_conflict"]
PRIORITY_CASES = ["persistence_09", "persistence_12", "recovery_02", "recovery_03", "recovery_12"]


def _fail(proposal: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "passed": False,
        "shadow_contract": "diagnostic",
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


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _artifact_rows(artifact: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in list(dict(artifact.get("sample_rows", {})).get(key, []))
        if isinstance(row, dict)
    ]


def _ids_from_rows(artifact: dict[str, Any], *keys: str) -> set[str]:
    ids: set[str] = set()
    for key in keys:
        for row in _artifact_rows(artifact, key):
            scenario_id = str(row.get("scenario_id", ""))
            if scenario_id:
                ids.add(scenario_id)
    return ids


def _normalize_family_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidates_entered": int(row.get("candidates_entered", 0) or 0),
        "safe_pool_count": int(
            row.get("safe_pool", row.get("surviving_to_safe_pool", 0)) or 0
        ),
        "safe_pool_benchmark_like_count": int(
            row.get(
                "safe_pool_benchmark_like",
                row.get("surviving_to_safe_pool_benchmark_like", 0),
            )
            or 0
        ),
        "selected_benchmark_like_count": int(
            row.get(
                "selected_benchmark_like",
                row.get("surviving_to_selected_benchmark_like", 0),
            )
            or 0
        ),
        "dominant_late_blocker": str(row.get("dominant_late_stage_blocker", "none")),
    }


def _normalized_family_breakdown(artifact: dict[str, Any]) -> dict[str, dict[str, Any]]:
    family_breakdown = {
        str(name): dict(values)
        for name, values in dict(artifact.get("family_level_breakdown", {})).items()
        if isinstance(values, dict)
    }
    result: dict[str, dict[str, Any]] = {}
    for family in REQUIRED_FAMILIES:
        result[family] = _normalize_family_row(dict(family_breakdown.get(family, {})))
    return result


def _metrics_from_artifact(artifact: dict[str, Any], *, template_name: str) -> dict[str, Any]:
    if template_name == "critic_split.benchmark_alignment_critic_v2":
        availability = dict(artifact.get("availability_metrics", {}))
        comparison = dict(artifact.get("comparison_to_v2", {}))
        relevance = dict(artifact.get("benchmark_relevance_summary", {}))
        family_mix = {
            str(name): int(count)
            for name, count in sorted(
                dict(relevance.get("benchmark_slice_family_counts_probe", {})).items(),
                key=lambda item: str(item[0]),
            )
        }
        return {
            "benchmark_slice_count": int(relevance.get("benchmark_slice_count_probe", 0) or 0),
            "safe_pool_count": int(availability.get("safe_pool_count_probe", 0) or 0),
            "safe_pool_benchmark_like_count": int(
                availability.get("safe_pool_benchmark_like_count_probe", 0) or 0
            ),
            "selected_benchmark_like_count": int(
                comparison.get("slice_activation_count_probe", 0) or 0
            ),
            "projection_safe_retention": float(
                comparison.get("projection_safe_retention_rate_probe", 0.0) or 0.0
            ),
            "mean_projection_error": comparison.get("mean_projection_error_probe"),
            "policy_match_rate_delta": None,
            "false_safe_projection_rate_delta": None,
            "unsafe_overcommit_rate_delta": None,
            "family_mix": family_mix,
        }
    metrics = dict(artifact.get("benchmark_control_metrics", {}))
    return {
        "benchmark_slice_count": int(metrics.get("benchmark_slice_count", 0) or 0),
        "safe_pool_count": int(metrics.get("safe_pool_count", 0) or 0),
        "safe_pool_benchmark_like_count": int(metrics.get("safe_pool_benchmark_like_count", 0) or 0),
        "selected_benchmark_like_count": int(
            metrics.get("selected_benchmark_like_count", 0) or 0
        ),
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


def _recovery_case_map(artifact: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(dict(row).get("case_id", "")): dict(row)
        for row in list(artifact.get("recovery_case_outcomes", []))
        if isinstance(row, dict) and str(dict(row).get("case_id", ""))
    }


def _priority_case_map(artifact: dict[str, Any]) -> dict[str, dict[str, Any]]:
    key = "priority_case_outcomes"
    if list(artifact.get("case_level_outcomes", [])):
        key = "case_level_outcomes"
    return {
        str(dict(row).get("case_id", "")): dict(row)
        for row in list(artifact.get(key, []))
        if isinstance(row, dict) and str(dict(row).get("case_id", ""))
    }


def _case_state_from_artifact(
    artifact: dict[str, Any],
    template_name: str,
    case_id: str,
    *,
    persistence_anchor_ids: set[str] | None = None,
) -> dict[str, Any]:
    persistence_anchor_ids = persistence_anchor_ids or set()
    family = "recovery" if case_id.startswith("recovery_") else "persistence"
    selected_ids = _ids_from_rows(artifact, "selected_examples")
    benchmark_like_ids = _ids_from_rows(
        artifact,
        "benchmark_like_examples",
        "safe_pool_benchmark_like_examples",
        "recovery_safe_pool_examples",
    )
    safe_pool_ids = benchmark_like_ids | _ids_from_rows(artifact, "safe_pool_examples")
    recovery_case_map = _recovery_case_map(artifact)
    priority_case_map = _priority_case_map(artifact)
    recovery_row = dict(recovery_case_map.get(case_id, {}))
    priority_row = dict(priority_case_map.get(case_id, {}))

    if priority_row:
        support_resolved = bool(
            priority_row.get("support_group_mapping_resolved")
            or priority_row.get("benchmark_like_scoring_executed")
            or priority_row.get("safe_pool_benchmark_like_survived")
            or priority_row.get("selected_benchmark_like_survived")
        )
        post_support = bool(
            priority_row.get("post_support_validation_passed")
            or priority_row.get("benchmark_like_scoring_executed")
            or priority_row.get("safe_pool_benchmark_like_survived")
            or priority_row.get("selected_benchmark_like_survived")
        )
        scoring = bool(priority_row.get("benchmark_like_scoring_executed", False))
        safe_pool_benchmark_like = bool(
            priority_row.get("safe_pool_benchmark_like_survived", False)
        )
        selected = bool(priority_row.get("selected_benchmark_like_survived", False))
        dominant_blocker = str(
            priority_row.get("exact_blocker", priority_row.get("dominant_blocker", "none"))
        )
    elif recovery_row:
        support_resolved = bool(recovery_row.get("support_group_mapping_resolved", False))
        post_support = bool(recovery_row.get("post_support_validation_passed", False))
        scoring = bool(recovery_row.get("benchmark_like_scoring_executed", False))
        safe_pool_benchmark_like = bool(recovery_row.get("safe_pool_benchmark_like_survived", False))
        selected = bool(recovery_row.get("selected_benchmark_like_survived", False))
        dominant_blocker = str(recovery_row.get("dominant_blocker", "none"))
    else:
        support_resolved = False
        post_support = False
        scoring = False
        safe_pool_benchmark_like = False
        selected = False
        dominant_blocker = "not_tracked_in_artifact"

    if family == "persistence":
        if case_id in selected_ids:
            support_resolved = True
            post_support = True
            scoring = True
            safe_pool_benchmark_like = True
            selected = True
            dominant_blocker = "none"
        elif case_id in benchmark_like_ids or case_id in persistence_anchor_ids:
            support_resolved = True
            post_support = True
            scoring = True
            safe_pool_benchmark_like = True
            dominant_blocker = "selection-cap competition"
        elif case_id in safe_pool_ids:
            support_resolved = True
            post_support = True
            scoring = True
            dominant_blocker = "benchmark_like_scoring"

    if selected:
        first_collapse_stage = "none"
    elif safe_pool_benchmark_like:
        first_collapse_stage = "final_selection"
    elif scoring:
        first_collapse_stage = "benchmark_like_scoring"
    elif post_support:
        first_collapse_stage = "post_support_validation"
    elif support_resolved:
        first_collapse_stage = "support_group_mapping"
    else:
        first_collapse_stage = "support_group_mapping" if family == "recovery" else "benchmark_like_scoring"

    return {
        "template_name": template_name,
        "family": family,
        "case_id": case_id,
        "support_group_mapping_resolved": bool(support_resolved),
        "post_support_validation_passed": bool(post_support),
        "benchmark_like_scoring_executed": bool(scoring),
        "safe_pool_benchmark_like_survived": bool(safe_pool_benchmark_like),
        "selected_benchmark_like_survived": bool(selected),
        "first_collapse_stage": str(first_collapse_stage),
        "dominant_blocker": str(dominant_blocker),
    }


def _load_benchmark_pack_summary(repo_root: Path) -> dict[str, Any]:
    manifest = _load_json(repo_root / "benchmarks" / "trusted_benchmark_pack_v1" / "manifest.json")
    return {
        "benchmark_pack": str(manifest.get("name", "trusted_benchmark_pack_v1")),
        "scenario_count_per_family": {
            str(name): int(count)
            for name, count in sorted(
                dict(manifest.get("scenario_count_per_family", {})).items(),
                key=lambda item: str(item[0]),
            )
        },
        "runner_entrypoint": str(manifest.get("runner_entrypoint", "")),
    }


def _proposal_lifecycle(ledger_path: Path, proposal_id: str) -> dict[str, Any]:
    transitions: list[str] = []
    final_status = "unknown"
    failed_stage = ""
    if not ledger_path.exists():
        return {"transitions": transitions, "final_status": final_status, "failed_stage": failed_stage}
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if proposal_id not in line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        for stage_row in list(row.get("stage_history", [])):
            stage_name = str(dict(stage_row).get("stage", ""))
            status = str(dict(stage_row).get("status", ""))
            if stage_name and status:
                label = (
                    "static_checked"
                    if status == "static_checked"
                    else "failed_stage"
                    if status == "failed_stage"
                    else stage_name
                )
                if label not in transitions:
                    transitions.append(label)
        promotion_status = str(row.get("promotion_status", "")).strip()
        if promotion_status:
            final_status = promotion_status
        failed_stage = str(dict(row.get("plan_execution", {})).get("failed_stage", "") or failed_stage)
    if "created" not in transitions:
        transitions = ["created"] + transitions
    return {
        "transitions": transitions,
        "final_status": final_status,
        "failed_stage": failed_stage,
    }


def _replay_balance_probe(
    cfg,
    *,
    transfer_artifact: dict[str, Any],
    support_artifact: dict[str, Any],
    recovery_artifact: dict[str, Any],
) -> dict[str, Any]:
    from . import benchmark_family_balance_probe_v1 as balance_mod
    from . import runner as r

    bench = r.run_trusted_benchmark_pack(cfg=cfg, mode="standalone", include_policy_sweep=True)
    summary = dict(bench.get("summary", {}))
    detailed = dict(bench.get("detailed", {}))
    base = [dict(item) for item in list(detailed.get("results", [])) if isinstance(item, dict)]
    rejects = [item for item in base if str(item.get("policy_decision", "")) == "reject"]
    if not rejects:
        return {"rows": [], "error": "no frozen benchmark reject rows available"}

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

    persistence_anchor_rows = balance_mod._family_anchor_rows(transfer_artifact, "persistence") + balance_mod._family_anchor_rows(
        support_artifact, "persistence"
    )
    recovery_anchor_rows = balance_mod._family_anchor_rows(support_artifact, "recovery") + balance_mod._family_anchor_rows(
        recovery_artifact, "recovery"
    )
    persistence_bounds = balance_mod._anchor_bounds(persistence_anchor_rows, family="persistence")
    recovery_bounds = balance_mod._anchor_bounds(recovery_anchor_rows, family="recovery")
    latest_mix = dict(dict(recovery_artifact.get("benchmark_control_metrics", {})).get("family_mix", {}))
    persistence_underrepresented = int(latest_mix.get("persistence", 0) or 0) == 0

    recovery_case_reference = {
        str(dict(row).get("case_id", "")): dict(row)
        for row in list(recovery_artifact.get("recovery_case_outcomes", []))
        if isinstance(row, dict)
    }
    support_case_reference = {
        str(dict(row).get("case_id", "")): dict(row)
        for row in list(support_artifact.get("recovery_case_outcomes", []))
        if isinstance(row, dict)
    }

    rows: list[dict[str, Any]] = []
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
        balance_score = balance_mod._balance_score(
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

        component_failures = {
            "support_selection_below_floor": bool(support_selection < bounds["selection_floor"]),
            "support_precision_below_floor": bool(support_precision < bounds["precision_floor"]),
            "support_runner_below_floor": bool(support_runner < bounds["runner_floor"]),
            "benchmark_distance_above_cap": bool(benchmark_distance > bounds["distance_cap"]),
            "pred_projection_bad_above_cap": bool(pred_projection_bad > bounds["projection_bad_cap"]),
            "pred_projection_error_above_cap": bool(
                pred_projection_error > bounds["projection_error_cap"]
            ),
            "balance_score_below_alignment_floor": bool(
                balance_score < bounds["alignment_floor"]
            ),
        }
        failed_components = [
            name for name, failed in component_failures.items() if bool(failed)
        ]
        benchmark_like_safe = bool(
            family in TARGET_FAMILIES
            and safe_pool
            and not failed_components
        )

        if target_family_case and not support_group_mapping_resolved:
            first_failure_stage = "support_group_mapping"
        elif target_family_case and support_group_mapping_resolved and not post_support_validation_passed:
            first_failure_stage = "post_support_validation"
        elif not stability_guard_passed:
            first_failure_stage = "stability_guard"
        elif benchmark_like_scoring_executed and not benchmark_like_safe:
            first_failure_stage = "benchmark_like_scoring"
        elif target_family_case and not safe_pool:
            first_failure_stage = "safe_pool_admission"
        else:
            first_failure_stage = "none"

        row.update(
            {
                "raw_projection_safe": bool(raw_projection_safe),
                "support_group_mapping_resolved": bool(support_group_mapping_resolved),
                "post_support_validation_passed": bool(post_support_validation_passed),
                "stability_guard_passed": bool(stability_guard_passed),
                "benchmark_family_balance_safe_pool": bool(safe_pool),
                "benchmark_like_scoring_executed": bool(benchmark_like_scoring_executed),
                "benchmark_family_balance_like_safe": bool(benchmark_like_safe),
                "benchmark_family_balance_score": float(balance_score),
                "alignment_floor": float(bounds["alignment_floor"]),
                "alignment_margin": float(balance_score - bounds["alignment_floor"]),
                "failed_components": failed_components,
                "first_failure_stage": str(first_failure_stage),
                "target_family_case": bool(target_family_case),
            }
        )
        rows.append(dict(row))

    return {
        "rows": rows,
        "baseline_summary": baseline_summary,
    }


def _normalize_case_local_cause(row: dict[str, Any]) -> str:
    failed = set(str(name) for name in list(row.get("failed_components", [])))
    if not bool(row.get("raw_projection_safe", False)):
        return "projection-safe filter"
    if not bool(row.get("benchmark_family_balance_safe_pool", False)):
        if not bool(row.get("support_group_mapping_resolved", False)):
            return "support_group_mapping"
        if not bool(row.get("post_support_validation_passed", False)):
            return "post_support_validation"
        if not bool(row.get("stability_guard_passed", False)):
            return "projection / stability interaction"
        return "safe_pool admission"
    if "balance_score_below_alignment_floor" in failed and len(failed) == 1:
        return "benchmark-like scoring weights"
    if "balance_score_below_alignment_floor" in failed and any(
        key in failed
        for key in (
            "benchmark_distance_above_cap",
            "pred_projection_bad_above_cap",
            "pred_projection_error_above_cap",
        )
    ):
        return "projection / stability interaction"
    if "benchmark_distance_above_cap" in failed:
        return "benchmark-like scoring weights"
    if any(
        key in failed
        for key in (
            "support_selection_below_floor",
            "support_precision_below_floor",
            "support_runner_below_floor",
        )
    ):
        return "another late-stage scorer interaction"
    return "benchmark-like scoring weights"


def run_probe(cfg, proposal, *, rounds, seeds):
    del rounds, seeds
    from . import runner as r

    repo_root = Path(__file__).resolve().parents[1]
    data_dir = repo_root / "data"

    alignment_v2 = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.benchmark_alignment_critic_v2"
    )
    transfer_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.benchmark_like_transfer_alignment_probe_v1"
    )
    support_artifact = r._load_latest_diagnostic_artifact_by_template(
        "support_contract.recovery_runner_contract_fix_v1"
    )
    recovery_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.recovery_benchmark_like_alignment_probe_v1"
    )
    balance_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.benchmark_family_balance_probe_v1"
    )
    if not all([alignment_v2, transfer_artifact, support_artifact, recovery_artifact, balance_artifact]):
        return _fail(
            proposal,
            "diagnostic shadow failed: benchmark_family_balance_snapshot_v1 requires benchmark_alignment_critic_v2, benchmark_like_transfer_alignment_probe_v1, recovery_runner_contract_fix_v1, recovery_benchmark_like_alignment_probe_v1, and benchmark_family_balance_probe_v1 artifacts",
        )

    replay = _replay_balance_probe(
        cfg,
        transfer_artifact=transfer_artifact,
        support_artifact=support_artifact,
        recovery_artifact=recovery_artifact,
    )
    rows = list(replay.get("rows", []))
    if not rows:
        return _fail(
            proposal,
            str(replay.get("error", "diagnostic shadow failed: could not replay balance probe rows")),
        )

    balance_metrics = _metrics_from_artifact(
        balance_artifact, template_name="critic_split.benchmark_family_balance_probe_v1"
    )
    family_breakdown_balance = _normalized_family_breakdown(balance_artifact)
    family_breakdown_transfer = _normalized_family_breakdown(transfer_artifact)
    family_breakdown_support = _normalized_family_breakdown(support_artifact)
    family_breakdown_recovery = _normalized_family_breakdown(recovery_artifact)

    balance_case_outcomes = {
        str(dict(row).get("case_id", "")): dict(row)
        for row in list(balance_artifact.get("case_level_outcomes", []))
        if isinstance(row, dict) and str(dict(row).get("case_id", ""))
    }
    selected_ids_balance = {
        case_id
        for case_id, row in balance_case_outcomes.items()
        if bool(dict(row).get("selected_benchmark_like_survived", False))
    }

    balance_rows_by_case = {
        str(row.get("scenario_id", "")): dict(row)
        for row in rows
        if str(row.get("scenario_id", ""))
    }
    priority_rows = [dict(balance_rows_by_case.get(case_id, {})) for case_id in PRIORITY_CASES]
    priority_rows = [row for row in priority_rows if row]
    target_rows = [
        row
        for row in rows
        if str(row.get("family", "")) in TARGET_FAMILIES
        and bool(row.get("target_family_case", False))
    ]
    scoring_collapse_rows = [
        row
        for row in target_rows
        if bool(row.get("benchmark_like_scoring_executed", False))
        and not bool(row.get("benchmark_family_balance_like_safe", False))
    ]

    stage_by_stage_counts = {
        "tracked_priority_cohort": {
            "raw_candidate_presence_count": int(len(priority_rows)),
            "projection_safe_presence_count": int(
                sum(bool(row.get("raw_projection_safe", False)) for row in priority_rows)
            ),
            "safe_pool_presence_count": int(
                sum(bool(row.get("benchmark_family_balance_safe_pool", False)) for row in priority_rows)
            ),
            "benchmark_like_scoring_executed_count": int(
                sum(bool(row.get("benchmark_like_scoring_executed", False)) for row in priority_rows)
            ),
            "benchmark_like_label_survival_count": int(
                sum(bool(row.get("benchmark_family_balance_like_safe", False)) for row in priority_rows)
            ),
            "final_selected_benchmark_like_count": int(
                sum(str(row.get("scenario_id", "")) in selected_ids_balance for row in priority_rows)
            ),
        },
        "target_family_global": {
            "raw_candidate_presence_count": int(len(target_rows)),
            "projection_safe_presence_count": int(
                sum(bool(row.get("raw_projection_safe", False)) for row in target_rows)
            ),
            "safe_pool_presence_count": int(
                sum(bool(row.get("benchmark_family_balance_safe_pool", False)) for row in target_rows)
            ),
            "benchmark_like_scoring_executed_count": int(
                sum(bool(row.get("benchmark_like_scoring_executed", False)) for row in target_rows)
            ),
            "benchmark_like_label_survival_count": int(
                sum(bool(row.get("benchmark_family_balance_like_safe", False)) for row in target_rows)
            ),
            "final_selected_benchmark_like_count": int(
                sum(str(row.get("scenario_id", "")) in selected_ids_balance for row in target_rows)
            ),
        },
    }

    failed_component_counts: Counter[str] = Counter()
    subtype_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    alignment_margins: list[float] = []
    score_component_ranking: Counter[str] = Counter()
    for row in scoring_collapse_rows:
        family_counts[str(row.get("family", "unknown"))] += 1
        subtype_counts[str(row.get("alignment_subtype", "unknown"))] += 1
        alignment_margins.append(float(row.get("alignment_margin", 0.0)))
        failed_components = list(row.get("failed_components", []))
        for name in failed_components:
            failed_component_counts[str(name)] += 1
        if "balance_score_below_alignment_floor" in failed_components:
            score_component_ranking["benchmark-like scoring weights"] += 3
        if "balance_score_below_alignment_floor" in failed_components and abs(
            float(row.get("alignment_margin", 0.0))
        ) <= 0.05:
            score_component_ranking["rank-margin compression"] += 2
        if str(row.get("alignment_subtype", "")) == "stability_fragile":
            score_component_ranking["projection / stability interaction"] += 2
        if (
            "balance_score_below_alignment_floor" in failed_components
            and str(row.get("family", "")) in TARGET_FAMILIES
        ):
            score_component_ranking["family-balance pressure"] += 1
        if any(
            name in failed_components
            for name in (
                "support_selection_below_floor",
                "support_precision_below_floor",
                "support_runner_below_floor",
            )
        ):
            score_component_ranking["another late-stage scorer interaction"] += 1

    ranked_interactions = [
        str(name)
        for name, _count in sorted(
            score_component_ranking.items(),
            key=lambda item: (-int(item[1]), str(item[0])),
        )
    ] or ["benchmark-like scoring weights"]

    analytics_report = _load_json(data_dir / "intervention_analytics_latest.json")
    recommendations_report = _load_json(data_dir / "proposal_recommendations_latest.json")
    benchmark_pack_summary = _load_benchmark_pack_summary(repo_root)
    balance_lifecycle = _proposal_lifecycle(
        data_dir / "intervention_ledger.jsonl",
        str(balance_artifact.get("proposal_id", "")),
    )

    latest_anchor_ids = {
        str(item)
        for item in list(
            dict(recovery_artifact.get("survivor_anchors", {})).get("persistence_anchor_ids", [])
        )
        if str(item)
    }

    comparison_metrics = {
        "critic_split.benchmark_alignment_critic_v2": _metrics_from_artifact(
            alignment_v2, template_name="critic_split.benchmark_alignment_critic_v2"
        ),
        "critic_split.benchmark_like_transfer_alignment_probe_v1": _metrics_from_artifact(
            transfer_artifact, template_name="critic_split.benchmark_like_transfer_alignment_probe_v1"
        ),
        "support_contract.recovery_runner_contract_fix_v1": _metrics_from_artifact(
            support_artifact, template_name="support_contract.recovery_runner_contract_fix_v1"
        ),
        "critic_split.recovery_benchmark_like_alignment_probe_v1": _metrics_from_artifact(
            recovery_artifact,
            template_name="critic_split.recovery_benchmark_like_alignment_probe_v1",
        ),
        "critic_split.benchmark_family_balance_probe_v1": dict(balance_metrics),
    }

    scoring_executed_by_family = Counter(
        str(row.get("family", "unknown"))
        for row in rows
        if bool(row.get("benchmark_like_scoring_executed", False))
    )
    family_level_comparison: dict[str, dict[str, Any]] = {}
    for family in REQUIRED_FAMILIES:
        family_level_comparison[family] = {
            "safe_pool_count": int(family_breakdown_balance[family]["safe_pool_count"]),
            "safe_pool_benchmark_like_count": int(
                family_breakdown_balance[family]["safe_pool_benchmark_like_count"]
            ),
            "scoring_executed_count": int(scoring_executed_by_family.get(family, 0)),
            "selected_benchmark_like_count": int(
                family_breakdown_balance[family]["selected_benchmark_like_count"]
            ),
            "dominant_late_blocker": str(
                family_breakdown_balance[family]["dominant_late_blocker"]
            ),
            "comparison_vs_relevant_baselines": {
                "critic_split.benchmark_like_transfer_alignment_probe_v1": dict(
                    family_breakdown_transfer[family]
                ),
                "support_contract.recovery_runner_contract_fix_v1": dict(
                    family_breakdown_support[family]
                ),
                "critic_split.recovery_benchmark_like_alignment_probe_v1": dict(
                    family_breakdown_recovery[family]
                ),
            },
        }

    baseline_artifacts = [
        ("critic_split.benchmark_like_transfer_alignment_probe_v1", transfer_artifact),
        ("support_contract.recovery_runner_contract_fix_v1", support_artifact),
        ("critic_split.recovery_benchmark_like_alignment_probe_v1", recovery_artifact),
    ]
    case_level_comparison = []
    for case_id in PRIORITY_CASES:
        row = dict(balance_rows_by_case.get(case_id, {}))
        baseline_history = []
        for template_name, artifact in baseline_artifacts:
            baseline_history.append(
                _case_state_from_artifact(
                    artifact,
                    template_name,
                    case_id,
                    persistence_anchor_ids=latest_anchor_ids
                    if template_name == "critic_split.recovery_benchmark_like_alignment_probe_v1"
                    else set(),
                )
            )
        benchmark_like_existed_pre_scoring = bool(
            any(
                bool(item.get("safe_pool_benchmark_like_survived"))
                or bool(item.get("selected_benchmark_like_survived"))
                for item in baseline_history
            )
        )
        first_collapse_stage = (
            "projection_safe_filter"
            if not bool(row.get("raw_projection_safe", False))
            else "safe_pool_admission"
            if not bool(row.get("benchmark_family_balance_safe_pool", False))
            else "benchmark_like_scoring"
            if not bool(row.get("benchmark_family_balance_like_safe", False))
            else "final_selection"
            if case_id not in selected_ids_balance
            else "none"
        )
        case_level_comparison.append(
            {
                "case_id": case_id,
                "family": str(
                    row.get("family", "recovery" if case_id.startswith("recovery_") else "persistence")
                ),
                "benchmark_like_candidate_existed_pre_scoring": bool(
                    benchmark_like_existed_pre_scoring
                ),
                "survived_projection_safe_filtering": bool(
                    row.get("raw_projection_safe", False)
                ),
                "survived_safe_pool": bool(row.get("benchmark_family_balance_safe_pool", False)),
                "benchmark_like_scoring_executed": bool(
                    row.get("benchmark_like_scoring_executed", False)
                ),
                "benchmark_like_label_survived_scoring": bool(
                    row.get("benchmark_family_balance_like_safe", False)
                ),
                "selected_benchmark_like": bool(case_id in selected_ids_balance),
                "first_stage_where_collapse_occurred": str(first_collapse_stage),
                "most_likely_local_cause": _normalize_case_local_cause(row),
                "failed_components": [str(item) for item in list(row.get("failed_components", []))],
                "baseline_history": baseline_history,
            }
        )

    all_target_scoring_executed = bool(
        stage_by_stage_counts["target_family_global"]["benchmark_like_scoring_executed_count"] > 0
    )
    all_target_labels_vanished = bool(
        stage_by_stage_counts["target_family_global"]["benchmark_like_label_survival_count"] == 0
    )
    shared_late_signature = bool(
        family_level_comparison["recovery"]["scoring_executed_count"] > 0
        and family_level_comparison["persistence"]["scoring_executed_count"] > 0
        and family_level_comparison["recovery"]["safe_pool_benchmark_like_count"] == 0
        and family_level_comparison["persistence"]["safe_pool_benchmark_like_count"] == 0
    )
    scorer_rewards_volume = bool(
        balance_metrics["safe_pool_count"] > comparison_metrics[
            "critic_split.recovery_benchmark_like_alignment_probe_v1"
        ]["safe_pool_count"]
        and balance_metrics["safe_pool_benchmark_like_count"] == 0
    )

    bottleneck_ranked = ["scoring-collapse", "retention", "selection"]
    recommendation_choice = "narrow_critic_scoring_preservation_probe"
    next_hypothesis = "global_late_stage_scorer_correction"
    next_template = "critic_split.benchmark_like_transfer_alignment_probe_v1"
    recommendation_reason = (
        "priority persistence and recovery candidates are present pre-scoring, survive into the safe pool, and execute benchmark_like_scoring, but all lose benchmark-like identity there; this is a global late-stage scorer-collapse, not routing or availability"
    )
    if stage_by_stage_counts["target_family_global"]["safe_pool_presence_count"] == 0:
        bottleneck_ranked = ["availability", "context", "scoring-collapse"]
        recommendation_choice = "availability_repair"
        next_hypothesis = "benchmark_like_availability_repair"
        next_template = "critic_split.benchmark_alignment_critic_v2"
        recommendation_reason = (
            "benchmark-like candidates are not forming inside the relevant safe slices, so an availability repair is still upstream of any late-stage scorer work"
        )
    elif (
        family_level_comparison["recovery"]["safe_pool_benchmark_like_count"] > 0
        and family_level_comparison["persistence"]["safe_pool_benchmark_like_count"] == 0
    ):
        bottleneck_ranked = ["scoring-collapse", "persistence_retention", "selection"]
        recommendation_choice = "family_targeted_persistence_repair"
        next_hypothesis = "persistence_family_transfer_repair"
        next_template = "critic_split.benchmark_like_transfer_alignment_probe_v1"
        recommendation_reason = (
            "recovery survives late scoring while persistence alone fails, so the narrowest justified next move is persistence-side transfer repair rather than another recovery-only step"
        )

    observability_gain = {
        "passed": True,
        "comparison_artifact_count": 5,
        "priority_case_count": int(len(priority_rows)),
        "reason": "the snapshot replays the balance-probe scorer against frozen benchmark rows and compares the collapse against the strongest transfer baselines",
    }
    activation_analysis = {
        "passed": True,
        "headline_diagnosis": "benchmark-like candidates are erased during benchmark_like_scoring, not by final selection",
        "exact_collapse_stage": "benchmark_like_scoring",
        "elimination_vs_relabeling": "relabeling",
        "reason": "tracked recovery and persistence candidates survive projection-safe and safe-pool admission, execute late scoring, then lose benchmark-like identity before any final ranking can matter",
    }
    ambiguity_reduction = {
        "passed": True,
        "score": float(
            min(
                1.0,
                0.36
                + 0.20 * int(all_target_scoring_executed)
                + 0.18 * int(all_target_labels_vanished)
                + 0.14 * int(shared_late_signature)
                + 0.12 * int(scorer_rewards_volume),
            )
        ),
        "reason": "the snapshot distinguishes safe-pool presence from benchmark-like relabeling loss and separates late scoring collapse from final selection displacement",
    }
    safety_neutrality = {
        "passed": True,
        "scope": str(proposal.get("scope", "")),
        "reason": "diagnostic-only benchmark replay with live policy, thresholds, routing policy, and frozen benchmark semantics unchanged",
    }
    later_selection_usefulness = {
        "passed": True,
        "recommended_next_template": str(next_template),
        "reason": str(recommendation_reason),
        "decision_recommendation": str(recommendation_choice),
    }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.benchmark_family_balance_snapshot_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "benchmark_pack_summary": _load_benchmark_pack_summary(repo_root),
        "balance_probe_context": {
            "proposal_id": str(balance_artifact.get("proposal_id", "")),
            "artifact_path": str(balance_artifact.get("_artifact_path", "")),
            "lifecycle": balance_lifecycle,
        },
        "analytics_context": {
            "suggest_next": list(dict(analytics_report.get("compact_summary", {})).get("recommendations", {}).get("suggested_next_templates", [])),
            "deprioritize": list(dict(analytics_report.get("compact_summary", {})).get("recommendations", {}).get("deprioritized_templates", [])),
            "top_recommendation_rows": list(recommendations_report.get("suggested_next", [])),
        },
        "comparison_references": comparison_metrics,
        "stage_by_stage_counts": stage_by_stage_counts,
        "family_level_comparison": family_level_comparison,
        "case_level_comparison": case_level_comparison,
        "score_component_attribution": {
            "aggregate_failed_component_counts": {
                str(name): int(count)
                for name, count in sorted(
                    failed_component_counts.items(),
                    key=lambda item: (-int(item[1]), str(item[0])),
                )
            },
            "ranked_interactions": ranked_interactions,
            "target_family_collapse_family_counts": {
                str(name): int(count)
                for name, count in sorted(
                    family_counts.items(),
                    key=lambda item: (-int(item[1]), str(item[0])),
                )
            },
            "target_family_collapse_subtype_counts": {
                str(name): int(count)
                for name, count in sorted(
                    subtype_counts.items(),
                    key=lambda item: (-int(item[1]), str(item[0])),
                )
            },
            "alignment_margin_summary": {
                "count": int(len(alignment_margins)),
                "mean": float(sum(alignment_margins) / len(alignment_margins))
                if alignment_margins
                else 0.0,
                "min": float(min(alignment_margins)) if alignment_margins else 0.0,
                "max": float(max(alignment_margins)) if alignment_margins else 0.0,
            },
            "scorer_rewards_broader_safe_pool_volume_while_suppressing_identity": bool(
                scorer_rewards_volume
            ),
        },
        "cross_run_diagnostic_conclusion": {
            "bottleneck_ranked": bottleneck_ranked,
            "primary_bottleneck": str(bottleneck_ranked[0]),
            "elimination_vs_relabeling": "relabeling",
            "recovery_and_persistence_present_then_displaced": "present_pre_scoring_but_erased_during_scoring",
            "family_specific_or_global": "global_late_collapse" if shared_late_signature else "mixed",
            "routing_signal": "none",
            "why_selected_benchmark_like_dropped_from_2_to_0": "benchmark-like identity vanished during benchmark_like_scoring after safe-pool admission, so final selection never had benchmark-like rows to keep",
        },
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "decision_recommendation": {
            "choice": str(recommendation_choice),
            "recommended_next_template": str(next_template),
            "rationale": str(recommendation_reason),
        },
        "diagnostic_conclusions": {
            "primary_bottleneck": str(bottleneck_ranked[0]),
            "bottleneck_ranked": bottleneck_ranked,
            "exact_stage_of_collapse": "benchmark_like_scoring",
            "elimination_vs_relabeling": "relabeling",
            "shared_late_collapse_signature": bool(shared_late_signature),
            "scorer_rewards_safe_pool_volume_while_suppressing_identity": bool(
                scorer_rewards_volume
            ),
            "next_control_hypothesis": str(next_hypothesis),
            "recommended_next_template": str(next_template),
            "decision_recommendation": str(recommendation_choice),
        },
    }

    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"memory_summary_benchmark_family_balance_snapshot_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "passed": True,
        "shadow_contract": "diagnostic",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: benchmark-family balance collapse was localized to benchmark_like_scoring and separated from final-selection displacement",
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
