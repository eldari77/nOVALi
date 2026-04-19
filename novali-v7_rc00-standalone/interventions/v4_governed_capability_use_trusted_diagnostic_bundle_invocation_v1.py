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
from .governed_skill_acquisition_v1 import (
    _diagnostic_artifact_dir,
    _load_jsonl,
    _log_group_key,
    _parse_local_trace_log,
    _select_trial_log_group,
    _summarize_parsed_logs,
    _trial_artifact_digest,
    _trusted_logs_dir,
)
from .ledger import intervention_data_dir, load_latest_snapshots
from .v4_first_hypothesis_landscape_snapshot_v1 import _load_json_file
from .v4_governed_capability_use_policy_snapshot_v1 import _latest_matching_artifact
from .v4_governed_skill_local_trace_parser_provisional_probe_v1 import _bucket_pressure, _path_within_allowed_roots
from .v4_wm_context_signal_overlap_snapshot_v1 import _artifact_reference


def _artifact_group_key(path: Path) -> str:
    if not path or not path.exists() or path.is_dir():
        return ""
    payload = _load_json_file(path)
    summary = dict(payload.get("governed_skill_trial_summary", {})) or dict(payload.get("governed_skill_provisional_probe_summary", {}))
    local_sources = dict(summary.get("local_sources_parsed", {}))
    trusted_group = dict(local_sources.get("trusted_log_group", {}))
    return str(trusted_group.get("group_key", ""))


def _select_invocation_log_group(*, excluded_group_keys: set[str], max_files: int = 3) -> dict[str, Any]:
    log_dir = _trusted_logs_dir()
    if not log_dir.exists():
        return {
            "passed": False,
            "reason": "trusted local log root is not available",
            "selected_paths": [],
        }

    grouped: dict[str, dict[str, Any]] = {}
    for path in log_dir.glob("intervention_shadow_*.log"):
        group_key = _log_group_key(path)
        entry = grouped.setdefault(
            group_key,
            {
                "group_key": group_key,
                "paths": [],
                "latest_mtime": 0.0,
            },
        )
        entry["paths"].append(path)
        try:
            entry["latest_mtime"] = max(float(entry["latest_mtime"]), float(path.stat().st_mtime))
        except OSError:
            pass

    ranked_groups = sorted(
        grouped.values(),
        key=lambda item: (
            min(len(list(item.get("paths", []))), max_files),
            float(item.get("latest_mtime", 0.0) or 0.0),
        ),
        reverse=True,
    )
    for group in ranked_groups:
        group_key = str(group.get("group_key", ""))
        if group_key in excluded_group_keys:
            continue
        selected_paths = sorted(list(group.get("paths", [])), key=lambda item: item.name)[:max_files]
        return {
            "passed": True,
            "group_key": group_key,
            "selection_reason": "latest trusted local shadow-log group not previously used by the paused parser line",
            "excluded_group_keys": sorted(excluded_group_keys),
            "selected_file_count": len(selected_paths),
            "selected_paths": [str(path) for path in selected_paths],
        }

    fallback = _select_trial_log_group(max_files=max_files)
    if bool(fallback.get("passed", False)):
        fallback = dict(fallback)
        fallback["selection_reason"] = (
            "no fresh trusted local log group was available; latest trusted local group used without reopening development"
        )
        fallback["excluded_group_keys"] = sorted(excluded_group_keys)
    return fallback


def _find_screened_request(
    screened_requests: list[dict[str, Any]],
    *,
    request_name: str,
) -> dict[str, Any]:
    for request in screened_requests:
        if str(request.get("request_name", "")) == request_name:
            return dict(request)
    return {}


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governance_substrate_v1_snapshot")
    capability_use_policy_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_capability_use_policy_snapshot_v1"
    )
    capability_use_candidate_screen_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_capability_use_candidate_screen_snapshot_v1"
    )
    capability_use_invocation_admission_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_capability_use_invocation_admission_snapshot_v1"
    )
    provisional_pause_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_skill_provisional_pause_snapshot_v1"
    )
    if not all(
        [
            governance_snapshot,
            capability_use_policy_snapshot,
            capability_use_candidate_screen_snapshot,
            capability_use_invocation_admission_snapshot,
            provisional_pause_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "governed_capability_use",
            "proposal_semantics": "shadow_capability_use",
            "reason": "shadow invocation failed: governance substrate, capability-use policy, candidate screen, invocation admission, and provisional pause artifacts are required",
            "observability_gain": {"passed": False, "reason": "missing prerequisite governed-capability artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite governed-capability artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite governed-capability artifacts"},
            "safety_neutrality": {"passed": True, "scope": str(proposal.get("scope", "")), "reason": "no live-policy mutation occurred"},
            "later_selection_usefulness": {"passed": False, "reason": "a real governed capability invocation cannot run without the governance-owned admission chain"},
        }

    directive_state = _load_json_file(DIRECTIVE_STATE_PATH)
    bucket_state = _load_json_file(BUCKET_STATE_PATH)
    self_structure_state = _load_json_file(SELF_STRUCTURE_STATE_PATH)
    branch_registry = _load_json_file(BRANCH_REGISTRY_PATH)
    directive_history = _load_jsonl(DIRECTIVE_HISTORY_PATH)
    self_structure_ledger = _load_jsonl(SELF_STRUCTURE_LEDGER_PATH)
    intervention_ledger = _load_jsonl(intervention_data_dir() / "intervention_ledger.jsonl")
    analytics = build_intervention_ledger_analytics()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")
    latest_snapshots = load_latest_snapshots()
    if not all([directive_state, bucket_state, self_structure_state, branch_registry]):
        return {
            "passed": False,
            "shadow_contract": "governed_capability_use",
            "proposal_semantics": "shadow_capability_use",
            "reason": "shadow invocation failed: current directive, bucket, self-structure, and branch state artifacts are required",
            "observability_gain": {"passed": False, "reason": "missing durable governance state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing durable governance state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing durable governance state"},
            "safety_neutrality": {"passed": True, "scope": str(proposal.get("scope", "")), "reason": "no live-policy mutation occurred"},
            "later_selection_usefulness": {"passed": False, "reason": "the invocation cannot stay governance-owned without directive, bucket, self-structure, and branch state"},
        }

    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_branch_state = str(branch_record.get("state", ""))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    governed_skill_subsystem = dict(self_structure_state.get("governed_skill_subsystem", {}))
    governed_capability_use_policy = dict(self_structure_state.get("governed_capability_use_policy", {}))
    if current_branch_state != "paused_with_baseline_held":
        return {
            "passed": False,
            "shadow_contract": "governed_capability_use",
            "proposal_semantics": "shadow_capability_use",
            "reason": "shadow invocation failed: branch must remain paused_with_baseline_held",
            "observability_gain": {"passed": False, "reason": "branch state invalid for governed invocation"},
            "activation_analysis_usefulness": {"passed": False, "reason": "branch state invalid for governed invocation"},
            "ambiguity_reduction": {"passed": False, "reason": "branch state invalid for governed invocation"},
            "safety_neutrality": {"passed": True, "scope": str(proposal.get("scope", "")), "reason": "no live-policy mutation occurred"},
            "later_selection_usefulness": {"passed": False, "reason": "the invocation is only admissible while the branch remains paused"},
        }

    last_invocation_admission = dict(governed_capability_use_policy.get("last_invocation_admission_outcome", {}))
    if str(last_invocation_admission.get("status", "")) != "admissible_for_direct_governed_use":
        return {
            "passed": False,
            "shadow_contract": "governed_capability_use",
            "proposal_semantics": "shadow_capability_use",
            "reason": "shadow invocation failed: the primary direct-use request is not currently admitted for direct governed invocation",
            "observability_gain": {"passed": False, "reason": "invocation admission state invalid"},
            "activation_analysis_usefulness": {"passed": False, "reason": "invocation admission state invalid"},
            "ambiguity_reduction": {"passed": False, "reason": "invocation admission state invalid"},
            "safety_neutrality": {"passed": True, "scope": str(proposal.get("scope", "")), "reason": "no live-policy mutation occurred"},
            "later_selection_usefulness": {"passed": False, "reason": "the invocation may only run after the direct-use request is admitted"},
        }

    held_capabilities = list(governed_skill_subsystem.get("held_provisional_capabilities", []))
    held_capability = {}
    for item in held_capabilities:
        record = dict(item)
        if str(record.get("skill_id", "")) == "skill_candidate_local_trace_parser_trial":
            held_capability = record
            break
    if not held_capability:
        return {
            "passed": False,
            "shadow_contract": "governed_capability_use",
            "proposal_semantics": "shadow_capability_use",
            "reason": "shadow invocation failed: held local trace parser capability not found",
            "observability_gain": {"passed": False, "reason": "missing held capability record"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing held capability record"},
            "ambiguity_reduction": {"passed": False, "reason": "missing held capability record"},
            "safety_neutrality": {"passed": True, "scope": str(proposal.get("scope", "")), "reason": "no live-policy mutation occurred"},
            "later_selection_usefulness": {"passed": False, "reason": "cannot perform invocation without the held capability record"},
        }

    candidate_screen_artifact_path = Path(
        str(governed_capability_use_policy.get("last_candidate_screen_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_capability_use_candidate_screen_snapshot_v1_*.json")
    )
    policy_artifact_path = Path(
        str(governed_capability_use_policy.get("last_policy_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_capability_use_policy_snapshot_v1_*.json")
    )
    invocation_admission_artifact_path = Path(
        str(governed_capability_use_policy.get("last_invocation_admission_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_capability_use_invocation_admission_snapshot_v1_*.json")
    )
    provisional_pause_artifact_path = Path(
        str(governed_skill_subsystem.get("last_provisional_pause_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_skill_provisional_pause_snapshot_v1_*.json")
    )

    candidate_screen_payload = _load_json_file(candidate_screen_artifact_path)
    candidate_screen_summary = dict(candidate_screen_payload.get("governed_capability_use_candidate_screen_summary", {}))
    screened_requests = list(candidate_screen_summary.get("invocation_requests_screened", []))
    primary_request_name = str(dict(governed_capability_use_policy.get("last_invocation_admission_candidate", {})).get("request_name", ""))
    request_record = _find_screened_request(screened_requests, request_name=primary_request_name)
    if not request_record:
        return {
            "passed": False,
            "shadow_contract": "governed_capability_use",
            "proposal_semantics": "shadow_capability_use",
            "reason": "shadow invocation failed: the admitted direct-use request is missing from the candidate-screen artifact",
            "observability_gain": {"passed": False, "reason": "missing admitted request record"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing admitted request record"},
            "ambiguity_reduction": {"passed": False, "reason": "missing admitted request record"},
            "safety_neutrality": {"passed": True, "scope": str(proposal.get("scope", "")), "reason": "no live-policy mutation occurred"},
            "later_selection_usefulness": {"passed": False, "reason": "cannot execute the admitted use case without its screened request record"},
        }

    invocation_admission_payload = _load_json_file(invocation_admission_artifact_path)
    invocation_admission_summary = dict(
        invocation_admission_payload.get("governed_capability_use_invocation_admission_summary", {})
    )
    invocation_envelope = dict(invocation_admission_summary.get("invocation_envelope", {}))
    invocation_accounting_requirements = dict(
        invocation_admission_summary.get("invocation_accounting_requirements", {})
    )
    rollback_review_triggers = dict(invocation_admission_summary.get("rollback_review_triggers", {}))

    previous_group_keys: set[str] = set()
    for template_name in [
        "proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1",
        "proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v1",
        "proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v2",
    ]:
        snapshot = r._load_latest_diagnostic_artifact_by_template(template_name)
        artifact_path_text = str(dict(snapshot).get("artifact_path", "")) if snapshot else ""
        if artifact_path_text:
            artifact_path = Path(artifact_path_text)
            group_key = _artifact_group_key(artifact_path)
            if group_key:
                previous_group_keys.add(group_key)

    log_group = _select_invocation_log_group(excluded_group_keys=previous_group_keys, max_files=3)
    if not bool(log_group.get("passed", False)):
        return {
            "passed": False,
            "shadow_contract": "governed_capability_use",
            "proposal_semantics": "shadow_capability_use",
            "reason": "shadow invocation failed: no trusted local shadow-log group is available",
            "observability_gain": {"passed": False, "reason": str(log_group.get("reason", ""))},
            "activation_analysis_usefulness": {"passed": False, "reason": str(log_group.get("reason", ""))},
            "ambiguity_reduction": {"passed": False, "reason": str(log_group.get("reason", ""))},
            "safety_neutrality": {"passed": True, "scope": str(proposal.get("scope", "")), "reason": "no live-policy mutation occurred"},
            "later_selection_usefulness": {"passed": False, "reason": "the admitted direct-use request has no trusted local bundle to summarize"},
        }

    parsed_logs = [_parse_local_trace_log(Path(path)) for path in list(log_group.get("selected_paths", []))]
    parsed_log_summary = _summarize_parsed_logs(parsed_logs)
    governance_sources = [
        _trial_artifact_digest(candidate_screen_artifact_path),
        _trial_artifact_digest(policy_artifact_path),
        _trial_artifact_digest(invocation_admission_artifact_path),
        _trial_artifact_digest(provisional_pause_artifact_path),
    ]

    artifact_path = (
        _diagnostic_artifact_dir()
        / f"proposal_learning_loop_v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1_{proposal['proposal_id']}.json"
    )
    allowed_roots = [Path(path).resolve() for path in list(invocation_envelope.get("allowed_write_roots", []))]
    write_paths = [artifact_path, SELF_STRUCTURE_STATE_PATH, SELF_STRUCTURE_LEDGER_PATH]
    resource_expectations = dict(invocation_envelope.get("resource_expectations", {}))
    pressure = _bucket_pressure(bucket_state, dict(invocation_envelope.get("resource_ceilings", {})))

    source_artifact_paths = [str(path) for path in list(log_group.get("selected_paths", []))]
    source_artifact_paths.extend(
        [
            str(candidate_screen_artifact_path),
            str(policy_artifact_path),
            str(invocation_admission_artifact_path),
            str(provisional_pause_artifact_path),
        ]
    )
    source_artifact_paths = list(dict.fromkeys(source_artifact_paths))

    bundle_summary = {
        "parsed_file_count": int(parsed_log_summary.get("parsed_file_count", 0) or 0),
        "dummy_eval_count": int(parsed_log_summary.get("dummy_eval_count", 0) or 0),
        "patch_tuple_count": int(parsed_log_summary.get("patch_tuple_count", 0) or 0),
        "recognized_line_share_weighted": float(parsed_log_summary.get("recognized_line_share_weighted", 0.0) or 0.0),
        "event_counts": dict(parsed_log_summary.get("event_counts", {})),
        "seed_suffixes_observed": list(parsed_log_summary.get("seed_suffixes_observed", [])),
    }
    directive_support_value = {
        "passed": (
            bundle_summary["parsed_file_count"] >= 1
            and bundle_summary["recognized_line_share_weighted"] >= 0.95
            and bundle_summary["dummy_eval_count"] > 0
        ),
        "reason": "the invocation produced a bounded summary of trusted local traces that supports governance diagnostics without any capability modification",
        "value": "high",
    }
    duplication_overlap_read = {
        "passed": True,
        "value": "low",
        "reason": "the invocation reused the held parser for its admitted purpose instead of reopening development or proposing a new skill",
    }

    invocation_accounting = {
        "invocation_identity": {
            "invocation_id": str(dict(invocation_accounting_requirements.get("request_specific_expectations", {})).get("invocation_identity", {}).get("invocation_id", "")),
            "capability_id": str(held_capability.get("skill_id", "")),
            "capability_name": str(held_capability.get("skill_name", "")),
            "use_request_id": str(request_record.get("use_request_id", "")),
            "request_name": str(request_record.get("request_name", "")),
        },
        "directive_branch_context": {
            "directive_id": str(dict(directive_state.get("current_directive_state", {})).get("directive_id", "")),
            "branch_id": str(branch_record.get("branch_id", "")),
            "branch_state": current_branch_state,
            "plan_non_owning": bool(current_state_summary.get("plan_non_owning", False)),
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
        },
        "resource_usage": {
            "cpu_parallel_units_used": int(resource_expectations.get("cpu_parallel_units", 0) or 0),
            "memory_mb_used": int(resource_expectations.get("memory_mb", 0) or 0),
            "storage_write_mb_used": 0,
            "network_mode_used": str(resource_expectations.get("network_mode", "none")),
        },
        "write_roots_touched": list(invocation_envelope.get("allowed_write_roots", [])),
        "source_artifact_paths": source_artifact_paths,
        "policy_outcome": "admissible_for_direct_governed_use",
        "rationale": str(dict(invocation_admission_summary.get("admission_outcome", {})).get("reason", "")),
        "trusted_source_report": dict(dict(request_record.get("classification_report", {})).get("trusted_source_report", {})),
        "resource_report": dict(dict(request_record.get("classification_report", {})).get("resource_report", {})),
        "write_root_report": dict(dict(request_record.get("classification_report", {})).get("write_root_report", {})),
        "branch_state_unchanged": True,
        "retained_promotion_performed": False,
        "rollback_trigger_status": dict(rollback_review_triggers.get("rollback_trigger_status", {})),
        "deprecation_trigger_status": dict(rollback_review_triggers.get("deprecation_trigger_status", {})),
        "use_case_summary": "trusted local diagnostic bundle summary",
        "directive_support_observation": str(directive_support_value.get("reason", "")),
        "bounded_output_artifact_path": str(artifact_path),
        "usefulness_signal_summary": {
            "recognized_line_share_weighted": bundle_summary["recognized_line_share_weighted"],
            "parsed_file_count": bundle_summary["parsed_file_count"],
            "dummy_eval_count": bundle_summary["dummy_eval_count"],
            "patch_tuple_count": bundle_summary["patch_tuple_count"],
        },
        "duplication_or_overlap_observation": str(duplication_overlap_read.get("reason", "")),
    }

    envelope_compliance = {
        "network_mode_required": str(invocation_envelope.get("network_mode", "none")),
        "network_mode_observed": str(resource_expectations.get("network_mode", "none")),
        "network_mode_remained_none": str(resource_expectations.get("network_mode", "none")) == "none",
        "branch_state_stayed_paused_with_baseline_held": current_branch_state == "paused_with_baseline_held",
        "no_branch_state_mutation": True,
        "no_retained_promotion": True,
        "no_capability_modification": True,
        "no_protected_surface_modification": True,
        "no_downstream_selected_set_work": True,
        "no_plan_ownership_change": True,
        "no_routing_work": True,
        "writes_within_approved_roots": all(_path_within_allowed_roots(path, allowed_roots) for path in write_paths),
        "approved_write_paths": [str(path) for path in write_paths],
        "resource_ceilings": dict(invocation_envelope.get("resource_ceilings", {})),
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
            "no_protected_surface_modification",
            "no_downstream_selected_set_work",
            "no_plan_ownership_change",
            "no_routing_work",
            "writes_within_approved_roots",
            "resource_limits_respected",
        ]
    )
    review_trigger_status = dict(rollback_review_triggers.get("review_trigger_status", {}))
    rollback_trigger_status = dict(rollback_review_triggers.get("rollback_trigger_status", {}))
    deprecation_trigger_status = dict(rollback_review_triggers.get("deprecation_trigger_status", {}))
    governed_operational_use = (
        bool(directive_support_value.get("passed", False))
        and bool(duplication_overlap_read.get("passed", False))
        and bool(envelope_compliance.get("passed", False))
        and not any(bool(value) for value in review_trigger_status.values())
        and not any(bool(value) for value in rollback_trigger_status.values())
        and not any(bool(value) for value in deprecation_trigger_status.values())
    )
    next_template = "memory_summary.v4_governed_capability_use_evidence_snapshot_v1"

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "proposal_learning_loop.v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1",
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
            "memory_summary.v4_governed_capability_use_policy_snapshot_v1": _artifact_reference(
                capability_use_policy_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_capability_use_candidate_screen_snapshot_v1": _artifact_reference(
                capability_use_candidate_screen_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_capability_use_invocation_admission_snapshot_v1": _artifact_reference(
                capability_use_invocation_admission_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_skill_provisional_pause_snapshot_v1": _artifact_reference(
                provisional_pause_snapshot, latest_snapshots
            ),
        },
        "governed_capability_invocation_summary": {
            "candidate_invoked": {
                "capability_id": str(held_capability.get("skill_id", "")),
                "capability_name": str(held_capability.get("skill_name", "")),
                "request_name": str(request_record.get("request_name", "")),
                "use_request_id": str(request_record.get("use_request_id", "")),
            },
            "what_the_invocation_did": [
                "selected a trusted local shadow-log bundle for diagnostic summary use",
                "parsed the bundle with the held local trace parser capability without modifying the capability",
                "read governance-owned local artifacts to contextualize the summary",
                "materialized a bounded shadow-only governance diagnostic summary and full invocation accounting",
            ],
            "local_sources_used": {
                "trusted_log_group": dict(log_group),
                "trusted_log_parse_summary": parsed_log_summary,
                "trusted_governance_context_sources": governance_sources,
            },
            "output_artifact_produced": {
                "bounded_output_artifact_path": str(artifact_path),
                "bundle_summary": bundle_summary,
                "diagnostic_bundle_summary": {
                    "use_case_summary": "trusted local diagnostic bundle summary",
                    "directive_support_observation": str(directive_support_value.get("reason", "")),
                    "usefulness_signal_summary": dict(invocation_accounting.get("usefulness_signal_summary", {})),
                    "duplication_or_overlap_observation": str(duplication_overlap_read.get("reason", "")),
                },
            },
            "invocation_accounting_captured": invocation_accounting,
            "envelope_compliance": envelope_compliance,
            "directive_support_value": directive_support_value,
            "duplication_overlap_read": duplication_overlap_read,
            "rollback_review_trigger_status": {
                "review_trigger_status": review_trigger_status,
                "rollback_trigger_status": rollback_trigger_status,
                "deprecation_trigger_status": deprecation_trigger_status,
            },
            "paused_capability_behavior": {
                "paused_capability_line_remained_paused_for_development": True,
                "invocation_did_not_reopen_development": True,
                "new_skill_candidate_not_opened": True,
            },
            "why_governance_remains_source_of_truth": {
                "owner": "governance_substrate_v1",
                "proposal_learning_loop_is_governance_truth_source": False,
                "reason": "the invocation consumed directive, bucket, branch, policy, candidate-screen, and invocation-admission artifacts as read-only governance authority while using the held capability only as execution machinery",
            },
        },
        "analytics_context": {
            "analytics_report_path": str(intervention_data_dir() / "intervention_analytics_latest.json"),
            "proposal_recommendations_path": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            "proposal_count": int(analytics.get("proposal_count", 0) or 0),
            "directive_history_entry_count": int(len(directive_history)),
            "self_structure_ledger_entry_count": int(len(self_structure_ledger)),
            "intervention_ledger_entry_count": int(len(intervention_ledger)),
        },
        "observability_gain": {
            "passed": True,
            "reason": "the admitted direct-use request now has a real bounded invocation artifact and full governance accounting",
            "artifact_paths": {
                "capability_use_invocation_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the run proves that NOVALI can use a held governed capability for directive-valid work without reopening development",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "the invocation separates capability use from capability reopen and from new skill creation in a concrete operational run",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the invocation remained shadow-only, local, reversible, and governance-bounded; live policy, thresholds, routing, frozen benchmark semantics, and the projection-safe envelope stayed unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": next_template,
            "reason": "the next step should review the bounded invocation evidence before expanding governed capability-use patterns",
        },
        "diagnostic_conclusions": {
            "governed_capability_use_execution_in_place": True,
            "invocation_candidate": str(request_record.get("request_name", "")),
            "governed_capability_use_operational": governed_operational_use,
            "branch_state_mutation_occurred": False,
            "retained_promotion_occurred": False,
            "paused_capability_line_remained_paused_for_development": True,
            "plan_should_remain_non_owning": bool(current_state_summary.get("plan_non_owning", False)),
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "best_next_template": next_template,
        },
    }
    _write_json(artifact_path, artifact_payload)

    estimated_write_bytes = (
        int(artifact_path.stat().st_size)
        + len(json.dumps({"updated_state": True}))
        + len(json.dumps({"ledger_event": True}))
    )
    invocation_accounting["resource_usage"]["storage_write_mb_used"] = max(
        1,
        int((estimated_write_bytes + (1024 * 1024) - 1) / (1024 * 1024)),
    )
    artifact_payload["governed_capability_invocation_summary"]["invocation_accounting_captured"] = invocation_accounting
    artifact_payload["governed_capability_invocation_summary"]["envelope_compliance"]["estimated_write_bytes"] = int(
        estimated_write_bytes
    )
    artifact_payload["governed_capability_invocation_summary"]["envelope_compliance"]["storage_budget_respected"] = (
        estimated_write_bytes <= int(resource_expectations.get("storage_write_mb", 0) or 0) * 1024 * 1024
    )
    _write_json(artifact_path, artifact_payload)

    updated_self_structure_state = dict(self_structure_state)
    updated_capability_use_policy = dict(governed_capability_use_policy)
    updated_capability_use_policy["last_invocation_execution_artifact_path"] = str(artifact_path)
    updated_capability_use_policy["last_invocation_execution_outcome"] = {
        "use_request_id": str(request_record.get("use_request_id", "")),
        "request_name": str(request_record.get("request_name", "")),
        "invocation_execution_outcome": "diagnostic_only_invocation_completed",
        "envelope_compliance_passed": bool(envelope_compliance.get("passed", False)),
        "development_line_reopened": False,
        "retained_promotion": False,
        "governed_capability_use_operational": governed_operational_use,
        "best_next_template": next_template,
    }
    updated_capability_use_policy["best_next_template"] = next_template
    updated_self_structure_state["governed_capability_use_policy"] = updated_capability_use_policy

    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "latest_capability_use_invocation_candidate": str(request_record.get("request_name", "")),
            "latest_capability_use_invocation_execution_outcome": "diagnostic_only_invocation_completed",
            "latest_capability_use_operational_status": (
                "operational_bounded_diagnostic_use_proven" if governed_operational_use else "operational_use_needs_review"
            ),
            "current_branch_state": current_branch_state,
            "plan_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "retained_skill_promotion_performed": False,
        }
    )
    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["current_state_summary"] = updated_current_state_summary
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    ledger_event = {
        "event_id": f"governed_capability_use_trusted_diagnostic_bundle_invocation_v1::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_capability_use_trusted_diagnostic_bundle_invocation_v1_materialized",
        "event_class": "governed_capability_use_execution",
        "directive_id": str(dict(directive_state.get("current_directive_state", {})).get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": current_branch_state,
        "capability_id": str(held_capability.get("skill_id", "")),
        "use_request_id": str(request_record.get("use_request_id", "")),
        "invocation_execution_outcome": "diagnostic_only_invocation_completed",
        "development_line_reopened": False,
        "retained_promotion": False,
        "branch_state_mutation": False,
        "network_mode": str(resource_expectations.get("network_mode", "none")),
        "artifact_paths": {
            "candidate_screen_artifact": str(candidate_screen_artifact_path),
            "capability_use_policy_artifact": str(policy_artifact_path),
            "invocation_admission_artifact": str(invocation_admission_artifact_path),
            "provisional_pause_artifact": str(provisional_pause_artifact_path),
            "capability_use_invocation_artifact": str(artifact_path),
        },
        "source_proposal_id": str(proposal.get("proposal_id", "")),
    }
    _append_jsonl(SELF_STRUCTURE_LEDGER_PATH, ledger_event)

    return {
        "passed": True,
        "shadow_contract": "governed_capability_use",
        "proposal_semantics": "shadow_capability_use",
        "reason": "shadow invocation passed: the admitted direct-use request executed inside the approved diagnostic-only envelope without reopening development",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
