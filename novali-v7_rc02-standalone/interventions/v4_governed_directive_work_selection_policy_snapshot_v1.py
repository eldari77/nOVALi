from __future__ import annotations

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
from .v4_governed_capability_use_policy_snapshot_v1 import _latest_matching_artifact
from .v4_wm_context_signal_overlap_snapshot_v1 import _artifact_reference


def _trusted_sources_allowed(
    requested_sources: list[str],
    directive_current: dict[str, Any],
    bucket_current: dict[str, Any],
) -> dict[str, Any]:
    directive_sources = set(str(item) for item in list(directive_current.get("trusted_sources", [])))
    bucket_sources = set(str(item) for item in list(dict(bucket_current).get("trusted_sources", [])))
    allowed_sources = sorted(directive_sources & bucket_sources) or sorted(bucket_sources)
    requested = sorted(set(str(item) for item in requested_sources))
    missing = sorted(set(requested) - set(allowed_sources))
    return {
        "passed": not missing,
        "allowed_sources": allowed_sources,
        "requested_sources": requested,
        "missing_sources": missing,
        "reason": (
            "requested trusted sources stay inside the current directive and bucket policy"
            if not missing
            else "requested trusted sources extend beyond the current directive and bucket policy"
        ),
    }


def _resource_request_within_bucket(
    requested_resources: dict[str, Any],
    bucket_current: dict[str, Any],
) -> dict[str, Any]:
    bucket_cpu_limit = int(dict(bucket_current.get("cpu_limit", {})).get("max_parallel_processes", 0) or 0)
    bucket_memory_limit = int(dict(bucket_current.get("memory_limit", {})).get("max_working_set_mb", 0) or 0)
    bucket_storage_limit = int(dict(bucket_current.get("storage_limit", {})).get("max_write_mb_per_action", 0) or 0)
    bucket_network_modes = set(
        str(item) for item in list(dict(bucket_current.get("network_policy", {})).get("allowed_network_modes", []))
    )

    requested_cpu = int(requested_resources.get("cpu_parallel_units", 0) or 0)
    requested_memory = int(requested_resources.get("memory_mb", 0) or 0)
    requested_storage = int(requested_resources.get("storage_write_mb", 0) or 0)
    requested_network_mode = str(requested_resources.get("network_mode", "none"))

    cpu_ok = requested_cpu <= bucket_cpu_limit
    memory_ok = requested_memory <= bucket_memory_limit
    storage_ok = requested_storage <= bucket_storage_limit
    network_ok = requested_network_mode in bucket_network_modes
    return {
        "passed": bool(cpu_ok and memory_ok and storage_ok and network_ok),
        "requested_resources": {
            "cpu_parallel_units": requested_cpu,
            "memory_mb": requested_memory,
            "storage_write_mb": requested_storage,
            "network_mode": requested_network_mode,
        },
        "bucket_limits": {
            "cpu_parallel_units": bucket_cpu_limit,
            "memory_mb": bucket_memory_limit,
            "storage_write_mb": bucket_storage_limit,
            "network_modes": sorted(bucket_network_modes),
        },
        "within_limits": {
            "cpu": bool(cpu_ok),
            "memory": bool(memory_ok),
            "storage": bool(storage_ok),
            "network": bool(network_ok),
        },
    }


def _write_roots_allowed(requested_write_roots: list[str], allowed_write_roots: list[str]) -> dict[str, Any]:
    allowed = set(str(item) for item in allowed_write_roots)
    requested = sorted(set(str(item) for item in requested_write_roots))
    disallowed = sorted(set(requested) - allowed)
    return {
        "passed": not disallowed,
        "allowed_write_roots": sorted(allowed),
        "requested_write_roots": requested,
        "disallowed_write_roots": disallowed,
    }


def _find_capability(capabilities: list[dict[str, Any]], capability_id: str) -> dict[str, Any]:
    for item in capabilities:
        record = dict(item)
        if str(record.get("capability_id", "")) == str(capability_id):
            return record
    return {}


def _classify_work_item(
    work_item: dict[str, Any],
    *,
    directive_current: dict[str, Any],
    bucket_current: dict[str, Any],
    current_branch_state: str,
    allowed_write_roots: list[str],
    callable_capabilities: list[dict[str, Any]],
    plan_non_owning: bool,
    routing_deferred: bool,
) -> dict[str, Any]:
    trusted_source_report = _trusted_sources_allowed(
        list(work_item.get("trusted_sources", [])),
        directive_current,
        bucket_current,
    )
    resource_report = _resource_request_within_bucket(
        dict(work_item.get("expected_resources", {})),
        bucket_current,
    )
    write_root_report = _write_roots_allowed(
        list(work_item.get("expected_write_roots", [])),
        allowed_write_roots,
    )

    directive_relevance = str(work_item.get("directive_relevance", "none"))
    support_vs_drift = str(work_item.get("support_vs_drift", "drift"))
    reversibility = str(work_item.get("reversibility", "low"))
    governance_observability = str(work_item.get("governance_observability", "low"))
    decision_criticality = str(work_item.get("decision_criticality", "low"))
    overlap_with_active_work = str(work_item.get("overlap_with_active_work", "low"))
    bounded_context = bool(work_item.get("bounded_context", True))
    existing_capability_id = str(work_item.get("existing_capability_id", ""))
    capability_family_fit = bool(work_item.get("capability_family_fit", False))
    requires_capability_use_admission = bool(work_item.get("requires_capability_use_admission", False))
    requires_capability_modification = bool(work_item.get("requires_capability_modification", False))
    new_bounded_use_case = bool(work_item.get("new_bounded_use_case", False))
    new_skill_family_required = bool(work_item.get("new_skill_family_required", False))

    matching_capability = _find_capability(callable_capabilities, existing_capability_id) if existing_capability_id else {}
    hidden_development_pressure = bool(existing_capability_id and (requires_capability_modification or new_bounded_use_case))

    blocked_reasons: list[str] = []
    if not trusted_source_report["passed"]:
        blocked_reasons.append("trusted-source policy violated")
    if not resource_report["passed"]:
        blocked_reasons.append("requested resources exceed current bucket limits")
    if not write_root_report["passed"]:
        blocked_reasons.append("requested write roots exceed the currently admitted diagnostic roots")
    if str(current_branch_state) != "paused_with_baseline_held":
        blocked_reasons.append("branch state is not paused_with_baseline_held")
    if directive_relevance not in {"high", "medium"}:
        blocked_reasons.append("directive relevance is too weak")
    if support_vs_drift != "support":
        blocked_reasons.append("the work item looks more like drift than directive support")
    if reversibility not in {"high", "medium"}:
        blocked_reasons.append("the work item is not sufficiently reversible")
    if governance_observability not in {"high", "medium"}:
        blocked_reasons.append("governance observability is too weak")
    if not bounded_context:
        blocked_reasons.append("context exploration is not bounded enough")
    if not plan_non_owning:
        blocked_reasons.append("plan_ non-owning guard no longer holds")
    if not routing_deferred:
        blocked_reasons.append("routing is no longer deferred")
    if bool(work_item.get("touches_protected_surface", False)):
        blocked_reasons.append("protected-surface work requested")
    if bool(work_item.get("touches_downstream_selected_set", False)):
        blocked_reasons.append("downstream selected-set work requested")
    if bool(work_item.get("touches_plan_ownership", False)):
        blocked_reasons.append("plan_ ownership change requested")
    if bool(work_item.get("touches_routing", False)):
        blocked_reasons.append("routing work requested")
    if bool(work_item.get("touches_branch_state", False)):
        blocked_reasons.append("branch-state mutation requested")
    if bool(work_item.get("unbounded_contextual_exploration", False)):
        blocked_reasons.append("unbounded contextual exploration requested")

    if blocked_reasons:
        outcome = "defer_or_block_work_candidate"
        reason = "; ".join(blocked_reasons)
    elif hidden_development_pressure:
        outcome = "reopen_required_work_candidate"
        reason = "the work item is really capability development or a materially new bounded use-case, so the paused capability line must go through a reopen screen"
    elif new_skill_family_required or (existing_capability_id and not capability_family_fit) or (
        existing_capability_id and not matching_capability
    ):
        outcome = "new_skill_candidate_required"
        reason = "the work item falls outside the currently held capability family and should begin as a governed skill candidate instead of directive-work execution"
    elif decision_criticality in {"medium", "high"} or overlap_with_active_work in {"medium", "high"}:
        outcome = "review_required_work_candidate"
        reason = "the work item is directive-valid but important enough to require review before selection or execution"
    elif existing_capability_id and capability_family_fit and requires_capability_use_admission:
        outcome = "use_existing_capability_candidate"
        reason = "the best path is governed reuse of an already held capability rather than direct work execution or new skill development"
    else:
        outcome = "direct_governed_work_candidate"
        reason = "the work item is directive-valid, governance-observable, reversible, and does not require capability reopen or new skill acquisition"

    return {
        "work_item_id": str(work_item.get("work_item_id", "")),
        "work_item_name": str(work_item.get("work_item_name", "")),
        "assigned_class": outcome,
        "rationale": reason,
        "expected_capability_path": str(work_item.get("expected_capability_path", "")),
        "directive_relevance": directive_relevance,
        "support_vs_drift": support_vs_drift,
        "decision_criticality": decision_criticality,
        "overlap_with_active_work": overlap_with_active_work,
        "bounded_context": bounded_context,
        "hidden_development_pressure": hidden_development_pressure,
        "trusted_source_report": trusted_source_report,
        "resource_report": resource_report,
        "write_root_report": write_root_report,
    }


def _build_work_item_examples(
    *,
    parser_capability: dict[str, Any],
    allowed_write_roots: list[str],
) -> list[dict[str, Any]]:
    parser_id = str(parser_capability.get("capability_id", ""))
    return [
        {
            "work_item_id": "directive_work_trusted_diagnostic_bundle_refresh",
            "work_item_name": "Trusted diagnostic bundle summary refresh",
            "work_summary": "refresh directive-supportive diagnostics by reusing the held local trace parser on a new trusted local log bundle",
            "directive_relevance": "high",
            "support_vs_drift": "support",
            "trusted_sources": ["local_artifacts:novali-v4/data", "local_logs:logs"],
            "expected_resources": {"cpu_parallel_units": 1, "memory_mb": 128, "storage_write_mb": 8, "network_mode": "none"},
            "expected_write_roots": list(allowed_write_roots),
            "reversibility": "high",
            "governance_observability": "high",
            "expected_capability_path": "use_existing_capability",
            "existing_capability_id": parser_id,
            "capability_family_fit": True,
            "requires_capability_use_admission": True,
            "requires_capability_modification": False,
            "new_bounded_use_case": False,
            "new_skill_family_required": False,
            "decision_criticality": "low",
            "overlap_with_active_work": "low",
            "bounded_context": True,
            "expected_success_signal": "bounded trusted-local diagnostic bundle summary preserved for governance review",
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "unbounded_contextual_exploration": False,
        },
        {
            "work_item_id": "directive_work_governance_state_coherence_audit_refresh",
            "work_item_name": "Governance state coherence audit refresh",
            "work_summary": "refresh a direct local governance audit across directive, branch, bucket, and self-structure artifacts without using a held capability",
            "directive_relevance": "high",
            "support_vs_drift": "support",
            "trusted_sources": ["local_artifacts:novali-v4/data"],
            "expected_resources": {"cpu_parallel_units": 1, "memory_mb": 64, "storage_write_mb": 4, "network_mode": "none"},
            "expected_write_roots": list(allowed_write_roots),
            "reversibility": "high",
            "governance_observability": "high",
            "expected_capability_path": "direct_governed_work",
            "existing_capability_id": "",
            "capability_family_fit": False,
            "requires_capability_use_admission": False,
            "requires_capability_modification": False,
            "new_bounded_use_case": False,
            "new_skill_family_required": False,
            "decision_criticality": "low",
            "overlap_with_active_work": "low",
            "bounded_context": True,
            "expected_success_signal": "coherence report showing directive, branch, bucket, and self-structure alignment",
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "unbounded_contextual_exploration": False,
        },
        {
            "work_item_id": "directive_work_high_consequence_review_support",
            "work_item_name": "High-consequence directive review support",
            "work_summary": "prepare bounded local evidence for a more consequential directive review decision",
            "directive_relevance": "high",
            "support_vs_drift": "support",
            "trusted_sources": ["local_artifacts:novali-v4/data", "local_logs:logs"],
            "expected_resources": {"cpu_parallel_units": 1, "memory_mb": 128, "storage_write_mb": 8, "network_mode": "none"},
            "expected_write_roots": list(allowed_write_roots),
            "reversibility": "high",
            "governance_observability": "high",
            "expected_capability_path": "review_then_select",
            "existing_capability_id": parser_id,
            "capability_family_fit": True,
            "requires_capability_use_admission": True,
            "requires_capability_modification": False,
            "new_bounded_use_case": False,
            "new_skill_family_required": False,
            "decision_criticality": "high",
            "overlap_with_active_work": "medium",
            "bounded_context": True,
            "expected_success_signal": "review packet with bounded evidence and explicit human review hooks",
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "unbounded_contextual_exploration": False,
        },
        {
            "work_item_id": "directive_work_local_trace_parser_new_family_extension",
            "work_item_name": "Local trace parser new trace-family extension",
            "work_summary": "extend the held parser family to a new local trace shape as part of directive work",
            "directive_relevance": "high",
            "support_vs_drift": "support",
            "trusted_sources": ["local_artifacts:novali-v4/data", "local_logs:logs"],
            "expected_resources": {"cpu_parallel_units": 1, "memory_mb": 128, "storage_write_mb": 8, "network_mode": "none"},
            "expected_write_roots": list(allowed_write_roots),
            "reversibility": "high",
            "governance_observability": "high",
            "expected_capability_path": "reopen_paused_capability_line",
            "existing_capability_id": parser_id,
            "capability_family_fit": True,
            "requires_capability_use_admission": False,
            "requires_capability_modification": True,
            "new_bounded_use_case": True,
            "new_skill_family_required": False,
            "decision_criticality": "low",
            "overlap_with_active_work": "low",
            "bounded_context": True,
            "expected_success_signal": "new bounded use-case justification strong enough for a reopen screen",
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "unbounded_contextual_exploration": False,
        },
        {
            "work_item_id": "directive_work_out_of_family_retrieval_need",
            "work_item_name": "Out-of-family retrieval need",
            "work_summary": "satisfy a retrieval or memory need that the held parser capability cannot cover",
            "directive_relevance": "medium",
            "support_vs_drift": "support",
            "trusted_sources": ["local_artifacts:novali-v4/data"],
            "expected_resources": {"cpu_parallel_units": 1, "memory_mb": 64, "storage_write_mb": 4, "network_mode": "none"},
            "expected_write_roots": list(allowed_write_roots),
            "reversibility": "high",
            "governance_observability": "high",
            "expected_capability_path": "new_skill_candidate",
            "existing_capability_id": parser_id,
            "capability_family_fit": False,
            "requires_capability_use_admission": False,
            "requires_capability_modification": False,
            "new_bounded_use_case": False,
            "new_skill_family_required": True,
            "decision_criticality": "low",
            "overlap_with_active_work": "low",
            "bounded_context": True,
            "expected_success_signal": "clear rationale for why a new skill family is required instead of parser reuse",
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "unbounded_contextual_exploration": False,
        },
        {
            "work_item_id": "directive_work_untrusted_external_exploration",
            "work_item_name": "Untrusted external directive exploration",
            "work_summary": "expand directive exploration into untrusted external sources without bounded diagnostic need",
            "directive_relevance": "low",
            "support_vs_drift": "drift",
            "trusted_sources": ["untrusted_remote_web"],
            "expected_resources": {"cpu_parallel_units": 1, "memory_mb": 128, "storage_write_mb": 8, "network_mode": "internet"},
            "expected_write_roots": list(allowed_write_roots),
            "reversibility": "medium",
            "governance_observability": "medium",
            "expected_capability_path": "defer_or_block",
            "existing_capability_id": "",
            "capability_family_fit": False,
            "requires_capability_use_admission": False,
            "requires_capability_modification": False,
            "new_bounded_use_case": False,
            "new_skill_family_required": False,
            "decision_criticality": "medium",
            "overlap_with_active_work": "low",
            "bounded_context": False,
            "expected_success_signal": "none because trust and boundedness should fail before execution",
            "touches_protected_surface": False,
            "touches_downstream_selected_set": False,
            "touches_plan_ownership": False,
            "touches_routing": False,
            "touches_branch_state": False,
            "unbounded_contextual_exploration": True,
        },
    ]


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
    capability_use_invocation_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1"
    )
    capability_use_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_capability_use_evidence_snapshot_v1"
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
            capability_use_invocation_snapshot,
            capability_use_evidence_snapshot,
            provisional_pause_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: directive-work selection policy requires governance, capability-use policy, candidate-screen, invocation-admission, invocation-execution, capability-use evidence, and provisional-pause artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite governed directive-work artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite governed directive-work artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite governed directive-work artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot define directive-work selection without the current governed capability-use layer and paused capability state",
            },
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
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: directive-work selection policy requires current directive, bucket, self-structure, and branch artifacts",
            "observability_gain": {"passed": False, "reason": "missing durable governance state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing durable governance state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing durable governance state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot define directive-work selection without current directive, bucket, self-structure, and branch state",
            },
        }

    current_directive = dict(directive_state.get("current_directive_state", {}))
    bucket_current = dict(bucket_state.get("current_bucket_state", {}))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_branch_state = str(branch_record.get("state", ""))
    governed_capability_use_policy = dict(self_structure_state.get("governed_capability_use_policy", {}))

    evidence_artifact_path = Path(
        str(governed_capability_use_policy.get("last_invocation_evidence_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_capability_use_evidence_snapshot_v1_*.json")
    )
    policy_artifact_path = Path(
        str(governed_capability_use_policy.get("last_policy_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_capability_use_policy_snapshot_v1_*.json")
    )
    candidate_screen_artifact_path = Path(
        str(governed_capability_use_policy.get("last_candidate_screen_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_capability_use_candidate_screen_snapshot_v1_*.json")
    )
    invocation_admission_artifact_path = Path(
        str(governed_capability_use_policy.get("last_invocation_admission_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_capability_use_invocation_admission_snapshot_v1_*.json")
    )
    invocation_execution_artifact_path = Path(
        str(governed_capability_use_policy.get("last_invocation_execution_artifact_path", ""))
        or _latest_matching_artifact("proposal_learning_loop_v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1_*.json")
    )
    provisional_pause_artifact_path = Path(
        str(dict(self_structure_state.get("governed_skill_subsystem", {})).get("last_provisional_pause_artifact_path", ""))
        or _latest_matching_artifact("memory_summary_v4_governed_skill_provisional_pause_snapshot_v1_*.json")
    )

    evidence_payload = _load_json_file(evidence_artifact_path)
    evidence_summary = dict(evidence_payload.get("governed_capability_use_evidence_summary", {}))
    policy_payload = _load_json_file(policy_artifact_path)
    capability_use_policy_summary = dict(policy_payload.get("governed_capability_use_policy_summary", {}))
    candidate_screen_payload = _load_json_file(candidate_screen_artifact_path)
    candidate_screen_summary = dict(candidate_screen_payload.get("governed_capability_use_candidate_screen_summary", {}))
    invocation_admission_payload = _load_json_file(invocation_admission_artifact_path)
    invocation_admission_summary = dict(
        invocation_admission_payload.get("governed_capability_use_invocation_admission_summary", {})
    )
    invocation_execution_payload = _load_json_file(invocation_execution_artifact_path)
    invocation_execution_summary = dict(
        invocation_execution_payload.get("governed_capability_invocation_summary", {})
    )
    provisional_pause_payload = _load_json_file(provisional_pause_artifact_path)
    provisional_pause_summary = dict(provisional_pause_payload.get("governed_skill_provisional_pause_summary", {}))
    if not all(
        [
            evidence_summary,
            capability_use_policy_summary,
            candidate_screen_summary,
            invocation_admission_summary,
            invocation_execution_summary,
            provisional_pause_summary,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: directive-work selection policy could not load one or more prerequisite governed summaries",
            "observability_gain": {"passed": False, "reason": "missing prerequisite summary payloads"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite summary payloads"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite summary payloads"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot define directive-work selection without the prerequisite governed summary payloads",
            },
        }

    directive_work_selection_ready = bool(
        dict(evidence_summary.get("broader_project_alignment", {})).get(
            "provides_real_base_for_directive_work_selection_next",
            False,
        )
    )
    if not directive_work_selection_ready:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: the capability-use evidence layer has not yet marked directive-work selection as ready",
            "observability_gain": {"passed": False, "reason": "directive-work selection readiness is not yet established"},
            "activation_analysis_usefulness": {"passed": False, "reason": "directive-work selection readiness is not yet established"},
            "ambiguity_reduction": {"passed": False, "reason": "directive-work selection readiness is not yet established"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {
                "passed": False,
                "reason": "the use layer must prove directive-work-selection readiness before a selection policy should be defined",
            },
        }

    callable_capabilities = list(governed_capability_use_policy.get("current_callable_capabilities", []))
    parser_capability = _find_capability(callable_capabilities, "skill_candidate_local_trace_parser_trial")
    if not parser_capability:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no current held callable capability record was found for the local trace parser",
            "observability_gain": {"passed": False, "reason": "missing held callable capability record"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing held callable capability record"},
            "ambiguity_reduction": {"passed": False, "reason": "missing held callable capability record"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {
                "passed": False,
                "reason": "directive-work selection cannot reason about use versus reopen without the current held capability record",
            },
        }

    allowed_write_roots = [
        str(intervention_data_dir()),
        str(Path(__file__).resolve().parent),
    ]
    next_template = "memory_summary.v4_governed_directive_work_candidate_screen_snapshot_v1"

    policy_classes = {
        "direct_governed_work_candidate": {
            "meaning": "work can proceed toward direct governed execution because it is directive-valid, reversible, bucket-feasible, and does not depend on capability development or reopen",
            "phase_1_status": "enabled_for_bounded_local_governance_support_work",
        },
        "review_required_work_candidate": {
            "meaning": "work is directive-valid but important enough to require explicit review before it can be selected or executed",
            "phase_1_status": "enabled",
        },
        "use_existing_capability_candidate": {
            "meaning": "the best path is to use an already held governed capability and then follow its separate invocation-admission path",
            "phase_1_status": "enabled",
        },
        "reopen_required_work_candidate": {
            "meaning": "the work item implies capability development or a materially new bounded use-case, so a paused capability line must go through reopen screening instead of being directly selected as work",
            "phase_1_status": "enabled",
        },
        "new_skill_candidate_required": {
            "meaning": "the work item falls outside currently held capability families and should begin through governed skill acquisition rather than directive-work execution",
            "phase_1_status": "enabled",
        },
        "defer_or_block_work_candidate": {
            "meaning": "the work item should be deferred or blocked because it violates trust, boundedness, guardrails, or directive support requirements",
            "phase_1_status": "enabled",
        },
    }

    work_selection_request_schema = {
        "schema_name": "GovernedDirectiveWorkSelectionRequest",
        "schema_version": "governed_directive_work_selection_policy_v1",
        "required_fields": [
            "work_item_id",
            "work_item_name",
            "work_summary",
            "directive_relevance",
            "support_vs_drift",
            "trusted_sources",
            "expected_resources",
            "expected_write_roots",
            "reversibility",
            "governance_observability",
            "expected_capability_path",
            "existing_capability_id",
            "capability_family_fit",
            "requires_capability_use_admission",
            "requires_capability_modification",
            "new_bounded_use_case",
            "new_skill_family_required",
            "decision_criticality",
            "overlap_with_active_work",
            "bounded_context",
            "expected_success_signal",
        ],
        "outcome_classes": list(policy_classes.keys()),
    }

    decision_criteria = {
        "directive_relevance_or_closeness": "candidate work must stay close to the active directive and be support rather than drift",
        "support_vs_drift_classification": "bounded directive support is admissible; unbounded contextual exploration or speculative drift is not",
        "trusted_source_compatibility": "all expected sources must stay inside current directive and bucket trusted-source policy",
        "bucket_resource_feasibility": "expected cpu, memory, storage, and network mode must fit the current bucket",
        "branch_state_compatibility": "the current branch must remain paused_with_baseline_held and work selection must not hide branch mutation",
        "held_capability_availability": "prefer an existing held capability when it already fits the work item cleanly",
        "use_vs_development_vs_escalation": "distinguish direct work, held capability use, capability reopen pressure, and new skill acquisition explicitly",
        "reversibility_and_governance_observability": "selected work must remain reversible and legible enough for later governance review",
    }

    decision_split = {
        "select_direct_governed_work_when": [
            "the task is bounded and directive-supportive",
            "no existing held capability is needed",
            "the task does not imply development or escalation",
        ],
        "select_work_that_requires_capability_use_admission_when": [
            "a held capability already fits the work item family",
            "reusing the held capability is cleaner than opening new acquisition or reopen work",
        ],
        "select_work_that_requires_reopen_screen_when": [
            "the task pressures a paused capability line toward modification",
            "the task depends on a materially new bounded use-case inside a paused capability family",
        ],
        "select_work_that_requires_new_skill_candidate_when": [
            "no currently held capability family fits cleanly",
            "using an existing capability would be a workaround for a different capability need",
        ],
        "select_work_that_should_wait_for_human_approval_when": [
            "the task is decision-critical",
            "the task materially overlaps with active work or has non-obvious consequences",
        ],
    }

    work_selection_accounting_requirements = {
        "work_identity_and_linkage_must_be_logged": [
            "work_item_id",
            "work_item_name",
            "directive_id",
            "directive_linkage_summary",
            "branch_id",
            "branch_state_precondition",
        ],
        "expected_execution_path_must_be_logged": [
            "expected_capability_path",
            "existing_capability_id",
            "expected_review_hooks",
            "expected_rollback_hooks",
            "governance_observability_level",
        ],
        "expected_budget_and_trust_must_be_logged": [
            "required_trusted_sources",
            "expected_resource_budget",
            "expected_write_roots",
            "network_mode_expectation",
            "reversibility_level",
        ],
        "expected_evidence_must_be_logged": [
            "expected_success_signal",
            "expected_usefulness_signal",
            "expected_duplicate_overlap_check",
        ],
    }

    work_selection_guardrails = {
        "protected_surface_drift_forbidden": True,
        "downstream_selected_set_work_forbidden": True,
        "plan_ownership_change_forbidden": True,
        "routing_drift_forbidden": True,
        "capability_development_hidden_inside_work_selection_forbidden": True,
        "directive_drift_via_unbounded_contextual_exploration_forbidden": True,
        "branch_state_mutation_forbidden": True,
        "untrusted_external_access_forbidden": True,
    }

    relationship_to_held_capabilities = {
        "prefer_held_capability_when": [
            "the work item cleanly matches a current held capability family",
            "the held capability can satisfy the need inside its current admitted envelope",
            "reuse is cleaner than new skill acquisition",
        ],
        "held_capability_is_insufficient_when": [
            "the work item needs capability modification or extension",
            "the work item falls outside the current capability family",
            "the work item would hide development pressure under a use label",
        ],
        "paused_capability_line_must_remain_paused_when": [
            "the request is only same-shape rerun pressure",
            "the task can be served by held use without development",
            "no reopen screen has been cleared for new bounded use-case work",
        ],
        "current_held_capabilities": callable_capabilities,
    }

    sample_work_items = _build_work_item_examples(
        parser_capability=parser_capability,
        allowed_write_roots=allowed_write_roots,
    )
    sample_work_item_decisions = [
        _classify_work_item(
            item,
            directive_current=current_directive,
            bucket_current=bucket_current,
            current_branch_state=current_branch_state,
            allowed_write_roots=allowed_write_roots,
            callable_capabilities=callable_capabilities,
            plan_non_owning=bool(current_state_summary.get("plan_non_owning", False)),
            routing_deferred=bool(current_state_summary.get("routing_deferred", False)),
        )
        for item in sample_work_items
    ]
    sample_decision_counts = {
        decision_class: sum(
            1 for item in sample_work_item_decisions if str(item.get("assigned_class", "")) == decision_class
        )
        for decision_class in policy_classes
    }

    broader_architecture_role = {
        "supports_self_directed_behavior_without_abandoning_governance": True,
        "prevents_chaos_by_distinguishing_use_reopen_new_skill_and_defer": True,
        "prevents_stagnation_by_preferring_held_capability_reuse_when_fit": True,
        "keeps_directive_work_selection_bucket_bounded": True,
        "preconditions_before_actual_directive_work_execution": [
            "a concrete work candidate must be screened through this policy layer",
            "any held-capability path must still pass capability-use admission when required",
            "any reopen or new-skill path must go through its own separate gate",
            "no branch-state mutation or routing drift may be introduced",
        ],
        "reason": "directive-work selection now has an explicit governance-owned method for choosing among direct work, held-capability use, reopen pressure, new skill acquisition, or defer or block outcomes",
    }

    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_v4_governed_directive_work_selection_policy_snapshot_v1_{proposal['proposal_id']}.json"

    governed_directive_work_selection_policy = {
        "schema_version": "governed_directive_work_selection_policy_v1",
        "work_selection_request_schema": work_selection_request_schema,
        "policy_classes": policy_classes,
        "decision_criteria": decision_criteria,
        "decision_split": decision_split,
        "work_selection_accounting_requirements": work_selection_accounting_requirements,
        "guardrails": work_selection_guardrails,
        "relationship_to_held_capabilities": relationship_to_held_capabilities,
        "current_selection_context": {
            "directive_id": str(current_directive.get("directive_id", "")),
            "branch_id": str(branch_record.get("branch_id", "")),
            "branch_state": current_branch_state,
            "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
            "held_capability_default_posture": str(parser_capability.get("default_use_class", "")),
            "held_capability_status": str(parser_capability.get("status", "")),
            "capability_use_operational_basis": str(
                dict(governed_capability_use_policy.get("last_invocation_evidence_outcome", {})).get("status", "")
            ),
        },
        "sample_work_item_decisions": sample_work_item_decisions,
        "sample_decision_counts": sample_decision_counts,
        "best_next_template": next_template,
    }

    updated_self_structure_state = dict(self_structure_state)
    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["governed_directive_work_selection_policy"] = governed_directive_work_selection_policy

    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "governed_directive_work_selection_policy_v1_defined": True,
            "latest_directive_work_selection_policy_status": "defined",
            "latest_directive_work_selection_best_next_template": next_template,
            "latest_directive_work_selection_readiness": "ready_for_candidate_screen",
            "current_branch_state": current_branch_state,
            "plan_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "retained_skill_promotion_performed": False,
        }
    )
    updated_self_structure_state["current_state_summary"] = updated_current_state_summary
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    ledger_event = {
        "event_id": f"governed_directive_work_selection_policy_snapshot_v1::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_directive_work_selection_policy_snapshot_v1_materialized",
        "event_class": "governed_directive_work_selection_policy",
        "directive_id": str(current_directive.get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": current_branch_state,
        "held_capability_id": str(parser_capability.get("capability_id", "")),
        "held_capability_status": str(parser_capability.get("status", "")),
        "new_behavior_changing_branch_opened": False,
        "retained_promotion": False,
        "branch_state_mutation": False,
        "artifact_paths": {
            "capability_use_policy_v1": str(policy_artifact_path),
            "capability_use_candidate_screen_v1": str(candidate_screen_artifact_path),
            "capability_use_invocation_admission_v1": str(invocation_admission_artifact_path),
            "capability_use_invocation_v1": str(invocation_execution_artifact_path),
            "capability_use_evidence_v1": str(evidence_artifact_path),
            "skill_provisional_pause_v1": str(provisional_pause_artifact_path),
            "directive_work_selection_policy_v1": str(artifact_path),
        },
        "source_proposal_id": str(proposal.get("proposal_id", "")),
    }
    _append_jsonl(SELF_STRUCTURE_LEDGER_PATH, ledger_event)

    all_ranked = list(recommendations.get("all_ranked_proposals", []))
    suggested_templates = [
        str(item.get("template_name", ""))
        for item in all_ranked
        if isinstance(item, dict) and str(item.get("decision", "")) == "suggested"
    ][:8]

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_governed_directive_work_selection_policy_snapshot_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "branch_context": {
            "current_branch_id": str(branch_record.get("branch_id", "")),
            "current_branch_state": current_branch_state,
            "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
            "plan_non_owning": True,
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
            "proposal_learning_loop.v4_governed_capability_use_trusted_diagnostic_bundle_invocation_v1": _artifact_reference(
                capability_use_invocation_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_capability_use_evidence_snapshot_v1": _artifact_reference(
                capability_use_evidence_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_skill_provisional_pause_snapshot_v1": _artifact_reference(
                provisional_pause_snapshot, latest_snapshots
            ),
        },
        "governed_directive_work_selection_policy_summary": {
            "policy_classes": policy_classes,
            "decision_criteria": decision_criteria,
            "work_selection_request_schema": work_selection_request_schema,
            "work_selection_accounting_requirements": work_selection_accounting_requirements,
            "guardrails": work_selection_guardrails,
            "relationship_to_held_capabilities": relationship_to_held_capabilities,
            "decision_split": decision_split,
            "readiness_reference": {
                "capability_use_future_posture": str(dict(evidence_summary.get("future_posture", {})).get("category", "")),
                "directive_work_selection_ready": directive_work_selection_ready,
                "operational_success_basis": bool(
                    dict(governed_capability_use_policy.get("last_invocation_evidence_outcome", {})).get(
                        "operationally_successful",
                        False,
                    )
                ),
            },
            "sample_work_item_decisions": sample_work_item_decisions,
            "sample_decision_counts": sample_decision_counts,
            "broader_architecture_role": broader_architecture_role,
            "governance_inputs_consumed": {
                "directive_state_latest": str(DIRECTIVE_STATE_PATH),
                "directive_history": str(DIRECTIVE_HISTORY_PATH),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
                "branch_registry_latest": str(BRANCH_REGISTRY_PATH),
                "bucket_state_latest": str(BUCKET_STATE_PATH),
                "intervention_ledger": str(intervention_data_dir() / "intervention_ledger.jsonl"),
                "intervention_analytics_latest": str(intervention_data_dir() / "intervention_analytics_latest.json"),
                "proposal_recommendations_latest": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            },
            "why_governance_remains_source_of_truth": {
                "owner": "governance_substrate_v1",
                "proposal_learning_loop_is_governance_truth_source": False,
                "reason": "directive-work selection is now derived from directive, bucket, branch, self-structure, held-capability, capability-use, and pause-state artifacts rather than from execution code or plan_ ownership",
            },
        },
        "analytics_context": {
            "analytics_report_path": str(intervention_data_dir() / "intervention_analytics_latest.json"),
            "proposal_recommendations_path": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            "proposal_count": int(analytics.get("proposal_count", 0) or 0),
            "current_recommendation_top_templates": suggested_templates,
            "directive_history_entry_count": int(len(directive_history)),
            "self_structure_ledger_entry_count": int(len(self_structure_ledger)),
            "intervention_ledger_entry_count": int(len(intervention_ledger)),
        },
        "observability_gain": {
            "passed": True,
            "reason": "directive-work selection now has an explicit governance-owned policy layer separating direct work, held capability use, reopen pressure, new-skill needs, and defer or block outcomes",
            "artifact_paths": {
                "directive_work_selection_policy_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the policy clarifies what must be true before actual directive-work execution is opened and cleanly separates use, reopen, new-skill, and defer paths",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "directive-work choice is now governance-owned rather than implicit inside capability use, skill acquisition, or plan_ behavior",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the policy snapshot is diagnostic-only; it opened no behavior-changing branch, mutated no branch state, promoted no retained skill, and changed no live behavior",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": next_template,
            "reason": "the next useful layer is a concrete directive-work candidate screen that applies this policy to actual work-item requests",
        },
        "diagnostic_conclusions": {
            "governed_directive_work_selection_policy_v1_defined": True,
            "new_behavior_changing_branch_opened": False,
            "branch_state_mutation_occurred": False,
            "retained_promotion_occurred": False,
            "plan_should_remain_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "best_next_template": next_template,
        },
    }
    _write_json(artifact_path, artifact_payload)

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: directive-work selection now has a governance-owned policy layer on top of governed capability use",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
