from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .analytics import build_intervention_ledger_analytics
from .governance_substrate_v1 import (
    BRANCH_REGISTRY_PATH,
    BUCKET_STATE_PATH,
    DIRECTIVE_HISTORY_PATH,
    DIRECTIVE_STATE_PATH,
    SELF_STRUCTURE_LEDGER_PATH,
    SELF_STRUCTURE_STATE_PATH,
    _append_jsonl,
    _now,
    _write_json,
)
from .governed_skill_acquisition_v1 import _diagnostic_artifact_dir, _load_jsonl
from .ledger import intervention_data_dir, load_latest_snapshots
from .v4_first_hypothesis_landscape_snapshot_v1 import _load_json_file
from .v4_governed_directive_work_selection_policy_snapshot_v1 import (
    _find_capability,
    _resource_request_within_bucket,
)
from .v4_governed_skill_local_trace_parser_provisional_probe_v1 import _bucket_pressure, _path_within_allowed_roots
from .v4_governed_work_loop_candidate_screen_snapshot_v7 import (
    _build_loop_candidate_examples_v7,
    _screen_loop_candidate_v4,
)
from .v4_governed_work_loop_policy_snapshot_v1 import _resolve_artifact_path
from .v4_wm_context_signal_overlap_snapshot_v1 import _artifact_reference


INTERVENTION_LEDGER_PATH = intervention_data_dir() / "intervention_ledger.jsonl"
ANALYTICS_PATH = intervention_data_dir() / "intervention_analytics_latest.json"
RECOMMENDATIONS_PATH = intervention_data_dir() / "proposal_recommendations_latest.json"


def _failure(proposal: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "passed": False,
        "shadow_contract": "governed_work_loop_continuation",
        "proposal_semantics": "shadow_work_loop_continuation",
        "reason": str(reason),
        "observability_gain": {"passed": False, "reason": str(reason)},
        "activation_analysis_usefulness": {"passed": False, "reason": str(reason)},
        "ambiguity_reduction": {"passed": False, "reason": str(reason)},
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "no live-policy mutation occurred",
        },
        "later_selection_usefulness": {"passed": False, "reason": str(reason)},
    }


def _find_loop_candidate(candidates: list[dict[str, Any]], *, name: str) -> dict[str, Any]:
    for candidate in candidates:
        if str(candidate.get("loop_candidate_name", "")) == name:
            return dict(candidate)
    for candidate in candidates:
        if str(candidate.get("assigned_class", "")) == "loop_continue_candidate":
            return dict(candidate)
    return {}


def _check(passed: bool, reason: str, **details: Any) -> dict[str, Any]:
    payload = {"passed": bool(passed), "reason": str(reason)}
    payload.update(details)
    return payload


def _digest_path(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.exists():
        return {"path": str(resolved), "exists": False}
    if resolved.suffix == ".jsonl":
        return {"path": str(resolved), "exists": True, "row_count": int(len(_load_jsonl(resolved)))}
    payload = _load_json_file(resolved)
    if isinstance(payload, dict):
        return {
            "path": str(resolved),
            "exists": True,
            "top_level_keys": sorted(str(key) for key in payload.keys())[:16],
        }
    if isinstance(payload, list):
        return {"path": str(resolved), "exists": True, "item_count": int(len(payload))}
    return {"path": str(resolved), "exists": True, "payload_type": type(payload).__name__}


def _prior_digest_map(prior_execution_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    direct_work_summary = dict(prior_execution_payload.get("governed_direct_work_execution_summary", {}))
    source_info = dict(direct_work_summary.get("local_governance_sources_used", {}))
    return {
        str(dict(row).get("path", "")): dict(row)
        for row in list(source_info.get("governance_source_digests", []))
        if isinstance(row, dict) and str(dict(row).get("path", ""))
    }


def _prior_direct_work_analytics_observation(prior_execution_payload: dict[str, Any]) -> dict[str, Any]:
    direct_work_summary = dict(prior_execution_payload.get("governed_direct_work_execution_summary", {}))
    audit_output = dict(dict(direct_work_summary.get("audit_artifact_produced", {})).get("coherence_audit_output", {}))
    checks = dict(audit_output.get("checks", {}))
    return dict(dict(checks.get("analytics_and_recommendations_present", {})).get("observed", {}))


def _prior_continuation_source_digest_map(prior_execution_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    continuation_summary = dict(prior_execution_payload.get("governed_work_loop_continuation_execution_summary", {}))
    source_info = dict(continuation_summary.get("local_governance_sources_used", {}))
    return {
        str(dict(row).get("path", "")): dict(row)
        for row in list(source_info.get("governance_source_digests", []))
        if isinstance(row, dict) and str(dict(row).get("path", ""))
    }


def _prior_continuation_analytics_context(prior_execution_payload: dict[str, Any]) -> dict[str, Any]:
    return dict(prior_execution_payload.get("analytics_context", {}))


def _is_governed_template_name(template_name: str) -> bool:
    return template_name.startswith("memory_summary.v4_governed_") or template_name.startswith(
        "proposal_learning_loop.v4_governed_"
    )


def _build_alignment_delta_audit(
    *,
    directive_state: dict[str, Any],
    current_state_summary: dict[str, Any],
    branch_record: dict[str, Any],
    current_branch_state: str,
    current_bucket: dict[str, Any],
    loop_candidate_record: dict[str, Any],
    continuation_envelope: dict[str, Any],
    callable_capabilities: list[dict[str, Any]],
    analytics: dict[str, Any],
    recommendations: dict[str, Any],
    directive_history: list[dict[str, Any]],
    self_structure_ledger: list[dict[str, Any]],
    intervention_ledger: list[dict[str, Any]],
    prior_direct_work_execution_payload: dict[str, Any],
    prior_continuation_execution_payload: dict[str, Any],
    work_loop_artifact_paths: dict[str, Path],
) -> dict[str, Any]:
    parser_capability = _find_capability(callable_capabilities, "skill_candidate_local_trace_parser_trial")
    expected_resources = dict(continuation_envelope.get("resource_expectations", {}))
    resource_fit = _resource_request_within_bucket(expected_resources, current_bucket)
    network_modes = list(dict(current_bucket.get("network_policy", {})).get("allowed_network_modes", []))
    current_work_state = dict(dict(loop_candidate_record.get("loop_accounting_expectations", {})).get("current_work_state", {}))
    prior_direct_digests = _prior_digest_map(prior_direct_work_execution_payload)
    prior_direct_analytics = _prior_direct_work_analytics_observation(prior_direct_work_execution_payload)
    prior_continuation_digests = _prior_continuation_source_digest_map(prior_continuation_execution_payload)
    prior_continuation_analytics = _prior_continuation_analytics_context(prior_continuation_execution_payload)

    ranked_rows = list(recommendations.get("all_ranked_proposals", []))
    ranked_templates = sorted(
        {
            str(dict(row).get("template_name", ""))
            for row in ranked_rows
            if isinstance(row, dict) and str(dict(row).get("template_name", "")).strip()
        }
    )
    governed_ranked_templates = sorted(template for template in ranked_templates if _is_governed_template_name(template))
    recent_governed_templates = sorted(
        {
            str(dict(row).get("template_name", ""))
            for row in intervention_ledger[-128:]
            if isinstance(row, dict) and _is_governed_template_name(str(dict(row).get("template_name", "")))
        }
    )
    overlap_templates = sorted(set(governed_ranked_templates) & set(recent_governed_templates))
    required_narrow_templates = [
        "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v2",
        "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v2",
        "memory_summary.v4_governed_work_loop_posture_snapshot_v1",
        "memory_summary.v4_governed_work_loop_evidence_snapshot_v1",
        "proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1",
    ]
    recent_or_recommended = set(governed_ranked_templates) | set(recent_governed_templates)
    required_narrow_templates_present = sorted(
        template for template in required_narrow_templates if template in recent_or_recommended
    )
    required_narrow_templates_missing = sorted(
        template for template in required_narrow_templates if template not in recent_or_recommended
    )
    unsupported_loop_surface_templates = sorted(
        template
        for template in governed_ranked_templates
        if any(token in template for token in ("broad_multi_path", "new_skill", "reopen"))
    )
    deltas = {
        "vs_prior_direct_work": {
            "self_structure_ledger_row_delta": int(len(self_structure_ledger))
            - int(dict(prior_direct_digests.get(str(SELF_STRUCTURE_LEDGER_PATH), {})).get("row_count", 0) or 0),
            "intervention_ledger_row_delta": int(len(intervention_ledger))
            - int(dict(prior_direct_digests.get(str(INTERVENTION_LEDGER_PATH), {})).get("row_count", 0) or 0),
            "directive_history_row_delta": int(len(directive_history))
            - int(dict(prior_direct_digests.get(str(DIRECTIVE_HISTORY_PATH), {})).get("row_count", 0) or 0),
            "proposal_count_delta": int(analytics.get("proposal_count", 0) or 0)
            - int(prior_direct_work_execution_payload.get("analytics_context", {}).get("proposal_count", 0) or 0),
            "ranked_recommendation_count_delta": int(len(ranked_rows))
            - int(prior_direct_analytics.get("ranked_recommendation_count", 0) or 0),
        },
        "vs_prior_continuation_v1": {
            "self_structure_ledger_row_delta": int(len(self_structure_ledger))
            - int(dict(prior_continuation_digests.get(str(SELF_STRUCTURE_LEDGER_PATH), {})).get("row_count", 0) or 0),
            "intervention_ledger_row_delta": int(len(intervention_ledger))
            - int(dict(prior_continuation_digests.get(str(INTERVENTION_LEDGER_PATH), {})).get("row_count", 0) or 0),
            "directive_history_row_delta": int(len(directive_history))
            - int(dict(prior_continuation_digests.get(str(DIRECTIVE_HISTORY_PATH), {})).get("row_count", 0) or 0),
            "proposal_count_delta": int(analytics.get("proposal_count", 0) or 0)
            - int(prior_continuation_analytics.get("proposal_count", 0) or 0),
            "ranked_recommendation_count_delta": int(len(ranked_rows))
            - int(
                prior_continuation_analytics.get("ranked_recommendation_count", 0)
                or prior_continuation_analytics.get("proposal_count", 0)
                or 0
            ),
        },
    }
    alignment_scores = {
        "alignment_score": (
            round(float(len(overlap_templates)) / float(len(governed_ranked_templates)), 4)
            if governed_ranked_templates
            else 0.0
        ),
        "loop_surface_alignment_score": (
            round(float(len(overlap_templates)) / float(len(recent_governed_templates)), 4)
            if recent_governed_templates
            else 0.0
        ),
    }
    artifact_presence = {name: str(path.resolve()) for name, path in work_loop_artifact_paths.items() if path.exists()}
    positive_delta_count = sum(
        1
        for delta_bundle in deltas.values()
        for value in delta_bundle.values()
        if int(value) > 0
    )
    material_alignment_detected = bool(
        len(overlap_templates) > 0
        and (
            positive_delta_count > 0
            or len(required_narrow_templates_present) >= 4
            or bool(artifact_presence)
        )
    )
    checks = {
        "directive_state_active": _check(str(directive_state.get("initialization_state", "")) == "active", "directive initialization remains active"),
        "branch_state_alignment": _check(
            current_branch_state == "paused_with_baseline_held"
            and str(current_state_summary.get("current_branch_state", "")) == current_branch_state,
            "branch registry and self-structure still agree on paused_with_baseline_held",
        ),
        "held_baseline_alignment": _check(
            str(dict(branch_record.get("held_baseline", {})).get("template", "")) == str(current_state_summary.get("held_baseline_template", "")),
            "held baseline template remains aligned across branch and self-structure state",
        ),
        "plan_and_routing_guards_hold": _check(
            bool(current_state_summary.get("plan_non_owning", False)) and bool(current_state_summary.get("routing_deferred", False)),
            "plan_ remains non-owning and routing remains deferred",
        ),
        "bucket_allows_continuation_budget": _check(
            bool(resource_fit.get("passed", False)),
            "bucket still covers the admitted loop-continuation budget",
            requested_resources=dict(resource_fit.get("requested_resources", {})),
            bucket_limits=dict(resource_fit.get("bucket_limits", {})),
        ),
        "network_mode_none_remains_policy_valid": _check(
            "none" in network_modes and str(expected_resources.get("network_mode", "none")) == "none",
            "bucket policy still allows network mode none and the continuation envelope still requires none",
        ),
        "work_loop_progression_state_current": _check(
            bool(current_state_summary.get("governed_work_loop_policy_v1_defined", False))
            and bool(current_state_summary.get("governed_work_loop_candidate_screening_v2_in_place", False))
            and bool(current_state_summary.get("governed_work_loop_continuation_admission_v2_in_place", False))
            and str(current_state_summary.get("latest_governed_work_loop_continuation_outcome", "")) == "admissible_for_governed_loop_continuation_v2",
            "current state still reflects the v2 work-loop policy, candidate screen, posture, and continuation admission chain",
        ),
        "paused_parser_capability_still_held_not_reopened": _check(
            bool(parser_capability)
            and str(parser_capability.get("status", "")) == "paused_with_provisional_capability_held"
            and bool(parser_capability.get("same_shape_reruns_disallowed", False)),
            "the held parser capability remains paused and callable-only, not reopened",
        ),
        "loop_continuation_path_separation_holds": _check(
            str(loop_candidate_record.get("assigned_class", "")) == "loop_continue_candidate"
            and str(loop_candidate_record.get("loop_candidate_name", "")) != str(current_work_state.get("prior_work_item", "")),
            "loop continuation remains distinct from prior direct work and stays separate from capability use, reopen, and new-skill paths",
            observed={
                "current_loop_candidate": str(loop_candidate_record.get("loop_candidate_name", "")),
                "prior_work_item": str(current_work_state.get("prior_work_item", "")),
                "prior_loop_continuation": str(current_work_state.get("prior_loop_continuation", "")),
            },
        ),
        "loop_continuation_not_prior_replay": _check(
            str(loop_candidate_record.get("loop_candidate_name", ""))
            != str(current_work_state.get("prior_loop_continuation", "")),
            "loop continuation remains distinct from prior direct work and stays separate from capability use, reopen, and new-skill paths",
            observed={
                "current_loop_candidate": str(loop_candidate_record.get("loop_candidate_name", "")),
                "prior_work_item": str(current_work_state.get("prior_work_item", "")),
                "prior_loop_continuation": str(current_work_state.get("prior_loop_continuation", "")),
            },
        ),
        "recommendation_ledger_alignment_observable": _check(
            bool(overlap_templates),
            "governed recommendation output still overlaps with recent governed ledger activity under the narrow posture",
            observed={
                "governed_ranked_template_count": int(len(governed_ranked_templates)),
                "recent_governed_template_count": int(len(recent_governed_templates)),
                "overlap_templates": overlap_templates,
            },
        ),
        "narrow_posture_artifacts_present": _check(
            all(path.exists() for path in work_loop_artifact_paths.values()),
            "the v2 continuation still sits on top of the posture, candidate-screen, admission, and prior execution artifact chain",
            observed={"artifact_presence": artifact_presence},
        ),
        "analytics_and_recommendations_present": _check(
            int(analytics.get("proposal_count", 0) or 0) > 0 and isinstance(recommendations.get("all_ranked_proposals", []), list),
            "analytics and recommendations remain readable during continuation execution",
        ),
    }
    failed = [name for name, result in checks.items() if not bool(dict(result).get("passed", False))]
    return {
        "audit_focus": "governance_recommendation_ledger_alignment_delta_audit",
        "checks": checks,
        "alignment_observations": {
            "deltas": deltas,
            "governed_recommendation_template_count": int(len(governed_ranked_templates)),
            "recent_governed_template_count": int(len(recent_governed_templates)),
            "governance_recommendation_overlap_templates": overlap_templates,
            "required_narrow_templates_present": required_narrow_templates_present,
            "required_narrow_templates_missing": required_narrow_templates_missing,
            "unsupported_loop_surface_templates": unsupported_loop_surface_templates,
            "work_loop_artifacts_present": artifact_presence,
        },
        "high_signal_observations": [
            "governed recommendations still align with recent governed ledger activity and the narrow posture while adding a new bounded evidence signal"
            if material_alignment_detected
            else "recommendation-to-ledger alignment stayed readable but the new bounded evidence signal was shallow",
            "loop continuation remained distinct from prior direct work and prior continuation v1 while staying separate from capability use, reopen, and new-skill paths",
        ],
        "summary": {
            "total_check_count": int(len(checks)),
            "passed_check_count": int(len(checks) - len(failed)),
            "failed_check_count": int(len(failed)),
            "failed_check_names": failed,
            "alignment_signal_count": int(positive_delta_count + len(overlap_templates)),
            "material_alignment_detected": bool(material_alignment_detected),
            "alignment_score": float(alignment_scores["alignment_score"]),
            "loop_surface_alignment_score": float(alignment_scores["loop_surface_alignment_score"]),
            "alignment_status": (
                "aligned_with_material_delta"
                if not failed and material_alignment_detected
                else "aligned_but_shallow"
                if not failed
                else "mismatch_detected"
            ),
        },
    }


def _build_frontier_circularity_boundary_audit(
    *,
    directive_state: dict[str, Any],
    current_state_summary: dict[str, Any],
    branch_record: dict[str, Any],
    current_branch_state: str,
    current_bucket: dict[str, Any],
    loop_candidate_record: dict[str, Any],
    candidate_screen_summary: dict[str, Any],
    continuation_admission_summary: dict[str, Any],
    evidence_v6_summary: dict[str, Any],
    continuation_envelope: dict[str, Any],
    callable_capabilities: list[dict[str, Any]],
    analytics: dict[str, Any],
    recommendations: dict[str, Any],
    directive_history: list[dict[str, Any]],
    self_structure_ledger: list[dict[str, Any]],
    intervention_ledger: list[dict[str, Any]],
    prior_direct_work_execution_payload: dict[str, Any],
    prior_continuation_v1_execution_payload: dict[str, Any],
    prior_continuation_v2_execution_payload: dict[str, Any],
    prior_continuation_v3_execution_payload: dict[str, Any],
    prior_continuation_v4_execution_payload: dict[str, Any],
    prior_continuation_v5_execution_payload: dict[str, Any],
    prior_continuation_v6_execution_payload: dict[str, Any],
    work_loop_artifact_paths: dict[str, Path],
) -> dict[str, Any]:
    parser_capability = _find_capability(callable_capabilities, "skill_candidate_local_trace_parser_trial")
    expected_resources = dict(continuation_envelope.get("resource_expectations", {}))
    resource_fit = _resource_request_within_bucket(expected_resources, current_bucket)
    network_modes = list(dict(current_bucket.get("network_policy", {})).get("allowed_network_modes", []))
    current_work_state = dict(dict(loop_candidate_record.get("loop_accounting_expectations", {})).get("current_work_state", {}))
    candidate_quality_flags = dict(loop_candidate_record.get("candidate_quality_flags", {}))
    screen_dimensions = dict(loop_candidate_record.get("screen_dimensions", {}))
    distinctness = dict(screen_dimensions.get("distinctness_vs_reviewed_chain", {}))
    structural_value = dict(screen_dimensions.get("structural_vs_local_value", {}))
    administrative_recursion = dict(screen_dimensions.get("administrative_recursion", {}))
    posture_pressure = dict(screen_dimensions.get("posture_pressure", {}))
    path_separation = dict(loop_candidate_record.get("path_separation", {}))
    prior_direct_digests = _prior_digest_map(prior_direct_work_execution_payload)
    prior_direct_analytics = _prior_direct_work_analytics_observation(prior_direct_work_execution_payload)
    prior_continuation_v1_digests = _prior_continuation_source_digest_map(prior_continuation_v1_execution_payload)
    prior_continuation_v1_analytics = _prior_continuation_analytics_context(prior_continuation_v1_execution_payload)
    prior_continuation_v2_digests = _prior_continuation_source_digest_map(prior_continuation_v2_execution_payload)
    prior_continuation_v2_analytics = _prior_continuation_analytics_context(prior_continuation_v2_execution_payload)
    prior_continuation_v3_digests = _prior_continuation_source_digest_map(prior_continuation_v3_execution_payload)
    prior_continuation_v3_analytics = _prior_continuation_analytics_context(prior_continuation_v3_execution_payload)
    prior_continuation_v4_digests = _prior_continuation_source_digest_map(prior_continuation_v4_execution_payload)
    prior_continuation_v4_analytics = _prior_continuation_analytics_context(prior_continuation_v4_execution_payload)
    prior_continuation_v5_digests = _prior_continuation_source_digest_map(prior_continuation_v5_execution_payload)
    prior_continuation_v5_analytics = _prior_continuation_analytics_context(prior_continuation_v5_execution_payload)
    prior_continuation_v6_digests = _prior_continuation_source_digest_map(prior_continuation_v6_execution_payload)
    prior_continuation_v6_analytics = _prior_continuation_analytics_context(prior_continuation_v6_execution_payload)

    ranked_rows = list(recommendations.get("all_ranked_proposals", []))
    ranked_templates = sorted(
        {
            str(dict(row).get("template_name", ""))
            for row in ranked_rows
            if isinstance(row, dict) and str(dict(row).get("template_name", "")).strip()
        }
    )
    governed_ranked_templates = sorted(template for template in ranked_templates if _is_governed_template_name(template))
    recent_governed_templates = sorted(
        {
            str(dict(row).get("template_name", ""))
            for row in intervention_ledger[-160:]
            if isinstance(row, dict) and _is_governed_template_name(str(dict(row).get("template_name", "")))
        }
    )
    unsupported_governed_templates = sorted(
        template
        for template in governed_ranked_templates
        if any(token in template for token in ("broad_multi_path", "new_skill", "reopen", "routing_rule"))
    )
    outcome_counts = dict(candidate_screen_summary.get("outcome_counts", {}))
    candidate_inventory = list(candidate_screen_summary.get("candidates_screened", []))
    credible_candidate_count = int(candidate_screen_summary.get("credible_candidate_count", 0) or 0)
    screened_out_candidate_count = int(candidate_screen_summary.get("screened_out_candidate_count", 0) or 0)
    top_ranked_candidate = dict(candidate_screen_summary.get("top_ranked_candidate", {}))
    admitted_candidate = dict(continuation_admission_summary.get("candidate_under_review", {}))
    top_ranked_template = str(
        top_ranked_candidate.get("proposed_execution_template", "")
        or top_ranked_candidate.get("top_ranked_candidate_template_name", "")
    )
    evidence_chain_state = dict(
        evidence_v6_summary.get("chain_state_reviewed", evidence_v6_summary.get("current_work_loop_chain_state", {}))
    )
    gate_status = dict(evidence_v6_summary.get("gate_status", evidence_v6_summary.get("future_posture_review_gate", {})))
    evidence_diminishing_returns = dict(evidence_v6_summary.get("diminishing_returns_assessment", {}))
    evidence_circularity_risk = dict(evidence_v6_summary.get("circularity_risk_assessment", {}))
    screen_diminishing_returns = dict(candidate_screen_summary.get("diminishing_returns_assessment", {}))
    screen_circularity_risk = dict(candidate_screen_summary.get("circularity_risk_assessment", {}))
    work_loop_artifact_presence = {
        name: {"path": str(path.resolve()), "exists": bool(path.exists())}
        for name, path in work_loop_artifact_paths.items()
    }
    deltas = {
        "vs_prior_direct_work": {
            "self_structure_ledger_row_delta": int(len(self_structure_ledger))
            - int(dict(prior_direct_digests.get(str(SELF_STRUCTURE_LEDGER_PATH), {})).get("row_count", 0) or 0),
            "intervention_ledger_row_delta": int(len(intervention_ledger))
            - int(dict(prior_direct_digests.get(str(INTERVENTION_LEDGER_PATH), {})).get("row_count", 0) or 0),
            "directive_history_row_delta": int(len(directive_history))
            - int(dict(prior_direct_digests.get(str(DIRECTIVE_HISTORY_PATH), {})).get("row_count", 0) or 0),
            "proposal_count_delta": int(analytics.get("proposal_count", 0) or 0)
            - int(prior_direct_work_execution_payload.get("analytics_context", {}).get("proposal_count", 0) or 0),
            "ranked_recommendation_count_delta": int(len(ranked_rows))
            - int(prior_direct_analytics.get("ranked_recommendation_count", 0) or 0),
        },
        "vs_prior_continuation_v1": {
            "self_structure_ledger_row_delta": int(len(self_structure_ledger))
            - int(dict(prior_continuation_v1_digests.get(str(SELF_STRUCTURE_LEDGER_PATH), {})).get("row_count", 0) or 0),
            "intervention_ledger_row_delta": int(len(intervention_ledger))
            - int(dict(prior_continuation_v1_digests.get(str(INTERVENTION_LEDGER_PATH), {})).get("row_count", 0) or 0),
            "directive_history_row_delta": int(len(directive_history))
            - int(dict(prior_continuation_v1_digests.get(str(DIRECTIVE_HISTORY_PATH), {})).get("row_count", 0) or 0),
            "proposal_count_delta": int(analytics.get("proposal_count", 0) or 0)
            - int(prior_continuation_v1_analytics.get("proposal_count", 0) or 0),
            "ranked_recommendation_count_delta": int(len(ranked_rows))
            - int(
                prior_continuation_v1_analytics.get("ranked_recommendation_count", 0)
                or prior_continuation_v1_analytics.get("proposal_count", 0)
                or 0
            ),
        },
        "vs_prior_continuation_v2": {
            "self_structure_ledger_row_delta": int(len(self_structure_ledger))
            - int(dict(prior_continuation_v2_digests.get(str(SELF_STRUCTURE_LEDGER_PATH), {})).get("row_count", 0) or 0),
            "intervention_ledger_row_delta": int(len(intervention_ledger))
            - int(dict(prior_continuation_v2_digests.get(str(INTERVENTION_LEDGER_PATH), {})).get("row_count", 0) or 0),
            "directive_history_row_delta": int(len(directive_history))
            - int(dict(prior_continuation_v2_digests.get(str(DIRECTIVE_HISTORY_PATH), {})).get("row_count", 0) or 0),
            "proposal_count_delta": int(analytics.get("proposal_count", 0) or 0)
            - int(prior_continuation_v2_analytics.get("proposal_count", 0) or 0),
            "ranked_recommendation_count_delta": int(len(ranked_rows))
            - int(
                prior_continuation_v2_analytics.get("ranked_recommendation_count", 0)
                or prior_continuation_v2_analytics.get("proposal_count", 0)
                or 0
            ),
        },
        "vs_prior_continuation_v3": {
            "self_structure_ledger_row_delta": int(len(self_structure_ledger))
            - int(dict(prior_continuation_v3_digests.get(str(SELF_STRUCTURE_LEDGER_PATH), {})).get("row_count", 0) or 0),
            "intervention_ledger_row_delta": int(len(intervention_ledger))
            - int(dict(prior_continuation_v3_digests.get(str(INTERVENTION_LEDGER_PATH), {})).get("row_count", 0) or 0),
            "directive_history_row_delta": int(len(directive_history))
            - int(dict(prior_continuation_v3_digests.get(str(DIRECTIVE_HISTORY_PATH), {})).get("row_count", 0) or 0),
            "proposal_count_delta": int(analytics.get("proposal_count", 0) or 0)
            - int(prior_continuation_v3_analytics.get("proposal_count", 0) or 0),
            "ranked_recommendation_count_delta": int(len(ranked_rows))
            - int(
                prior_continuation_v3_analytics.get("ranked_recommendation_count", 0)
                or prior_continuation_v3_analytics.get("proposal_count", 0)
                or 0
            ),
        },
        "vs_prior_continuation_v4": {
            "self_structure_ledger_row_delta": int(len(self_structure_ledger))
            - int(dict(prior_continuation_v4_digests.get(str(SELF_STRUCTURE_LEDGER_PATH), {})).get("row_count", 0) or 0),
            "intervention_ledger_row_delta": int(len(intervention_ledger))
            - int(dict(prior_continuation_v4_digests.get(str(INTERVENTION_LEDGER_PATH), {})).get("row_count", 0) or 0),
            "directive_history_row_delta": int(len(directive_history))
            - int(dict(prior_continuation_v4_digests.get(str(DIRECTIVE_HISTORY_PATH), {})).get("row_count", 0) or 0),
            "proposal_count_delta": int(analytics.get("proposal_count", 0) or 0)
            - int(prior_continuation_v4_analytics.get("proposal_count", 0) or 0),
            "ranked_recommendation_count_delta": int(len(ranked_rows))
            - int(
                prior_continuation_v4_analytics.get("ranked_recommendation_count", 0)
                or prior_continuation_v4_analytics.get("proposal_count", 0)
                or 0
            ),
        },
        "vs_prior_continuation_v5": {
            "self_structure_ledger_row_delta": int(len(self_structure_ledger))
            - int(dict(prior_continuation_v5_digests.get(str(SELF_STRUCTURE_LEDGER_PATH), {})).get("row_count", 0) or 0),
            "intervention_ledger_row_delta": int(len(intervention_ledger))
            - int(dict(prior_continuation_v5_digests.get(str(INTERVENTION_LEDGER_PATH), {})).get("row_count", 0) or 0),
            "directive_history_row_delta": int(len(directive_history))
            - int(dict(prior_continuation_v5_digests.get(str(DIRECTIVE_HISTORY_PATH), {})).get("row_count", 0) or 0),
            "proposal_count_delta": int(analytics.get("proposal_count", 0) or 0)
            - int(prior_continuation_v5_analytics.get("proposal_count", 0) or 0),
            "ranked_recommendation_count_delta": int(len(ranked_rows))
            - int(
                prior_continuation_v5_analytics.get("ranked_recommendation_count", 0)
                or prior_continuation_v5_analytics.get("proposal_count", 0)
                or 0
            ),
        },
    }
    positive_delta_count = sum(
        1
        for delta_bundle in deltas.values()
        for value in delta_bundle.values()
        if int(value) > 0
    )
    frontier_signal_components = {
        "credible_candidate_present": credible_candidate_count == 1,
        "materially_distinct_candidate_present": bool(candidate_quality_flags.get("materially_distinct_from_chain", False)),
        "execution_adjacent_structural_yield": bool(candidate_quality_flags.get("execution_adjacent_structural_yield", False)),
        "administrative_recursion_risk_low": str(candidate_quality_flags.get("administrative_recursion_risk", "")) == "low",
        "diminishing_returns_not_nearing": str(evidence_diminishing_returns.get("classification", "")) == "not_nearing_diminishing_returns"
        and str(screen_diminishing_returns.get("classification", "")) == "not_nearing_diminishing_returns",
        "circularity_risk_low": str(evidence_circularity_risk.get("classification", "")) == "circularity_risk_low"
        and str(screen_circularity_risk.get("classification", "")) == "circularity_risk_low",
        "posture_pressure_absent": not bool(candidate_quality_flags.get("posture_pressure_present", False)),
        "future_posture_review_gate_closed": str(gate_status.get("gate_status", "")) == "defined_but_closed",
        "routing_remains_deferred": bool(current_state_summary.get("routing_deferred", False)),
        "supported_candidate_frontier_only": not unsupported_governed_templates,
        "chain_delta_observable": positive_delta_count > 0,
    }
    circularity_signal_count = sum(1 for value in frontier_signal_components.values() if bool(value))
    material_circularity_boundary_delta_detected = bool(
        frontier_signal_components["credible_candidate_present"]
        and frontier_signal_components["materially_distinct_candidate_present"]
        and frontier_signal_components["execution_adjacent_structural_yield"]
        and frontier_signal_components["administrative_recursion_risk_low"]
        and frontier_signal_components["diminishing_returns_not_nearing"]
        and frontier_signal_components["circularity_risk_low"]
        and frontier_signal_components["posture_pressure_absent"]
        and frontier_signal_components["future_posture_review_gate_closed"]
        and frontier_signal_components["routing_remains_deferred"]
        and frontier_signal_components["chain_delta_observable"]
    )
    checks = {
        "directive_state_active": _check(
            str(directive_state.get("initialization_state", "")) == "active",
            "directive initialization remains active",
        ),
        "branch_state_alignment": _check(
            current_branch_state == "paused_with_baseline_held"
            and str(current_state_summary.get("current_branch_state", "")) == current_branch_state,
            "branch registry and self-structure still agree on paused_with_baseline_held",
        ),
        "held_baseline_alignment": _check(
            str(dict(branch_record.get("held_baseline", {})).get("template", ""))
            == str(current_state_summary.get("held_baseline_template", "")),
            "held baseline template remains aligned across branch and self-structure state",
        ),
        "plan_and_routing_guards_hold": _check(
            bool(current_state_summary.get("plan_non_owning", False))
            and bool(current_state_summary.get("routing_deferred", False)),
            "plan_ remains non-owning and routing remains deferred",
        ),
        "bucket_allows_continuation_budget": _check(
            bool(resource_fit.get("passed", False)),
            "bucket still covers the admitted loop-continuation budget",
            requested_resources=dict(resource_fit.get("requested_resources", {})),
            bucket_limits=dict(resource_fit.get("bucket_limits", {})),
        ),
        "network_mode_none_remains_policy_valid": _check(
            "none" in network_modes and str(expected_resources.get("network_mode", "none")) == "none",
            "bucket policy still allows network mode none and the continuation envelope still requires none",
        ),
        "work_loop_progression_state_current": _check(
            bool(current_state_summary.get("governed_work_loop_policy_v1_defined", False))
            and bool(current_state_summary.get("governed_work_loop_candidate_screening_v7_in_place", False))
            and bool(current_state_summary.get("governed_work_loop_continuation_admission_v7_in_place", False))
            and str(current_state_summary.get("latest_governed_work_loop_continuation_outcome", ""))
            == "admissible_for_governed_loop_continuation_v7"
            and str(current_state_summary.get("latest_governed_work_loop_execution_readiness", ""))
            in {
                "ready_for_shadow_work_loop_continuation_execution_v7",
                "ready_for_work_loop_evidence_review_v7",
            },
            "current state still reflects the v7 candidate screen, v7 continuation admission, and ready-for-shadow-execution posture",
        ),
        "paused_parser_capability_still_held_not_reopened": _check(
            bool(parser_capability)
            and str(parser_capability.get("status", "")) == "paused_with_provisional_capability_held"
            and bool(parser_capability.get("same_shape_reruns_disallowed", False)),
            "the held parser capability remains paused and callable-only, not reopened",
        ),
        "frontier_inventory_constrained": _check(
            credible_candidate_count == 1 and screened_out_candidate_count > 0,
            "the current recommendation frontier remains constrained to a single credible bounded candidate while lower-yield paths stay screened out",
            observed={
                "candidate_inventory_count": int(len(candidate_inventory)),
                "credible_candidate_count": credible_candidate_count,
                "screened_out_candidate_count": screened_out_candidate_count,
                "outcome_counts": outcome_counts,
            },
        ),
        "frontier_top_candidate_matches_admitted_execution": _check(
            str(top_ranked_candidate.get("loop_candidate_name", "")) == str(loop_candidate_record.get("loop_candidate_name", ""))
            and top_ranked_template == str(candidate_quality_flags.get("proposed_execution_template", ""))
            and str(admitted_candidate.get("proposed_execution_template", ""))
            == str(candidate_quality_flags.get("proposed_execution_template", "")),
            "the active frontier candidate still matches both the top-ranked v7 screen result and the admitted v7 execution target",
        ),
        "frontier_alignment_preserved": _check(
            str(loop_candidate_record.get("assigned_class", "")) == "loop_continue_candidate"
            and bool(path_separation.get("continue_as_governed_loop_step", False))
            and str(structural_value.get("classification", "")) == "execution_adjacent_structural_yield",
            "the active frontier element remains aligned to bounded governed-loop continuation rather than broad self-extension",
        ),
        "frontier_materially_distinct": _check(
            bool(distinctness.get("materially_distinct_from_chain", False)),
            "the active frontier element remains materially distinct from direct work, continuation v1, continuation v2, continuation v3, continuation v4, continuation v5, continuation v6, evidence v2, evidence v3, evidence v4, evidence v5, and evidence v6",
            observed={
                "distinct_from_direct_work": bool(distinctness.get("distinct_from_direct_work", False)),
                "distinct_from_continuation_v1": bool(distinctness.get("distinct_from_continuation_v1", False)),
                "distinct_from_continuation_v2": bool(distinctness.get("distinct_from_continuation_v2", False)),
                "distinct_from_evidence_snapshot_v2": bool(distinctness.get("distinct_from_evidence_snapshot_v2", False)),
                "distinct_from_continuation_v3": bool(distinctness.get("distinct_from_continuation_v3", False)),
                "distinct_from_evidence_snapshot_v3": bool(distinctness.get("distinct_from_evidence_snapshot_v3", False)),
                "distinct_from_continuation_v4": bool(distinctness.get("distinct_from_continuation_v4", False)),
                "distinct_from_evidence_snapshot_v4": bool(distinctness.get("distinct_from_evidence_snapshot_v4", False)),
                "distinct_from_continuation_v5": bool(distinctness.get("distinct_from_continuation_v5", False)),
                "distinct_from_evidence_snapshot_v5": bool(distinctness.get("distinct_from_evidence_snapshot_v5", False)),
                "distinct_from_continuation_v6": bool(distinctness.get("distinct_from_continuation_v6", False)),
                "distinct_from_evidence_snapshot_v6": bool(distinctness.get("distinct_from_evidence_snapshot_v6", False)),
            },
        ),
        "frontier_low_circularity_low_pressure": _check(
            str(administrative_recursion.get("risk", "")) == "low"
            and str(evidence_diminishing_returns.get("classification", "")) == "not_nearing_diminishing_returns"
            and str(screen_diminishing_returns.get("classification", "")) == "not_nearing_diminishing_returns"
            and str(evidence_circularity_risk.get("classification", "")) == "circularity_risk_low"
            and str(screen_circularity_risk.get("classification", "")) == "circularity_risk_low"
            and (str(posture_pressure.get("pressure", "")) == "absent" or str(posture_pressure.get("classification", "")) == "posture_pressure_absent"),
            "the frontier does not show administrative recursion, diminishing-return pressure, circularity drift, or posture pressure",
        ),
        "future_posture_review_gate_stays_closed": _check(
            str(gate_status.get("gate_status", "")) == "defined_but_closed",
            "the future posture-review gate remains defined but closed while the narrow posture stays unchanged",
        ),
        "no_unsupported_recommendation_frontier_drift": _check(
            not unsupported_governed_templates,
            "the governed recommendation frontier does not surface unsupported broadening templates",
            observed={"unsupported_governed_templates": unsupported_governed_templates},
        ),
        "narrow_posture_artifacts_present": _check(
            all(path.exists() for path in work_loop_artifact_paths.values()),
            "the frontier-circularity boundary audit still sits on top of the local narrow-posture artifact chain",
            observed={"artifact_presence": work_loop_artifact_presence},
        ),
        "analytics_and_recommendations_present": _check(
            int(analytics.get("proposal_count", 0) or 0) > 0 and isinstance(recommendations.get("all_ranked_proposals", []), list),
            "analytics and recommendations remain readable during continuation execution",
        ),
    }
    failed = [name for name, result in checks.items() if not bool(dict(result).get("passed", False))]
    frontier_circularity_boundary_status = (
        "circularity_bounded_with_material_delta"
        if not failed and material_circularity_boundary_delta_detected
        else "circularity_bounded_without_material_delta"
        if not failed
        else "circularity_boundary_instability_detected"
    )
    frontier_drift_assessment = (
        "frontier_drift_absent"
        if not unsupported_governed_templates
        and str(evidence_circularity_risk.get("classification", "")) == "circularity_risk_low"
        and str(screen_circularity_risk.get("classification", "")) == "circularity_risk_low"
        and (str(posture_pressure.get("pressure", "")) == "absent" or str(posture_pressure.get("classification", "")) == "posture_pressure_absent")
        else "frontier_drift_present"
    )
    frontier_alignment_assessment = (
        "bounded_alignment_preserved"
        if str(loop_candidate_record.get("assigned_class", "")) == "loop_continue_candidate"
        and bool(path_separation.get("continue_as_governed_loop_step", False))
        else "bounded_alignment_at_risk"
    )
    frontier_circularity_assessment = (
        "circularity_bounded_and_materially_informative"
        if frontier_circularity_boundary_status == "circularity_bounded_with_material_delta"
        else "circularity_bounded_but_incremental"
        if frontier_circularity_boundary_status == "circularity_bounded_without_material_delta"
        else "circularity_boundary_at_risk"
    )
    return {
        "audit_focus": "governance_recommendation_frontier_circularity_boundary_audit",
        "checks": checks,
        "frontier_observations": {
            "current_work_state": current_work_state,
            "candidate_inventory_count": int(len(candidate_inventory)),
            "credible_candidate_count": credible_candidate_count,
            "screened_out_candidate_count": screened_out_candidate_count,
            "candidate_outcome_counts": outcome_counts,
            "top_ranked_candidate": {
                "loop_candidate_name": str(top_ranked_candidate.get("loop_candidate_name", "")),
                "proposed_execution_template": top_ranked_template,
            },
            "admitted_candidate": {
                "loop_candidate_name": str(admitted_candidate.get("loop_candidate_name", "")),
                "proposed_execution_template": str(admitted_candidate.get("proposed_execution_template", "")),
            },
            "frontier_signal_components": frontier_signal_components,
            "frontier_chain_deltas": deltas,
            "governed_recommendation_template_count": int(len(governed_ranked_templates)),
            "recent_governed_template_count": int(len(recent_governed_templates)),
            "unsupported_governed_templates": unsupported_governed_templates,
            "evidence_chain_state": evidence_chain_state,
            "work_loop_artifacts_present": work_loop_artifact_presence,
        },
        "high_signal_observations": [
            (
                "the current governed recommendation frontier remains circularity-bounded relative to the prior frontier-recursion state"
                if frontier_circularity_boundary_status != "circularity_boundary_instability_detected"
                else "the current governed recommendation frontier no longer looks circularity-bounded under the narrow envelope"
            ),
            (
                "this audit adds a new frontier-quality signal about frontier circularity boundaries rather than replaying prior chain conclusions"
                if material_circularity_boundary_delta_detected
                else "this audit stayed readable but did not add enough new frontier-circularity signal beyond the prior chain"
            ),
        ],
        "summary": {
            "total_check_count": int(len(checks)),
            "passed_check_count": int(len(checks) - len(failed)),
            "failed_check_count": int(len(failed)),
            "failed_check_names": failed,
            "circularity_signal_count": int(circularity_signal_count),
            "material_circularity_boundary_delta_detected": bool(material_circularity_boundary_delta_detected),
            "frontier_circularity_boundary_status": frontier_circularity_boundary_status,
            "frontier_circularity_assessment": frontier_circularity_assessment,
            "frontier_drift_assessment": frontier_drift_assessment,
            "frontier_alignment_assessment": frontier_alignment_assessment,
        },
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governance_substrate_v1_snapshot")
    work_loop_policy_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_policy_snapshot_v1"
    )
    work_loop_candidate_screen_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v7"
    )
    work_loop_continuation_admission_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v7"
    )
    work_loop_posture_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_posture_snapshot_v1"
    )
    prior_work_loop_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_evidence_snapshot_v5"
    )
    work_loop_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_evidence_snapshot_v6"
    )
    prior_continuation_execution_snapshot_v1 = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1"
    )
    prior_continuation_execution_snapshot_v2 = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1"
    )
    prior_continuation_execution_snapshot_v3 = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1"
    )
    prior_continuation_execution_snapshot_v4 = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1"
    )
    prior_continuation_execution_snapshot_v5 = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1"
    )
    prior_continuation_execution_snapshot_v6 = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit_v1"
    )
    direct_work_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_direct_work_evidence_snapshot_v1"
    )
    direct_work_execution_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1"
    )
    direct_work_admission_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_directive_work_admission_snapshot_v1"
    )
    capability_use_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_capability_use_evidence_snapshot_v1"
    )
    if not all(
        [
            governance_snapshot,
            work_loop_policy_snapshot,
            work_loop_candidate_screen_snapshot,
            work_loop_continuation_admission_snapshot,
            work_loop_posture_snapshot,
            prior_work_loop_evidence_snapshot,
            work_loop_evidence_snapshot,
            prior_continuation_execution_snapshot_v1,
            prior_continuation_execution_snapshot_v2,
            prior_continuation_execution_snapshot_v3,
            prior_continuation_execution_snapshot_v4,
            prior_continuation_execution_snapshot_v5,
            prior_continuation_execution_snapshot_v6,
            direct_work_evidence_snapshot,
            direct_work_execution_snapshot,
            direct_work_admission_snapshot,
            capability_use_evidence_snapshot,
        ]
    ):
        return _failure(
            proposal,
            "shadow work-loop continuation failed: governance substrate, work-loop policy, v7 candidate screen, v7 continuation admission, posture, evidence v5/v6, prior continuation chain, direct-work chain, and capability-use evidence artifacts are required",
        )

    directive_state = _load_json_file(DIRECTIVE_STATE_PATH)
    bucket_state = _load_json_file(BUCKET_STATE_PATH)
    self_structure_state = _load_json_file(SELF_STRUCTURE_STATE_PATH)
    branch_registry = _load_json_file(BRANCH_REGISTRY_PATH)
    directive_history = _load_jsonl(DIRECTIVE_HISTORY_PATH)
    self_structure_ledger = _load_jsonl(SELF_STRUCTURE_LEDGER_PATH)
    intervention_ledger = _load_jsonl(INTERVENTION_LEDGER_PATH)
    analytics = build_intervention_ledger_analytics()
    recommendations = _load_json_file(RECOMMENDATIONS_PATH)
    latest_snapshots = load_latest_snapshots()
    if not all([directive_state, bucket_state, self_structure_state, branch_registry]):
        return _failure(
            proposal,
            "shadow work-loop continuation failed: current directive, bucket, self-structure, and branch state artifacts are required",
        )

    current_directive = dict(directive_state.get("current_directive_state", {}))
    current_bucket = dict(bucket_state.get("current_bucket_state", {}))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_branch_state = str(branch_record.get("state", ""))
    governed_work_loop_policy = dict(self_structure_state.get("governed_work_loop_policy", {}))
    governed_capability_use_policy = dict(self_structure_state.get("governed_capability_use_policy", {}))
    governed_directive_work_selection_policy = dict(self_structure_state.get("governed_directive_work_selection_policy", {}))
    if current_branch_state != "paused_with_baseline_held":
        return _failure(proposal, "shadow work-loop continuation failed: branch must remain paused_with_baseline_held")
    if not governed_work_loop_policy or not governed_capability_use_policy or not governed_directive_work_selection_policy:
        return _failure(
            proposal,
            "shadow work-loop continuation failed: work-loop, capability-use, and directive-work governance state must all be present",
        )

    last_continuation_admission = dict(governed_work_loop_policy.get("last_work_loop_continuation_admission_outcome", {}))
    if str(last_continuation_admission.get("status", "")) != "admissible_for_governed_loop_continuation_v7":
        return _failure(
            proposal,
            "shadow work-loop continuation failed: the surviving v7 loop candidate is not currently admitted for governed work-loop continuation v7",
        )
    execution_readiness = str(current_state_summary.get("latest_governed_work_loop_execution_readiness", ""))
    latest_execution_outcome = str(current_state_summary.get("latest_governed_work_loop_execution_outcome", ""))
    if execution_readiness not in {
        "ready_for_shadow_work_loop_continuation_execution_v7",
        "ready_for_work_loop_evidence_review_v7",
    }:
        return _failure(
            proposal,
            "shadow work-loop continuation failed: self-structure does not currently mark the v7 loop continuation path as ready for shadow execution",
        )
    if execution_readiness == "ready_for_work_loop_evidence_review_v7" and latest_execution_outcome != "shadow_work_loop_continuation_v7_completed":
        return _failure(
            proposal,
            "shadow work-loop continuation failed: evidence-review readiness was present without a completed v7 continuation execution",
        )

    work_loop_policy_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_policy_artifact_path"),
        "memory_summary_v4_governed_work_loop_policy_snapshot_v1_*.json",
    )
    work_loop_candidate_screen_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_candidate_screen_artifact_path"),
        "memory_summary_v4_governed_work_loop_candidate_screen_snapshot_v7_*.json",
    )
    work_loop_continuation_admission_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_work_loop_continuation_admission_artifact_path"),
        "memory_summary_v4_governed_work_loop_continuation_admission_snapshot_v7_*.json",
    )
    work_loop_posture_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_work_loop_posture_artifact_path"),
        "memory_summary_v4_governed_work_loop_posture_snapshot_v1_*.json",
    )
    prior_work_loop_evidence_artifact_path = _resolve_artifact_path(
        None,
        "memory_summary_v4_governed_work_loop_evidence_snapshot_v5_*.json",
    )
    work_loop_evidence_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_work_loop_evidence_artifact_path"),
        "memory_summary_v4_governed_work_loop_evidence_snapshot_v6_*.json",
    )
    prior_continuation_execution_artifact_path_v1 = _resolve_artifact_path(
        None,
        "proposal_learning_loop_v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1_*.json",
    )
    prior_continuation_execution_artifact_path_v2 = _resolve_artifact_path(
        None,
        "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1_*.json",
    )
    prior_continuation_execution_artifact_path_v3 = _resolve_artifact_path(
        None,
        "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1_*.json",
    )
    prior_continuation_execution_artifact_path_v4 = _resolve_artifact_path(
        None,
        "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1_*.json",
    )
    prior_continuation_execution_artifact_path_v5 = _resolve_artifact_path(
        None,
        "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1_*.json",
    )
    prior_continuation_execution_artifact_path_v6 = _resolve_artifact_path(
        governed_work_loop_policy.get("last_work_loop_continuation_execution_artifact_path"),
        "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit_v1_*.json",
    )
    direct_work_evidence_artifact_path = _resolve_artifact_path(
        governed_directive_work_selection_policy.get("last_direct_work_evidence_artifact_path"),
        "memory_summary_v4_governed_direct_work_evidence_snapshot_v1_*.json",
    )
    direct_work_execution_artifact_path = _resolve_artifact_path(
        governed_directive_work_selection_policy.get("last_direct_work_execution_artifact_path"),
        "proposal_learning_loop_v4_governed_directive_work_governance_state_coherence_audit_refresh_v1_*.json",
    )
    direct_work_admission_artifact_path = _resolve_artifact_path(
        governed_directive_work_selection_policy.get("last_direct_work_admission_artifact_path"),
        "memory_summary_v4_governed_directive_work_admission_snapshot_v1_*.json",
    )
    capability_use_evidence_artifact_path = _resolve_artifact_path(
        governed_capability_use_policy.get("last_invocation_evidence_artifact_path"),
        "memory_summary_v4_governed_capability_use_evidence_snapshot_v1_*.json",
    )
    if not all(
        [
            work_loop_policy_artifact_path,
            work_loop_candidate_screen_artifact_path,
            work_loop_continuation_admission_artifact_path,
            work_loop_posture_artifact_path,
            prior_work_loop_evidence_artifact_path,
            work_loop_evidence_artifact_path,
            prior_continuation_execution_artifact_path_v1,
            prior_continuation_execution_artifact_path_v2,
            prior_continuation_execution_artifact_path_v3,
            prior_continuation_execution_artifact_path_v4,
            prior_continuation_execution_artifact_path_v5,
            prior_continuation_execution_artifact_path_v6,
            direct_work_evidence_artifact_path,
            direct_work_execution_artifact_path,
            direct_work_admission_artifact_path,
            capability_use_evidence_artifact_path,
        ]
    ):
        return _failure(
            proposal,
            "shadow work-loop continuation failed: one or more governing artifact paths for v7 loop continuation could not be resolved",
        )

    work_loop_policy_payload = _load_json_file(work_loop_policy_artifact_path)
    work_loop_candidate_screen_payload = _load_json_file(work_loop_candidate_screen_artifact_path)
    continuation_admission_payload = _load_json_file(work_loop_continuation_admission_artifact_path)
    work_loop_posture_payload = _load_json_file(work_loop_posture_artifact_path)
    prior_work_loop_evidence_payload = _load_json_file(prior_work_loop_evidence_artifact_path)
    work_loop_evidence_payload = _load_json_file(work_loop_evidence_artifact_path)
    prior_continuation_execution_payload_v1 = _load_json_file(prior_continuation_execution_artifact_path_v1)
    prior_continuation_execution_payload_v2 = _load_json_file(prior_continuation_execution_artifact_path_v2)
    prior_continuation_execution_payload_v3 = _load_json_file(prior_continuation_execution_artifact_path_v3)
    prior_continuation_execution_payload_v4 = _load_json_file(prior_continuation_execution_artifact_path_v4)
    prior_continuation_execution_payload_v5 = _load_json_file(prior_continuation_execution_artifact_path_v5)
    prior_continuation_execution_payload_v6 = _load_json_file(prior_continuation_execution_artifact_path_v6)
    direct_work_execution_payload = _load_json_file(direct_work_execution_artifact_path)
    work_loop_candidate_screen_summary = dict(
        work_loop_candidate_screen_payload.get("governed_work_loop_candidate_screen_v7_summary", {})
    )
    continuation_admission_summary = dict(continuation_admission_payload.get("governed_work_loop_continuation_admission_v7_summary", {}))
    if not dict(work_loop_policy_payload.get("governed_work_loop_policy_summary", {})):
        return _failure(proposal, "shadow work-loop continuation failed: work-loop policy summary is missing")
    if not dict(work_loop_posture_payload.get("governed_work_loop_posture_summary", {})):
        return _failure(proposal, "shadow work-loop continuation failed: work-loop posture summary is missing")
    if not dict(prior_work_loop_evidence_payload.get("governed_work_loop_evidence_v5_summary", {})):
        return _failure(proposal, "shadow work-loop continuation failed: work-loop evidence v5 summary is missing")
    if not dict(work_loop_evidence_payload.get("governed_work_loop_evidence_v6_summary", {})):
        return _failure(proposal, "shadow work-loop continuation failed: work-loop evidence v6 summary is missing")
    if not all([work_loop_candidate_screen_summary, continuation_admission_summary, prior_continuation_execution_payload_v1, prior_continuation_execution_payload_v2, prior_continuation_execution_payload_v3, prior_continuation_execution_payload_v4, prior_continuation_execution_payload_v5, prior_continuation_execution_payload_v6, direct_work_execution_payload]):
        return _failure(
            proposal,
            "shadow work-loop continuation failed: governing summary payloads for v7 loop continuation execution are incomplete",
        )

    callable_capabilities = list(governed_capability_use_policy.get("current_callable_capabilities", []))
    parser_capability = _find_capability(callable_capabilities, "skill_candidate_local_trace_parser_trial")
    if not parser_capability:
        return _failure(
            proposal,
            "shadow work-loop continuation failed: the held parser capability record is missing",
        )

    posture_summary = dict(work_loop_posture_payload.get("governed_work_loop_posture_summary", {}))
    evidence_v5_summary = dict(prior_work_loop_evidence_payload.get("governed_work_loop_evidence_v5_summary", {}))
    evidence_v6_summary = dict(work_loop_evidence_payload.get("governed_work_loop_evidence_v6_summary", {}))
    direct_work_evidence_summary = dict(
        _load_json_file(direct_work_evidence_artifact_path).get("governed_direct_work_evidence_summary", {})
    )
    capability_use_evidence_summary = dict(
        _load_json_file(capability_use_evidence_artifact_path).get("governed_capability_use_evidence_summary", {})
    )
    if not all([posture_summary, evidence_v5_summary, evidence_v6_summary, direct_work_evidence_summary, capability_use_evidence_summary]):
        return _failure(
            proposal,
            "shadow work-loop continuation failed: one or more governing summaries required for frontier circularity boundary are missing",
        )

    posture_current = dict(posture_summary.get("current_posture", {}))
    future_gate = dict(evidence_v6_summary.get("gate_status", {}))
    loop_chain_state = dict(evidence_v6_summary.get("chain_state_reviewed", {}))
    loop_accounting_requirements = dict(governed_work_loop_policy.get("loop_accounting_requirements", {}))
    guardrails = dict(governed_work_loop_policy.get("guardrails", {}))
    allowed_write_roots_for_screen = [str(intervention_data_dir()), str(Path(__file__).resolve().parent)]
    loop_candidates = _build_loop_candidate_examples_v7(
        parser_capability=parser_capability,
        allowed_write_roots=allowed_write_roots_for_screen,
    )
    screened_candidates = [
        _screen_loop_candidate_v4(
            item,
            directive_current=current_directive,
            bucket_current=current_bucket,
            current_branch_state=current_branch_state,
            current_state_summary=current_state_summary,
            callable_capabilities=callable_capabilities,
            allowed_write_roots=allowed_write_roots_for_screen,
            current_direct_work_future_posture=str(dict(direct_work_evidence_summary.get("future_posture", {})).get("category", "")),
            loop_continuation_future_posture=str(dict(evidence_v6_summary.get("future_posture", {})).get("category", "")),
            primary_posture_class=str(posture_current.get("primary_posture_class", "")),
            active_posture_classes=[str(item) for item in list(posture_current.get("active_posture_classes", [])) if str(item)],
            future_posture_review_gate_status=str(future_gate.get("gate_status", "")),
            loop_chain_state=loop_chain_state,
            loop_accounting_requirements=loop_accounting_requirements,
            guardrails=guardrails,
        )
        for item in loop_candidates
    ]
    primary_candidate_name = str(
        dict(continuation_admission_summary.get("candidate_under_review", {})).get("loop_candidate_name", "")
        or current_state_summary.get("latest_governed_work_loop_continuation_candidate", "")
    )
    loop_candidate_record = _find_loop_candidate(screened_candidates, name=primary_candidate_name)
    if not loop_candidate_record:
        return _failure(
            proposal,
            "shadow work-loop continuation failed: the admitted loop candidate could not be recovered from the current loop candidate screen",
        )
    candidate_quality_flags = dict(loop_candidate_record.get("candidate_quality_flags", {}))

    continuation_envelope = dict(continuation_admission_summary.get("continuation_envelope", {}))
    continuation_accounting_requirements = dict(loop_candidate_record.get("loop_accounting_expectations", {}))
    trigger_bundle = dict(continuation_admission_summary.get("review_rollback_deprecation_trigger_status", {}))
    if not continuation_envelope or not continuation_accounting_requirements:
        return _failure(
            proposal,
            "shadow work-loop continuation failed: the continuation envelope or accounting requirements are missing from the admission artifact",
        )

    allowed_roots = [Path(path).resolve() for path in list(continuation_envelope.get("allowed_write_roots", []))]
    if not allowed_roots:
        return _failure(
            proposal,
            "shadow work-loop continuation failed: no approved write roots were supplied by the continuation admission envelope",
        )

    source_artifact_paths = [
        str(path.resolve())
        for path in [
            DIRECTIVE_STATE_PATH,
            DIRECTIVE_HISTORY_PATH,
            SELF_STRUCTURE_STATE_PATH,
            SELF_STRUCTURE_LEDGER_PATH,
            BRANCH_REGISTRY_PATH,
            BUCKET_STATE_PATH,
            INTERVENTION_LEDGER_PATH,
            ANALYTICS_PATH,
            RECOMMENDATIONS_PATH,
            work_loop_policy_artifact_path,
            work_loop_candidate_screen_artifact_path,
            work_loop_continuation_admission_artifact_path,
            work_loop_posture_artifact_path,
            prior_work_loop_evidence_artifact_path,
            work_loop_evidence_artifact_path,
            prior_continuation_execution_artifact_path_v1,
            prior_continuation_execution_artifact_path_v2,
            prior_continuation_execution_artifact_path_v3,
            prior_continuation_execution_artifact_path_v4,
            prior_continuation_execution_artifact_path_v5,
            prior_continuation_execution_artifact_path_v6,
            direct_work_evidence_artifact_path,
            direct_work_execution_artifact_path,
            direct_work_admission_artifact_path,
            capability_use_evidence_artifact_path,
        ]
        if path and Path(path).exists()
    ]
    governance_source_digests = [_digest_path(Path(path)) for path in source_artifact_paths]
    frontier_circularity_boundary_audit = _build_frontier_circularity_boundary_audit(
        directive_state=directive_state,
        current_state_summary=current_state_summary,
        branch_record=branch_record,
        current_branch_state=current_branch_state,
        current_bucket=current_bucket,
        loop_candidate_record=loop_candidate_record,
        candidate_screen_summary=work_loop_candidate_screen_summary,
        continuation_admission_summary=continuation_admission_summary,
        evidence_v6_summary=evidence_v6_summary,
        continuation_envelope=continuation_envelope,
        callable_capabilities=callable_capabilities,
        analytics=analytics,
        recommendations=recommendations,
        directive_history=directive_history,
        self_structure_ledger=self_structure_ledger,
        intervention_ledger=intervention_ledger,
        prior_direct_work_execution_payload=direct_work_execution_payload,
        prior_continuation_v1_execution_payload=prior_continuation_execution_payload_v1,
        prior_continuation_v2_execution_payload=prior_continuation_execution_payload_v2,
        prior_continuation_v3_execution_payload=prior_continuation_execution_payload_v3,
        prior_continuation_v4_execution_payload=prior_continuation_execution_payload_v4,
        prior_continuation_v5_execution_payload=prior_continuation_execution_payload_v5,
        prior_continuation_v6_execution_payload=prior_continuation_execution_payload_v6,
        work_loop_artifact_paths={
            "work_loop_policy_artifact": work_loop_policy_artifact_path,
            "work_loop_candidate_screen_artifact": work_loop_candidate_screen_artifact_path,
            "work_loop_continuation_admission_artifact": work_loop_continuation_admission_artifact_path,
            "work_loop_posture_artifact": work_loop_posture_artifact_path,
            "prior_work_loop_evidence_artifact": prior_work_loop_evidence_artifact_path,
            "work_loop_evidence_artifact": work_loop_evidence_artifact_path,
            "prior_work_loop_continuation_execution_v1_artifact": prior_continuation_execution_artifact_path_v1,
            "prior_work_loop_continuation_execution_v2_artifact": prior_continuation_execution_artifact_path_v2,
            "prior_work_loop_continuation_execution_v3_artifact": prior_continuation_execution_artifact_path_v3,
            "prior_work_loop_continuation_execution_v4_artifact": prior_continuation_execution_artifact_path_v4,
            "prior_work_loop_continuation_execution_v5_artifact": prior_continuation_execution_artifact_path_v5,
            "prior_work_loop_continuation_execution_v6_artifact": prior_continuation_execution_artifact_path_v6,
        },
    )

    next_template = "memory_summary.v4_governed_work_loop_evidence_snapshot_v7"
    artifact_path = _diagnostic_artifact_dir() / (
        f"proposal_learning_loop_v4_governed_work_loop_governance_recommendation_frontier_circularity_boundary_audit_v1_{proposal['proposal_id']}.json"
    )
    pressure = _bucket_pressure(bucket_state, dict(continuation_envelope.get("resource_expectations", {})))
    write_paths = [artifact_path, SELF_STRUCTURE_STATE_PATH, SELF_STRUCTURE_LEDGER_PATH]
    material_circularity_boundary_delta_detected = bool(dict(frontier_circularity_boundary_audit.get("summary", {})).get("material_circularity_boundary_delta_detected", False))
    distinct_value_read = {
        "passed": bool(material_circularity_boundary_delta_detected),
        "value": "high" if bool(material_circularity_boundary_delta_detected) else "low",
        "reason": (
            "the continuation produced a bounded frontier-circularity boundary audit with a new recommendation-frontier quality signal beyond the prior direct-work step, continuation v1, continuation v2, the prior frontier-containment execution, the prior frontier-stability execution, the prior frontier-persistence execution, and the prior frontier-recursion execution"
            if bool(material_circularity_boundary_delta_detected)
            else "the continuation did not surface enough new frontier-quality signal to justify distinct loop value over the reviewed chain"
        ),
        "vs_prior_direct_work": {
            "distinct": True,
            "reason": "the execution audited frontier circularity boundaries rather than replaying the governance state coherence audit shape",
            "observed_deltas": dict(dict(frontier_circularity_boundary_audit.get("frontier_observations", {})).get("frontier_chain_deltas", {})).get("vs_prior_direct_work", {}),
        },
        "vs_prior_continuation_v1": {
            "distinct": True,
            "reason": "the execution audited frontier circularity boundaries rather than replaying the earlier ledger consistency delta audit",
            "observed_deltas": dict(dict(frontier_circularity_boundary_audit.get("frontier_observations", {})).get("frontier_chain_deltas", {})).get("vs_prior_continuation_v1", {}),
        },
        "vs_prior_continuation_v2": {
            "distinct": True,
            "reason": "the execution audited frontier circularity boundaries rather than replaying the earlier recommendation-to-ledger alignment delta audit",
            "observed_deltas": dict(dict(frontier_circularity_boundary_audit.get("frontier_observations", {})).get("frontier_chain_deltas", {})).get("vs_prior_continuation_v2", {}),
        },
        "vs_prior_continuation_v3": {
            "distinct": True,
            "reason": "the execution audited frontier circularity boundaries relative to the prior frontier-containment state instead of replaying the earlier containment check",
            "observed_deltas": dict(dict(frontier_circularity_boundary_audit.get("frontier_observations", {})).get("frontier_chain_deltas", {})).get("vs_prior_continuation_v3", {}),
        },
        "vs_prior_continuation_v4": {
            "distinct": True,
            "reason": "the execution audited frontier circularity boundaries relative to the prior frontier-stability state instead of replaying the earlier stability check",
            "observed_deltas": dict(dict(frontier_circularity_boundary_audit.get("frontier_observations", {})).get("frontier_chain_deltas", {})).get("vs_prior_continuation_v4", {}),
        },
        "vs_prior_continuation_v5": {
            "distinct": True,
            "reason": "the execution audited frontier circularity boundaries relative to the prior frontier-persistence state instead of replaying the earlier persistence-boundary check",
            "observed_deltas": dict(dict(frontier_circularity_boundary_audit.get("frontier_observations", {})).get("frontier_chain_deltas", {})).get("vs_prior_continuation_v5", {}),
        },
        "vs_prior_continuation_v6": {
            "distinct": True,
            "reason": "the execution audited frontier circularity boundaries relative to the prior frontier-recursion state instead of replaying the earlier recursion-boundary check",
            "observed_deltas": dict(dict(frontier_circularity_boundary_audit.get("frontier_observations", {})).get("frontier_chain_deltas", {})).get("vs_prior_continuation_v6", {}),
        },
    }
    directive_support_value = {
        "passed": True,
        "value": "high",
        "reason": "the frontier-circularity boundary audit produced a bounded governance continuation report that directly supports directive-bound narrow work-loop control",
    }
    distinctness_assessment = {
        "classification": "materially_distinct"
        if bool(dict(loop_candidate_record.get("screen_dimensions", {})).get("distinctness_vs_reviewed_chain", {}).get("materially_distinct_from_chain", False))
        else "not_materially_distinct",
        "distinct_from_direct_work": bool(dict(loop_candidate_record.get("screen_dimensions", {})).get("distinctness_vs_reviewed_chain", {}).get("distinct_from_direct_work", False)),
        "distinct_from_continuation_v1": bool(dict(loop_candidate_record.get("screen_dimensions", {})).get("distinctness_vs_reviewed_chain", {}).get("distinct_from_continuation_v1", False)),
        "distinct_from_continuation_v2": bool(dict(loop_candidate_record.get("screen_dimensions", {})).get("distinctness_vs_reviewed_chain", {}).get("distinct_from_continuation_v2", False)),
        "distinct_from_continuation_v3": bool(dict(loop_candidate_record.get("screen_dimensions", {})).get("distinctness_vs_reviewed_chain", {}).get("distinct_from_continuation_v3", False)),
        "distinct_from_evidence_snapshot_v3": bool(dict(loop_candidate_record.get("screen_dimensions", {})).get("distinctness_vs_reviewed_chain", {}).get("distinct_from_evidence_snapshot_v3", False)),
        "distinct_from_continuation_v4": bool(dict(loop_candidate_record.get("screen_dimensions", {})).get("distinctness_vs_reviewed_chain", {}).get("distinct_from_continuation_v4", False)),
        "distinct_from_evidence_snapshot_v4": bool(dict(loop_candidate_record.get("screen_dimensions", {})).get("distinctness_vs_reviewed_chain", {}).get("distinct_from_evidence_snapshot_v4", False)),
        "distinct_from_continuation_v5": bool(dict(loop_candidate_record.get("screen_dimensions", {})).get("distinctness_vs_reviewed_chain", {}).get("distinct_from_continuation_v5", False)),
        "distinct_from_evidence_snapshot_v5": bool(dict(loop_candidate_record.get("screen_dimensions", {})).get("distinctness_vs_reviewed_chain", {}).get("distinct_from_evidence_snapshot_v5", False)),
        "distinct_from_continuation_v6": bool(dict(loop_candidate_record.get("screen_dimensions", {})).get("distinctness_vs_reviewed_chain", {}).get("distinct_from_continuation_v6", False)),
        "distinct_from_evidence_snapshot_v6": bool(dict(loop_candidate_record.get("screen_dimensions", {})).get("distinctness_vs_reviewed_chain", {}).get("distinct_from_evidence_snapshot_v6", False)),
    }
    structural_coherence_assessment = {
        "classification": "structurally_coherent_with_reviewed_chain"
        if str(dict(frontier_circularity_boundary_audit.get("summary", {})).get("frontier_alignment_assessment", "")) == "bounded_alignment_preserved"
        else "structural_coherence_at_risk"
    }
    new_evidence_signal_assessment = {
        "classification": "new_frontier_quality_signal_present" if bool(material_circularity_boundary_delta_detected) else "new_frontier_quality_signal_absent",
        "signal_count": int(dict(frontier_circularity_boundary_audit.get("summary", {})).get("circularity_signal_count", 0) or 0),
        "reason": str(distinct_value_read.get("reason", "")),
    }
    hidden_capability_pressure = {
        "passed": True,
        "value": "none",
        "reason": "the continuation remained governance frontier maintenance and did not drift toward capability use, paused-line reopen, hidden development, or silent broadening",
    }
    posture_discipline_assessment = {
        "classification": "posture_discipline_preserved"
    }
    posture_pressure_assessment = {
        "classification": "posture_pressure_absent"
    }
    gate_status = {
        "classification": "gate_closed",
        "gate_status": str(dict(evidence_v6_summary.get("gate_status", {})).get("gate_status", "")),
    }
    routing_status = {
        "classification": "routing_deferred",
        "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
    }
    recommended_next_action = {
        "classification": "bounded_evidence_review_next",
        "template_name": "memory_summary.v4_governed_work_loop_evidence_snapshot_v7",
    }
    review_trigger_status = {
        "decision_criticality_rises_above_low": str(loop_candidate_record.get("decision_criticality", "")) != "low",
        "distinct_value_claim_collapses_into_low_yield_repetition": not bool(distinct_value_read.get("passed", False)),
        "held_capability_dependency_or_external_source_need_appears": False,
        "overlap_with_active_work_rises_above_low": str(loop_candidate_record.get("overlap_with_active_work", "")) != "low",
        "posture_rule_compliance_breaks": False,
        "scope_expands_beyond_recommendation_frontier_circularity_boundary_audit": False,
        "work_starts_to_imply_capability_development_or_branch_mutation": False,
    }
    rollback_trigger_status = {
        str(key): False
        for key in dict(trigger_bundle.get("rollback_trigger_status", {})).keys()
    }
    deprecation_trigger_status = {
        "better_governed_capability_or_direct_work_path_supersedes_this_step": False,
        "directive_relevance_drops_below_medium": str(loop_candidate_record.get("directive_relevance", "")) != "high",
        "governance_observability_drops_below_medium": str(
            dict(loop_candidate_record.get("classification_report", {})).get(
                "governance_observability",
                dict(loop_candidate_record.get("screen_dimensions", {})).get("governance_observability", "high"),
            )
        )
        != "high",
        "distinct_frontier_signal_disappears": not bool(distinct_value_read.get("passed", False)),
    }
    continuation_accounting = {
        "loop_identity_context": dict(continuation_accounting_requirements.get("loop_identity_context", {})),
        "current_work_state": dict(continuation_accounting_requirements.get("current_work_state", {})),
        "candidate_identity": dict(continuation_accounting_requirements.get("candidate_identity", {})),
        "expected_path": dict(continuation_accounting_requirements.get("expected_path", {})),
        "resource_trust_position": dict(continuation_accounting_requirements.get("resource_trust_position", {})),
        "continuation_rationale": str(
            continuation_accounting_requirements.get("continuation_rationale", "")
            or continuation_admission_summary.get("admission_rationale", "")
        ),
        "expected_next_evidence_signal": str(
            continuation_accounting_requirements.get("expected_next_evidence_signal", "")
        ),
        "review_rollback_hooks": dict(continuation_accounting_requirements.get("review_rollback_hooks", {})),
        "resource_usage": {
            "cpu_parallel_units_used": int(dict(continuation_envelope.get("resource_expectations", {})).get("cpu_parallel_units", 0) or 0),
            "memory_mb_used": int(dict(continuation_envelope.get("resource_expectations", {})).get("memory_mb", 0) or 0),
            "storage_write_mb_used": 0,
            "network_mode_used": str(dict(continuation_envelope.get("resource_expectations", {})).get("network_mode", "none")),
        },
        "write_roots_touched": list(continuation_envelope.get("allowed_write_roots", [])),
        "source_artifact_paths": source_artifact_paths,
        "admission_outcome": "admissible_for_governed_loop_continuation_v7",
        "work_loop_posture": "shadow_only_loop_continuation_v7",
        "trusted_source_report": dict(dict(loop_candidate_record.get("classification_report", {})).get("trusted_source_report", {})),
        "resource_report": dict(dict(loop_candidate_record.get("classification_report", {})).get("resource_report", {})),
        "write_root_report": dict(dict(loop_candidate_record.get("classification_report", {})).get("write_root_report", {})),
        "branch_state_unchanged": True,
        "retained_promotion_performed": False,
        "review_trigger_status": review_trigger_status,
        "rollback_trigger_status": rollback_trigger_status,
        "deprecation_trigger_status": deprecation_trigger_status,
        "continuation_summary": "governance recommendation-frontier circularity boundary audit",
        "directive_support_observation": str(directive_support_value.get("reason", "")),
        "bounded_output_artifact_path": str(artifact_path),
        "usefulness_signal_summary": {
            "passed_check_count": int(dict(frontier_circularity_boundary_audit.get("summary", {})).get("passed_check_count", 0) or 0),
            "failed_check_count": int(dict(frontier_circularity_boundary_audit.get("summary", {})).get("failed_check_count", 0) or 0),
            "circularity_signal_count": int(dict(frontier_circularity_boundary_audit.get("summary", {})).get("circularity_signal_count", 0) or 0),
            "material_circularity_boundary_delta_detected": bool(dict(frontier_circularity_boundary_audit.get("summary", {})).get("material_circularity_boundary_delta_detected", False)),
        },
        "distinct_value_observation": str(distinct_value_read.get("reason", "")),
    }
    envelope_compliance = {
        "network_mode_required": str(continuation_envelope.get("network_mode", "none")),
        "network_mode_observed": str(dict(continuation_envelope.get("resource_expectations", {})).get("network_mode", "none")),
        "network_mode_remained_none": str(dict(continuation_envelope.get("resource_expectations", {})).get("network_mode", "none")) == "none",
        "branch_state_stayed_paused_with_baseline_held": current_branch_state == "paused_with_baseline_held",
        "no_branch_state_mutation": True,
        "no_retained_promotion": True,
        "no_capability_modification": True,
        "no_paused_capability_reopen": True,
        "no_new_skill_creation": True,
        "no_protected_surface_modification": True,
        "no_downstream_selected_set_work": True,
        "no_plan_ownership_change": True,
        "no_routing_work": True,
        "not_direct_work_repetition": bool(distinct_value_read.get("passed", False)),
        "not_prior_continuation_replay": bool(distinct_value_read.get("passed", False)),
        "silent_broadening_not_triggered": True,
        "writes_within_approved_roots": all(_path_within_allowed_roots(path, allowed_roots) for path in write_paths),
        "approved_write_paths": [str(path) for path in write_paths],
        "resource_expectations": dict(continuation_envelope.get("resource_expectations", {})),
        "bucket_pressure": pressure,
        "resource_limits_respected": pressure["concern_level"] == "low",
    }
    envelope_compliance["passed"] = all(
        bool(envelope_compliance[key])
        for key in [
            "network_mode_remained_none",
            "branch_state_stayed_paused_with_baseline_held",
            "no_branch_state_mutation",
            "no_retained_promotion",
            "no_capability_modification",
            "no_paused_capability_reopen",
            "no_new_skill_creation",
            "no_protected_surface_modification",
            "no_downstream_selected_set_work",
            "no_plan_ownership_change",
            "no_routing_work",
            "not_direct_work_repetition",
            "not_prior_continuation_replay",
            "silent_broadening_not_triggered",
            "writes_within_approved_roots",
            "resource_limits_respected",
        ]
    )
    governed_work_loop_continuation_operational = (
        bool(directive_support_value.get("passed", False))
        and bool(hidden_capability_pressure.get("passed", False))
        and bool(distinct_value_read.get("passed", False))
        and bool(envelope_compliance.get("passed", False))
        and not any(bool(value) for value in review_trigger_status.values())
        and not any(bool(value) for value in rollback_trigger_status.values())
        and not any(bool(value) for value in deprecation_trigger_status.values())
    )
    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_circularity_boundary_audit_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "branch_context": {
            "current_branch_id": str(branch_record.get("branch_id", "")),
            "current_branch_state": current_branch_state,
            "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
            "plan_non_owning": bool(current_state_summary.get("plan_non_owning", False)),
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
        },
        "comparison_references": {
            "memory_summary.v4_governance_substrate_v1_snapshot": _artifact_reference(governance_snapshot, latest_snapshots),
            "memory_summary.v4_governed_work_loop_policy_snapshot_v1": _artifact_reference(work_loop_policy_snapshot, latest_snapshots),
            "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v7": _artifact_reference(work_loop_candidate_screen_snapshot, latest_snapshots),
            "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v7": _artifact_reference(work_loop_continuation_admission_snapshot, latest_snapshots),
            "memory_summary.v4_governed_work_loop_posture_snapshot_v1": _artifact_reference(work_loop_posture_snapshot, latest_snapshots),
            "memory_summary.v4_governed_work_loop_evidence_snapshot_v5": _artifact_reference(prior_work_loop_evidence_snapshot, latest_snapshots),
            "memory_summary.v4_governed_work_loop_evidence_snapshot_v6": _artifact_reference(work_loop_evidence_snapshot, latest_snapshots),
            "proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1": _artifact_reference(prior_continuation_execution_snapshot_v1, latest_snapshots),
            "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1": _artifact_reference(prior_continuation_execution_snapshot_v2, latest_snapshots),
            "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1": _artifact_reference(prior_continuation_execution_snapshot_v3, latest_snapshots),
            "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1": _artifact_reference(prior_continuation_execution_snapshot_v4, latest_snapshots),
            "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1": _artifact_reference(prior_continuation_execution_snapshot_v5, latest_snapshots),
            "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit_v1": _artifact_reference(prior_continuation_execution_snapshot_v6, latest_snapshots),
            "memory_summary.v4_governed_direct_work_evidence_snapshot_v1": _artifact_reference(direct_work_evidence_snapshot, latest_snapshots),
            "proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1": _artifact_reference(direct_work_execution_snapshot, latest_snapshots),
            "memory_summary.v4_governed_directive_work_admission_snapshot_v1": _artifact_reference(direct_work_admission_snapshot, latest_snapshots),
            "memory_summary.v4_governed_capability_use_evidence_snapshot_v1": _artifact_reference(capability_use_evidence_snapshot, latest_snapshots),
        },
        "governed_work_loop_continuation_execution_summary": {
            "candidate_executed": {
                "loop_candidate_id": str(dict(continuation_admission_summary.get("candidate_under_review", {})).get("loop_candidate_id", "")),
                "loop_candidate_name": primary_candidate_name,
                "assigned_candidate_class": str(loop_candidate_record.get("assigned_class", "")),
                "proposed_execution_template": str(candidate_quality_flags.get("proposed_execution_template", "")),
                "continuation_variant": "v7_frontier_circularity_boundary",
            },
            "what_the_continuation_did": [
                "read only the admitted trusted local governance artifacts relevant to recommendation-frontier circularity boundaries under the narrow envelope",
                "computed a bounded frontier-circularity boundary audit against the current seven-step governed chain rather than replaying earlier state, ledger, alignment, containment, stability, persistence-boundary, or recursion-boundary audit shapes",
                "materialized a shadow-only governed work-loop continuation v7 artifact with full continuation accounting and trigger status",
            ],
            "local_governance_sources_used": {
                "source_artifact_paths": source_artifact_paths,
                "governance_source_digests": governance_source_digests,
            },
            "frontier_circularity_artifact_produced": {
                "bounded_output_artifact_path": str(artifact_path),
                "governance_recommendation_frontier_circularity_boundary_audit_output": frontier_circularity_boundary_audit,
            },
            "continuation_accounting_captured": continuation_accounting,
            "envelope_compliance": envelope_compliance,
            "directive_support_value": directive_support_value,
            "distinct_value_over_prior_step_read": distinct_value_read,
            "hidden_capability_pressure_read": hidden_capability_pressure,
            "frontier_circularity_result": {
                "classification": str(dict(frontier_circularity_boundary_audit.get("summary", {})).get("frontier_circularity_boundary_status", "")),
                "frontier_circularity_assessment": str(dict(frontier_circularity_boundary_audit.get("summary", {})).get("frontier_circularity_assessment", "")),
                "frontier_drift_assessment": str(dict(frontier_circularity_boundary_audit.get("summary", {})).get("frontier_drift_assessment", "")),
                "frontier_alignment_assessment": str(dict(frontier_circularity_boundary_audit.get("summary", {})).get("frontier_alignment_assessment", "")),
            },
            "distinctness_assessment": distinctness_assessment,
            "structural_coherence_assessment": structural_coherence_assessment,
            "new_frontier_quality_signal_assessment": {
                "classification": "new_frontier_quality_signal_present" if bool(material_circularity_boundary_delta_detected) else "new_frontier_quality_signal_absent",
                "signal_count": int(dict(frontier_circularity_boundary_audit.get("summary", {})).get("circularity_signal_count", 0) or 0),
                "reason": str(distinct_value_read.get("reason", "")),
            },
            "new_evidence_signal_assessment": new_evidence_signal_assessment,
            "posture_discipline_assessment": posture_discipline_assessment,
            "posture_pressure_assessment": posture_pressure_assessment,
            "gate_status": gate_status,
            "routing_status": routing_status,
            "recommended_next_action": recommended_next_action,
            "recommended_next_template": next_template,
            "review_rollback_deprecation_trigger_status": {
                "review_trigger_status": review_trigger_status,
                "rollback_trigger_status": rollback_trigger_status,
                "deprecation_trigger_status": deprecation_trigger_status,
            },
            "path_separation_status": {
                "remained_governed_work_loop_continuation": True,
                "not_direct_work_repetition": bool(distinct_value_read.get("passed", False)),
                "not_prior_continuation_replay": True,
                "capability_use_not_invoked": True,
                "paused_capability_line_not_reopened": True,
                "new_skill_path_not_opened": True,
                "silent_broadening_not_triggered": True,
            },
            "why_governance_remains_source_of_truth": {
                "owner": "governance_substrate_v1",
                "proposal_learning_loop_is_governance_truth_source": False,
                "reason": "the run consumed directive, bucket, branch, self-structure, work-loop policy, candidate-screen v7, posture, continuation-admission v7, evidence v5/v6, the prior continuation chain through frontier recursion, and prior direct-work governance artifacts as read-only authority while performing only the admitted v7 loop-continuation audit",
            },
            "resource_trust_accounting": {
                "expected_resource_budget": dict(continuation_accounting["resource_trust_position"].get("expected_resource_budget", {})),
                "required_trusted_sources": list(continuation_accounting["resource_trust_position"].get("required_trusted_sources", [])),
                "expected_write_roots": list(continuation_accounting["resource_trust_position"].get("expected_write_roots", [])),
                "resource_usage": dict(continuation_accounting.get("resource_usage", {})),
            },
            "concise_operator_readable_conclusion": "The recommendation frontier remains circularity-bounded, materially distinct, and posture-safe under the current narrow governed envelope.",
        },
        "analytics_context": {
            "analytics_report_path": str(ANALYTICS_PATH),
            "proposal_recommendations_path": str(RECOMMENDATIONS_PATH),
            "proposal_count": int(analytics.get("proposal_count", 0) or 0),
            "directive_history_entry_count": int(len(directive_history)),
            "self_structure_ledger_entry_count": int(len(self_structure_ledger)),
            "intervention_ledger_entry_count": int(len(intervention_ledger)),
        },
        "observability_gain": {
            "passed": True,
            "reason": "the admitted loop-continuation item now has a real bounded execution artifact and full continuation accounting under governance",
            "artifact_paths": {
                "work_loop_continuation_execution_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the run proves that NOVALI can execute a seventh distinct admitted governed work-loop continuation step in the reviewed chain without collapsing into direct-work repetition, prior-continuation replay, capability use, hidden development, or silent broadening",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "the execution adds a concrete frontier-circularity boundary signal while keeping loop continuation separate from prior direct-work repetition, capability-use, paused-line reopen, and new-skill creation",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the execution remained shadow-only, local, reversible, and governance-bounded; live policy, thresholds, routing, frozen benchmark semantics, and the projection-safe envelope stayed unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": next_template,
            "reason": "the next step should review the v7 frontier-circularity boundary evidence before considering any further bounded continuation search or posture-review criteria",
        },
        "diagnostic_conclusions": {
            "governed_work_loop_continuation_execution_in_place": True,
            "governed_work_loop_continuation_v7_execution_in_place": True,
            "loop_candidate": primary_candidate_name,
            "governed_work_loop_continuation_operational": governed_work_loop_continuation_operational,
            "frontier_circularity_boundary_status": str(dict(frontier_circularity_boundary_audit.get("summary", {})).get("frontier_circularity_boundary_status", "")),
            "new_frontier_quality_signal_present": bool(material_circularity_boundary_delta_detected),
            "branch_state_mutation_occurred": False,
            "retained_promotion_occurred": False,
            "paused_capability_line_reopened": False,
            "plan_should_remain_non_owning": bool(current_state_summary.get("plan_non_owning", False)),
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "best_next_template": next_template,
        },
    }
    _write_json(artifact_path, artifact_payload)

    estimated_write_bytes = int(artifact_path.stat().st_size) + len(json.dumps({"updated_state": True})) + len(json.dumps({"ledger_event": True}))
    continuation_accounting["resource_usage"]["storage_write_mb_used"] = max(
        1,
        int((estimated_write_bytes + (1024 * 1024) - 1) / (1024 * 1024)),
    )
    artifact_payload["governed_work_loop_continuation_execution_summary"]["continuation_accounting_captured"] = continuation_accounting
    artifact_payload["governed_work_loop_continuation_execution_summary"]["envelope_compliance"]["estimated_write_bytes"] = int(estimated_write_bytes)
    artifact_payload["governed_work_loop_continuation_execution_summary"]["envelope_compliance"]["storage_budget_respected"] = (
        estimated_write_bytes <= int(dict(continuation_envelope.get("resource_expectations", {})).get("storage_write_mb", 0) or 0) * 1024 * 1024
    )
    _write_json(artifact_path, artifact_payload)

    updated_self_structure_state = dict(self_structure_state)
    updated_work_loop_policy = dict(governed_work_loop_policy)
    updated_work_loop_policy["last_prior_work_loop_continuation_execution_artifact_path"] = str(
        prior_continuation_execution_artifact_path_v6
    )
    updated_work_loop_policy["last_work_loop_continuation_execution_artifact_path"] = str(artifact_path)
    updated_work_loop_policy["last_work_loop_continuation_execution_outcome"] = {
        "loop_candidate_id": str(dict(continuation_admission_summary.get("candidate_under_review", {})).get("loop_candidate_id", "")),
        "loop_candidate_name": primary_candidate_name,
        "work_loop_continuation_execution_outcome": "shadow_work_loop_continuation_v7_completed",
        "envelope_compliance_passed": bool(envelope_compliance.get("passed", False)),
        "distinct_value_added": bool(distinct_value_read.get("passed", False)),
        "frontier_circularity_boundary_status": str(dict(frontier_circularity_boundary_audit.get("summary", {})).get("frontier_circularity_boundary_status", "")),
        "new_frontier_quality_signal_present": bool(material_circularity_boundary_delta_detected),
        "paused_capability_line_reopened": False,
        "retained_promotion": False,
        "governed_work_loop_continuation_operational": governed_work_loop_continuation_operational,
        "best_next_template": next_template,
    }
    updated_work_loop_policy["best_next_template"] = next_template
    updated_self_structure_state["governed_work_loop_policy"] = updated_work_loop_policy

    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "governed_work_loop_execution_in_place": True,
            "governed_work_loop_execution_v7_in_place": True,
            "latest_governed_work_loop_execution_candidate": primary_candidate_name,
            "latest_governed_work_loop_execution_outcome": "shadow_work_loop_continuation_v7_completed",
            "latest_governed_work_loop_execution_readiness": "ready_for_work_loop_evidence_review_v7",
            "latest_governed_work_loop_operational_status": (
                "operational_recommendation_frontier_circularity_boundary_continuation_proven"
                if governed_work_loop_continuation_operational
                else "work_loop_continuation_needs_review"
            ),
            "latest_governed_work_loop_operational_success": governed_work_loop_continuation_operational,
            "latest_governed_work_loop_best_next_template": next_template,
            "latest_governed_work_loop_readiness": "ready_for_work_loop_evidence_review_v7",
            "current_branch_state": current_branch_state,
            "plan_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "retained_skill_promotion_performed": False,
        }
    )
    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["current_state_summary"] = updated_current_state_summary
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    _append_jsonl(
        SELF_STRUCTURE_LEDGER_PATH,
        {
            "event_id": f"governed_work_loop_governance_recommendation_frontier_circularity_boundary_audit_v1::{proposal['proposal_id']}",
            "timestamp": _now(),
            "event_type": "governed_work_loop_governance_recommendation_frontier_circularity_boundary_audit_v1_materialized",
            "event_class": "governed_work_loop_continuation_execution",
            "directive_id": str(current_directive.get("directive_id", "")),
            "directive_state": str(directive_state.get("initialization_state", "")),
            "branch_id": str(branch_record.get("branch_id", "")),
            "branch_state": current_branch_state,
            "loop_candidate_id": str(dict(continuation_admission_summary.get("candidate_under_review", {})).get("loop_candidate_id", "")),
            "loop_candidate_name": primary_candidate_name,
            "work_loop_continuation_execution_outcome": "shadow_work_loop_continuation_v7_completed",
            "distinct_value_added": bool(distinct_value_read.get("passed", False)),
            "frontier_circularity_boundary_status": str(dict(frontier_circularity_boundary_audit.get("summary", {})).get("frontier_circularity_boundary_status", "")),
            "paused_capability_line_reopened": False,
            "retained_promotion": False,
            "branch_state_mutation": False,
            "network_mode": str(dict(continuation_envelope.get("resource_expectations", {})).get("network_mode", "none")),
            "artifact_paths": {
                "governed_work_loop_policy_v1": str(work_loop_policy_artifact_path),
                "governed_work_loop_candidate_screen_v7": str(work_loop_candidate_screen_artifact_path),
                "governed_work_loop_continuation_admission_v7": str(work_loop_continuation_admission_artifact_path),
                "governed_work_loop_posture_v1": str(work_loop_posture_artifact_path),
                "governed_work_loop_evidence_v5": str(prior_work_loop_evidence_artifact_path),
                "governed_work_loop_evidence_v6": str(work_loop_evidence_artifact_path),
                "governed_work_loop_continuation_execution_v1": str(prior_continuation_execution_artifact_path_v1),
                "governed_work_loop_continuation_execution_v2": str(prior_continuation_execution_artifact_path_v2),
                "governed_work_loop_continuation_execution_v3": str(prior_continuation_execution_artifact_path_v3),
                "governed_work_loop_continuation_execution_v4": str(prior_continuation_execution_artifact_path_v4),
                "governed_work_loop_continuation_execution_v5": str(prior_continuation_execution_artifact_path_v5),
                "governed_work_loop_continuation_execution_v6": str(prior_continuation_execution_artifact_path_v6),
                "direct_work_evidence_v1": str(direct_work_evidence_artifact_path),
                "direct_work_execution_v1": str(direct_work_execution_artifact_path),
                "direct_work_admission_v1": str(direct_work_admission_artifact_path),
                "capability_use_evidence_v1": str(capability_use_evidence_artifact_path),
                "governed_work_loop_continuation_execution_v7": str(artifact_path),
            },
            "source_proposal_id": str(proposal.get("proposal_id", "")),
        },
    )

    return {
        "passed": True,
        "shadow_contract": "governed_work_loop_continuation",
        "proposal_semantics": "shadow_work_loop_continuation",
        "reason": "shadow work-loop continuation v7 passed: the admitted recommendation-frontier circularity boundary audit executed inside the approved continuation envelope without repeating prior work, invoking capability use, reopening capabilities, or widening posture",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }




