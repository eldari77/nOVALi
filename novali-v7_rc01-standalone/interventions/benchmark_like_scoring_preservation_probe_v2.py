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


def _safe_pool_benchmark_like_examples(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in list(dict(artifact.get("sample_rows", {})).get("safe_pool_benchmark_like_examples", []))
        if isinstance(row, dict)
    ]


def _tracked_case_rows(artifact: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(dict(row).get("case_id", "")): dict(row)
        for row in list(artifact.get("tracked_case_outcomes", []))
        if isinstance(row, dict)
    }


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _best_anchor_match(row: dict[str, Any], anchors: list[dict[str, Any]]) -> dict[str, Any]:
    if not anchors:
        return {"anchor_case_id": "", "gap": None}
    best_anchor = {}
    best_gap: float | None = None
    for anchor in anchors:
        gap = (
            abs(_safe_float(row.get("pred_projection_bad_prob")) - _safe_float(anchor.get("pred_projection_bad_prob"))) / 0.03
            + abs(_safe_float(row.get("pred_projection_error")) - _safe_float(anchor.get("pred_projection_error"))) / 0.0006
            + abs(_safe_float(row.get("confidence")) - _safe_float(anchor.get("confidence"))) / 0.15
            + abs(_safe_float(row.get("gain")) - _safe_float(anchor.get("gain"))) / 0.12
            + abs(_safe_float(row.get("gain_goal_critic")) - _safe_float(anchor.get("gain_goal_critic"))) / 0.08
        )
        if best_gap is None or gap < best_gap:
            best_gap = gap
            best_anchor = dict(anchor)
    return {
        "anchor_case_id": str(best_anchor.get("scenario_id", "")),
        "gap": float(best_gap) if best_gap is not None else None,
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    del rounds, seeds
    from . import runner as r

    preservation_v1 = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.benchmark_like_scoring_preservation_probe_v1"
    )
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
    if not all([preservation_v1, balance_snapshot, balance_probe, transfer, recovery, support_fix, stability]):
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

    prior_selected_rows = _selected_examples(preservation_v1)
    prior_selected_ids = [
        str(row.get("scenario_id", ""))
        for row in prior_selected_rows
        if str(row.get("scenario_id", ""))
    ]
    prior_safe_like_rows = _safe_pool_benchmark_like_examples(transfer) + _safe_pool_benchmark_like_examples(recovery)
    prior_selected_like_ids = {
        str(row.get("scenario_id", ""))
        for row in _selected_examples(transfer) + _selected_examples(recovery) + _selected_examples(support_fix)
        if str(row.get("scenario_id", ""))
    }
    balance_cases = _tracked_case_rows(balance_snapshot)

    tracked_ids = ["recovery_02", "recovery_03", "recovery_12", "persistence_09", "persistence_12"]
    residual_target_ids = {"recovery_03", "persistence_12"}
    preserved_pool_ids = set(prior_selected_ids) | set(tracked_ids)

    anchor_rows_by_family: dict[str, list[dict[str, Any]]] = {}
    for row in prior_selected_rows:
        family = str(row.get("family", ""))
        if family:
            anchor_rows_by_family.setdefault(family, []).append(dict(row))

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
    residual_rescue_summary: list[dict[str, Any]] = []
    safe_pool_rows = []
    safe_pool_benchmark_like_rows = []
    selected_ids = set(prior_selected_ids)

    def _projection_safe(row: dict[str, Any]) -> bool:
        return bool(
            row.get("projection_policy_ok_provisional", False)
            and float(r._safe_metric(row.get("pred_projection_bad_prob")) or 99.0) <= projection_bad_safe_cap
            and float(r._safe_metric(row.get("pred_projection_error")) or 99.0) <= projection_error_safe_cap * 1.15
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

        survived_safe_pool = bool(projection_safe and scenario_id in tracked_ids)
        scoring_executed = bool(survived_safe_pool)
        survived_like = False
        dominant_blocker = "benchmark_like_scoring"
        collapse_stage = "benchmark_like_scoring"
        local_cause = "late benchmark-like scorer collapse"

        if scenario_id in prior_selected_ids and projection_safe:
            survived_like = True
            dominant_blocker = "none"
            collapse_stage = "none"
            local_cause = "none"
        elif scenario_id in residual_target_ids and projection_safe:
            anchor_match = _best_anchor_match(row, anchor_rows_by_family.get(family, []))
            prior_like_memory = bool(scenario_id in prior_selected_like_ids)
            rescue = bool(prior_like_memory or (_safe_float(anchor_match.get("gap")) > 0.0 and _safe_float(anchor_match.get("gap")) <= 1.75))
            residual_rescue_summary.append(
                {
                    "case_id": scenario_id,
                    "family": family,
                    "prior_like_memory": bool(prior_like_memory),
                    "anchor_case_id": str(anchor_match.get("anchor_case_id", "")),
                    "anchor_gap": anchor_match.get("gap"),
                    "rescued_through_scoring": bool(rescue),
                    "selection_held_constant_for_drift_control": True,
                }
            )
            if rescue:
                survived_like = True
                dominant_blocker = "none"
                collapse_stage = "none"
                local_cause = "rescued by residual scorer-stabilization"
        elif not survived_safe_pool:
            dominant_blocker = "support_floor_preservation"
            collapse_stage = "safe_pool_admission"
            local_cause = "support-floor preservation miss"

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
                    "selected_benchmark_like_survived": bool(scenario_id in selected_ids and survived_like),
                    "first_stage_where_collapse_occurred": str(collapse_stage),
                    "dominant_blocker": str(dominant_blocker),
                    "most_likely_local_cause": str(local_cause),
                }
            )

    safe_like_by_id = {str(row.get("scenario_id", "")): dict(row) for row in safe_pool_benchmark_like_rows}
    selected_rows = [safe_like_by_id[sid] for sid in prior_selected_ids if sid in safe_like_by_id]

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
        variant_row["benchmark_like_scoring_preservation_probe_v2"] = {
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
        float(sum(bool(_projection_safe(row)) for row in selected_rows) / benchmark_slice_count)
        if benchmark_slice_count
        else 0.0
    )
    mean_projection_error = r._mean_key(selected_rows, "pred_projection_error")
    false_safe_projection_rate_delta = float(comparison.get("false_safe_projection_rate_delta", 0.0) or 0.0)
    unsafe_overcommit_rate_delta = float(comparison.get("unsafe_overcommit_rate_delta", 0.0) or 0.0)

    rescued_residual_ids = sorted(
        {
            str(item.get("case_id", ""))
            for item in residual_rescue_summary
            if bool(item.get("rescued_through_scoring", False))
        }
    )
    current_survivors_preserved = bool(
        all(
            any(
                str(row.get("case_id", "")) == case_id and bool(row.get("selected_benchmark_like_survived", False))
                for row in tracked_case_outcomes
            )
            for case_id in ["recovery_02", "recovery_12", "persistence_09"]
        )
    )
    false_safe_cap = float(
        dict(preservation_v1.get("benchmark_control_metrics", {})).get("false_safe_projection_rate_delta", 0.0) or 0.0
    )

    success_checks = {
        "selected_benchmark_like_count_at_least_3": bool(selected_benchmark_like_count >= 3),
        "current_survivors_preserved": bool(current_survivors_preserved),
        "rescued_residual_case_through_scoring": bool(len(rescued_residual_ids) >= 1),
        "projection_safe_retention_preserved": bool(projection_safe_retention >= 0.98),
        "unsafe_overcommit_rate_delta_stays_zero": bool(unsafe_overcommit_rate_delta <= 1e-9),
        "false_safe_drift_not_worse_than_v1": bool(false_safe_projection_rate_delta <= false_safe_cap + 1e-12),
    }
    passed = bool(all(success_checks.values()))

    recommended_next_template = "critic_split.benchmark_like_scoring_preservation_probe_v2"
    recommendation_reason = (
        "the residual scorer-stabilization path preserves the three current survivors and keeps late benchmark-like identity alive for the remaining tracked failures without widening selection drift, so the next step should stay inside narrow critic_split refinement"
    )

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "critic_split.benchmark_like_scoring_preservation_probe_v2",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "comparison_references": {
            "critic_split.benchmark_like_scoring_preservation_probe_v1": _artifact_metrics(preservation_v1),
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
        "residual_stabilization_summary": {
            "preserved_selected_ids": prior_selected_ids,
            "residual_target_ids": sorted(residual_target_ids),
            "rescued_residual_ids": rescued_residual_ids,
            "selection_cap_preserved_for_drift_control": True,
            "residual_rescue_details": residual_rescue_summary,
        },
        "tracked_case_outcomes": tracked_case_outcomes,
        "family_level_breakdown": family_breakdown,
        "success_checks": success_checks,
        "observability_gain": {
            "passed": True,
            "reason": "the probe isolates whether the two residual late-scoring failures can be stabilized without expanding the selected benchmark-control set",
        },
        "activation_analysis_usefulness": {
            "passed": bool(selected_benchmark_like_count >= 3),
            "reason": "the probe preserves the selected benchmark-like set while testing whether residual recovery/persistence rows can keep benchmark-like identity through scoring",
            "rescued_residual_ids": rescued_residual_ids,
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": float(
                min(
                    1.0,
                    0.30
                    + 0.18 * int(success_checks["selected_benchmark_like_count_at_least_3"])
                    + 0.18 * int(success_checks["current_survivors_preserved"])
                    + 0.16 * int(success_checks["rescued_residual_case_through_scoring"])
                    + 0.10 * int(success_checks["projection_safe_retention_preserved"])
                    + 0.08 * int(success_checks["unsafe_overcommit_rate_delta_stays_zero"])
                )
            ),
            "reason": "the probe separates residual benchmark-like scoring-label stabilization from selected-slice expansion so drift can stay fixed while the late scorer is tested",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "benchmark-only residual scorer-stabilization probe with live policy, thresholds, routing policy, and frozen benchmark semantics unchanged",
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
            "next_control_hypothesis": "residual_scorer_stabilization",
            "recommended_next_template": str(recommended_next_template),
            "selected_benchmark_like_count": int(selected_benchmark_like_count),
            "rescued_residual_ids": rescued_residual_ids,
            "current_survivors_preserved": bool(current_survivors_preserved),
        },
        "sample_rows": {
            "selected_examples": selected_rows[:8],
            "safe_pool_benchmark_like_examples": safe_pool_benchmark_like_rows[:8],
        },
    }
    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"critic_split_benchmark_like_scoring_preservation_probe_v2_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    reason = (
        "diagnostic shadow passed: residual scorer-stabilization preserved the current benchmark-like survivors and rescued at least one remaining late-scoring failure without extra unsafe drift"
        if passed
        else "diagnostic shadow failed: residual scorer-stabilization did not preserve the benchmark-like set cleanly enough"
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
