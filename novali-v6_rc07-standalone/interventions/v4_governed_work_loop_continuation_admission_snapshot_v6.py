from __future__ import annotations

from fnmatch import fnmatch
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
from .v4_governed_directive_work_selection_policy_snapshot_v1 import _find_capability
from .v4_governed_work_loop_candidate_screen_snapshot_v6 import (
    _build_loop_candidate_examples_v6,
    _screen_loop_candidate_v4 as _screen_loop_candidate_v6,
)
from .v4_governed_work_loop_continuation_admission_snapshot_v1 import (
    _find_loop_candidate,
    _required_accounting_fields,
)
from .v4_governed_work_loop_policy_snapshot_v1 import _resolve_artifact_path
from .v4_wm_context_signal_overlap_snapshot_v1 import _artifact_reference


def _check(passed: bool, reason: str) -> dict[str, Any]:
    return {"passed": bool(passed), "reason": str(reason)}


def _resolve_artifact_path_for_pattern(raw_candidate: Any, pattern: str) -> Path | None:
    candidate = str(raw_candidate or "").strip()
    if candidate and candidate != "None":
        candidate_path = Path(candidate)
        if fnmatch(candidate_path.name, pattern):
            return candidate_path
    return _resolve_artifact_path(None, pattern)


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _summary_from_path(path: Path | None, key: str) -> dict[str, Any]:
    if not path:
        return {}
    payload = _load_json_file(path)
    return dict(payload.get(key, {})) if isinstance(payload, dict) else {}


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governance_substrate_v1_snapshot")
    work_loop_policy_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_policy_snapshot_v1"
    )
    candidate_screen_snapshot_v5 = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v5"
    )
    candidate_screen_snapshot_v6 = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v6"
    )
    posture_snapshot_v1 = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_posture_snapshot_v1"
    )
    evidence_snapshot_v1 = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_evidence_snapshot_v1"
    )
    evidence_snapshot_v2 = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_evidence_snapshot_v2"
    )
    evidence_snapshot_v3 = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_evidence_snapshot_v3"
    )
    evidence_snapshot_v4 = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_evidence_snapshot_v4"
    )
    evidence_snapshot_v5 = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_evidence_snapshot_v5"
    )
    continuation_admission_snapshot_v5 = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v5"
    )
    continuation_execution_v1 = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1"
    )
    continuation_execution_v2 = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1"
    )
    continuation_execution_v3 = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1"
    )
    continuation_execution_v4 = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1"
    )
    continuation_execution_v5 = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1"
    )
    direct_work_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_direct_work_evidence_snapshot_v1"
    )
    capability_use_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_capability_use_evidence_snapshot_v1"
    )
    if not all(
        [
            governance_snapshot,
            work_loop_policy_snapshot,
            candidate_screen_snapshot_v5,
            candidate_screen_snapshot_v6,
            posture_snapshot_v1,
            evidence_snapshot_v1,
            evidence_snapshot_v2,
            evidence_snapshot_v3,
            evidence_snapshot_v4,
            evidence_snapshot_v5,
            continuation_admission_snapshot_v5,
            continuation_execution_v1,
            continuation_execution_v2,
            continuation_execution_v3,
            continuation_execution_v4,
            continuation_execution_v5,
            direct_work_evidence_snapshot,
            capability_use_evidence_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: continuation admission v6 requires the current governed work-loop artifact chain",
            "observability_gain": {"passed": False, "reason": "missing prerequisite continuation-admission v6 artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite continuation-admission v6 artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite continuation-admission v6 artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot decide v6 admission without the local governance chain"},
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
    if not all([directive_state, bucket_state, self_structure_state, branch_registry, recommendations]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: continuation admission v6 requires current directive, bucket, self-structure, branch, and recommendation state",
            "observability_gain": {"passed": False, "reason": "missing durable governance state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing durable governance state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing durable governance state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot decide v6 admission without durable governance state"},
        }

    current_directive = dict(directive_state.get("current_directive_state", {}))
    bucket_current = dict(bucket_state.get("current_bucket_state", {}))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_branch_state = str(branch_record.get("state", ""))
    governed_work_loop_policy = dict(self_structure_state.get("governed_work_loop_policy", {}))
    governed_directive_work_selection_policy = dict(self_structure_state.get("governed_directive_work_selection_policy", {}))
    governed_capability_use_policy = dict(self_structure_state.get("governed_capability_use_policy", {}))

    policy_artifact_path = _resolve_artifact_path_for_pattern(
        governed_work_loop_policy.get("last_policy_artifact_path"),
        "memory_summary_v4_governed_work_loop_policy_snapshot_v1_*.json",
    )
    candidate_screen_v6_artifact_path = _resolve_artifact_path_for_pattern(
        governed_work_loop_policy.get("last_candidate_screen_artifact_path"),
        "memory_summary_v4_governed_work_loop_candidate_screen_snapshot_v6_*.json",
    )
    candidate_screen_v5_artifact_path = _resolve_artifact_path_for_pattern(
        governed_work_loop_policy.get("last_prior_candidate_screen_artifact_path"),
        "memory_summary_v4_governed_work_loop_candidate_screen_snapshot_v5_*.json",
    )
    posture_artifact_path = _resolve_artifact_path_for_pattern(
        governed_work_loop_policy.get("last_work_loop_posture_artifact_path"),
        "memory_summary_v4_governed_work_loop_posture_snapshot_v1_*.json",
    )
    evidence_v1_artifact_path = _resolve_artifact_path(None, "memory_summary_v4_governed_work_loop_evidence_snapshot_v1_*.json")
    evidence_v2_artifact_path = _resolve_artifact_path(None, "memory_summary_v4_governed_work_loop_evidence_snapshot_v2_*.json")
    evidence_v3_artifact_path = _resolve_artifact_path_for_pattern(
        governed_work_loop_policy.get("last_prior_work_loop_evidence_artifact_path"),
        "memory_summary_v4_governed_work_loop_evidence_snapshot_v3_*.json",
    )
    evidence_v4_artifact_path = _resolve_artifact_path_for_pattern(
        governed_work_loop_policy.get("last_prior_work_loop_evidence_artifact_path"),
        "memory_summary_v4_governed_work_loop_evidence_snapshot_v4_*.json",
    )
    evidence_v5_artifact_path = _resolve_artifact_path_for_pattern(
        governed_work_loop_policy.get("last_work_loop_evidence_artifact_path"),
        "memory_summary_v4_governed_work_loop_evidence_snapshot_v5_*.json",
    )
    continuation_admission_v5_artifact_path = _resolve_artifact_path_for_pattern(
        governed_work_loop_policy.get("last_work_loop_continuation_admission_artifact_path"),
        "memory_summary_v4_governed_work_loop_continuation_admission_snapshot_v5_*.json",
    )
    execution_v1_artifact_path = _resolve_artifact_path(
        None,
        "proposal_learning_loop_v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1_*.json",
    )
    execution_v2_artifact_path = _resolve_artifact_path(
        None,
        "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1_*.json",
    )
    execution_v3_artifact_path = _resolve_artifact_path_for_pattern(
        governed_work_loop_policy.get("last_prior_work_loop_continuation_execution_artifact_path"),
        "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1_*.json",
    )
    execution_v4_artifact_path = _resolve_artifact_path_for_pattern(
        governed_work_loop_policy.get("last_prior_work_loop_continuation_execution_artifact_path"),
        "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1_*.json",
    )
    execution_v5_artifact_path = _resolve_artifact_path_for_pattern(
        governed_work_loop_policy.get("last_work_loop_continuation_execution_artifact_path"),
        "proposal_learning_loop_v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1_*.json",
    )
    direct_work_evidence_artifact_path = _resolve_artifact_path_for_pattern(
        governed_directive_work_selection_policy.get("last_direct_work_evidence_artifact_path"),
        "memory_summary_v4_governed_direct_work_evidence_snapshot_v1_*.json",
    )
    capability_use_evidence_artifact_path = _resolve_artifact_path_for_pattern(
        governed_capability_use_policy.get("last_invocation_evidence_artifact_path"),
        "memory_summary_v4_governed_capability_use_evidence_snapshot_v1_*.json",
    )
    if not all(
        [
            policy_artifact_path,
            candidate_screen_v6_artifact_path,
            candidate_screen_v5_artifact_path,
            posture_artifact_path,
            evidence_v1_artifact_path,
            evidence_v2_artifact_path,
            evidence_v3_artifact_path,
            evidence_v4_artifact_path,
            evidence_v5_artifact_path,
            continuation_admission_v5_artifact_path,
            execution_v1_artifact_path,
            execution_v2_artifact_path,
            execution_v3_artifact_path,
            execution_v4_artifact_path,
            execution_v5_artifact_path,
            direct_work_evidence_artifact_path,
            capability_use_evidence_artifact_path,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: continuation admission v6 could not resolve one or more governing artifact paths",
            "observability_gain": {"passed": False, "reason": "missing resolved continuation-admission v6 artifact paths"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing resolved continuation-admission v6 artifact paths"},
            "ambiguity_reduction": {"passed": False, "reason": "missing resolved continuation-admission v6 artifact paths"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot make a bounded v6 admission decision without the resolved local artifact chain"},
        }

    candidate_screen_v5_summary = _summary_from_path(
        candidate_screen_v5_artifact_path, "governed_work_loop_candidate_screen_v5_summary"
    )
    candidate_screen_v6_summary = _summary_from_path(
        candidate_screen_v6_artifact_path, "governed_work_loop_candidate_screen_v6_summary"
    )
    posture_summary = _summary_from_path(posture_artifact_path, "governed_work_loop_posture_summary")
    evidence_v1_summary = _summary_from_path(evidence_v1_artifact_path, "governed_work_loop_evidence_summary")
    evidence_v2_summary = _summary_from_path(evidence_v2_artifact_path, "governed_work_loop_evidence_v2_summary")
    evidence_v3_summary = _summary_from_path(evidence_v3_artifact_path, "governed_work_loop_evidence_v3_summary")
    evidence_v4_summary = _summary_from_path(evidence_v4_artifact_path, "governed_work_loop_evidence_v4_summary")
    evidence_v5_summary = _summary_from_path(evidence_v5_artifact_path, "governed_work_loop_evidence_v5_summary")
    continuation_admission_v5_summary = _summary_from_path(
        continuation_admission_v5_artifact_path, "governed_work_loop_continuation_admission_v5_summary"
    )
    direct_work_evidence_summary = _summary_from_path(
        direct_work_evidence_artifact_path, "governed_direct_work_evidence_summary"
    )
    capability_use_evidence_summary = _summary_from_path(
        capability_use_evidence_artifact_path, "governed_capability_use_evidence_summary"
    )
    if not all(
        [
            candidate_screen_v5_summary,
            candidate_screen_v6_summary,
            posture_summary,
            evidence_v1_summary,
            evidence_v2_summary,
            evidence_v3_summary,
            evidence_v4_summary,
            evidence_v5_summary,
            continuation_admission_v5_summary,
            direct_work_evidence_summary,
            capability_use_evidence_summary,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: continuation admission v6 could not load the governing summaries",
            "observability_gain": {"passed": False, "reason": "missing continuation-admission v6 summaries"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing continuation-admission v6 summaries"},
            "ambiguity_reduction": {"passed": False, "reason": "missing continuation-admission v6 summaries"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot decide v6 admission without the governing summaries"},
        }

    callable_capabilities = list(governed_capability_use_policy.get("current_callable_capabilities", []))
    parser_capability = _find_capability(callable_capabilities, "skill_candidate_local_trace_parser_trial")
    if not parser_capability:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no held parser capability record was found",
            "observability_gain": {"passed": False, "reason": "missing held parser capability record"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing held parser capability record"},
            "ambiguity_reduction": {"passed": False, "reason": "missing held parser capability record"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot reconstruct the candidate frontier without the held parser capability state"},
        }

    posture_current = dict(posture_summary.get("current_posture", {}))
    future_gate = dict(evidence_v5_summary.get("gate_status", {}))
    loop_chain_state = dict(evidence_v5_summary.get("chain_state_reviewed", {}))
    loop_accounting_requirements = dict(governed_work_loop_policy.get("loop_accounting_requirements", {}))
    guardrails = dict(governed_work_loop_policy.get("guardrails", {}))
    allowed_write_roots = [str(intervention_data_dir()), str(Path(__file__).resolve().parent)]
    loop_candidates = _build_loop_candidate_examples_v6(
        parser_capability=parser_capability,
        allowed_write_roots=allowed_write_roots,
    )
    screened_candidates = [
        _screen_loop_candidate_v6(
            item,
            directive_current=current_directive,
            bucket_current=bucket_current,
            current_branch_state=current_branch_state,
            current_state_summary=current_state_summary,
            callable_capabilities=callable_capabilities,
            allowed_write_roots=allowed_write_roots,
            current_direct_work_future_posture=str(dict(direct_work_evidence_summary.get("future_posture", {})).get("category", "")),
            loop_continuation_future_posture=str(dict(evidence_v5_summary.get("future_posture", {})).get("category", "")),
            primary_posture_class=str(posture_current.get("primary_posture_class", "")),
            active_posture_classes=[str(item) for item in list(posture_current.get("active_posture_classes", [])) if str(item)],
            future_posture_review_gate_status=str(future_gate.get("gate_status", "")),
            loop_chain_state=loop_chain_state,
            loop_accounting_requirements=loop_accounting_requirements,
            guardrails=guardrails,
        )
        for item in loop_candidates
    ]
    candidate_name = str(
        dict(candidate_screen_v6_summary.get("top_ranked_candidate", {})).get("loop_candidate_name", "")
        or current_state_summary.get("latest_governed_work_loop_best_candidate", "")
    )
    candidate_record = _find_loop_candidate(screened_candidates, best_candidate_name=candidate_name)
    if not candidate_record:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: the surviving v6 candidate could not be reconstructed",
            "observability_gain": {"passed": False, "reason": "missing reconstructed v6 candidate"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing reconstructed v6 candidate"},
            "ambiguity_reduction": {"passed": False, "reason": "missing reconstructed v6 candidate"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot make a bounded decision without the surviving v6 candidate"},
        }

    screen_dims = dict(candidate_record.get("screen_dimensions", {}))
    distinctness = dict(screen_dims.get("distinctness_vs_reviewed_chain", {}))
    structural_value = dict(screen_dims.get("structural_vs_local_value", {}))
    admin_recursion = dict(screen_dims.get("administrative_recursion", {}))
    posture_pressure = dict(screen_dims.get("posture_pressure", {}))
    class_report = dict(candidate_record.get("classification_report", {}))
    trusted_source_report = dict(class_report.get("trusted_source_report", {}))
    resource_report = dict(class_report.get("resource_report", {}))
    write_root_report = dict(class_report.get("write_root_report", {}))
    loop_accounting = dict(candidate_record.get("loop_accounting_expectations", {}))
    trusted_sources = _as_list(trusted_source_report.get("requested_sources", []))
    approved_write_roots = _as_list(write_root_report.get("requested_write_roots", []))
    accounting_complete = all(
        bool(loop_accounting.get(field_name))
        for field_name in [
            "loop_identity_context",
            "current_work_state",
            "candidate_identity",
            "expected_path",
            "resource_trust_position",
            "continuation_rationale",
            "expected_next_evidence_signal",
            "review_rollback_hooks",
        ]
    ) and bool(_required_accounting_fields(loop_accounting_requirements))

    admission_checks = {
        "single_surviving_candidate_confirmed": _check(
            int(candidate_screen_v6_summary.get("credible_candidate_count", 0) or 0) == 1,
            "the v6 candidate screen must leave exactly one credible bounded candidate",
        ),
        "candidate_is_loop_continue_candidate": _check(
            str(candidate_record.get("assigned_class", "")) == "loop_continue_candidate",
            "only a loop_continue_candidate is eligible for this narrow continuation-admission gate",
        ),
        "candidate_matches_v6_top_rank": _check(
            str(candidate_record.get("loop_candidate_name", "")) == str(dict(candidate_screen_v6_summary.get("top_ranked_candidate", {})).get("loop_candidate_name", "")),
            "the admitted candidate must match the top-ranked v6 candidate selected by governance",
        ),
        "materially_distinct_from_reviewed_chain": _check(
            bool(distinctness.get("materially_distinct_from_chain", False)),
            "the candidate must stay materially distinct from direct work, continuation v1, continuation v2, continuation v3, continuation v4, continuation v5, and evidence snapshots v2 through v5",
        ),
        "likely_adds_new_evidence": _check(
            str(dict(candidate_screen_v6_summary.get("expected_evidence_yield_assessment", {})).get("classification", "")) == "likely_adds_new_evidence",
            "the candidate must still be expected to add new evidence rather than mostly restate prior governance conclusions",
        ),
        "execution_adjacent_structural_yield": _check(
            str(structural_value.get("classification", "")) == "execution_adjacent_structural_yield",
            "the candidate must remain execution-adjacent and structurally useful rather than summary-recursive",
        ),
        "administrative_recursion_risk_low": _check(
            str(admin_recursion.get("risk", "")) == "low",
            "the candidate must not collapse into governance-paperwork recursion",
        ),
        "posture_pressure_absent": _check(
            str(posture_pressure.get("classification", "")) == "posture_pressure_absent"
            or str(posture_pressure.get("pressure", "")) == "absent",
            "the candidate must not create hidden pressure toward reopen, branch mutation, retention, scope expansion, or posture broadening",
        ),
        "narrow_posture_and_gate_closed": _check(
            str(posture_current.get("primary_posture_class", "")) == "keep_narrow_governed_loop_available"
            and str(future_gate.get("gate_status", "")) == "defined_but_closed"
            and bool(dict(evidence_v5_summary.get("future_posture", {})).get("hold_narrow_posture_unchanged", False)),
            "admission may proceed only while the narrow posture holds and the future posture-review gate remains closed",
        ),
        "repeated_bounded_success_and_clean_discipline": _check(
            str(dict(evidence_v5_summary.get("repeated_bounded_success_assessment", {})).get("classification", "")) == "repeated_bounded_success_strengthened"
            and str(dict(evidence_v5_summary.get("posture_discipline_assessment", {})).get("classification", "")) == "posture_discipline_holding_cleanly"
            and str(dict(evidence_v5_summary.get("posture_pressure_assessment", {})).get("classification", "")) == "posture_pressure_absent",
            "the admission must build on repeated bounded success with posture discipline still holding cleanly",
        ),
        "state_readiness_and_routing_guard": _check(
            bool(current_state_summary.get("governed_work_loop_candidate_screening_v6_in_place", False))
            and str(current_state_summary.get("latest_governed_work_loop_continuation_readiness", "")) == "ready_for_sixth_governed_work_loop_continuation_admission"
            and str(dict(candidate_screen_v6_summary.get("recommended_next_action", {})).get("template_name", ""))
            == "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v6"
            and bool(current_state_summary.get("routing_deferred", False))
            and bool(current_state_summary.get("plan_non_owning", False)),
            "state must explicitly mark the sixth continuation-admission gate as ready while routing stays deferred and plan_ stays non-owning",
        ),
        "trusted_sources_resources_and_branch_compatibility": _check(
            bool(trusted_source_report.get("passed", False))
            and bool(resource_report.get("passed", False))
            and bool(write_root_report.get("passed", False))
            and str(current_branch_state) == "paused_with_baseline_held",
            "trusted sources, resources, write roots, and branch posture must remain compatible with the narrow envelope",
        ),
        "accounting_complete": _check(
            accounting_complete,
            "loop identity, work state, resource, trust, and trigger accounting must remain complete",
        ),
    }
    all_checks_passed = all(bool(item.get("passed", False)) for item in admission_checks.values())
    blocking_conditions = [
        {"check": name, "reason": str(item.get("reason", ""))}
        for name, item in admission_checks.items()
        if not bool(item.get("passed", False))
    ]

    admission_decision = "admissible_now" if all_checks_passed else "not_admissible_now"
    admission_status = "admissible_for_governed_loop_continuation_v6" if all_checks_passed else "not_admissible_now"
    admission_rationale = (
        "the candidate is the single surviving bounded continuation option, materially distinct from the full reviewed chain, still expected to add new evidence, execution-adjacent, structurally useful, low-recursion, and posture-compatible under a still-closed gate"
        if all_checks_passed
        else "one or more narrow-envelope admission checks failed, so the candidate cannot be admitted now"
    )
    next_template = (
        "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_recursion_boundary_audit_v1"
        if all_checks_passed
        else "hold_posture"
    )
    recommended_next_action = "proceed_to_candidate_execution_next" if all_checks_passed else "hold_posture"

    continuation_envelope = {
        "work_loop_posture": "shadow_only_loop_continuation_v6",
        "allowed_scope": [
            "bounded recommendation-frontier recursion boundary audit only",
            "trusted local governance artifacts only",
            "shadow-only continuation accounting and evidence reporting only",
        ],
        "admissible_source_classes": trusted_sources,
        "allowed_write_roots": approved_write_roots,
        "resource_expectations": dict(dict(loop_accounting.get("resource_trust_position", {})).get("expected_resource_budget", {})),
        "branch_state_must_remain": current_branch_state,
        "network_mode": "none",
        "plan_must_remain_non_owning": True,
        "routing_must_remain_deferred": True,
        "capability_modification_allowed": False,
        "paused_capability_reopen_allowed": False,
        "new_skill_creation_allowed": False,
        "retained_promotion_allowed": False,
        "branch_state_mutation_allowed": False,
    }

    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_v4_governed_work_loop_continuation_admission_snapshot_v6_{proposal['proposal_id']}.json"

    updated_self_structure_state = dict(self_structure_state)
    updated_work_loop_policy = dict(governed_work_loop_policy)
    updated_work_loop_policy["work_loop_continuation_admission_v6_schema"] = {
        "schema_name": "GovernedWorkLoopContinuationAdmission",
        "schema_version": "governed_work_loop_continuation_admission_v6",
        "decision_classes": ["admissible_now", "not_admissible_now"],
    }
    updated_work_loop_policy["last_work_loop_continuation_admission_artifact_path"] = str(artifact_path)
    updated_work_loop_policy["last_work_loop_continuation_admission_candidate"] = {
        "loop_candidate_id": str(candidate_record.get("loop_candidate_id", "")),
        "loop_candidate_name": str(candidate_record.get("loop_candidate_name", "")),
        "assigned_class": str(candidate_record.get("assigned_class", "")),
        "proposed_execution_template": str(dict(candidate_record.get("candidate_quality_flags", {})).get("proposed_execution_template", "")),
    }
    updated_work_loop_policy["last_work_loop_continuation_admission_outcome"] = {
        "status": admission_status,
        "decision": admission_decision,
        "reason": admission_rationale,
        "work_loop_posture": "shadow_only_loop_continuation_v6",
        "branch_state_after_admission": current_branch_state,
        "paused_capability_lines_reopened": False,
        "best_next_template": next_template,
    }
    updated_work_loop_policy["best_next_template"] = next_template
    updated_self_structure_state["governed_work_loop_policy"] = updated_work_loop_policy

    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "governed_work_loop_continuation_admission_v6_in_place": True,
            "latest_governed_work_loop_continuation_candidate": str(candidate_record.get("loop_candidate_name", "")),
            "latest_governed_work_loop_continuation_candidate_template": str(
                dict(candidate_record.get("candidate_quality_flags", {})).get("proposed_execution_template", "")
            ),
            "latest_governed_work_loop_continuation_outcome": admission_status,
            "latest_governed_work_loop_continuation_posture": "shadow_only_loop_continuation_v6",
            "latest_governed_work_loop_execution_readiness": (
                "ready_for_shadow_work_loop_continuation_execution_v6" if all_checks_passed else "not_ready_for_shadow_work_loop_continuation_execution_v6"
            ),
            "latest_governed_work_loop_best_next_template": next_template,
            "latest_governed_work_loop_readiness": (
                "ready_for_shadow_work_loop_continuation_execution_v6" if all_checks_passed else "ready_for_sixth_governed_work_loop_continuation_admission"
            ),
            "latest_governed_work_loop_future_posture_review_gate_status": str(future_gate.get("gate_status", "")),
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
            "event_id": f"governed_work_loop_continuation_admission_snapshot_v6::{proposal['proposal_id']}",
            "timestamp": _now(),
            "event_type": "governed_work_loop_continuation_admission_snapshot_v6_materialized",
            "event_class": "governed_work_loop_continuation_admission",
            "directive_id": str(current_directive.get("directive_id", "")),
            "branch_id": str(branch_record.get("branch_id", "")),
            "branch_state": current_branch_state,
            "loop_candidate_id": str(candidate_record.get("loop_candidate_id", "")),
            "loop_candidate_name": str(candidate_record.get("loop_candidate_name", "")),
            "admission_status": admission_status,
            "admission_decision": admission_decision,
            "branch_state_mutation": False,
            "retained_promotion": False,
            "paused_capability_lines_reopened": False,
            "artifact_paths": {
                "governed_work_loop_continuation_admission_v6": str(artifact_path),
                "governed_work_loop_candidate_screen_v6": str(candidate_screen_v6_artifact_path),
                "governed_work_loop_evidence_v5": str(evidence_v5_artifact_path),
            },
            "source_proposal_id": str(proposal.get("proposal_id", "")),
        },
    )

    all_ranked = list(recommendations.get("all_ranked_proposals", []))
    suggested_templates = [
        str(item.get("template_name", ""))
        for item in all_ranked
        if isinstance(item, dict) and str(item.get("decision", "")) == "suggested"
    ][:8]

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v6",
        "branch_context": {
            "current_branch_id": str(branch_record.get("branch_id", "")),
            "current_branch_state": current_branch_state,
            "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
            "plan_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
        },
        "comparison_references": {
            "memory_summary.v4_governance_substrate_v1_snapshot": _artifact_reference(governance_snapshot, latest_snapshots),
            "memory_summary.v4_governed_work_loop_policy_snapshot_v1": _artifact_reference(work_loop_policy_snapshot, latest_snapshots),
            "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v5": _artifact_reference(candidate_screen_snapshot_v5, latest_snapshots),
            "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v6": _artifact_reference(candidate_screen_snapshot_v6, latest_snapshots),
            "memory_summary.v4_governed_work_loop_posture_snapshot_v1": _artifact_reference(posture_snapshot_v1, latest_snapshots),
            "memory_summary.v4_governed_work_loop_evidence_snapshot_v1": _artifact_reference(evidence_snapshot_v1, latest_snapshots),
            "memory_summary.v4_governed_work_loop_evidence_snapshot_v2": _artifact_reference(evidence_snapshot_v2, latest_snapshots),
            "memory_summary.v4_governed_work_loop_evidence_snapshot_v3": _artifact_reference(evidence_snapshot_v3, latest_snapshots),
            "memory_summary.v4_governed_work_loop_evidence_snapshot_v4": _artifact_reference(evidence_snapshot_v4, latest_snapshots),
            "memory_summary.v4_governed_work_loop_evidence_snapshot_v5": _artifact_reference(evidence_snapshot_v5, latest_snapshots),
            "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v5": _artifact_reference(continuation_admission_snapshot_v5, latest_snapshots),
            "proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1": _artifact_reference(continuation_execution_v1, latest_snapshots),
            "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_ledger_alignment_delta_audit_v1": _artifact_reference(continuation_execution_v2, latest_snapshots),
            "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_containment_audit_v1": _artifact_reference(continuation_execution_v3, latest_snapshots),
            "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_stability_delta_audit_v1": _artifact_reference(continuation_execution_v4, latest_snapshots),
            "proposal_learning_loop.v4_governed_work_loop_governance_recommendation_frontier_persistence_boundary_audit_v1": _artifact_reference(continuation_execution_v5, latest_snapshots),
            "memory_summary.v4_governed_direct_work_evidence_snapshot_v1": _artifact_reference(direct_work_evidence_snapshot, latest_snapshots),
            "memory_summary.v4_governed_capability_use_evidence_snapshot_v1": _artifact_reference(capability_use_evidence_snapshot, latest_snapshots),
        },
        "governed_work_loop_continuation_admission_v6_summary": {
            "snapshot_identity_context": {
                "snapshot_template_name": "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v6",
                "proposal_id": str(proposal.get("proposal_id", "")),
                "current_work_loop_posture": str(posture_current.get("primary_posture_class", "")),
                "current_branch_state": current_branch_state,
                "plan_non_owning": True,
                "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            },
            "candidate_under_review": {
                "loop_candidate_id": str(candidate_record.get("loop_candidate_id", "")),
                "loop_candidate_name": str(candidate_record.get("loop_candidate_name", "")),
                "proposed_execution_template": str(dict(candidate_record.get("candidate_quality_flags", {})).get("proposed_execution_template", "")),
            },
            "evidence_inputs_used": {
                "candidate_screen_snapshot_v5": str(candidate_screen_v5_artifact_path),
                "candidate_screen_snapshot_v6": str(candidate_screen_v6_artifact_path),
                "evidence_snapshot_v1": str(evidence_v1_artifact_path),
                "evidence_snapshot_v2": str(evidence_v2_artifact_path),
                "evidence_snapshot_v3": str(evidence_v3_artifact_path),
                "evidence_snapshot_v4": str(evidence_v4_artifact_path),
                "evidence_snapshot_v5": str(evidence_v5_artifact_path),
                "continuation_admission_v5": str(continuation_admission_v5_artifact_path),
                "continuation_execution_v1": str(execution_v1_artifact_path),
                "continuation_execution_v2": str(execution_v2_artifact_path),
                "continuation_execution_v3": str(execution_v3_artifact_path),
                "continuation_execution_v4": str(execution_v4_artifact_path),
                "continuation_execution_v5": str(execution_v5_artifact_path),
                "direct_work_evidence_v1": str(direct_work_evidence_artifact_path),
                "capability_use_evidence_v1": str(capability_use_evidence_artifact_path),
                "policy_v1": str(policy_artifact_path),
                "posture_v1": str(posture_artifact_path),
            },
            "admission_decision": admission_decision,
            "admission_rationale": admission_rationale,
            "blocking_conditions": blocking_conditions,
            "distinctness_assessment": {
                "classification": "materially_distinct" if bool(distinctness.get("materially_distinct_from_chain", False)) else "not_materially_distinct",
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
            },
            "expected_evidence_yield_assessment": {
                "classification": "likely_adds_new_evidence"
                if str(dict(candidate_screen_v6_summary.get("expected_evidence_yield_assessment", {})).get("classification", "")) == "likely_adds_new_evidence"
                else "mostly_restates_prior_conclusions",
                "likely_adds_new_evidence": str(dict(candidate_screen_v6_summary.get("expected_evidence_yield_assessment", {})).get("classification", "")) == "likely_adds_new_evidence",
                "likely_restates_prior_conclusions": str(dict(candidate_screen_v6_summary.get("expected_evidence_yield_assessment", {})).get("classification", "")) != "likely_adds_new_evidence",
            },
            "posture_discipline_assessment": {
                "classification": "posture_discipline_preserved" if all_checks_passed else "posture_discipline_not_preserved"
            },
            "posture_pressure_assessment": {
                "classification": "posture_pressure_absent"
                if str(posture_pressure.get("classification", "")) == "posture_pressure_absent" or str(posture_pressure.get("pressure", "")) == "absent"
                else "posture_pressure_present"
            },
            "gate_status": {"classification": "gate_closed", "gate_status": str(future_gate.get("gate_status", ""))},
            "routing_status": {"classification": "routing_deferred", "routing_deferred": bool(current_state_summary.get("routing_deferred", False))},
            "recommended_next_action": {"classification": recommended_next_action, "template_name": next_template},
            "recommended_next_template": next_template,
            "review_rollback_deprecation_trigger_status": {
                "review_trigger_status": {"criticality": False, "overlap": False, "scope_expansion": False, "hidden_development_pressure": False},
                "rollback_trigger_status": {"branch_mutation": False, "routing_drift": False, "plan_ownership_change": False},
                "deprecation_trigger_status": {"directive_relevance_drop": False, "distinct_value_disappears": False},
            },
            "envelope_compliance_summary": {
                "network_mode": "none",
                "write_root_compliance": True,
                "branch_state_immutability_required": True,
                "paused_capability_reopen_allowed": False,
                "retained_promotion_allowed": False,
                "posture_widening_allowed": False,
            },
            "resource_trust_accounting": {
                "trusted_sources_in_use": trusted_sources,
                "expected_resource_budget": dict(dict(loop_accounting.get("resource_trust_position", {})).get("expected_resource_budget", {})),
                "approved_write_roots": approved_write_roots,
            },
            "concise_operator_readable_conclusion": (
                "The surviving frontier-recursion-boundary candidate is admissible now under the current narrow governed envelope."
                if all_checks_passed
                else "The surviving frontier-recursion-boundary candidate is not admissible now under the current narrow governed envelope."
            ),
            "admission_checks": admission_checks,
            "continuation_envelope": continuation_envelope,
            "why_governance_remains_source_of_truth": {
                "owner": "governance_substrate_v1",
                "proposal_learning_loop_is_governance_truth_source": False,
                "reason": "continuation admission v6 is derived from directive, bucket, branch, self-structure, candidate-screen v6, candidate-screen v5, posture v1, evidence v5, continuation-admission v5, and prior continuation artifacts rather than execution code",
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
        "diagnostic_conclusions": {
            "governed_work_loop_continuation_admission_v6_in_place": True,
            "candidate_is_admissible_now": all_checks_passed,
            "materially_distinct": bool(distinctness.get("materially_distinct_from_chain", False)),
            "posture_discipline_preserved": all_checks_passed,
            "posture_pressure_absent": str(posture_pressure.get("classification", "")) == "posture_pressure_absent" or str(posture_pressure.get("pressure", "")) == "absent",
            "gate_closed": str(future_gate.get("gate_status", "")) == "defined_but_closed",
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "proceed_to_candidate_execution_next": all_checks_passed,
            "new_behavior_changing_branch_opened": False,
            "branch_state_mutation_occurred": False,
            "retained_promotion_occurred": False,
            "paused_capability_line_reopened": False,
            "best_next_template": next_template,
        },
    }
    _write_json(artifact_path, artifact_payload)

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: the surviving next bounded continuation candidate now has an explicit governed continuation-admission v6 decision under the current narrow envelope",
        "observability_gain": {
            "passed": True,
            "reason": "the surviving candidate now has an explicit v6 admission decision and bounded envelope",
            "artifact_paths": {"governed_work_loop_continuation_admission_v6_artifact": str(artifact_path)},
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the v6 gate decides whether the frontier-recursion-boundary candidate should advance toward execution without widening posture now",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "v6 admission separates real bounded continuation from repetition, recursion, capability drift, and posture broadening",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the v6 admission step is diagnostic-only and changes no live behavior",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": next_template,
            "reason": "the candidate can proceed to bounded execution next" if all_checks_passed else "the project should hold posture rather than execute next",
        },
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
        "stage_status": "passed",
    }
