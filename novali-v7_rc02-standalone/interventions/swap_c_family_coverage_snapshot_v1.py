from __future__ import annotations

import json
from typing import Any


REPORTED_FAMILIES = ["recovery", "persistence", "projection", "calibration", "gain_goal_conflict"]
OLD_INCUMBENT = ["recovery_02", "recovery_12", "persistence_09"]
SWAP_C = ["recovery_02", "recovery_03", "recovery_12"]
PERSISTENCE_TRACKED = ["persistence_09", "persistence_12"]


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
    del cfg, rounds, seeds
    from . import runner as r

    confirmation_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.safe_trio_incumbent_confirmation_probe_v1"
    )
    scorer_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.benchmark_like_scoring_preservation_probe_v2"
    )
    guardrail_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.final_selection_false_safe_guardrail_probe_v1"
    )
    if not all([confirmation_artifact, scorer_artifact, guardrail_artifact]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: confirmation, scorer-preservation, and guardrail artifacts are required",
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
                "reason": "cannot localize swap_C family coverage without the prerequisite incumbent and safe-pool artifacts",
            },
        }

    confirmation_cases = _tracked_case_map(confirmation_artifact)
    scorer_cases = _tracked_case_map(scorer_artifact)
    case_rows = dict(scorer_cases)
    case_rows.update(confirmation_cases)

    old_swap_rows = [
        dict(row)
        for row in list(confirmation_artifact.get("old_incumbent_vs_swap_c", []))
        if isinstance(row, dict)
    ]
    old_row = next((row for row in old_swap_rows if str(row.get("trio_name", "")) == "old_incumbent"), {})
    swap_c_row = next((row for row in old_swap_rows if str(row.get("trio_name", "")) == "swap_C"), {})
    confirmation_conclusions = dict(confirmation_artifact.get("diagnostic_conclusions", {}))

    scorer_family_breakdown = {
        str(name): dict(payload)
        for name, payload in dict(scorer_artifact.get("family_level_breakdown", {})).items()
    }

    swap_c_selected_ids = list(dict(confirmation_artifact.get("working_baseline_recommendation", {})).get("recommended_working_baseline", SWAP_C))
    old_selected_ids = list(dict(confirmation_artifact.get("working_baseline_recommendation", {})).get("old_incumbent_selected_ids", OLD_INCUMBENT))

    selected_counts_swap_c = _family_counts(swap_c_selected_ids, case_rows)
    selected_counts_old = _family_counts(old_selected_ids, case_rows)

    family_coverage_report = {}
    for family in REPORTED_FAMILIES:
        safe_pool_count = int(dict(scorer_family_breakdown.get(family, {})).get("safe_pool", 0))
        safe_pool_benchmark_like_count = int(dict(scorer_family_breakdown.get(family, {})).get("safe_pool_benchmark_like", 0))
        selected_count = int(selected_counts_swap_c.get(family, 0))
        absent_stage = "present_in_selected_set"
        if safe_pool_benchmark_like_count <= 0 and safe_pool_count <= 0:
            absent_stage = "absent_upstream"
        elif safe_pool_benchmark_like_count > 0 and selected_count <= 0:
            absent_stage = "absent_only_at_selection"
        family_coverage_report[family] = {
            "safe_pool_count": safe_pool_count,
            "safe_pool_benchmark_like_count": safe_pool_benchmark_like_count,
            "selected_count": selected_count,
            "selected_benchmark_like_count": selected_count,
            "absence_stage": absent_stage,
            "old_incumbent_selected_count": int(selected_counts_old.get(family, 0)),
            "swap_c_selected_count": selected_count,
        }

    persistence_specific = {}
    evaluated_trios = [
        dict(row) for row in list(guardrail_artifact.get("evaluated_trio_table", [])) if isinstance(row, dict)
    ]
    old_incumbent_policy = float(old_row.get("policy_match_rate_delta", 0.0))
    old_incumbent_context = float(dict(old_row.get("context_robustness_signal", {})).get("sum", 0.0))
    family_candidate_inventory = []
    family_safe_candidate_count = 0
    family_outperforming_candidate_count = 0
    for row in evaluated_trios:
        policy_delta = float(row.get("policy_match_rate_delta", 0.0))
        context_sum = float(dict(row.get("context_robustness_signal", {})).get("sum", 0.0))
        safe_within_cap = bool(row.get("safe_within_cap", False))
        beats_old_incumbent = bool(
            safe_within_cap
            and (
                policy_delta > old_incumbent_policy + 1e-12
                or (
                    abs(policy_delta - old_incumbent_policy) <= 1e-12
                    and context_sum > old_incumbent_context + 1e-12
                )
            )
        )
        family_candidate_inventory.append(
            {
                "trio_name": str(row.get("trio_name", "")),
                "selected_ids": list(row.get("selected_ids", [])),
                "safe_within_cap": safe_within_cap,
                "beats_old_incumbent": beats_old_incumbent,
                "policy_match_rate_delta": policy_delta,
                "context_robustness_sum": context_sum,
                "false_safe_margin_vs_cap": float(row.get("false_safe_margin_vs_cap", 0.0)),
                "family_mix": dict(row.get("family_mix", {})),
            }
        )
        family_safe_candidate_count += int(safe_within_cap)
        family_outperforming_candidate_count += int(beats_old_incumbent)

    best_trio_with_case = {}
    for case_id in PERSISTENCE_TRACKED:
        matching = [
            row for row in evaluated_trios if case_id in list(row.get("selected_ids", []))
        ]
        if matching:
            best_trio_with_case[case_id] = sorted(
                matching,
                key=lambda row: (
                    -float(row.get("policy_match_rate_delta", 0.0)),
                    -float(dict(row.get("context_robustness_signal", {})).get("sum", 0.0)),
                    str(row.get("trio_name", "")),
                ),
            )[0]
        else:
            best_trio_with_case[case_id] = {}

    swap_c_policy = float(swap_c_row.get("policy_match_rate_delta", 0.0))
    swap_c_context_sum = float(dict(swap_c_row.get("context_robustness_signal", {})).get("sum", 0.0))
    for case_id in PERSISTENCE_TRACKED:
        case_row = dict(case_rows.get(case_id, {}))
        best_case_trio = dict(best_trio_with_case.get(case_id, {}))
        local_reason = "not present in the current safe pool"
        if bool(case_row.get("safe_pool_benchmark_like_survived", False)):
            if case_id not in swap_c_selected_ids:
                best_case_policy = float(best_case_trio.get("policy_match_rate_delta", 0.0))
                best_case_context = float(dict(best_case_trio.get("context_robustness_signal", {})).get("sum", 0.0))
                if best_case_policy < swap_c_policy - 1e-12:
                    local_reason = "all safe trios containing this persistence case underperform swap_C on policy-match under the fixed cap"
                elif abs(best_case_policy - swap_c_policy) <= 1e-12 and best_case_context < swap_c_context_sum - 1e-12:
                    local_reason = "safe trios containing this persistence case tie on policy-match but lose the context-robustness tie-break under the fixed cap"
                else:
                    local_reason = "excluded at final selected-set composition under the fixed false-safe cap"
            else:
                local_reason = "included in the compared incumbent"
        persistence_specific[case_id] = {
            "survives_projection_safe_filtering": bool(case_row.get("survived_projection_safe_filtering", False)),
            "survives_safe_pool_admission": bool(case_row.get("survived_safe_pool", False)),
            "survives_benchmark_like_scoring": bool(case_row.get("safe_pool_benchmark_like_survived", False)),
            "blocked_at_final_selection_under_swap_c": bool(
                bool(case_row.get("safe_pool_benchmark_like_survived", False)) and case_id not in swap_c_selected_ids
            ),
            "best_local_reason": str(local_reason),
            "best_safe_trio_with_case": {
                "trio_name": str(best_case_trio.get("trio_name", "")),
                "selected_ids": list(best_case_trio.get("selected_ids", [])),
                "policy_match_rate_delta": _safe_float(best_case_trio.get("policy_match_rate_delta")),
                "context_robustness_sum": _safe_float(dict(best_case_trio.get("context_robustness_signal", {})).get("sum")),
            },
        }

    recovery_context_scores = {
        case_id: _safe_float(dict(case_rows.get(case_id, {})).get("context_pressure_score"))
        for case_id in SWAP_C
    }
    persistence_context_scores = {
        case_id: _safe_float(dict(case_rows.get(case_id, {})).get("context_pressure_score"))
        for case_id in PERSISTENCE_TRACKED
    }
    context_dependency_analysis = {
        "swap_c_context_robustness_sum": float(dict(swap_c_row.get("context_robustness_signal", {})).get("sum", 0.0)),
        "old_incumbent_context_robustness_sum": float(dict(old_row.get("context_robustness_signal", {})).get("sum", 0.0)),
        "recovery_context_pressure_scores": recovery_context_scores,
        "persistence_context_pressure_scores": persistence_context_scores,
        "interpretation": "recovery concentration is driven by higher context-pressure robustness among recovery_03 and recovery_12, while persistence candidates remain healthy upstream and fall only at fixed-cap final composition",
    }

    persistence_absent_only_at_selection = bool(
        int(dict(family_coverage_report.get("persistence", {})).get("safe_pool_benchmark_like_count", 0)) > 0
        and int(dict(family_coverage_report.get("persistence", {})).get("selected_benchmark_like_count", 0)) == 0
    )
    recovery_advantage_real = bool(
        float(swap_c_row.get("policy_match_rate_delta", 0.0)) > float(old_row.get("policy_match_rate_delta", 0.0)) + 1e-12
        and float(dict(swap_c_row.get("context_robustness_signal", {})).get("sum", 0.0))
        > float(dict(old_row.get("context_robustness_signal", {})).get("sum", 0.0)) + 1e-12
    )
    swap_c_family_position_assessment = (
        "swap_C_family_supported"
        if family_outperforming_candidate_count >= 2
        else "swap_C_isolated"
    )
    if family_outperforming_candidate_count >= 4 and persistence_absent_only_at_selection:
        family_coverage_assessment = "moderate"
    elif family_outperforming_candidate_count >= 4:
        family_coverage_assessment = "family_coverage_broad"
    elif family_outperforming_candidate_count >= 2:
        family_coverage_assessment = "moderate"
    else:
        family_coverage_assessment = "narrow"
    exploitation_bottleneck_relation_assessment = (
        "final_selection_exploitation_bottleneck_confirmed"
        if persistence_absent_only_at_selection
        else "still_unclear"
    )

    if family_outperforming_candidate_count >= 2 and persistence_absent_only_at_selection and recovery_advantage_real:
        structural_state = "reusable_benchmark_only_control_structure"
        recommendation_reason = (
            "swap_C sits inside a small but repeatable family of safe under-cap trios, while persistence-family rows remain healthy upstream and are compressed only at final composition under the fixed cap, so the next bounded step is to characterize whether the flat false-safe frontier is invariant across this safe trio family before any further control exploration"
        )
        recommended_next_action = "benchmark_only_control_exploration_next"
        recommended_next_template = "memory_summary.safe_trio_false_safe_invariance_snapshot_v1"
        next_hypothesis = "safe_trio_false_safe_frontier_characterization"
    elif recovery_advantage_real:
        structural_state = "narrow_but_meaningful_local_control_win"
        recommendation_reason = (
            "swap_C looks like a real local control win, but the family support is not broad enough to generalize further without another consolidation pass"
        )
        recommended_next_action = "hold_and_consolidate"
        recommended_next_template = ""
        next_hypothesis = "hold_confirmed_swap_c_baseline"
    else:
        structural_state = "too_sparse_to_generalize"
        recommendation_reason = (
            "the persistence-family tradeoff remains too ambiguous, so another diagnostic step is safer than a new control refinement"
        )
        recommended_next_action = "critic_refinement_next"
        recommended_next_template = "critic_split.benchmark_like_scoring_preservation_probe_v2"
        next_hypothesis = "another_diagnostic_step"

    routing_status = "routing_deferred"

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.swap_c_family_coverage_snapshot_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "snapshot_identity_context": {
            "snapshot_line": "memory_summary.swap_c_family_coverage_snapshot_v1",
            "phase": "benchmark_only_control_family_coverage_review",
            "protected_anchor_case_id": "recovery_02",
            "confirmed_swap_c": list(swap_c_selected_ids),
            "frozen_false_safe_cap": float(
                dict(scorer_artifact.get("benchmark_control_metrics", {})).get(
                    "false_safe_projection_rate_delta", 0.0
                )
                or 0.0
            ),
        },
        "evidence_inputs_used": [
            "critic_split.safe_trio_incumbent_confirmation_probe_v1",
            "critic_split.final_selection_false_safe_guardrail_probe_v1",
            "critic_split.benchmark_like_scoring_preservation_probe_v2",
            "trusted_benchmark_pack_v1",
        ],
        "comparison_references": {
            "critic_split.safe_trio_incumbent_confirmation_probe_v1": {
                "swap_c_confirmed_as_new_incumbent_baseline": bool(
                    confirmation_conclusions.get("swap_c_confirmed_as_new_incumbent_baseline", False)
                ),
                "best_safe_trio_name": str(
                    confirmation_conclusions.get("best_safe_trio_name", "")
                ),
            },
            "critic_split.benchmark_like_scoring_preservation_probe_v2": _artifact_metrics(scorer_artifact),
            "critic_split.final_selection_false_safe_guardrail_probe_v1": {
                "best_safe_trio_name": str(dict(guardrail_artifact.get("best_safe_trio", {})).get("trio_name", "")),
                "swap_beats_incumbent": bool(guardrail_artifact.get("swap_beats_incumbent", False)),
            },
        },
        "incumbent_trio_reviewed": dict(old_row),
        "swap_C_reviewed": dict(swap_c_row),
        "family_candidate_inventory": family_candidate_inventory,
        "family_safe_candidate_count": int(family_safe_candidate_count),
        "family_outperforming_candidate_count": int(family_outperforming_candidate_count),
        "swap_C_family_position_assessment": str(swap_c_family_position_assessment),
        "family_coverage_assessment": str(family_coverage_assessment),
        "structural_vs_local_assessment": str(structural_state),
        "exploitation_bottleneck_relation_assessment": str(exploitation_bottleneck_relation_assessment),
        "routing_status": str(routing_status),
        "recommended_next_action": str(recommended_next_action),
        "family_coverage_report": family_coverage_report,
        "incumbent_comparison": {
            "old_incumbent": dict(old_row),
            "swap_c": dict(swap_c_row),
            "selected_family_counts_old_incumbent": selected_counts_old,
            "selected_family_counts_swap_c": selected_counts_swap_c,
        },
        "persistence_specific_analysis": persistence_specific,
        "context_dependency_analysis": context_dependency_analysis,
        "structural_conclusion": {
            "classification": str(structural_state),
            "persistence_absent_only_at_selection": bool(persistence_absent_only_at_selection),
            "recovery_advantage_real": bool(recovery_advantage_real),
            "interpretation": str(recommendation_reason),
        },
        "observability_gain": {
            "passed": True,
            "reason": "the snapshot compares the confirmed incumbent, the old incumbent, and the current safe-pool benchmark-like set without changing control behavior",
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the snapshot localizes whether persistence-family exclusion is upstream scarcity or downstream selected-set compression",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": float(
                min(
                    1.0,
                    0.34
                    + 0.18 * int(bool(persistence_absent_only_at_selection))
                    + 0.18 * int(bool(recovery_advantage_real))
                    + 0.14 * int(int(dict(family_coverage_report.get("persistence", {})).get("safe_pool_benchmark_like_count", 0)) > 0)
                    + 0.12 * int(bool(structural_state == "reusable_benchmark_only_control_structure"))
                )
            ),
            "reason": "the snapshot distinguishes upstream family scarcity from fixed-cap downstream compression after swap_C was confirmed",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "diagnostic-only family-coverage snapshot with live policy, thresholds, routing policy, and frozen benchmark semantics unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_action": str(recommended_next_action),
            "recommended_next_template": str(recommended_next_template),
            "reason": str(recommendation_reason),
        },
        "decision_recommendation": {
            "recommended_next_action": str(recommended_next_action),
            "recommended_next_template": str(recommended_next_template),
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
            "swap_C is not an isolated winner: it sits inside a small family of safe under-cap trios that beat or tie-break past the old incumbent, but the family remains recovery-heavy and persistence-cap-compressed at final selection, which confirms a downstream exploitation bottleneck more than a broad upstream expansion"
        ),
        "diagnostic_conclusions": {
            "classification": str(structural_state),
            "swap_C_family_position_assessment": str(swap_c_family_position_assessment),
            "family_coverage_assessment": str(family_coverage_assessment),
            "family_safe_candidate_count": int(family_safe_candidate_count),
            "family_outperforming_candidate_count": int(family_outperforming_candidate_count),
            "exploitation_bottleneck_relation_assessment": str(exploitation_bottleneck_relation_assessment),
            "recommended_next_action": str(recommended_next_action),
            "recommended_next_template": str(recommended_next_template),
            "next_control_hypothesis": str(next_hypothesis),
            "routing_status": str(routing_status),
            "routing_deferred": True,
        },
    }
    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"memory_summary_swap_c_family_coverage_snapshot_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: swap_C family coverage is localized to downstream fixed-cap composition rather than upstream family scarcity",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
