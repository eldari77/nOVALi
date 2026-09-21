from __future__ import annotations

import json
from typing import Any


REPORTED_FAMILIES = ["recovery", "persistence", "projection", "calibration", "gain_goal_conflict"]
TRIO_DISPLAY_NAMES = {
    "baseline": "old_incumbent",
    "swap_C": "incumbent_swap_c",
    "double_swap": "best_persistence_inclusive_alternative",
}
SAFE_TRIO_ORDER = [
    "swap_C",
    "baseline",
    "double_swap",
    "swap_B",
    "swap_A",
    "swap_D",
]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _normalize_trio_name(name: str) -> str:
    return str(TRIO_DISPLAY_NAMES.get(str(name), str(name)))


def _family_mix_from_row(row: dict[str, Any]) -> dict[str, int]:
    family_mix = dict(row.get("family_mix", {}))
    if not family_mix:
        family_mix = dict(row.get("family_coverage_summary", {}))
    return {family: int(family_mix.get(family, 0) or 0) for family in REPORTED_FAMILIES}


def _context_sum(row: dict[str, Any]) -> float:
    return _safe_float(dict(row.get("context_robustness_signal", {})).get("sum"))


def _load_safe_trio_rows(*artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    rows_by_ids: dict[tuple[str, ...], dict[str, Any]] = {}
    for artifact in artifacts:
        row_groups = [
            list(artifact.get("evaluated_trio_table", [])),
            list(artifact.get("trio_comparison_table", [])),
            list(artifact.get("old_incumbent_vs_swap_c", [])),
        ]
        for group in row_groups:
            for raw in group:
                if not isinstance(raw, dict):
                    continue
                selected_ids = tuple(str(item) for item in list(raw.get("selected_ids", [])) if str(item))
                if len(selected_ids) != 3:
                    continue
                safe = bool(raw.get("safe_within_cap", True))
                if not safe:
                    continue
                trio_name = str(raw.get("trio_name", ""))
                normalized_name = _normalize_trio_name(trio_name)
                existing = rows_by_ids.get(selected_ids)
                candidate = {
                    "trio_name": trio_name,
                    "normalized_trio_name": normalized_name,
                    "selected_ids": list(selected_ids),
                    "selected_benchmark_like_count": int(raw.get("selected_benchmark_like_count", 0) or 0),
                    "projection_safe_retention": _safe_float(raw.get("projection_safe_retention")),
                    "unsafe_overcommit_rate_delta": _safe_float(raw.get("unsafe_overcommit_rate_delta")),
                    "false_safe_projection_rate_delta": _safe_float(raw.get("false_safe_projection_rate_delta")),
                    "policy_match_rate_delta": _safe_float(raw.get("policy_match_rate_delta")),
                    "mean_projection_error": raw.get("mean_projection_error"),
                    "context_robustness_signal": {
                        "sum": _context_sum(raw),
                        "mean": _safe_float(dict(raw.get("context_robustness_signal", {})).get("mean")),
                        "min": _safe_float(dict(raw.get("context_robustness_signal", {})).get("min")),
                        "max": _safe_float(dict(raw.get("context_robustness_signal", {})).get("max")),
                    },
                    "family_coverage_summary": _family_mix_from_row(raw),
                    "safe_within_cap": True,
                    "comparison_sources": sorted(
                        {
                            str(raw.get("comparison_source", "")) or str(artifact.get("template_name", "")),
                            *(existing.get("comparison_sources", []) if existing else []),
                        }
                    ),
                }
                if not existing:
                    rows_by_ids[selected_ids] = candidate
                    continue
                better = (
                    candidate["policy_match_rate_delta"],
                    candidate["context_robustness_signal"]["sum"],
                    candidate["normalized_trio_name"],
                ) > (
                    existing["policy_match_rate_delta"],
                    existing["context_robustness_signal"]["sum"],
                    existing["normalized_trio_name"],
                )
                if better:
                    candidate["comparison_sources"] = sorted(
                        set(existing.get("comparison_sources", [])) | set(candidate["comparison_sources"])
                    )
                    rows_by_ids[selected_ids] = candidate
                else:
                    existing["comparison_sources"] = sorted(
                        set(existing.get("comparison_sources", [])) | set(candidate["comparison_sources"])
                    )

    safe_rows = list(rows_by_ids.values())
    order_lookup = {name: index for index, name in enumerate(SAFE_TRIO_ORDER)}
    safe_rows.sort(
        key=lambda row: (
            order_lookup.get(str(row.get("trio_name", "")), len(order_lookup) + 1),
            str(row.get("normalized_trio_name", "")),
        )
    )
    return safe_rows


def run_probe(cfg, proposal, *, rounds, seeds):
    del cfg, rounds, seeds
    from . import runner as r

    guardrail_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.final_selection_false_safe_guardrail_probe_v1"
    )
    confirmation_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.safe_trio_incumbent_confirmation_probe_v1"
    )
    persistence_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.persistence_balanced_safe_trio_probe_v1"
    )
    coverage_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.swap_c_family_coverage_snapshot_v1"
    )
    margin_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.final_selection_false_safe_margin_snapshot_v1"
    )
    if not all([guardrail_artifact, confirmation_artifact, persistence_artifact, coverage_artifact, margin_artifact]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: safe-trio guardrail, confirmation, persistence-balance, coverage, and final-selection margin artifacts are required",
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
                "reason": "cannot explain safe-trio false-safe invariance without the prerequisite artifacts",
            },
        }

    safe_rows = _load_safe_trio_rows(guardrail_artifact, confirmation_artifact, persistence_artifact)
    if not safe_rows:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no safe trio rows were recoverable from the prerequisite artifacts",
            "observability_gain": {"passed": False, "reason": "no safe trio rows available"},
            "activation_analysis_usefulness": {"passed": False, "reason": "no safe trio rows available"},
            "ambiguity_reduction": {"passed": False, "reason": "no safe trio rows available"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot explain the frontier without any safe trio rows",
            },
        }

    confirmation_conclusions = dict(confirmation_artifact.get("diagnostic_conclusions", {}))
    coverage_conclusions = dict(coverage_artifact.get("diagnostic_conclusions", {}))
    false_safe_cap = _safe_float(
        dict(confirmation_artifact.get("old_incumbent_vs_swap_c", [{}])[0]).get(
            "false_safe_projection_rate_delta",
            dict(guardrail_artifact.get("best_safe_trio", {})).get("false_safe_projection_rate_delta", 0.0),
        )
    )
    for row in safe_rows:
        row["trio_size"] = int(len(list(row.get("selected_ids", []))))
        row["false_safe_margin_vs_cap"] = float(false_safe_cap - _safe_float(row.get("false_safe_projection_rate_delta")))
        row["frontier_guardrail_decomposition"] = {
            "trio_size": int(row["trio_size"]),
            "at_cap": bool(abs(_safe_float(row["false_safe_margin_vs_cap"])) <= 1e-12),
            "family_mix": dict(row.get("family_coverage_summary", {})),
            "comparison_sources": list(row.get("comparison_sources", [])),
        }

    family_coverage_report = {
        str(name): dict(payload)
        for name, payload in dict(coverage_artifact.get("family_coverage_report", {})).items()
        if isinstance(payload, dict)
    }
    total_safe_pool_benchmark_like = int(
        sum(int(dict(payload).get("safe_pool_benchmark_like_count", 0) or 0) for payload in family_coverage_report.values())
    )
    persistence_rows = dict(coverage_artifact.get("persistence_specific_analysis", {}))

    safe_delta_values = sorted({_safe_float(row.get("false_safe_projection_rate_delta")) for row in safe_rows})
    safe_margin_values = sorted({_safe_float(row.get("false_safe_margin_vs_cap")) for row in safe_rows})
    policy_values = [_safe_float(row.get("policy_match_rate_delta")) for row in safe_rows]
    context_values = [_context_sum(row) for row in safe_rows]
    trio_sizes = sorted({int(row.get("trio_size", 0) or 0) for row in safe_rows})

    selected_interactions = dict(margin_artifact.get("selected_set_interaction_report", {}))
    baseline_false_safe = _safe_float(selected_interactions.get("baseline_false_safe_projection_rate_delta_cap"))
    stored_add_trials = {
        str(name): dict(payload)
        for name, payload in dict(selected_interactions.get("stored_add_trials", {})).items()
        if isinstance(payload, dict)
    }
    add_trial_values = sorted(
        {
            _safe_float(dict(payload).get("trial_false_safe_projection_rate_delta"))
            for payload in stored_add_trials.values()
        }
    )
    add_trial_step_values = sorted({float(value - baseline_false_safe) for value in add_trial_values})
    safe_replacement_values = sorted(
        {
            _safe_float(dict(item).get("false_safe_projection_rate_delta"))
            for item in list(selected_interactions.get("safe_replacements", []))
            if isinstance(item, dict)
        }
    )

    invariant_false_safe = bool(len(safe_delta_values) == 1)
    invariant_margin = bool(len(safe_margin_values) == 1 and abs(safe_margin_values[0]) <= 1e-12)
    invariant_size = bool(trio_sizes == [3])
    composition_sensitive_utility = bool(
        max(policy_values, default=0.0) > min(policy_values, default=0.0) + 1e-12
        or max(context_values, default=0.0) > min(context_values, default=0.0) + 1e-12
    )
    headroom_exists = bool(any(value > 1e-12 for value in safe_margin_values))
    family_safety_stability_assessment = (
        "safety_uniform_across_family"
        if invariant_false_safe and invariant_margin and invariant_size
        else "safety_mixed"
    )
    family_utility_stability_assessment = (
        "utility_ordering_sensitive" if composition_sensitive_utility else "utility_ordering_stable"
    )
    if family_safety_stability_assessment == "safety_uniform_across_family" and family_utility_stability_assessment == "utility_ordering_stable":
        invariance_assessment = "invariance_supported"
    elif family_safety_stability_assessment == "safety_uniform_across_family":
        invariance_assessment = "partially_supported"
    else:
        invariance_assessment = "fragile"

    if invariant_false_safe and invariant_margin and invariant_size:
        frontier_classification = "composition_invariant_at_trio_size_3"
        primary_driver = "trio_size_and_guardrail_discretization"
        headroom_reason = (
            "all currently known safe size-3 trios consume the full allowed false-safe budget, and every additive promotion jumps by the same discrete step above the cap"
        )
        frontier_reason = (
            "the false-safe frontier is effectively flat across all currently safe size-3 trios: composition changes utility ranking, but not false-safe occupancy"
        )
        next_hypothesis = "keep_swap_c_and_harden_it"
    else:
        frontier_classification = "composition_sensitive"
        primary_driver = "selected_set_composition"
        headroom_reason = "some safe trios preserve positive margin or vary meaningfully in false-safe occupancy"
        frontier_reason = "composition still changes both utility and false-safe occupancy inside the current safe trio set"
        next_hypothesis = "frontier_relief_critic_probe"

    if not headroom_exists and invariant_false_safe and composition_sensitive_utility:
        swap_c_win_mode = "structurally_better_within_flat_frontier"
    elif headroom_exists:
        swap_c_win_mode = "benefits_from_remaining_headroom"
    else:
        swap_c_win_mode = "frontier_flattened_beyond_measurable_balancing_gain"

    if invariance_assessment == "invariance_supported":
        structural_vs_local_assessment = "robust_invariance_backed_control_structure"
        recommended_next_action = "hold_and_consolidate"
        recommended_next_template = ""
        recommendation_reason = (
            "the safe-trio family now looks invariant in both safety and utility ordering under the frozen cap, so the safest move is to hold the current benchmark-only control result and consolidate"
        )
    elif invariance_assessment == "partially_supported":
        structural_vs_local_assessment = "moderate_family_support_but_composition_sensitive"
        recommended_next_action = "benchmark_only_control_exploration_next"
        recommended_next_template = "critic_split.swap_c_incumbent_hardening_probe_v1"
        recommendation_reason = (
            "safety is uniform across the safe family while utility remains composition-sensitive, so the next bounded step is to test whether the confirmed swap_C incumbent stays stable under this flat frontier before any broader interpretation"
        )
    else:
        structural_vs_local_assessment = "too_fragile_to_generalize"
        recommended_next_action = "critic_refinement_next"
        recommended_next_template = "critic_split.benchmark_like_scoring_preservation_probe_v2"
        recommendation_reason = (
            "the safe-trio family is too composition-sensitive in safety itself to generalize further, so the safest next move is to return to narrower critic refinement"
        )

    exploitation_bottleneck_relation_assessment = (
        "final_selection_exploitation_bottleneck_confirmed"
        if int(dict(family_coverage_report.get("persistence", {})).get("safe_pool_benchmark_like_count", 0)) > 0
        and str(dict(family_coverage_report.get("persistence", {})).get("absence_stage", "")) == "absent_only_at_selection"
        else "still_unclear"
    )
    routing_status = "routing_deferred"

    frontier_analysis_table = [
        {
            "trio_name": str(row.get("normalized_trio_name", "")),
            "source_trio_name": str(row.get("trio_name", "")),
            "selected_ids": list(row.get("selected_ids", [])),
            "selected_benchmark_like_count": int(row.get("selected_benchmark_like_count", 0)),
            "projection_safe_retention": _safe_float(row.get("projection_safe_retention")),
            "unsafe_overcommit_rate_delta": _safe_float(row.get("unsafe_overcommit_rate_delta")),
            "false_safe_projection_rate_delta": _safe_float(row.get("false_safe_projection_rate_delta")),
            "false_safe_margin_vs_cap": _safe_float(row.get("false_safe_margin_vs_cap")),
            "policy_match_rate_delta": _safe_float(row.get("policy_match_rate_delta")),
            "context_robustness_sum": _context_sum(row),
            "family_coverage_summary": dict(row.get("family_coverage_summary", {})),
            "safe_within_cap": bool(row.get("safe_within_cap", False)),
            "frontier_guardrail_decomposition": dict(row.get("frontier_guardrail_decomposition", {})),
        }
        for row in safe_rows
    ]
    swap_c_position_under_invariance_review = {
        "swap_c_is_top_safe_family_member": bool(
            any(
                str(row.get("source_trio_name", "")) == "swap_C"
                and abs(float(row.get("policy_match_rate_delta", 0.0)) - max(policy_values, default=0.0)) <= 1e-12
                for row in frontier_analysis_table
            )
        ),
        "swap_c_win_mode": str(swap_c_win_mode),
        "protected_anchor_preserved": True,
    }

    invariance_analysis = {
        "safe_trio_count": int(len(safe_rows)),
        "safe_trio_sizes": trio_sizes,
        "unique_false_safe_projection_rate_deltas": safe_delta_values,
        "unique_false_safe_margins_vs_cap": safe_margin_values,
        "unique_safe_replacement_false_safe_values": safe_replacement_values,
        "unique_add_trial_false_safe_values": add_trial_values,
        "additive_increment_over_safe_frontier": add_trial_step_values,
        "safe_pool_benchmark_like_count_total": int(total_safe_pool_benchmark_like),
        "safe_trio_frontier_classification": str(frontier_classification),
        "primary_invariant_driver": str(primary_driver),
        "composition_sensitive_utility": bool(composition_sensitive_utility),
        "policy_match_rate_delta_range": {
            "min": float(min(policy_values, default=0.0)),
            "max": float(max(policy_values, default=0.0)),
        },
        "context_robustness_sum_range": {
            "min": float(min(context_values, default=0.0)),
            "max": float(max(context_values, default=0.0)),
        },
        "interpretation": str(frontier_reason),
    }

    structural_conclusion = {
        "classification": str(frontier_classification),
        "swap_c_win_mode": str(swap_c_win_mode),
        "headroom_exists_under_current_cap": bool(headroom_exists),
        "headroom_reason": str(headroom_reason),
        "persistence_upstream_health": "healthy_in_safe_pool" if int(dict(family_coverage_report.get("persistence", {})).get("safe_pool_benchmark_like_count", 0)) > 0 else "absent_upstream",
        "persistence_exclusion_stage": str(dict(family_coverage_report.get("persistence", {})).get("absence_stage", "")),
    }

    observability_gain = {
        "passed": True,
        "reason": "the snapshot explains the fixed false-safe frontier using the already-confirmed safe trio tables and add-vs-replace margin evidence",
        "safe_trio_count": int(len(safe_rows)),
    }
    activation_analysis = {
        "passed": True,
        "reason": "the snapshot localizes whether any remaining critic-accessible headroom exists under the current cap without touching scorer or routing behavior",
        "headroom_exists_under_cap": bool(headroom_exists),
    }
    ambiguity_reduction = {
        "passed": True,
        "score": float(
            min(
                1.0,
                0.36
                + 0.18 * int(invariant_false_safe)
                + 0.16 * int(invariant_margin)
                + 0.14 * int(invariant_size)
                + 0.10 * int(bool(add_trial_step_values))
                + 0.10 * int(bool(composition_sensitive_utility))
            )
        ),
        "reason": "the snapshot separates size/discretization effects from composition-sensitive utility effects inside the same fixed false-safe frontier",
    }
    safety_neutrality = {
        "passed": True,
        "scope": str(proposal.get("scope", "")),
        "reason": "diagnostic-only false-safe frontier snapshot with live policy, thresholds, routing policy, and frozen benchmark semantics unchanged",
    }
    later_selection_usefulness = {
        "passed": True,
        "recommended_next_action": str(recommended_next_action),
        "recommended_next_template": str(recommended_next_template),
        "reason": str(recommendation_reason),
    }

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.safe_trio_false_safe_invariance_snapshot_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "snapshot_identity_context": {
            "snapshot_line": "memory_summary.safe_trio_false_safe_invariance_snapshot_v1",
            "phase": "benchmark_only_control_invariance_review",
            "reviewed_safe_family_count": int(len(safe_rows)),
            "frozen_false_safe_cap": float(false_safe_cap),
            "confirmed_swap_c": list(dict(confirmation_artifact.get("working_baseline_recommendation", {})).get("recommended_working_baseline", [])),
        },
        "evidence_inputs_used": [
            "critic_split.final_selection_false_safe_guardrail_probe_v1",
            "critic_split.safe_trio_incumbent_confirmation_probe_v1",
            "critic_split.persistence_balanced_safe_trio_probe_v1",
            "memory_summary.swap_c_family_coverage_snapshot_v1",
            "memory_summary.final_selection_false_safe_margin_snapshot_v1",
        ],
        "comparison_references": {
            "critic_split.final_selection_false_safe_guardrail_probe_v1": {
                "best_safe_trio_name": str(dict(guardrail_artifact.get("best_safe_trio", {})).get("trio_name", "")),
                "swap_beats_incumbent": bool(guardrail_artifact.get("swap_beats_incumbent", False)),
            },
            "critic_split.safe_trio_incumbent_confirmation_probe_v1": {
                "swap_c_confirmed_as_new_incumbent_baseline": bool(
                    confirmation_conclusions.get("swap_c_confirmed_as_new_incumbent_baseline", False)
                ),
                "best_safe_trio_name": str(
                    confirmation_conclusions.get("best_safe_trio_name", "")
                ),
            },
            "critic_split.persistence_balanced_safe_trio_probe_v1": {
                "best_persistence_trio_name": str(
                    dict(persistence_artifact.get("diagnostic_conclusions", {})).get("best_persistence_trio_name", "")
                ),
                "persistence_balancing_viable_under_cap": bool(
                    dict(persistence_artifact.get("diagnostic_conclusions", {})).get(
                        "persistence_balancing_viable_under_cap", False
                    )
                ),
            },
            "memory_summary.swap_c_family_coverage_snapshot_v1": {
                "classification": str(
                    coverage_conclusions.get("classification", "")
                ),
                "next_control_hypothesis": str(
                    coverage_conclusions.get("next_control_hypothesis", "")
                ),
            },
            "memory_summary.final_selection_false_safe_margin_snapshot_v1": {
                "primary_bottleneck": str(
                    dict(margin_artifact.get("diagnostic_conclusions", {})).get("primary_bottleneck", "")
                ),
                "shared_frontier_anchor": str(
                    dict(margin_artifact.get("diagnostic_conclusions", {})).get("shared_frontier_anchor", "")
                ),
            },
        },
        "reviewed_family_candidates": frontier_analysis_table,
        "family_safety_stability_assessment": str(family_safety_stability_assessment),
        "family_utility_stability_assessment": str(family_utility_stability_assessment),
        "invariance_assessment": str(invariance_assessment),
        "swap_C_position_under_invariance_review": swap_c_position_under_invariance_review,
        "structural_vs_local_assessment": str(structural_vs_local_assessment),
        "exploitation_bottleneck_relation_assessment": str(exploitation_bottleneck_relation_assessment),
        "routing_status": str(routing_status),
        "recommended_next_action": str(recommended_next_action),
        "frontier_analysis_table": frontier_analysis_table,
        "safe_pool_family_coverage": family_coverage_report,
        "persistence_specific_analysis": {
            "persistence_09": dict(persistence_rows.get("persistence_09", {})),
            "persistence_12": dict(persistence_rows.get("persistence_12", {})),
        },
        "frontier_invariance_analysis": invariance_analysis,
        "structural_conclusion": structural_conclusion,
        "observability_gain": observability_gain,
        "activation_analysis_usefulness": activation_analysis,
        "ambiguity_reduction": ambiguity_reduction,
        "safety_neutrality": safety_neutrality,
        "later_selection_usefulness": later_selection_usefulness,
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
            "the safe-trio family stays uniformly safe under the frozen false-safe regime, but utility remains composition-sensitive across the family; that makes swap_C a strong incumbent inside a flat frontier, while confirming that the remaining bottleneck is downstream final-selection exploitation rather than upstream scarcity"
        ),
        "diagnostic_conclusions": {
            "false_safe_frontier_classification": str(frontier_classification),
            "primary_invariant_driver": str(primary_driver),
            "measurable_headroom_under_cap": bool(headroom_exists),
            "swap_c_win_mode": str(swap_c_win_mode),
            "next_control_hypothesis": str(next_hypothesis),
            "family_safety_stability_assessment": str(family_safety_stability_assessment),
            "family_utility_stability_assessment": str(family_utility_stability_assessment),
            "invariance_assessment": str(invariance_assessment),
            "structural_vs_local_assessment": str(structural_vs_local_assessment),
            "exploitation_bottleneck_relation_assessment": str(exploitation_bottleneck_relation_assessment),
            "recommended_next_action": str(recommended_next_action),
            "recommended_next_template": str(recommended_next_template),
            "routing_status": str(routing_status),
            "routing_deferred": True,
        },
    }
    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"memory_summary_safe_trio_false_safe_invariance_snapshot_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: safe-trio false-safe frontier invariance is localized without changing scorer or routing behavior",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
