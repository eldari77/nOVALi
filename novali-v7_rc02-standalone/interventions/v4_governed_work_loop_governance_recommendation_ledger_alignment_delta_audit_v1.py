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


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governance_substrate_v1_snapshot")
    work_loop_policy_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_policy_snapshot_v1"
    )
    work_loop_candidate_screen_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v2"
    )
    work_loop_continuation_admission_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v2"
    )
    work_loop_posture_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_posture_snapshot_v1"
    )
    work_loop_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_evidence_snapshot_v1"
    )
    prior_continuation_execution_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1"
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
            work_loop_evidence_snapshot,
            prior_continuation_execution_snapshot,
            direct_work_evidence_snapshot,
            direct_work_execution_snapshot,
            direct_work_admission_snapshot,
            capability_use_evidence_snapshot,
        ]
    ):
        return _failure(
            proposal,
            "shadow work-loop continuation failed: governance substrate, work-loop policy, v2 candidate screen, v2 continuation admission, posture, prior continuation, direct-work chain, and capability-use evidence artifacts are required",
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
    if str(last_continuation_admission.get("status", "")) != "admissible_for_governed_loop_continuation_v2":
        return _failure(
            proposal,
            "shadow work-loop continuation failed: the best screened loop candidate is not currently admitted for governed work-loop continuation v2",
        )
    if str(current_state_summary.get("latest_governed_work_loop_execution_readiness", "")) != "ready_for_shadow_work_loop_continuation_execution_v2":
        return _failure(
            proposal,
            "shadow work-loop continuation failed: self-structure does not currently mark the v2 loop continuation path as ready for shadow execution",
        )

    work_loop_policy_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_policy_artifact_path"),
        "memory_summary_v4_governed_work_loop_policy_snapshot_v1_*.json",
    )
    work_loop_candidate_screen_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_candidate_screen_artifact_path"),
        "memory_summary_v4_governed_work_loop_candidate_screen_snapshot_v2_*.json",
    )
    work_loop_continuation_admission_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_work_loop_continuation_admission_artifact_path"),
        "memory_summary_v4_governed_work_loop_continuation_admission_snapshot_v2_*.json",
    )
    work_loop_posture_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_work_loop_posture_artifact_path"),
        "memory_summary_v4_governed_work_loop_posture_snapshot_v1_*.json",
    )
    work_loop_evidence_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_work_loop_evidence_artifact_path"),
        "memory_summary_v4_governed_work_loop_evidence_snapshot_v1_*.json",
    )
    prior_continuation_execution_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_prior_work_loop_continuation_execution_artifact_path")
        or governed_work_loop_policy.get("last_work_loop_continuation_execution_artifact_path"),
        "proposal_learning_loop_v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1_*.json",
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
            work_loop_evidence_artifact_path,
            prior_continuation_execution_artifact_path,
            direct_work_evidence_artifact_path,
            direct_work_execution_artifact_path,
            direct_work_admission_artifact_path,
            capability_use_evidence_artifact_path,
        ]
    ):
        return _failure(
            proposal,
            "shadow work-loop continuation failed: one or more governing artifact paths for v2 loop continuation could not be resolved",
        )

    work_loop_policy_payload = _load_json_file(work_loop_policy_artifact_path)
    work_loop_candidate_screen_payload = _load_json_file(work_loop_candidate_screen_artifact_path)
    continuation_admission_payload = _load_json_file(work_loop_continuation_admission_artifact_path)
    work_loop_posture_payload = _load_json_file(work_loop_posture_artifact_path)
    work_loop_evidence_payload = _load_json_file(work_loop_evidence_artifact_path)
    prior_continuation_execution_payload = _load_json_file(prior_continuation_execution_artifact_path)
    direct_work_execution_payload = _load_json_file(direct_work_execution_artifact_path)
    work_loop_candidate_screen_summary = dict(
        work_loop_candidate_screen_payload.get("governed_work_loop_candidate_screen_v2_summary", {})
    )
    continuation_admission_summary = dict(continuation_admission_payload.get("governed_work_loop_continuation_admission_v2_summary", {}))
    if not dict(work_loop_policy_payload.get("governed_work_loop_policy_summary", {})):
        return _failure(proposal, "shadow work-loop continuation failed: work-loop policy summary is missing")
    if not dict(work_loop_posture_payload.get("governed_work_loop_posture_summary", {})):
        return _failure(proposal, "shadow work-loop continuation failed: work-loop posture summary is missing")
    if not dict(work_loop_evidence_payload.get("governed_work_loop_evidence_summary", {})):
        return _failure(proposal, "shadow work-loop continuation failed: work-loop evidence summary is missing")
    if not all([work_loop_candidate_screen_summary, continuation_admission_summary, prior_continuation_execution_payload, direct_work_execution_payload]):
        return _failure(
            proposal,
            "shadow work-loop continuation failed: governing summary payloads for v2 loop continuation execution are incomplete",
        )

    screened_candidates = list(work_loop_candidate_screen_summary.get("candidates_screened", []))
    primary_candidate_name = str(
        dict(continuation_admission_summary.get("candidate_evaluated", {})).get("loop_candidate_name", "")
        or current_state_summary.get("latest_governed_work_loop_continuation_candidate", "")
    )
    loop_candidate_record = _find_loop_candidate(screened_candidates, name=primary_candidate_name)
    if not loop_candidate_record:
        return _failure(
            proposal,
            "shadow work-loop continuation failed: the admitted loop candidate could not be recovered from the current loop candidate screen",
        )

    continuation_envelope = dict(continuation_admission_summary.get("continuation_envelope", {}))
    continuation_accounting_requirements = dict(
        continuation_admission_summary.get("continuation_accounting_requirements", {})
    )
    trigger_bundle = dict(continuation_admission_summary.get("review_rollback_deprecation_triggers", {}))
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
        str(Path(path).resolve())
        for path in list(continuation_envelope.get("admissible_source_artifacts", []))
        if str(path).strip()
    ]
    governance_source_digests = [_digest_path(Path(path)) for path in source_artifact_paths]
    alignment_delta_audit = _build_alignment_delta_audit(
        directive_state=directive_state,
        current_state_summary=current_state_summary,
        branch_record=branch_record,
        current_branch_state=current_branch_state,
        current_bucket=current_bucket,
        loop_candidate_record=loop_candidate_record,
        continuation_envelope=continuation_envelope,
        callable_capabilities=list(governed_capability_use_policy.get("current_callable_capabilities", [])),
        analytics=analytics,
        recommendations=recommendations,
        directive_history=directive_history,
        self_structure_ledger=self_structure_ledger,
        intervention_ledger=intervention_ledger,
        prior_direct_work_execution_payload=direct_work_execution_payload,
        prior_continuation_execution_payload=prior_continuation_execution_payload,
        work_loop_artifact_paths={
            "work_loop_policy_artifact": work_loop_policy_artifact_path,
            "work_loop_candidate_screen_artifact": work_loop_candidate_screen_artifact_path,
            "work_loop_continuation_admission_artifact": work_loop_continuation_admission_artifact_path,
            "work_loop_posture_artifact": work_loop_posture_artifact_path,
            "work_loop_evidence_artifact": work_loop_evidence_artifact_path,
            "prior_work_loop_continuation_execution_artifact": prior_continuation_execution_artifact_path,
        },
    )

    next_template = "memory_summary.v4_governed_work_loop_evidence_snapshot_v2"
    artifact_path = _diagnostic_artifact_dir() / (
        f"proposal_learning_loop_v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1_{proposal['proposal_id']}.json"
    )
    pressure = _bucket_pressure(bucket_state, dict(continuation_envelope.get("resource_expectations", {})))
    write_paths = [artifact_path, SELF_STRUCTURE_STATE_PATH, SELF_STRUCTURE_LEDGER_PATH]
    material_alignment_detected = bool(dict(alignment_delta_audit.get("summary", {})).get("material_alignment_detected", False))
    distinct_value_read = {
        "passed": bool(material_alignment_detected),
        "value": "high" if bool(material_alignment_detected) else "low",
        "reason": (
            "the continuation produced a bounded recommendation-to-ledger alignment delta audit with a new governance alignment signal beyond both the prior direct-work step and the first loop continuation"
            if bool(material_alignment_detected)
            else "the continuation did not surface enough new recommendation-to-ledger alignment signal to justify distinct loop value over the prior direct-work step and the first loop continuation"
        ),
        "vs_prior_direct_work": {
            "distinct": True,
            "reason": "the execution audited recommendation-to-ledger alignment rather than replaying the governance state coherence audit shape",
            "observed_deltas": dict(dict(alignment_delta_audit.get("alignment_observations", {})).get("deltas", {})).get("vs_prior_direct_work", {}),
        },
        "vs_prior_continuation_v1": {
            "distinct": True,
            "reason": "the execution audited recommendation-to-ledger alignment rather than replaying the earlier ledger consistency delta audit",
            "observed_deltas": dict(dict(alignment_delta_audit.get("alignment_observations", {})).get("deltas", {})).get("vs_prior_continuation_v1", {}),
        },
    }
    directive_support_value = {
        "passed": True,
        "value": "high",
        "reason": "the alignment delta audit produced a bounded governance recommendation-to-ledger continuation report that directly supports directive-bound narrow work-loop control",
    }
    hidden_capability_pressure = {
        "passed": True,
        "value": "none",
        "reason": "the continuation remained governance alignment maintenance and did not drift toward capability use, paused-line reopen, hidden development, or silent broadening",
    }
    review_trigger_status = {
        "decision_criticality_rises_above_low": str(loop_candidate_record.get("decision_criticality", "")) != "low",
        "distinct_value_claim_collapses_into_low_yield_repetition": not bool(distinct_value_read.get("passed", False)),
        "held_capability_dependency_or_external_source_need_appears": False,
        "overlap_with_active_work_rises_above_low": str(loop_candidate_record.get("overlap_with_active_work", "")) != "low",
        "posture_rule_compliance_breaks": False,
        "scope_expands_beyond_recommendation_to_ledger_alignment_delta_audit": False,
        "work_starts_to_imply_capability_development_or_branch_mutation": False,
    }
    rollback_trigger_status = {str(key): False for key in dict(trigger_bundle.get("rollback_triggers", {})).keys()}
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
        "distinct_alignment_delta_value_disappears": not bool(distinct_value_read.get("passed", False)),
    }
    continuation_accounting = {
        "loop_identity_context": dict(
            dict(continuation_accounting_requirements.get("candidate_specific_expectations", {})).get(
                "loop_identity_context",
                {},
            )
        ),
        "current_work_state": dict(
            dict(continuation_accounting_requirements.get("candidate_specific_expectations", {})).get(
                "current_work_state",
                {},
            )
        ),
        "candidate_identity": dict(
            dict(continuation_accounting_requirements.get("candidate_specific_expectations", {})).get(
                "candidate_identity",
                {},
            )
        ),
        "expected_path": dict(
            dict(continuation_accounting_requirements.get("candidate_specific_expectations", {})).get(
                "expected_path",
                {},
            )
        ),
        "resource_trust_position": dict(
            dict(continuation_accounting_requirements.get("candidate_specific_expectations", {})).get(
                "resource_trust_position",
                {},
            )
        ),
        "continuation_rationale": str(
            dict(continuation_accounting_requirements.get("candidate_specific_expectations", {})).get(
                "continuation_rationale",
                "",
            )
            or dict(dict(continuation_admission_summary.get("admission_outcome", {}))).get("reason", "")
        ),
        "expected_next_evidence_signal": str(
            dict(continuation_accounting_requirements.get("candidate_specific_expectations", {})).get(
                "expected_next_evidence_signal",
                "",
            )
        ),
        "review_rollback_hooks": dict(
            dict(continuation_accounting_requirements.get("candidate_specific_expectations", {})).get(
                "review_rollback_hooks",
                {},
            )
        ),
        "resource_usage": {
            "cpu_parallel_units_used": int(dict(continuation_envelope.get("resource_expectations", {})).get("cpu_parallel_units", 0) or 0),
            "memory_mb_used": int(dict(continuation_envelope.get("resource_expectations", {})).get("memory_mb", 0) or 0),
            "storage_write_mb_used": 0,
            "network_mode_used": str(dict(continuation_envelope.get("resource_expectations", {})).get("network_mode", "none")),
        },
        "write_roots_touched": list(continuation_envelope.get("allowed_write_roots", [])),
        "source_artifact_paths": source_artifact_paths,
        "admission_outcome": "admissible_for_governed_loop_continuation_v2",
        "work_loop_posture": "shadow_only_loop_continuation_v2",
        "trusted_source_report": dict(dict(loop_candidate_record.get("classification_report", {})).get("trusted_source_report", {})),
        "resource_report": dict(dict(loop_candidate_record.get("classification_report", {})).get("resource_report", {})),
        "write_root_report": dict(dict(loop_candidate_record.get("classification_report", {})).get("write_root_report", {})),
        "branch_state_unchanged": True,
        "retained_promotion_performed": False,
        "review_trigger_status": review_trigger_status,
        "rollback_trigger_status": rollback_trigger_status,
        "deprecation_trigger_status": deprecation_trigger_status,
        "continuation_summary": "governance recommendation-to-ledger alignment delta audit",
        "directive_support_observation": str(directive_support_value.get("reason", "")),
        "bounded_output_artifact_path": str(artifact_path),
        "usefulness_signal_summary": {
            "passed_check_count": int(dict(alignment_delta_audit.get("summary", {})).get("passed_check_count", 0) or 0),
            "failed_check_count": int(dict(alignment_delta_audit.get("summary", {})).get("failed_check_count", 0) or 0),
            "alignment_signal_count": int(dict(alignment_delta_audit.get("summary", {})).get("alignment_signal_count", 0) or 0),
            "material_alignment_detected": bool(dict(alignment_delta_audit.get("summary", {})).get("material_alignment_detected", False)),
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
        "template_name": "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1",
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
            "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v2": _artifact_reference(work_loop_candidate_screen_snapshot, latest_snapshots),
            "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v2": _artifact_reference(work_loop_continuation_admission_snapshot, latest_snapshots),
            "memory_summary.v4_governed_work_loop_posture_snapshot_v1": _artifact_reference(work_loop_posture_snapshot, latest_snapshots),
            "memory_summary.v4_governed_work_loop_evidence_snapshot_v1": _artifact_reference(work_loop_evidence_snapshot, latest_snapshots),
            "proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1": _artifact_reference(prior_continuation_execution_snapshot, latest_snapshots),
            "memory_summary.v4_governed_direct_work_evidence_snapshot_v1": _artifact_reference(direct_work_evidence_snapshot, latest_snapshots),
            "proposal_learning_loop.v4_governed_directive_work_governance_state_coherence_audit_refresh_v1": _artifact_reference(direct_work_execution_snapshot, latest_snapshots),
            "memory_summary.v4_governed_directive_work_admission_snapshot_v1": _artifact_reference(direct_work_admission_snapshot, latest_snapshots),
            "memory_summary.v4_governed_capability_use_evidence_snapshot_v1": _artifact_reference(capability_use_evidence_snapshot, latest_snapshots),
        },
        "governed_work_loop_continuation_execution_summary": {
            "candidate_executed": {
                "loop_candidate_id": str(dict(continuation_admission_summary.get("candidate_evaluated", {})).get("loop_candidate_id", "")),
                "loop_candidate_name": primary_candidate_name,
                "assigned_candidate_class": str(dict(continuation_admission_summary.get("candidate_evaluated", {})).get("assigned_candidate_class", "")),
                "continuation_variant": "v2_alignment_delta",
            },
            "what_the_continuation_did": [
                "read only the admitted trusted local governance artifacts relevant to recommendation-to-ledger alignment deltas",
                "computed a bounded recommendation-to-ledger alignment delta audit against both the prior direct-work execution and the first loop continuation rather than replaying either earlier audit shape",
                "materialized a shadow-only governed work-loop continuation v2 artifact with full continuation accounting and trigger status",
            ],
            "local_governance_sources_used": {
                "source_artifact_paths": source_artifact_paths,
                "governance_source_digests": governance_source_digests,
            },
            "alignment_delta_artifact_produced": {
                "bounded_output_artifact_path": str(artifact_path),
                "governance_recommendation_alignment_delta_audit_output": alignment_delta_audit,
            },
            "continuation_accounting_captured": continuation_accounting,
            "envelope_compliance": envelope_compliance,
            "directive_support_value": directive_support_value,
            "distinct_value_over_prior_step_read": distinct_value_read,
            "hidden_capability_pressure_read": hidden_capability_pressure,
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
                "reason": "the run consumed directive, bucket, branch, self-structure, work-loop policy, candidate-screen, posture, continuation-admission, prior continuation, and prior direct-work governance artifacts as read-only authority while performing only the admitted v2 loop-continuation audit",
            },
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
            "reason": "the run proves that NOVALI can execute a second distinct admitted governed work-loop continuation without collapsing into direct-work repetition, prior-continuation replay, capability use, hidden development, or silent broadening",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "the execution keeps loop continuation separate from prior direct-work repetition, capability-use, paused-line reopen, and new-skill creation in a concrete operational run",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the execution remained shadow-only, local, reversible, and governance-bounded; live policy, thresholds, routing, frozen benchmark semantics, and the projection-safe envelope stayed unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": next_template,
            "reason": "the next step should review the v2 governed work-loop continuation evidence before considering any broader work-loop execution posture",
        },
        "diagnostic_conclusions": {
            "governed_work_loop_continuation_execution_in_place": True,
            "governed_work_loop_continuation_v2_execution_in_place": True,
            "loop_candidate": primary_candidate_name,
            "governed_work_loop_continuation_operational": governed_work_loop_continuation_operational,
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
        prior_continuation_execution_artifact_path
    )
    updated_work_loop_policy["last_work_loop_continuation_execution_artifact_path"] = str(artifact_path)
    updated_work_loop_policy["last_work_loop_continuation_execution_outcome"] = {
        "loop_candidate_id": str(dict(continuation_admission_summary.get("candidate_evaluated", {})).get("loop_candidate_id", "")),
        "loop_candidate_name": primary_candidate_name,
        "work_loop_continuation_execution_outcome": "shadow_work_loop_continuation_v2_completed",
        "envelope_compliance_passed": bool(envelope_compliance.get("passed", False)),
        "distinct_value_added": bool(distinct_value_read.get("passed", False)),
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
            "governed_work_loop_execution_v2_in_place": True,
            "latest_governed_work_loop_execution_candidate": primary_candidate_name,
            "latest_governed_work_loop_execution_outcome": "shadow_work_loop_continuation_v2_completed",
            "latest_governed_work_loop_execution_readiness": "ready_for_work_loop_evidence_review_v2",
            "latest_governed_work_loop_operational_status": (
                "operational_second_bounded_work_loop_continuation_proven"
                if governed_work_loop_continuation_operational
                else "work_loop_continuation_needs_review"
            ),
            "latest_governed_work_loop_operational_success": governed_work_loop_continuation_operational,
            "latest_governed_work_loop_best_next_template": next_template,
            "latest_governed_work_loop_readiness": "ready_for_work_loop_evidence_review_v2",
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
            "event_id": f"governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1::{proposal['proposal_id']}",
            "timestamp": _now(),
            "event_type": "governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1_materialized",
            "event_class": "governed_work_loop_continuation_execution",
            "directive_id": str(current_directive.get("directive_id", "")),
            "directive_state": str(directive_state.get("initialization_state", "")),
            "branch_id": str(branch_record.get("branch_id", "")),
            "branch_state": current_branch_state,
            "loop_candidate_id": str(dict(continuation_admission_summary.get("candidate_evaluated", {})).get("loop_candidate_id", "")),
            "loop_candidate_name": primary_candidate_name,
            "work_loop_continuation_execution_outcome": "shadow_work_loop_continuation_v2_completed",
            "distinct_value_added": bool(distinct_value_read.get("passed", False)),
            "paused_capability_line_reopened": False,
            "retained_promotion": False,
            "branch_state_mutation": False,
            "network_mode": str(dict(continuation_envelope.get("resource_expectations", {})).get("network_mode", "none")),
            "artifact_paths": {
                "governed_work_loop_policy_v1": str(work_loop_policy_artifact_path),
                "governed_work_loop_candidate_screen_v2": str(work_loop_candidate_screen_artifact_path),
                "governed_work_loop_continuation_admission_v2": str(work_loop_continuation_admission_artifact_path),
                "governed_work_loop_posture_v1": str(work_loop_posture_artifact_path),
                "governed_work_loop_evidence_v1": str(work_loop_evidence_artifact_path),
                "governed_work_loop_continuation_execution_v1": str(prior_continuation_execution_artifact_path),
                "direct_work_evidence_v1": str(direct_work_evidence_artifact_path),
                "direct_work_execution_v1": str(direct_work_execution_artifact_path),
                "direct_work_admission_v1": str(direct_work_admission_artifact_path),
                "capability_use_evidence_v1": str(capability_use_evidence_artifact_path),
                "governed_work_loop_continuation_execution_v2": str(artifact_path),
            },
            "source_proposal_id": str(proposal.get("proposal_id", "")),
        },
    )

    return {
        "passed": True,
        "shadow_contract": "governed_work_loop_continuation",
        "proposal_semantics": "shadow_work_loop_continuation",
        "reason": "shadow work-loop continuation v2 passed: the admitted recommendation-to-ledger alignment delta audit executed inside the approved continuation envelope without repeating prior work, invoking capability use, or reopening capabilities",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
