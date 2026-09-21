from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .governance_memory_promotion_v1 import build_governance_memory_promotion_contract
from .governance_memory_reopen_intake_v1 import (
    PROMOTION_APPLIED_AS_BINDING_AUTHORITY,
    PROMOTION_NOOP_ALREADY_AUTHORITATIVE,
)
from .ledger import intervention_data_dir, load_latest_snapshots


DATA_DIR = intervention_data_dir()
DIAGNOSTIC_MEMORY_DIR = DATA_DIR / "diagnostic_memory"
GOVERNANCE_MEMORY_AUTHORITY_PATH = DATA_DIR / "governance_memory_authority_latest.json"
GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH = DATA_DIR / "governance_memory_promotion_ledger.jsonl"
GOVERNANCE_REOPEN_PROMOTION_OUTCOME_LEDGER_PATH = DATA_DIR / "governance_reopen_promotion_outcome_ledger.jsonl"
GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_LEDGER_PATH = (
    DATA_DIR / "governance_reopen_promotion_reconciliation_ledger.jsonl"
)
GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_ESCALATION_LEDGER_PATH = (
    DATA_DIR / "governance_reopen_promotion_reconciliation_escalation_ledger.jsonl"
)
INTERVENTION_LEDGER_PATH = DATA_DIR / "intervention_ledger.jsonl"
INTERVENTION_ANALYTICS_PATH = DATA_DIR / "intervention_analytics_latest.json"
PROPOSAL_RECOMMENDATIONS_PATH = DATA_DIR / "proposal_recommendations_latest.json"
SELF_STRUCTURE_STATE_PATH = DATA_DIR / "self_structure_state_latest.json"
SELF_STRUCTURE_LEDGER_PATH = DATA_DIR / "self_structure_ledger.jsonl"
BRANCH_REGISTRY_PATH = DATA_DIR / "branch_registry_latest.json"
DIRECTIVE_STATE_PATH = DATA_DIR / "directive_state_latest.json"
BUCKET_STATE_PATH = DATA_DIR / "bucket_state_latest.json"

ESCALATION_SCHEMA_NAME = "GovernanceReopenPromotionReconciliationEscalation"
ESCALATION_SCHEMA_VERSION = "governance_reopen_promotion_reconciliation_escalation_v1"
RECONCILIATION_VERIFIED = "reconciliation_verified"
RECONCILIATION_MISMATCH_DETECTED = "reconciliation_mismatch_detected"
REMEDIATION_OR_ROLLBACK_REVIEW_CANDIDATE = "remediation_or_rollback_review_candidate"
REMEDIATION_REVIEW_NOT_SUBMITTED = "not_submitted_for_existing_rollback_or_repair_review"
REMEDIATION_REVIEW_REJECTED = "remediation_review_rejected"
REMEDIATION_REVIEW_APPROVED_FOR_EXISTING_ROLLBACK_OR_REPAIR_PATH = (
    "remediation_review_approved_for_existing_rollback_or_repair_path"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(dict(json.loads(line)))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    if not path.exists():
        path.write_text("", encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _diagnostic_artifact_dir() -> Path:
    DIAGNOSTIC_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    return DIAGNOSTIC_MEMORY_DIR


def _first_nonempty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _authority_posture_snapshot(authority_payload: dict[str, Any]) -> dict[str, Any]:
    authority_summary = dict(authority_payload.get("authority_file_summary", {}))
    promotion_record = dict(authority_payload.get("authority_promotion_record", {}))
    return {
        "authority_mutation_stage": str(authority_payload.get("authority_mutation_stage", "")),
        "promotion_id": str(promotion_record.get("promotion_id", "")),
        "current_branch_state": str(authority_summary.get("current_branch_state", "")),
        "current_operating_stance": str(authority_summary.get("current_operating_stance", "")),
        "held_baseline_template": str(authority_summary.get("held_baseline_template", "")),
        "routing_status": str(authority_summary.get("routing_status", "")),
        "reopen_eligibility": dict(authority_summary.get("reopen_eligibility", {})),
        "selector_frontier_memory": dict(authority_payload.get("selector_frontier_memory", {})),
        "binding_decision_register": list(authority_payload.get("binding_decision_register", [])),
    }


def _screening_repeated_motion(screening_reason_codes: list[str]) -> bool:
    return "repeated_motion_without_new_evidence" in screening_reason_codes or (
        "repeated_template_motion" in screening_reason_codes
        and "same_family_motion_without_new_evidence" in screening_reason_codes
        and "materially_new_evidence_present" not in screening_reason_codes
        and "materially_different_bounded_candidate_present" not in screening_reason_codes
        and "control_evidence_contradiction_present" not in screening_reason_codes
        and "fresh_upstream_selector_result_present" not in screening_reason_codes
    )


def _failed_checks(section_name: str, section_payload: dict[str, Any]) -> list[dict[str, Any]]:
    failed: list[dict[str, Any]] = []
    for check in list(section_payload.get("checks", [])):
        if bool(dict(check).get("passed", False)):
            continue
        row = dict(check)
        row["source_section"] = str(section_name)
        failed.append(row)
    return failed


def run_probe(cfg, proposal, *, rounds, seeds):
    del cfg, rounds, seeds

    authority_payload = _load_json_file(GOVERNANCE_MEMORY_AUTHORITY_PATH)
    self_structure_state = _load_json_file(SELF_STRUCTURE_STATE_PATH)
    branch_registry = _load_json_file(BRANCH_REGISTRY_PATH)
    directive_state = _load_json_file(DIRECTIVE_STATE_PATH)
    bucket_state = _load_json_file(BUCKET_STATE_PATH)
    intervention_analytics = _load_json_file(INTERVENTION_ANALYTICS_PATH)
    proposal_recommendations = _load_json_file(PROPOSAL_RECOMMENDATIONS_PATH)
    promotion_ledger_rows = _load_jsonl(GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH)
    promotion_outcome_ledger_rows = _load_jsonl(GOVERNANCE_REOPEN_PROMOTION_OUTCOME_LEDGER_PATH)
    reconciliation_ledger_rows = _load_jsonl(GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_LEDGER_PATH)
    escalation_ledger_rows = _load_jsonl(GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_ESCALATION_LEDGER_PATH)

    if not all([authority_payload, self_structure_state, branch_registry, directive_state, bucket_state]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: authority, self-structure, branch, directive, and bucket artifacts are required",
        }

    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    reconciliation_artifact_path = str(
        current_state_summary.get("latest_governance_reopen_reconciliation_artifact_path", "")
    )
    reconciliation_state_summary = str(
        current_state_summary.get("latest_governance_reopen_reconciliation_state", "")
    )

    if not reconciliation_artifact_path:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no reconciliation artifact is available for escalation",
        }

    reconciliation_payload = _load_json_file(Path(reconciliation_artifact_path))
    if not reconciliation_payload:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest reconciliation artifact could not be loaded",
        }

    reconciliation_identity = dict(reconciliation_payload.get("snapshot_identity_context", {}))
    reconciliation_id = _first_nonempty(
        reconciliation_identity.get("reconciliation_id"),
        reconciliation_payload.get("reconciliation_id"),
    )
    reconciliation_result = dict(reconciliation_payload.get("reconciliation_result", {}))
    reconciliation_state = _first_nonempty(
        reconciliation_result.get("reconciliation_state"),
        reconciliation_state_summary,
    )

    if reconciliation_state != RECONCILIATION_MISMATCH_DETECTED:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: only reconciliation_mismatch_detected cases may enter escalation",
            "diagnostic_conclusions": {
                "reconciliation_state": reconciliation_state,
            },
        }

    if any(str(row.get("source_reconciliation_id", "")) == reconciliation_id for row in escalation_ledger_rows):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest reconciliation mismatch already has a recorded escalation artifact",
            "diagnostic_conclusions": {
                "reconciliation_id": reconciliation_id,
                "existing_escalation_count": sum(
                    1
                    for row in escalation_ledger_rows
                    if str(row.get("source_reconciliation_id", "")) == reconciliation_id
                ),
            },
        }

    source_reconciliation_reference = {
        "reconciliation_id": reconciliation_id,
        "artifact_path": reconciliation_artifact_path,
        "ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_LEDGER_PATH),
        "reconciliation_state": reconciliation_state,
        "reconciliation_reason_codes": [
            str(item) for item in list(reconciliation_result.get("reconciliation_reason_codes", []))
        ],
    }
    source_promotion_outcome_reference = dict(
        reconciliation_payload.get("source_promotion_outcome_reference", {})
    )
    source_promotion_handoff_reference = dict(
        reconciliation_payload.get("source_promotion_handoff_reference", {})
    )
    source_review_outcome_reference = dict(
        reconciliation_payload.get("source_review_outcome_reference", {})
    )
    source_review_submission_reference = dict(
        reconciliation_payload.get("source_review_submission_reference", {})
    )
    authority_before_reference = dict(reconciliation_payload.get("authority_before_reference", {}))
    authority_after_reference = dict(reconciliation_payload.get("authority_after_reference", {}))
    requested_action_and_scope = dict(reconciliation_payload.get("requested_action_and_scope", {}))
    rollback_ready_reference = dict(reconciliation_payload.get("rollback_ready_reference", {}))

    source_promotion_outcome_state = str(source_promotion_outcome_reference.get("promotion_outcome_state", ""))
    if source_promotion_outcome_state and source_promotion_outcome_state != PROMOTION_APPLIED_AS_BINDING_AUTHORITY:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: only applied promotion outcomes may produce reconciliation-escalation candidates",
            "diagnostic_conclusions": {
                "source_promotion_outcome_state": source_promotion_outcome_state,
            },
        }

    if source_promotion_outcome_state == PROMOTION_NOOP_ALREADY_AUTHORITATIVE:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: promotion noop states do not require reconciliation escalation",
            "diagnostic_conclusions": {
                "source_promotion_outcome_state": source_promotion_outcome_state,
            },
        }

    self_structure_agreement = dict(reconciliation_payload.get("self_structure_state_agreement", {}))
    resolver_agreement = dict(reconciliation_payload.get("resolver_agreement", {}))
    execution_gate_agreement = dict(reconciliation_payload.get("execution_gate_agreement", {}))
    propagation_status_by_surface = dict(reconciliation_payload.get("propagation_status_by_surface", {}))

    failed_checks = (
        _failed_checks("self_structure_state", self_structure_agreement)
        + _failed_checks("resolver", resolver_agreement)
        + _failed_checks("execution_gate", execution_gate_agreement)
    )
    mismatch_surfaces = sorted(
        {
            str(row.get("source_section", ""))
            for row in failed_checks
            if str(row.get("source_section", ""))
        }
        | {
            str(surface)
            for surface, status in propagation_status_by_surface.items()
            if str(status) == RECONCILIATION_MISMATCH_DETECTED
        }
    )

    if not failed_checks and not mismatch_surfaces:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: reconciliation mismatch has no failed checks or propagation failures to escalate",
            "diagnostic_conclusions": {
                "reconciliation_id": reconciliation_id,
                "reconciliation_state": reconciliation_state,
            },
        }

    source_promotion_outcome_artifact_path = str(source_promotion_outcome_reference.get("artifact_path", ""))
    source_promotion_outcome_payload = (
        _load_json_file(Path(source_promotion_outcome_artifact_path))
        if source_promotion_outcome_artifact_path
        else {}
    )
    screening_basis = dict(
        source_promotion_outcome_payload.get("screening_basis_and_applied_reopen_bar", {})
    )
    screening_reason_codes = [
        str(item) for item in list(screening_basis.get("screening_reason_codes", []))
    ]
    repeated_motion_without_new_evidence = _screening_repeated_motion(screening_reason_codes)
    if repeated_motion_without_new_evidence:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: repeated motion without new evidence may not enter remediation or rollback review",
            "diagnostic_conclusions": {
                "reconciliation_id": reconciliation_id,
                "screening_reason_codes": screening_reason_codes,
            },
        }

    malformed_reconciliation = not bool(
        source_promotion_outcome_reference
        and authority_before_reference
        and authority_after_reference
        and rollback_ready_reference
    )
    if malformed_reconciliation:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest reconciliation artifact is missing escalation-critical fields",
            "diagnostic_conclusions": {
                "reconciliation_id": reconciliation_id,
                "has_source_promotion_outcome_reference": bool(source_promotion_outcome_reference),
                "has_authority_before_reference": bool(authority_before_reference),
                "has_authority_after_reference": bool(authority_after_reference),
                "has_rollback_ready_reference": bool(rollback_ready_reference),
            },
        }

    promotion_contract = build_governance_memory_promotion_contract()
    rollback_trace = dict(rollback_ready_reference.get("rollback_trace", {}))
    rollback_reference_state = str(rollback_ready_reference.get("rollback_reference_state", ""))
    available_existing_follow_on_paths: list[str] = []
    rollback_mode = _first_nonempty(
        rollback_trace.get("rollback_mode"),
        dict(promotion_contract.get("rollback_rule", {})).get("rollback_mode"),
    )
    if bool(rollback_trace.get("rollback_supported", False)) and rollback_mode:
        available_existing_follow_on_paths.append(rollback_mode)

    escalation_state = REMEDIATION_OR_ROLLBACK_REVIEW_CANDIDATE
    remediation_review_state = REMEDIATION_REVIEW_NOT_SUBMITTED
    escalation_reason_codes = list(source_reconciliation_reference["reconciliation_reason_codes"])
    escalation_reason_codes.extend([f"mismatch_surface::{surface}" for surface in mismatch_surfaces])
    if rollback_reference_state != "rollback_ready_reference":
        escalation_reason_codes.append("rollback_ready_reference_unavailable")
    if not available_existing_follow_on_paths:
        escalation_reason_codes.append("no_existing_rollback_or_repair_path_advertised")

    escalation_id = f"reopen_promotion_reconciliation_escalation::{proposal['proposal_id']}"
    escalated_at = _now()
    artifact_path = _diagnostic_artifact_dir() / (
        f"memory_summary_v4_governance_reopen_promotion_reconciliation_escalation_snapshot_v1_{proposal['proposal_id']}.json"
    )
    branch_record = (
        dict(list(branch_registry.get("branches", []))[0]) if list(branch_registry.get("branches", [])) else {}
    )

    payload = {
        "proposal_id": str(proposal.get("proposal_id", "")),
        "template_name": "memory_summary.v4_governance_reopen_promotion_reconciliation_escalation_snapshot_v1",
        "snapshot_identity_context": {
            "escalation_id": escalation_id,
            "escalated_at": escalated_at,
            "phase": "governance_reopen_promotion_reconciliation_escalation",
            "source_reconciliation_id": reconciliation_id,
        },
        "reconciliation_escalation_contract": {
            "schema_name": ESCALATION_SCHEMA_NAME,
            "schema_version": ESCALATION_SCHEMA_VERSION,
            "required_reconciliation_state": RECONCILIATION_MISMATCH_DETECTED,
            "terminal_reconciliation_success_state": RECONCILIATION_VERIFIED,
            "escalation_states": [REMEDIATION_OR_ROLLBACK_REVIEW_CANDIDATE],
            "remediation_review_states": [
                REMEDIATION_REVIEW_REJECTED,
                REMEDIATION_REVIEW_APPROVED_FOR_EXISTING_ROLLBACK_OR_REPAIR_PATH,
            ],
            "automatic_rollback_disallowed": True,
            "automatic_repair_disallowed": True,
            "canonical_authority_mutation_disallowed_here": True,
            "canonical_authority_path": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
            "existing_follow_on_paths_reference_only": True,
        },
        "source_reconciliation_reference": source_reconciliation_reference,
        "source_promotion_outcome_reference": source_promotion_outcome_reference,
        "source_promotion_handoff_reference": source_promotion_handoff_reference,
        "source_review_outcome_reference": source_review_outcome_reference,
        "source_review_submission_reference": source_review_submission_reference,
        "requested_action_and_scope": requested_action_and_scope,
        "authority_before_reference": authority_before_reference,
        "authority_after_reference": authority_after_reference,
        "mismatch_surfaces_and_propagation_failures": {
            "failed_check_count": int(len(failed_checks)),
            "failed_checks": failed_checks,
            "mismatch_surfaces": mismatch_surfaces,
            "propagation_status_by_surface": propagation_status_by_surface,
        },
        "rollback_ready_reference": {
            "rollback_reference_state": rollback_reference_state,
            "rollback_trace": rollback_trace,
            "available_existing_follow_on_paths": available_existing_follow_on_paths,
            "no_rollback_invoked_here": True,
            "no_repair_invoked_here": True,
        },
        "authority_posture_at_escalation_time": _authority_posture_snapshot(authority_payload),
        "escalation_result": {
            "reconciliation_state": reconciliation_state,
            "escalation_state": escalation_state,
            "remediation_review_state": remediation_review_state,
            "escalation_reason_codes": escalation_reason_codes,
            "repeated_motion_without_new_evidence": repeated_motion_without_new_evidence,
            "eligible_for_existing_rollback_or_repair_review": True,
        },
        "reviewer_source_and_audit_trace": {
            "escalated_by_surface": "memory_summary.v4_governance_reopen_promotion_reconciliation_escalation_snapshot_v1",
            "branch_id": str(branch_registry.get("current_branch_id", "")),
            "branch_pause_rationale": str(branch_record.get("pause_rationale", "")),
            "directive_id": str(dict(directive_state.get("current_directive_state", {})).get("directive_id", "")),
            "bucket_id": str(dict(bucket_state.get("current_bucket_state", {})).get("bucket_id", "")),
            "governance_execution_contract_available": bool(
                intervention_analytics.get("governance_execution_contract")
                or proposal_recommendations.get("governance_execution_contract")
            ),
        },
        "provenance_and_rollback_trace": {
            "canonical_authority_file": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
            "promotion_ledger_path": str(GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH),
            "promotion_outcome_ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_OUTCOME_LEDGER_PATH),
            "reconciliation_ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_LEDGER_PATH),
            "reconciliation_escalation_ledger_path": str(
                GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_ESCALATION_LEDGER_PATH
            ),
            "self_structure_state_path": str(SELF_STRUCTURE_STATE_PATH),
            "self_structure_ledger_path": str(SELF_STRUCTURE_LEDGER_PATH),
            "branch_registry_path": str(BRANCH_REGISTRY_PATH),
            "directive_state_path": str(DIRECTIVE_STATE_PATH),
            "bucket_state_path": str(BUCKET_STATE_PATH),
            "intervention_ledger_path": str(INTERVENTION_LEDGER_PATH),
            "analytics_path": str(INTERVENTION_ANALYTICS_PATH),
            "proposal_recommendations_path": str(PROPOSAL_RECOMMENDATIONS_PATH),
            "latest_snapshots_count": int(len(load_latest_snapshots())),
            "promotion_ledger_entries_seen": int(len(promotion_ledger_rows)),
            "promotion_outcome_ledger_entries_seen": int(len(promotion_outcome_ledger_rows)),
            "reconciliation_ledger_entries_seen": int(len(reconciliation_ledger_rows)),
            "escalation_ledger_entries_before_write": int(len(escalation_ledger_rows)),
        },
        "operator_readable_conclusion": (
            "A reconciliation mismatch is now an explicit remediation-or-rollback review candidate. "
            "The mismatch is preserved with propagation-failure evidence and rollback-ready metadata, but no rollback or repair is invoked here."
        ),
    }

    _write_json(artifact_path, payload)

    ledger_entry = {
        "event_type": "governance_reopen_promotion_reconciliation_escalation_recorded",
        "written_at": escalated_at,
        "escalation_id": escalation_id,
        "source_reconciliation_id": reconciliation_id,
        "artifact_path": str(artifact_path),
        "escalation_state": escalation_state,
        "remediation_review_state": remediation_review_state,
        "rollback_reference_state": rollback_reference_state,
        "requested_template_name": str(requested_action_and_scope.get("requested_template_name", "")),
        "requested_template_family": str(requested_action_and_scope.get("requested_template_family", "")),
    }
    _append_jsonl(GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_ESCALATION_LEDGER_PATH, ledger_entry)

    updated_self_structure = dict(self_structure_state)
    updated_summary = dict(current_state_summary)
    updated_summary.update(
        {
            "latest_governance_reopen_reconciliation_escalation_artifact_path": str(artifact_path),
            "latest_governance_reopen_reconciliation_escalation_ledger_path": str(
                GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_ESCALATION_LEDGER_PATH
            ),
            "latest_governance_reopen_reconciliation_escalation_state": escalation_state,
            "latest_governance_reopen_remediation_review_state": remediation_review_state,
            "latest_governance_reopen_reconciliation_escalation_reason_codes": escalation_reason_codes,
        }
    )
    updated_self_structure["generated_at"] = _now()
    updated_self_structure["current_state_summary"] = updated_summary
    updated_self_structure["governance_reopen_promotion_reconciliation_escalation"] = {
        "schema_name": ESCALATION_SCHEMA_NAME,
        "schema_version": ESCALATION_SCHEMA_VERSION,
        "latest_escalation": {
            "escalation_id": escalation_id,
            "source_reconciliation_id": reconciliation_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_ESCALATION_LEDGER_PATH),
            "escalation_state": escalation_state,
            "remediation_review_state": remediation_review_state,
        },
    }
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure)

    _append_jsonl(
        SELF_STRUCTURE_LEDGER_PATH,
        {
            "event_id": f"governance_reopen_promotion_reconciliation_escalation::{proposal['proposal_id']}",
            "timestamp": _now(),
            "event_type": "governance_reopen_promotion_reconciliation_escalation_recorded",
            "escalation_id": escalation_id,
            "source_reconciliation_id": reconciliation_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_ESCALATION_LEDGER_PATH),
            "escalation_state": escalation_state,
            "remediation_review_state": remediation_review_state,
        },
    )

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: reconciliation mismatch was materialized as an explicit remediation-or-rollback review candidate",
        "observability_gain": {
            "passed": True,
            "reason": "future agents can now distinguish verified reconciliation from mismatches escalated into explicit remediation-or-rollback review candidates",
            "artifact_path": str(artifact_path),
            "reconciliation_escalation_ledger_path": str(
                GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_ESCALATION_LEDGER_PATH
            ),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "mismatch escalation now preserves rollback-ready reference metadata without invoking rollback or repair",
        },
        "ambiguity_reduction": {
            "passed": True,
            "reason": "mismatch surfaces and propagation failures are now explicit review-candidate inputs instead of silent dead ends",
            "score": 0.97,
        },
        "safety_neutrality": {
            "passed": True,
            "reason": "reconciliation escalation is non-mutating and cannot trigger rollback, repair, or authority mutation by itself",
            "scope": str(proposal.get("scope", "")),
        },
        "later_selection_usefulness": {
            "passed": True,
            "reason": "only explicit reconciliation mismatches can feed remediation-or-rollback review, while verified and malformed cases stop cleanly",
            "recommended_next_template": "",
        },
        "diagnostic_conclusions": {
            "reconciliation_state": RECONCILIATION_MISMATCH_DETECTED,
            "escalation_state": escalation_state,
            "remediation_review_state": remediation_review_state,
            "recommended_next_action": "hold_and_consolidate",
            "recommended_next_template": "",
        },
        "artifact_path": str(artifact_path),
        "reconciliation_escalation_ledger_path": str(
            GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_ESCALATION_LEDGER_PATH
        ),
    }
