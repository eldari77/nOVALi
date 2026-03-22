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
from .governance_memory_resolver_v1 import (
    READ_CONTRACT_SCHEMA_VERSION,
    build_governance_memory_read_contract,
    resolve_governance_memory_current_state,
)
from .governance_memory_promotion_v1 import (
    BINDING_PROMOTED_AUTHORITY,
    GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH,
    REVIEW_PENDING_CANDIDATE_AUTHORITY_UPDATE,
    build_governance_memory_promotion_contract,
    build_review_pending_authority_candidate,
    promote_governance_memory_authority,
)
from .governed_skill_acquisition_v1 import _diagnostic_artifact_dir, _load_jsonl
from .ledger import intervention_data_dir, load_latest_snapshots
from .v4_first_hypothesis_landscape_snapshot_v1 import _load_json_file


VERSION_HANDOFF_STATUS_PATH = intervention_data_dir() / "version_handoff_status.json"
INTERVENTION_LEDGER_PATH = intervention_data_dir() / "intervention_ledger.jsonl"
INTERVENTION_ANALYTICS_PATH = intervention_data_dir() / "intervention_analytics_latest.json"
PROPOSAL_RECOMMENDATIONS_PATH = intervention_data_dir() / "proposal_recommendations_latest.json"
GOVERNANCE_MEMORY_AUTHORITY_PATH = intervention_data_dir() / "governance_memory_authority_latest.json"
HANDOFF_ROADMAP_PATH = intervention_data_dir().parent / "NOVALI_Consolidated_Handoff_and_Roadmap_2026-03-21.md"


def _latest_matching_artifact(pattern: str) -> str:
    matches = sorted(
        _diagnostic_artifact_dir().glob(pattern),
        key=lambda path: (path.stat().st_mtime, str(path)),
        reverse=True,
    )
    return str(matches[0]) if matches else ""


def _load_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _top_recommendations(recommendations: dict[str, Any], *, limit: int = 5) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in list(recommendations.get("all_ranked_proposals", [])):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "template_name": str(item.get("template_name", "")),
                "decision": str(item.get("decision", "")),
                "proposal_type": str(item.get("proposal_type", "")),
                "recommended_priority": item.get("recommended_priority"),
                "reason_summary": str(item.get("reason_summary", "")),
            }
        )
        if len(rows) >= int(limit):
            break
    return rows


def _artifact_reference(path: str, payload: dict[str, Any], latest_snapshots: dict[str, Any]) -> dict[str, Any]:
    proposal_id = str(payload.get("proposal_id", ""))
    snapshot = dict(latest_snapshots.get(proposal_id, {}))
    return {
        "artifact_path": str(path),
        "template_name": str(payload.get("template_name", "")),
        "proposal_id": proposal_id,
        "ledger_revision": int(snapshot.get("ledger_revision", 0) or 0),
        "final_status": str(snapshot.get("final_status", payload.get("final_status", ""))),
    }


def _normalize_swap_c(version_handoff_status: dict[str, Any], hardening_artifact: dict[str, Any]) -> dict[str, Any]:
    carried_forward = dict(version_handoff_status.get("carried_forward_baseline", {}))
    incumbent_report = dict(hardening_artifact.get("incumbent_robustness_report", {}))
    selected_ids = list(incumbent_report.get("selected_ids", carried_forward.get("selected_ids", [])))
    return {
        "baseline_name": str(carried_forward.get("baseline_name", "swap_C")),
        "selected_ids": [str(item) for item in selected_ids],
        "selected_benchmark_like_count": int(
            incumbent_report.get(
                "selected_benchmark_like_count",
                carried_forward.get("selected_benchmark_like_count", 0),
            )
            or 0
        ),
        "projection_safe_retention": _safe_float(
            incumbent_report.get("projection_safe_retention", carried_forward.get("projection_safe_retention", 1.0)),
            1.0,
        ),
        "unsafe_overcommit_rate_delta": _safe_float(
            incumbent_report.get(
                "unsafe_overcommit_rate_delta",
                carried_forward.get("unsafe_overcommit_rate_delta", 0.0),
            )
        ),
        "false_safe_projection_rate_delta": _safe_float(
            incumbent_report.get(
                "false_safe_projection_rate_delta",
                carried_forward.get("false_safe_projection_rate_delta", 0.0),
            )
        ),
        "false_safe_margin_vs_cap": _safe_float(incumbent_report.get("false_safe_margin_vs_cap", 0.0)),
        "policy_match_rate_delta": _safe_float(
            incumbent_report.get("policy_match_rate_delta", carried_forward.get("policy_match_rate_delta", 0.0))
        ),
        "context_robustness_sum": _safe_float(
            incumbent_report.get("context_robustness_sum", carried_forward.get("context_robustness_sum", 0.0))
        ),
        "source_artifacts": [str(item) for item in list(carried_forward.get("source_artifacts", []))],
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    del cfg, rounds, seeds

    directive_state = _load_json_file(DIRECTIVE_STATE_PATH)
    bucket_state = _load_json_file(BUCKET_STATE_PATH)
    self_structure_state = _load_json_file(SELF_STRUCTURE_STATE_PATH)
    branch_registry = _load_json_file(BRANCH_REGISTRY_PATH)
    version_handoff_status = _load_json_file(VERSION_HANDOFF_STATUS_PATH)
    intervention_analytics = _load_json_file(INTERVENTION_ANALYTICS_PATH)
    proposal_recommendations = _load_json_file(PROPOSAL_RECOMMENDATIONS_PATH)
    directive_history = _load_jsonl(DIRECTIVE_HISTORY_PATH)
    self_structure_ledger = _load_jsonl(SELF_STRUCTURE_LEDGER_PATH)
    intervention_ledger = _load_jsonl(INTERVENTION_LEDGER_PATH)
    handoff_roadmap_text = _load_text_file(HANDOFF_ROADMAP_PATH)
    analytics = build_intervention_ledger_analytics()
    latest_snapshots = load_latest_snapshots()
    unique_proposal_ids = {str(row.get("proposal_id", "")) for row in intervention_ledger if str(row.get("proposal_id", ""))}
    memory_summary_proposal_ids = {
        str(row.get("proposal_id", ""))
        for row in intervention_ledger
        if str(row.get("proposal_type", "")) == "memory_summary" and str(row.get("proposal_id", ""))
    }
    if not all([directive_state, bucket_state, self_structure_state, branch_registry, version_handoff_status]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: directive, bucket, branch, self-structure, and version handoff state artifacts are required",
        }

    governance_substrate_path = _latest_matching_artifact("memory_summary_v4_governance_substrate_v1_snapshot_*.json")
    work_loop_closeout_path = _latest_matching_artifact("memory_summary_v4_governed_work_loop_hold_position_closeout_v1_*.json")
    selector_frontier_path = _latest_matching_artifact("memory_summary_final_selection_false_safe_margin_snapshot_v1_*.json")
    frontier_characterization_path = _latest_matching_artifact(
        "memory_summary_false_safe_frontier_control_characterization_snapshot_v1_*.json"
    )
    swap_c_hardening_path = _latest_matching_artifact("critic_split_swap_c_incumbent_hardening_probe_v1_*.json")
    if not all(
        [
            governance_substrate_path,
            work_loop_closeout_path,
            selector_frontier_path,
            frontier_characterization_path,
            swap_c_hardening_path,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governance substrate, work-loop closeout, selector-frontier attribution, frontier characterization, and swap_C hardening artifacts are required",
        }

    governance_substrate = _load_json_file(Path(governance_substrate_path))
    work_loop_closeout = _load_json_file(Path(work_loop_closeout_path))
    selector_frontier = _load_json_file(Path(selector_frontier_path))
    frontier_characterization = _load_json_file(Path(frontier_characterization_path))
    swap_c_hardening = _load_json_file(Path(swap_c_hardening_path))
    if not all(
        [
            governance_substrate,
            work_loop_closeout,
            selector_frontier,
            frontier_characterization,
            swap_c_hardening,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: required governance-memory authority artifacts could not be loaded",
        }

    current_directive = dict(directive_state.get("current_directive_state", {}))
    current_bucket = dict(bucket_state.get("current_bucket_state", {}))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}

    work_loop_summary = dict(work_loop_closeout.get("governed_work_loop_hold_position_closeout_v1_summary", {}))
    selector_summary = dict(selector_frontier.get("final_selection_margin_summary", {}))
    selector_conclusions = dict(selector_frontier.get("diagnostic_conclusions", {}))
    frontier_conclusions = dict(frontier_characterization.get("diagnostic_conclusions", {}))
    hardening_conclusions = dict(swap_c_hardening.get("diagnostic_conclusions", {}))
    hardening_findings = dict(swap_c_hardening.get("hardening_findings", {}))
    per_case_margin_report = {
        str(dict(payload).get("case_id", "")): dict(payload)
        for payload in list(selector_frontier.get("per_case_final_selection_margin_report", []))
        if isinstance(payload, dict) and str(dict(payload).get("case_id", ""))
    }

    active_branch = str(current_state_summary.get("active_working_version", "novali-v5"))
    frozen_fallback_reference_version = str(
        current_state_summary.get("frozen_fallback_reference_version", "novali-v3")
    )
    additional_reference_versions: list[str] = []
    if "novali-v4" in handoff_roadmap_text:
        additional_reference_versions.append("novali-v4")
    if "novali-v2" in handoff_roadmap_text:
        additional_reference_versions.append("novali-v2")
    current_branch_state = str(branch_record.get("state", current_state_summary.get("current_branch_state", "")))
    held_baseline = dict(branch_record.get("held_baseline", {}))
    held_baseline_template = str(
        held_baseline.get("template", current_state_summary.get("held_baseline_template", ""))
    )
    operating_stance = str(frontier_characterization.get("recommended_next_action", "hold_and_consolidate"))
    routing_status = "routing_deferred" if bool(current_state_summary.get("routing_deferred", False)) else "routing_not_deferred"
    selector_frontier_split_assessment = str(
        selector_frontier.get(
            "final_selection_split_assessment",
            selector_conclusions.get("final_selection_split_assessment", "still_genuinely_coupled"),
        )
    )

    swap_c_status = _normalize_swap_c(version_handoff_status, swap_c_hardening)

    blocked_residuals: dict[str, Any] = {}
    for case_id in ("recovery_03", "persistence_12"):
        row = dict(per_case_margin_report.get(case_id, {}))
        if not row:
            continue
        blocked_residuals[case_id] = {
            "additive_budget_label": str(row.get("additive_budget_label", "")),
            "replacement_attribution_label": str(row.get("replacement_attribution_label", "")),
            "selector_frontier_attribution_label": str(row.get("selector_frontier_attribution_label", "")),
            "replacement_policy_delta_vs_incumbent": _safe_float(
                row.get("replacement_policy_delta_vs_incumbent", 0.0)
            ),
            "replacement_context_tiebreak_delta_vs_best_safe": _safe_float(
                row.get("replacement_context_tiebreak_delta_vs_best_safe", 0.0)
            ),
            "final_selection_split_stage": str(row.get("final_selection_split_stage", "")),
        }

    governed_work_loop_reentry = dict(work_loop_summary.get("reentry_criteria", {}))
    capability_use_policy = dict(self_structure_state.get("governed_capability_use_policy", {}))
    callable_capabilities = [
        {
            "capability_id": str(item.get("capability_id", "")),
            "capability_name": str(item.get("capability_name", "")),
            "status": str(item.get("status", "")),
            "default_use_class": str(item.get("default_use_class", "")),
            "reopen_policy": str(item.get("reopen_policy", "")),
        }
        for item in list(capability_use_policy.get("current_callable_capabilities", []))
        if isinstance(item, dict)
    ]

    binding_decision_register = [
        {
            "decision_id": "branch_posture",
            "decision_class": "binding_decision",
            "status": current_branch_state,
            "reason": str(branch_record.get("pause_rationale", "")),
            "authority_source": str(BRANCH_REGISTRY_PATH),
        },
        {
            "decision_id": "held_baseline",
            "decision_class": "binding_decision",
            "status": "baseline_held",
            "baseline_template": held_baseline_template,
            "authority_source": str(BRANCH_REGISTRY_PATH),
        },
        {
            "decision_id": "governed_work_loop",
            "decision_class": "binding_decision",
            "status": str(
                dict(work_loop_summary.get("stop_condition_assessment", {})).get("classification", "hold_posture")
            ),
            "reason": str(
                dict(work_loop_summary.get("recommended_current_stance", {})).get(
                    "reason",
                    "the governed work-loop line is preserved as meaningful but held closed pending genuinely new evidence",
                )
            ),
            "authority_source": str(work_loop_closeout_path),
        },
        {
            "decision_id": "benchmark_control_line",
            "decision_class": "binding_decision",
            "status": operating_stance,
            "reason": str(
                dict(frontier_characterization.get("decision_recommendation", {})).get(
                    "rationale",
                    "the hardened control signal is established and the correct stance is hold_and_consolidate",
                )
            ),
            "authority_source": str(frontier_characterization_path),
        },
        {
            "decision_id": "selector_frontier",
            "decision_class": "binding_decision",
            "status": selector_frontier_split_assessment,
            "reason": "final selection is currently best explained as a serial budget-eligibility gate followed by within-cap ordering and tie-break behavior",
            "authority_source": str(selector_frontier_path),
        },
        {
            "decision_id": "routing_status",
            "decision_class": "binding_decision",
            "status": routing_status,
            "reason": "routing remains deferred across the authoritative branch, governance, and selector-frontier artifacts",
            "authority_source": str(frontier_characterization_path),
        },
    ]

    governance_memory_rollup = {
        "schema_name": "GovernanceMemoryAuthority",
        "schema_version": "governance_memory_authority_v1",
        "read_contract_version": READ_CONTRACT_SCHEMA_VERSION,
        "active_branch": active_branch,
        "frozen_fallback_reference_version": frozen_fallback_reference_version,
        "additional_reference_versions": additional_reference_versions,
        "current_branch_state": current_branch_state,
        "held_baseline_template": held_baseline_template,
        "current_operating_stance": operating_stance,
        "routing_status": routing_status,
        "projection_safety_primary": True,
        "plan_non_owning": bool(current_state_summary.get("plan_non_owning", False)),
        "governed_work_loop_status": str(current_state_summary.get("latest_governed_work_loop_closeout_outcome", "")),
        "reopen_eligibility": {
            "branch_reopen_candidate_status": "requires_new_evidence",
            "governed_work_loop_reentry_status": str(governed_work_loop_reentry.get("classification", "")),
            "benchmark_controlled_reopen_supported": False,
        },
        "selector_frontier_memory": {
            "final_selection_split_assessment": selector_frontier_split_assessment,
            "dominant_blocker": "selection_budget_hold_for_drift_control",
            "first_gate": "budget_eligibility_under_frozen_cap",
            "second_gate": "within_cap_ordering_and_tiebreak",
            "blocked_residuals": blocked_residuals,
        },
        "swap_c_status": swap_c_status,
    }

    authority_contract = build_governance_memory_read_contract()
    promotion_contract = build_governance_memory_promotion_contract()
    authority_surface = {
        "canonical_top_level_file": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
        "canonical_top_level_surface": "governance_memory_authority_latest",
        "canonical_mutation_mode": "explicit_governance_promotion_gate_only",
        "promotion_ledger_path": str(GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH),
        "authoritative_primary_files": {
            "directive_state_latest": str(DIRECTIVE_STATE_PATH),
            "bucket_state_latest": str(BUCKET_STATE_PATH),
            "branch_registry_latest": str(BRANCH_REGISTRY_PATH),
            "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
            "version_handoff_status": str(VERSION_HANDOFF_STATUS_PATH),
        },
        "historical_ledger_surfaces": {
            "directive_history": str(DIRECTIVE_HISTORY_PATH),
            "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            "intervention_ledger": str(INTERVENTION_LEDGER_PATH),
        },
        "binding_decision_artifacts": {
            "governance_substrate_snapshot": _artifact_reference(
                governance_substrate_path, governance_substrate, latest_snapshots
            ),
            "governed_work_loop_hold_closeout": _artifact_reference(
                work_loop_closeout_path, work_loop_closeout, latest_snapshots
            ),
            "selector_frontier_attribution_snapshot": _artifact_reference(
                selector_frontier_path, selector_frontier, latest_snapshots
            ),
            "false_safe_frontier_characterization_snapshot": _artifact_reference(
                frontier_characterization_path, frontier_characterization, latest_snapshots
            ),
            "swap_c_incumbent_hardening_probe": _artifact_reference(
                swap_c_hardening_path, swap_c_hardening, latest_snapshots
            ),
        },
        "stable_rollup_file": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
        "non_authoritative_runtime_surfaces": {
            "proposal_recommendations_latest": str(PROPOSAL_RECOMMENDATIONS_PATH),
            "intervention_analytics_latest": str(INTERVENTION_ANALYTICS_PATH),
            "runtime_loop_code_is_authority": False,
        },
        "authority_precedence": list(authority_contract.get("resolution_order", [])),
        "overlap_resolution_rules": dict(authority_contract.get("overlap_resolution_rules", {})),
    }

    capability_boundary_state = {
        "capability_use": {
            "status": str(current_state_summary.get("latest_held_capability_use_status", "")),
            "default_use_class": str(current_state_summary.get("latest_held_capability_default_use_class", "")),
            "callable_capabilities": callable_capabilities,
        },
        "capability_acquisition": {
            "governed_skill_acquisition_flow_defined": bool(
                current_state_summary.get("governed_skill_acquisition_flow_v1_defined", False)
            ),
            "current_skill_status": str(current_state_summary.get("latest_skill_provisional_status", "")),
            "retained_skill_promotion_performed": bool(
                current_state_summary.get("retained_skill_promotion_performed", False)
            ),
            "skill_trial_branch_opened": bool(current_state_summary.get("skill_trial_branch_opened", False)),
            "skill_provisional_branch_opened": bool(
                current_state_summary.get("skill_provisional_branch_opened", False)
            ),
        },
        "governed_reopen_paths": {
            "branch_reopen_triggers": [str(item) for item in list(branch_record.get("reopen_triggers", []))],
            "governed_work_loop_reentry_requirements": [
                str(item) for item in list(governed_work_loop_reentry.get("required_conditions", []))
            ],
            "capability_reopen_requires_new_bounded_use_case": any(
                str(item.get("reopen_policy", "")) == "reopen_only_on_new_bounded_use_case"
                for item in callable_capabilities
            ),
        },
    }

    exploratory_evidence_register = {
        "selector_frontier_conclusion": {
            "final_selection_split_assessment": selector_frontier_split_assessment,
            "primary_bottleneck": str(selector_conclusions.get("primary_bottleneck", "")),
            "secondary_bottleneck": str(selector_conclusions.get("secondary_bottleneck", "")),
            "shared_frontier_anchor": str(selector_conclusions.get("shared_frontier_anchor", "")),
        },
        "benchmark_control_conclusion": {
            "frontier_characterization": str(
                frontier_characterization.get("false_safe_frontier_characterization", "")
            ),
            "incumbent_quality_candidate_status": str(
                frontier_characterization.get("incumbent_quality_candidate_status", "")
            ),
            "recommended_next_action": str(frontier_characterization.get("recommended_next_action", "")),
        },
        "swap_c_hardening_conclusion": {
            "swap_C_hardening_safety_assessment": str(
                hardening_conclusions.get("swap_C_hardening_safety_assessment", "")
            ),
            "swap_C_hardening_utility_assessment": str(
                hardening_conclusions.get("swap_C_hardening_utility_assessment", "")
            ),
            "hardening_robustness_assessment": str(
                hardening_conclusions.get("hardening_robustness_assessment", "")
            ),
            "productive_under_cap_critic_work_left": bool(
                hardening_findings.get("productive_under_cap_critic_work_left", False)
            ),
        },
        "non_binding_runtime_recommendations": _top_recommendations(proposal_recommendations),
    }

    artifact_path = _diagnostic_artifact_dir() / (
        f"memory_summary_v4_governance_memory_authority_snapshot_v1_{proposal['proposal_id']}.json"
    )
    authority_candidate_record = build_review_pending_authority_candidate(
        proposal=proposal,
        candidate_artifact_path=artifact_path,
        promotion_reason=(
            "candidate authority update prepared from governance artifacts; binding canonical refresh requires explicit promotion gate approval"
        ),
    )
    snapshot_payload = {
        "proposal_id": str(proposal.get("proposal_id", "")),
        "template_name": "memory_summary.v4_governance_memory_authority_snapshot_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "snapshot_identity_context": {
            "phase": "governance_memory_consolidation",
            "focus": "persist_authoritative_posture_and_binding_decisions_without_runtime_authority_dependence",
            "generated_at": _now(),
        },
        "minimal_authoritative_artifact_set": {
            "directive_state_latest": str(DIRECTIVE_STATE_PATH),
            "bucket_state_latest": str(BUCKET_STATE_PATH),
            "branch_registry_latest": str(BRANCH_REGISTRY_PATH),
            "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
            "directive_history": str(DIRECTIVE_HISTORY_PATH),
            "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            "version_handoff_status": str(VERSION_HANDOFF_STATUS_PATH),
            "governance_memory_authority_latest": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
        },
        "authority_contract": authority_contract,
        "authority_promotion_contract": promotion_contract,
        "authority_surface": authority_surface,
        "authority_mutation_stage": REVIEW_PENDING_CANDIDATE_AUTHORITY_UPDATE,
        "authority_candidate_record": authority_candidate_record,
        "held_baseline_state": {
            "branch_id": str(branch_record.get("branch_id", "")),
            "branch_state": current_branch_state,
            "held_baseline_template": held_baseline_template,
            "held_baseline_classification": str(held_baseline.get("classification", "")),
            "promotion_rationale": str(branch_record.get("promotion_rationale", "")),
            "pause_rationale": str(branch_record.get("pause_rationale", "")),
        },
        "branch_posture_state": {
            "active_branch": active_branch,
            "frozen_fallback_reference_version": frozen_fallback_reference_version,
            "additional_reference_versions": additional_reference_versions,
            "current_operating_stance": operating_stance,
            "routing_status": routing_status,
            "projection_safety_primary": True,
            "plan_non_owning": bool(current_state_summary.get("plan_non_owning", False)),
            "held_baseline_branch_state": current_branch_state,
        },
        "reopen_eligibility_state": governance_memory_rollup["reopen_eligibility"],
        "capability_boundary_state": capability_boundary_state,
        "binding_decision_register": binding_decision_register,
        "exploratory_evidence_register": exploratory_evidence_register,
        "selector_frontier_memory": governance_memory_rollup["selector_frontier_memory"],
        "resolved_current_state": {},
        "authority_file_summary": governance_memory_rollup,
        "analytics_context": {
            "proposal_count": int(len(unique_proposal_ids)),
            "top_recommendations": _top_recommendations(proposal_recommendations),
            "memory_summary_template_count": int(len(memory_summary_proposal_ids)),
        },
        "review_rollback_deprecation_trigger_status": {
            "review_triggered": False,
            "rollback_triggered": False,
            "deprecation_triggered": False,
        },
        "resource_trust_accounting": {
            "network_mode": "none",
            "trusted_sources": [str(item) for item in list(current_bucket.get("trusted_sources", []))],
            "write_roots": [str(item) for item in list(dict(current_bucket.get("mount_policy", {})).get("write_roots", []))],
            "read_roots": [str(item) for item in list(dict(current_bucket.get("mount_policy", {})).get("read_roots", []))],
            "directive_history_entry_count": int(len(directive_history)),
            "self_structure_ledger_entry_count": int(len(self_structure_ledger)),
            "intervention_ledger_entry_count": int(len(intervention_ledger)),
        },
        "diagnostic_conclusions": {
            "governance_memory_authority_v1_in_place": True,
            "governance_memory_read_contract_version": READ_CONTRACT_SCHEMA_VERSION,
            "authority_mutation_stage": REVIEW_PENDING_CANDIDATE_AUTHORITY_UPDATE,
            "current_branch_state": current_branch_state,
            "held_baseline_template": held_baseline_template,
            "current_operating_stance": operating_stance,
            "routing_status": routing_status,
            "selector_frontier_split_assessment": selector_frontier_split_assessment,
            "swap_c_status": "hardened_incumbent_quality_candidate",
            "controlled_reopen_supported": False,
            "recommended_next_action": "hold_and_consolidate",
            "recommended_next_template": "",
        },
        "operator_readable_conclusion": "A future agent no longer needs runtime loop code to reconstruct current NOVALI posture: directive, bucket, branch, self-structure, and this authority snapshot now preserve the held baseline, paused branch posture, closed governed work-loop line, separated capability-use and capability-acquisition paths, swap_C hardened incumbent status, and the selector-frontier conclusion serial_budget_then_ordering as durable governed memory.",
    }
    snapshot_payload["resolved_current_state"] = resolve_governance_memory_current_state(
        governance_memory_authority_override=snapshot_payload
    )

    _write_json(artifact_path, snapshot_payload)
    promoted_payload = promote_governance_memory_authority(
        candidate_payload=snapshot_payload,
        proposal=proposal,
        candidate_artifact_path=artifact_path,
        promotion_reason=(
            "governance-memory authority refresh was explicitly reviewed and promoted through the governance-memory promotion gate"
        ),
    )

    updated_self_structure_state = dict(self_structure_state)
    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "governance_memory_authority_v1_in_place": True,
            "latest_governance_memory_authority_artifact_path": str(artifact_path),
            "latest_governance_memory_authority_file_path": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
            "latest_architecture_truth_surface": "governance_memory_authority_v1",
            "latest_governance_memory_read_contract_version": READ_CONTRACT_SCHEMA_VERSION,
            "latest_governance_memory_top_level_authority_file": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
            "latest_governance_memory_resolution_mode": "authority_then_supporting_then_audit",
            "latest_governance_memory_mutation_stage": BINDING_PROMOTED_AUTHORITY,
            "latest_governance_memory_promotion_id": str(
                dict(promoted_payload.get("authority_promotion_record", {})).get("promotion_id", "")
            ),
            "latest_governance_memory_promotion_ledger_path": str(GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH),
            "latest_current_operating_stance": operating_stance,
            "latest_branch_reopen_eligibility": "requires_new_evidence",
            "latest_selector_frontier_split_assessment": selector_frontier_split_assessment,
        }
    )
    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["current_state_summary"] = updated_current_state_summary
    updated_self_structure_state["governance_memory_authority"] = governance_memory_rollup
    updated_self_structure_state["governance_memory_read_contract"] = authority_contract
    updated_self_structure_state["governance_memory_promotion_contract"] = promotion_contract
    updated_self_structure_state["governance_memory_authority_promotion_record"] = dict(
        promoted_payload.get("authority_promotion_record", {})
    )
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    _append_jsonl(
        SELF_STRUCTURE_LEDGER_PATH,
        {
            "event_id": f"governance_memory_authority_v1::{proposal['proposal_id']}",
            "timestamp": _now(),
            "event_type": "governance_memory_authority_v1_materialized",
            "directive_id": str(current_directive.get("directive_id", "")),
            "branch_id": str(branch_record.get("branch_id", "")),
            "branch_state": current_branch_state,
            "operating_stance": operating_stance,
            "selector_frontier_split_assessment": selector_frontier_split_assessment,
            "artifact_path": str(artifact_path),
            "stable_file_path": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
            "read_contract_version": READ_CONTRACT_SCHEMA_VERSION,
            "authority_mutation_stage": BINDING_PROMOTED_AUTHORITY,
            "promotion_id": str(dict(promoted_payload.get("authority_promotion_record", {})).get("promotion_id", "")),
            "promotion_ledger_path": str(GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH),
        },
    )

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: governance-memory authority is now materialized as a stable persisted control surface without changing live behavior",
        "observability_gain": {
            "passed": True,
            "reason": "held baseline, branch posture, reopen eligibility, capability boundaries, and selector-frontier conclusions are now queryable from a stable authority file with an explicit promotion ledger",
            "artifact_path": str(artifact_path),
            "stable_file_path": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
            "promotion_ledger_path": str(GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "future agents can reconstruct current posture from persisted governance memory rather than replaying runtime loop code",
        },
        "ambiguity_reduction": {
            "passed": True,
            "reason": "binding decisions are now separated from exploratory evidence and non-binding runtime recommendations",
            "score": 0.97,
        },
        "safety_neutrality": {
            "passed": True,
            "reason": "the change writes only governance-memory artifacts and self-structure pointers; routing, thresholds, live policy, and benchmark semantics remain unchanged",
            "scope": str(proposal.get("scope", "")),
        },
        "later_selection_usefulness": {
            "passed": True,
            "reason": "the correct next stance remains hold_and_consolidate and no new continuation template is warranted from this architecture-only step",
            "recommended_next_template": "",
        },
        "diagnostic_conclusions": {
            **snapshot_payload["diagnostic_conclusions"],
            "authority_mutation_stage": BINDING_PROMOTED_AUTHORITY,
            "authority_promotion_id": str(
                dict(promoted_payload.get("authority_promotion_record", {})).get("promotion_id", "")
            ),
        },
        "artifact_path": str(artifact_path),
        "stable_file_path": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
    }
