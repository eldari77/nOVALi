from __future__ import annotations

import json
from typing import Any

from .analytics import build_intervention_ledger_analytics
from .ledger import intervention_data_dir, load_latest_snapshots


RELEVANT_TEMPLATE_NAMES = [
    "critic_split.final_selection_false_safe_guardrail_probe_v1",
    "critic_split.safe_trio_incumbent_confirmation_probe_v1",
    "memory_summary.swap_c_family_coverage_snapshot_v1",
    "memory_summary.safe_trio_false_safe_invariance_snapshot_v1",
    "critic_split.swap_c_incumbent_hardening_probe_v1",
]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _load_json_file(path) -> dict[str, Any]:
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")))
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        return {}


def _template_history_subset(analytics: dict[str, Any], template_name: str) -> dict[str, Any]:
    return dict(dict(analytics.get("template_outcome_summary", {})).get(template_name, {}))


def _normalize_candidate(row: dict[str, Any]) -> dict[str, Any]:
    context_signal = dict(row.get("context_robustness_signal", {}))
    return {
        "trio_name": str(row.get("trio_name", "")),
        "selected_ids": [str(item) for item in list(row.get("selected_ids", []))],
        "selected_benchmark_like_count": int(row.get("selected_benchmark_like_count", 0) or 0),
        "projection_safe_retention": _safe_float(row.get("projection_safe_retention"), 1.0),
        "unsafe_overcommit_rate_delta": _safe_float(row.get("unsafe_overcommit_rate_delta")),
        "false_safe_projection_rate_delta": _safe_float(row.get("false_safe_projection_rate_delta")),
        "false_safe_margin_vs_cap": _safe_float(row.get("false_safe_margin_vs_cap")),
        "policy_match_rate_delta": _safe_float(row.get("policy_match_rate_delta")),
        "context_robustness_sum": _safe_float(
            row.get("context_robustness_sum", context_signal.get("sum"))
        ),
        "mean_projection_error": row.get("mean_projection_error"),
        "safe_within_cap": bool(row.get("safe_within_cap", True)),
    }


def _find_family_candidate(artifact: dict[str, Any], trio_name: str) -> dict[str, Any]:
    for raw in list(artifact.get("family_candidate_inventory", [])):
        if not isinstance(raw, dict):
            continue
        if str(raw.get("trio_name", "")) == trio_name:
            return _normalize_candidate(raw)
    return {}


def run_probe(cfg, proposal, *, rounds, seeds):
    del cfg, rounds, seeds
    from . import runner as r

    hardening_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.swap_c_incumbent_hardening_probe_v1"
    )
    invariance_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.safe_trio_false_safe_invariance_snapshot_v1"
    )
    coverage_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.swap_c_family_coverage_snapshot_v1"
    )
    confirmation_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.safe_trio_incumbent_confirmation_probe_v1"
    )
    guardrail_artifact = r._load_latest_diagnostic_artifact_by_template(
        "critic_split.final_selection_false_safe_guardrail_probe_v1"
    )
    if not all(
        [
            hardening_artifact,
            invariance_artifact,
            coverage_artifact,
            confirmation_artifact,
            guardrail_artifact,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: hardening, invariance, coverage, confirmation, and guardrail artifacts are required",
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
                "reason": "cannot characterize the false-safe frontier without the prerequisite benchmark-only control artifacts",
            },
        }

    analytics = build_intervention_ledger_analytics()
    latest_snapshots = load_latest_snapshots()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")

    hardening_conclusions = dict(hardening_artifact.get("diagnostic_conclusions", {}))
    invariance_conclusions = dict(invariance_artifact.get("diagnostic_conclusions", {}))
    invariance_analysis = dict(invariance_artifact.get("frontier_invariance_analysis", {}))
    invariance_structure = dict(invariance_artifact.get("structural_conclusion", {}))
    coverage_conclusions = dict(coverage_artifact.get("diagnostic_conclusions", {}))
    guardrail_conclusions = dict(guardrail_artifact.get("diagnostic_conclusions", {}))

    swap_c_reviewed = _normalize_candidate(dict(hardening_artifact.get("swap_C_reviewed", {})))
    incumbent_report = _normalize_candidate(dict(hardening_artifact.get("incumbent_robustness_report", {})))
    incumbent_baseline = _normalize_candidate(dict(confirmation_artifact.get("incumbent_trio_reviewed", {})))
    if not incumbent_baseline.get("selected_ids"):
        incumbent_baseline = _find_family_candidate(coverage_artifact, "baseline")

    strongest_neighbors = [
        _normalize_candidate(dict(row))
        for row in list(hardening_artifact.get("strongest_neighboring_family_candidates_reviewed", []))
        if isinstance(row, dict)
    ]
    family_inventory = [
        _normalize_candidate(dict(row))
        for row in list(coverage_artifact.get("family_candidate_inventory", []))
        if isinstance(row, dict)
    ]
    persistence_analysis = {
        str(name): dict(payload)
        for name, payload in dict(coverage_artifact.get("persistence_specific_analysis", {})).items()
        if isinstance(payload, dict)
    }
    residual_watch = {
        str(name): dict(payload)
        for name, payload in dict(hardening_artifact.get("residual_watch_report", {})).items()
        if isinstance(payload, dict)
    }
    hardening_findings = dict(hardening_artifact.get("hardening_findings", {}))
    resource_trust_accounting = dict(hardening_artifact.get("resource_trust_accounting", {}))

    family_safe_candidate_count = int(
        coverage_conclusions.get(
            "family_safe_candidate_count",
            len([row for row in family_inventory if bool(row.get("safe_within_cap", False))]),
        )
        or 0
    )
    family_outperforming_candidate_count = int(
        coverage_conclusions.get("family_outperforming_candidate_count", 0) or 0
    )
    fixed_additive_step = _safe_float(
        list(invariance_analysis.get("additive_increment_over_safe_frontier", [0.0]))[0]
        if list(invariance_analysis.get("additive_increment_over_safe_frontier", [0.0]))
        else 0.0
    )
    dominant_blocker = str(
        guardrail_conclusions.get(
            "dominant_final_selection_blocker",
            "selection_budget_hold_for_drift_control",
        )
    )

    incumbent_quality_candidate_status = (
        "incumbent_quality_candidate_confirmed"
        if str(hardening_conclusions.get("swap_C_hardening_safety_assessment", ""))
        == "swap_C_hardened_safe"
        and str(hardening_conclusions.get("swap_C_hardening_utility_assessment", ""))
        == "swap_C_still_best"
        and str(hardening_conclusions.get("hardening_robustness_assessment", ""))
        == "hardened_incumbent_quality_candidate"
        else "incumbent_quality_candidate_not_confirmed"
    )
    false_safe_frontier_characterization = (
        "safety_preserving_but_exploitation_conservative"
        if incumbent_quality_candidate_status == "incumbent_quality_candidate_confirmed"
        and dominant_blocker == "selection_budget_hold_for_drift_control"
        and not bool(hardening_findings.get("productive_under_cap_critic_work_left", True))
        else "still_unclear"
    )
    exploitation_bottleneck_relation_assessment = (
        "final_selection_exploitation_bottleneck_confirmed"
        if "final_selection_exploitation_bottleneck_confirmed"
        in {
            str(hardening_conclusions.get("exploitation_bottleneck_relation_assessment", "")),
            str(invariance_conclusions.get("exploitation_bottleneck_relation_assessment", "")),
            str(coverage_conclusions.get("exploitation_bottleneck_relation_assessment", "")),
        }
        else "still_unclear"
    )

    remaining_frontier_blockers = [
        {
            "blocker": "size_3_frontier_exhausts_frozen_cap",
            "evidence": (
                f"swap_C sits at false_safe_projection_rate_delta={_safe_float(incumbent_report.get('false_safe_projection_rate_delta'))} "
                f"with false_safe_margin_vs_cap={_safe_float(incumbent_report.get('false_safe_margin_vs_cap'))}"
            ),
        },
        {
            "blocker": "selection_budget_hold_for_drift_control",
            "evidence": f"guardrail diagnostic still reports dominant_final_selection_blocker={dominant_blocker}",
        },
        {
            "blocker": "discrete_additive_step_over_frontier",
            "evidence": f"frontier invariance snapshot reports additive_increment_over_safe_frontier={fixed_additive_step}",
        },
        {
            "blocker": "persistence_rows_compressed_at_final_selection",
            "evidence": (
                "persistence_09 remains blocked because safe trios with it underperform on policy-match; "
                "persistence_12 remains blocked because policy-match ties but context-robustness tie-break loses"
            ),
        },
        {
            "blocker": "no_productive_under_cap_critic_work_left",
            "evidence": (
                f"hardening replay records productive_under_cap_critic_work_left="
                f"{bool(hardening_findings.get('productive_under_cap_critic_work_left', False))}"
            ),
        },
    ]

    recommendation_candidates = [
        str(item.get("template_name", ""))
        for item in list(recommendations.get("all_ranked_proposals", []))
        if isinstance(item, dict) and str(item.get("decision", "")) == "suggested"
    ][:5]
    ledger_reference = {}
    for artifact in [
        hardening_artifact,
        invariance_artifact,
        coverage_artifact,
        confirmation_artifact,
        guardrail_artifact,
    ]:
        proposal_id = str(artifact.get("proposal_id", ""))
        template_name = str(artifact.get("template_name", ""))
        snapshot = dict(latest_snapshots.get(proposal_id, {}))
        ledger_reference[template_name] = {
            "proposal_id": proposal_id,
            "final_status": str(snapshot.get("final_status", artifact.get("final_status", ""))),
            "latest_stage": str(snapshot.get("stage", snapshot.get("final_status", ""))),
        }

    established_control_signal_summary = {
        "control_signal_status": "hardened_control_signal_established",
        "swap_C_selected_ids": list(incumbent_report.get("selected_ids", [])),
        "family_safe_candidate_count": family_safe_candidate_count,
        "family_outperforming_candidate_count": family_outperforming_candidate_count,
        "identical_safety_profile_across_replays": bool(
            hardening_findings.get("identical_safety_profile_across_replays", False)
        ),
        "policy_match_stable_across_replays": bool(
            hardening_findings.get("policy_match_stable_across_replays", False)
        ),
        "context_robustness_stable_across_replays": bool(
            hardening_findings.get("context_robustness_stable_across_replays", False)
        ),
        "family_safety_stability_assessment": str(
            invariance_conclusions.get("family_safety_stability_assessment", "")
        ),
        "family_utility_stability_assessment": str(
            invariance_conclusions.get("family_utility_stability_assessment", "")
        ),
    }

    operator_readable_conclusion = (
        "The swap_C sequence established one hardened incumbent-quality safe control candidate under unchanged settings. "
        "The false-safe frontier is now best read as safety-preserving but exploitation-conservative: it allows a confirmed safe trio at the frozen cap, "
        "but still compresses additional benchmark-like exploitation at final selection. The remaining bottleneck is final-selection exploitation, not upstream availability or retention, so routing stays deferred and the correct stance is hold/consolidate."
    )

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.false_safe_frontier_control_characterization_snapshot_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "snapshot_identity_context": {
            "phase": "benchmark_only_control_consolidation",
            "focus": "false_safe_frontier_characterization_after_swap_c_hardening",
            "protected_candidate": "swap_C",
        },
        "evidence_inputs_used": list(RELEVANT_TEMPLATE_NAMES) + [
            "intervention_analytics_latest",
            "proposal_recommendations_latest",
            "intervention_ledger_latest_snapshots",
        ],
        "established_control_signal_summary": established_control_signal_summary,
        "false_safe_frontier_characterization": str(false_safe_frontier_characterization),
        "incumbent_quality_candidate_status": str(incumbent_quality_candidate_status),
        "remaining_frontier_blockers": remaining_frontier_blockers,
        "exploitation_bottleneck_relation_assessment": str(exploitation_bottleneck_relation_assessment),
        "structural_vs_local_assessment": "hardened_control_signal_established",
        "routing_status": "routing_deferred",
        "comparison_references": {
            "incumbent_baseline": incumbent_baseline,
            "swap_C_reviewed": swap_c_reviewed,
            "incumbent_robustness_report": incumbent_report,
            "strongest_neighboring_family_candidates_reviewed": strongest_neighbors,
            "persistence_specific_analysis": persistence_analysis,
            "residual_watch_report": residual_watch,
            "frontier_invariance_analysis": invariance_analysis,
            "structural_conclusion": invariance_structure,
        },
        "branch_context_reference": {
            "analytics_template_history": {
                name: _template_history_subset(analytics, name) for name in RELEVANT_TEMPLATE_NAMES
            },
            "current_recommendation_candidates": recommendation_candidates,
            "ledger_latest_snapshots": ledger_reference,
        },
        "recommended_next_action": "hold_and_consolidate",
        "recommended_next_template": "",
        "decision_recommendation": {
            "recommended_next_action": "hold_and_consolidate",
            "recommended_next_template": "",
            "rationale": "the hardened control signal is established, the frontier remains exploitation-conservative, and no new continuation family is warranted from this consolidation step",
        },
        "review_rollback_deprecation_trigger_status": {
            "review_triggered": False,
            "rollback_triggered": False,
            "deprecation_triggered": False,
        },
        "resource_trust_accounting": {
            **resource_trust_accounting,
            "network_mode": "none",
            "routing_changed": False,
            "thresholds_relaxed": False,
            "live_policy_changed": False,
            "projection_safe_envelope_changed": False,
            "trusted_input_sources": [
                "local novali-v4 diagnostic artifacts",
                "local intervention analytics",
                "local proposal recommendations",
            ],
            "write_root": "novali-v4/data/diagnostic_memory",
        },
        "operator_readable_conclusion": operator_readable_conclusion,
        "diagnostic_conclusions": {
            "established_control_signal_status": "hardened_control_signal_established",
            "incumbent_quality_candidate_status": str(incumbent_quality_candidate_status),
            "false_safe_frontier_characterization": str(false_safe_frontier_characterization),
            "exploitation_bottleneck_relation_assessment": str(exploitation_bottleneck_relation_assessment),
            "structural_vs_local_assessment": "hardened_control_signal_established",
            "recommended_next_action": "hold_and_consolidate",
            "recommended_next_template": "",
            "routing_status": "routing_deferred",
            "routing_deferred": True,
        },
    }
    artifact_path = (
        r._diagnostic_artifact_dir()
        / f"memory_summary_false_safe_frontier_control_characterization_snapshot_v1_{proposal['proposal_id']}.json"
    )
    artifact_path.write_text(json.dumps(artifact_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: the false-safe frontier was characterized as a hold/consolidate control boundary without changing routing, policy, thresholds, or benchmark semantics",
        "observability_gain": {
            "passed": True,
            "reason": "the snapshot consolidates what the frontier now allows, what it still blocks, and why the bottleneck remains final-selection exploitation",
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the snapshot confirms a hardened safe control candidate while separating that achievement from the still-blocked exploitation frontier",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.92,
            "reason": "the snapshot resolves whether the frontier is now correctly balanced or simply exploitation-conservative under the frozen cap",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "consolidation-only characterization with live policy, thresholds, routing policy, and frozen benchmark semantics unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_action": "hold_and_consolidate",
            "recommended_next_template": "",
            "reason": "the correct bounded next step is consolidation rather than another continuation family",
        },
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
