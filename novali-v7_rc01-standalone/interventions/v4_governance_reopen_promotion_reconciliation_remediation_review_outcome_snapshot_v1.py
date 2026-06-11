from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .governance_memory_reopen_intake_v1 import (
    PROMOTION_APPLIED_AS_BINDING_AUTHORITY,
    PROMOTION_NOOP_ALREADY_AUTHORITATIVE,
)
from .ledger import intervention_data_dir, load_latest_snapshots
from .v4_governance_reopen_promotion_reconciliation_escalation_snapshot_v1 import (
    REMEDIATION_OR_ROLLBACK_REVIEW_CANDIDATE,
    RECONCILIATION_MISMATCH_DETECTED,
)
from .v4_governance_reopen_promotion_reconciliation_remediation_review_submission_snapshot_v1 import (
    REMEDIATION_REVIEW_NON_AUTHORITATIVE,
    REMEDIATION_REVIEW_OUTCOME_PENDING,
    SUBMITTED_FOR_REMEDIATION_REVIEW,
)


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
GOVERNANCE_REOPEN_REMEDIATION_REVIEW_LEDGER_PATH = (
    DATA_DIR / "governance_reopen_remediation_review_ledger.jsonl"
)
GOVERNANCE_REOPEN_REMEDIATION_REVIEW_OUTCOME_LEDGER_PATH = (
    DATA_DIR / "governance_reopen_remediation_review_outcome_ledger.jsonl"
)
INTERVENTION_LEDGER_PATH = DATA_DIR / "intervention_ledger.jsonl"
INTERVENTION_ANALYTICS_PATH = DATA_DIR / "intervention_analytics_latest.json"
PROPOSAL_RECOMMENDATIONS_PATH = DATA_DIR / "proposal_recommendations_latest.json"
SELF_STRUCTURE_STATE_PATH = DATA_DIR / "self_structure_state_latest.json"
SELF_STRUCTURE_LEDGER_PATH = DATA_DIR / "self_structure_ledger.jsonl"
BRANCH_REGISTRY_PATH = DATA_DIR / "branch_registry_latest.json"
DIRECTIVE_STATE_PATH = DATA_DIR / "directive_state_latest.json"
BUCKET_STATE_PATH = DATA_DIR / "bucket_state_latest.json"

OUTCOME_SCHEMA_NAME = "GovernanceReopenPromotionReconciliationRemediationReviewOutcome"
OUTCOME_SCHEMA_VERSION = "governance_reopen_promotion_reconciliation_remediation_review_outcome_v1"
REMEDIATION_REVIEW_REJECTED = "remediation_review_rejected"
REMEDIATION_REVIEW_APPROVED_FOR_EXISTING_ROLLBACK_OR_REPAIR_PATH = (
    "remediation_review_approved_for_existing_rollback_or_repair_path"
)
ROLLBACK_OR_REPAIR_PATH_NOT_ELIGIBLE = "not_eligible_for_existing_rollback_or_repair_path"
ROLLBACK_OR_REPAIR_PATH_ELIGIBLE = "eligible_for_existing_rollback_or_repair_path"
ROLLBACK_READY_REFERENCE = "rollback_ready_reference"
OUTCOME_NON_AUTHORITATIVE = (
    "remediation_review_outcome_non_authoritative_until_explicit_existing_rollback_or_repair_path_invocation"
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
    remediation_review_ledger_rows = _load_jsonl(GOVERNANCE_REOPEN_REMEDIATION_REVIEW_LEDGER_PATH)
    remediation_review_outcome_ledger_rows = _load_jsonl(
        GOVERNANCE_REOPEN_REMEDIATION_REVIEW_OUTCOME_LEDGER_PATH
    )

    if not all([authority_payload, self_structure_state, branch_registry, directive_state, bucket_state]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: authority, self-structure, branch, directive, and bucket artifacts are required",
        }

    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    remediation_review_artifact_path = str(
        current_state_summary.get("latest_governance_reopen_remediation_review_artifact_path", "")
    )
    remediation_review_submission_state_summary = str(
        current_state_summary.get("latest_governance_reopen_remediation_review_submission_state", "")
    )
    remediation_review_outcome_state_summary = str(
        current_state_summary.get("latest_governance_reopen_remediation_review_outcome_state", "")
    )

    if not remediation_review_artifact_path:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no remediation-review submission artifact is available for remediation review outcome",
        }

    remediation_review_payload = _load_json_file(Path(remediation_review_artifact_path))
    if not remediation_review_payload:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest remediation-review submission artifact could not be loaded",
        }

    snapshot_identity_context = dict(remediation_review_payload.get("snapshot_identity_context", {}))
    remediation_review_packet_id = _first_nonempty(
        snapshot_identity_context.get("remediation_review_packet_id"),
        remediation_review_payload.get("remediation_review_packet_id"),
    )
    submission_result = dict(remediation_review_payload.get("remediation_review_submission_result", {}))
    remediation_review_submission_state = _first_nonempty(
        submission_result.get("remediation_review_submission_state"),
        remediation_review_submission_state_summary,
    )
    remediation_review_outcome_state_before = _first_nonempty(
        submission_result.get("remediation_review_outcome_state"),
        remediation_review_outcome_state_summary,
    )

    if remediation_review_submission_state != SUBMITTED_FOR_REMEDIATION_REVIEW:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: only submitted remediation-review packets may receive explicit remediation-review outcomes",
            "diagnostic_conclusions": {
                "remediation_review_submission_state": remediation_review_submission_state,
                "remediation_review_outcome_state": remediation_review_outcome_state_before,
            },
        }

    if remediation_review_outcome_state_before not in {"", REMEDIATION_REVIEW_OUTCOME_PENDING}:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest remediation-review packet already has an explicit remediation-review outcome",
            "diagnostic_conclusions": {
                "remediation_review_packet_id": remediation_review_packet_id,
                "remediation_review_outcome_state": remediation_review_outcome_state_before,
            },
        }

    if any(
        str(row.get("source_remediation_review_packet_id", "")) == remediation_review_packet_id
        for row in remediation_review_outcome_ledger_rows
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest remediation-review packet already has a recorded remediation-review outcome",
            "diagnostic_conclusions": {
                "remediation_review_packet_id": remediation_review_packet_id,
                "existing_remediation_review_outcome_count": sum(
                    1
                    for row in remediation_review_outcome_ledger_rows
                    if str(row.get("source_remediation_review_packet_id", "")) == remediation_review_packet_id
                ),
            },
        }

    source_reconciliation_escalation_reference = dict(
        remediation_review_payload.get("source_reconciliation_escalation_reference", {})
    )
    source_reconciliation_reference = dict(remediation_review_payload.get("source_reconciliation_reference", {}))
    source_promotion_outcome_reference = dict(
        remediation_review_payload.get("source_promotion_outcome_reference", {})
    )
    source_promotion_handoff_reference = dict(
        remediation_review_payload.get("source_promotion_handoff_reference", {})
    )
    source_review_outcome_reference = dict(
        remediation_review_payload.get("source_review_outcome_reference", {})
    )
    source_review_submission_reference = dict(
        remediation_review_payload.get("source_review_submission_reference", {})
    )
    authority_before_reference = dict(remediation_review_payload.get("authority_before_reference", {}))
    authority_after_reference = dict(remediation_review_payload.get("authority_after_reference", {}))
    mismatch_surfaces_and_propagation_failures = dict(
        remediation_review_payload.get("mismatch_surfaces_and_propagation_failures", {})
    )
    rollback_ready_reference = dict(remediation_review_payload.get("rollback_ready_reference", {}))
    requested_remediation_scope = dict(remediation_review_payload.get("requested_remediation_scope", {}))

    source_escalation_state = str(source_reconciliation_escalation_reference.get("escalation_state", ""))
    source_reconciliation_state = str(source_reconciliation_reference.get("reconciliation_state", ""))
    source_promotion_outcome_state = str(source_promotion_outcome_reference.get("promotion_outcome_state", ""))
    repeated_motion_without_new_evidence = bool(
        submission_result.get("repeated_motion_without_new_evidence", False)
    )

    if source_escalation_state != REMEDIATION_OR_ROLLBACK_REVIEW_CANDIDATE:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: only remediation_or_rollback_review_candidate packets may receive remediation-review outcomes",
            "diagnostic_conclusions": {
                "source_escalation_state": source_escalation_state,
                "remediation_review_submission_state": remediation_review_submission_state,
            },
        }

    if source_reconciliation_state != RECONCILIATION_MISMATCH_DETECTED:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: reconciliation_verified or non-mismatch cases may not receive remediation-review outcomes",
            "diagnostic_conclusions": {
                "source_reconciliation_state": source_reconciliation_state,
            },
        }

    if source_promotion_outcome_state == PROMOTION_NOOP_ALREADY_AUTHORITATIVE:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: already-resolved noop cases may not receive remediation-review outcomes",
            "diagnostic_conclusions": {
                "source_promotion_outcome_state": source_promotion_outcome_state,
            },
        }

    if source_promotion_outcome_state and source_promotion_outcome_state != PROMOTION_APPLIED_AS_BINDING_AUTHORITY:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: remediation-review outcome requires an applied promotion outcome as the source mismatch case",
            "diagnostic_conclusions": {
                "source_promotion_outcome_state": source_promotion_outcome_state,
            },
        }

    if repeated_motion_without_new_evidence:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: repeated motion without new evidence may not receive remediation-review outcomes",
            "diagnostic_conclusions": {
                "remediation_review_packet_id": remediation_review_packet_id,
            },
        }

    failed_checks = list(mismatch_surfaces_and_propagation_failures.get("failed_checks", []))
    mismatch_surfaces = [
        str(item)
        for item in list(mismatch_surfaces_and_propagation_failures.get("mismatch_surfaces", []))
        if str(item)
    ]
    propagation_status_by_surface = dict(
        mismatch_surfaces_and_propagation_failures.get("propagation_status_by_surface", {})
    )
    rollback_reference_state = str(rollback_ready_reference.get("rollback_reference_state", ""))
    available_existing_follow_on_paths = [
        str(item)
        for item in list(rollback_ready_reference.get("available_existing_follow_on_paths", []))
        if str(item)
    ]

    malformed_submission = not bool(
        source_reconciliation_escalation_reference
        and source_reconciliation_reference
        and source_promotion_outcome_reference
        and authority_before_reference
        and authority_after_reference
        and requested_remediation_scope
        and rollback_ready_reference
        and (failed_checks or mismatch_surfaces)
    )
    if malformed_submission:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest remediation-review submission artifact is missing outcome-critical fields",
            "diagnostic_conclusions": {
                "has_source_reconciliation_escalation_reference": bool(source_reconciliation_escalation_reference),
                "has_source_reconciliation_reference": bool(source_reconciliation_reference),
                "has_source_promotion_outcome_reference": bool(source_promotion_outcome_reference),
                "has_authority_before_reference": bool(authority_before_reference),
                "has_authority_after_reference": bool(authority_after_reference),
                "has_requested_remediation_scope": bool(requested_remediation_scope),
                "has_rollback_ready_reference": bool(rollback_ready_reference),
                "failed_check_count": int(len(failed_checks)),
                "mismatch_surface_count": int(len(mismatch_surfaces)),
            },
        }

    authority_posture_at_review = _authority_posture_snapshot(authority_payload)
    authority_posture_at_submission_time = dict(
        remediation_review_payload.get("authority_posture_at_submission_time", {})
    )
    authority_posture_changed_since_submission = any(
        authority_posture_at_submission_time.get(key) != authority_posture_at_review.get(key)
        for key in [
            "current_branch_state",
            "current_operating_stance",
            "held_baseline_template",
            "routing_status",
        ]
    )

    actionable_mismatch_present = bool(failed_checks or mismatch_surfaces)
    rollback_ready_for_existing_path = bool(
        rollback_reference_state == ROLLBACK_READY_REFERENCE and available_existing_follow_on_paths
    )

    if actionable_mismatch_present and rollback_ready_for_existing_path and not authority_posture_changed_since_submission:
        remediation_review_outcome_state = (
            REMEDIATION_REVIEW_APPROVED_FOR_EXISTING_ROLLBACK_OR_REPAIR_PATH
        )
        follow_on_handoff_state = ROLLBACK_OR_REPAIR_PATH_ELIGIBLE
        review_decision_reason_codes = [
            "actionable_mismatch_confirmed",
            "rollback_ready_reference_present",
            "existing_follow_on_path_available",
            "explicit_existing_rollback_or_repair_path_invocation_required",
        ]
    else:
        remediation_review_outcome_state = REMEDIATION_REVIEW_REJECTED
        follow_on_handoff_state = ROLLBACK_OR_REPAIR_PATH_NOT_ELIGIBLE
        review_decision_reason_codes = []
        if not actionable_mismatch_present:
            review_decision_reason_codes.append("mismatch_evidence_not_actionable")
        if rollback_reference_state != ROLLBACK_READY_REFERENCE:
            review_decision_reason_codes.append("rollback_ready_reference_unavailable")
        if not available_existing_follow_on_paths:
            review_decision_reason_codes.append("no_existing_follow_on_path_advertised")
        if authority_posture_changed_since_submission:
            review_decision_reason_codes.append("authority_posture_changed_since_submission")

    remediation_review_outcome_id = f"reopen_remediation_review_outcome::{proposal['proposal_id']}"
    decided_at = _now()
    artifact_path = _diagnostic_artifact_dir() / (
        "memory_summary_v4_governance_reopen_promotion_reconciliation_remediation_review_outcome_snapshot_v1_"
        f"{proposal['proposal_id']}.json"
    )
    branch_record = (
        dict(list(branch_registry.get("branches", []))[0]) if list(branch_registry.get("branches", [])) else {}
    )

    payload = {
        "proposal_id": str(proposal.get("proposal_id", "")),
        "template_name": "memory_summary.v4_governance_reopen_promotion_reconciliation_remediation_review_outcome_snapshot_v1",
        "snapshot_identity_context": {
            "remediation_review_outcome_id": remediation_review_outcome_id,
            "decided_at": decided_at,
            "phase": "governance_reopen_promotion_reconciliation_remediation_review_outcome",
            "source_remediation_review_packet_id": remediation_review_packet_id,
            "source_escalation_id": str(source_reconciliation_escalation_reference.get("escalation_id", "")),
            "source_reconciliation_id": str(source_reconciliation_reference.get("reconciliation_id", "")),
        },
        "remediation_review_outcome_contract": {
            "schema_name": OUTCOME_SCHEMA_NAME,
            "schema_version": OUTCOME_SCHEMA_VERSION,
            "required_submission_state": SUBMITTED_FOR_REMEDIATION_REVIEW,
            "required_submission_outcome_state": REMEDIATION_REVIEW_OUTCOME_PENDING,
            "required_reconciliation_state": RECONCILIATION_MISMATCH_DETECTED,
            "required_escalation_state": REMEDIATION_OR_ROLLBACK_REVIEW_CANDIDATE,
            "remediation_review_outcome_states": [
                REMEDIATION_REVIEW_REJECTED,
                REMEDIATION_REVIEW_APPROVED_FOR_EXISTING_ROLLBACK_OR_REPAIR_PATH,
            ],
            "follow_on_handoff_states": [
                ROLLBACK_OR_REPAIR_PATH_NOT_ELIGIBLE,
                ROLLBACK_OR_REPAIR_PATH_ELIGIBLE,
            ],
            "authority_relation": OUTCOME_NON_AUTHORITATIVE,
            "automatic_rollback_disallowed": True,
            "automatic_repair_disallowed": True,
            "canonical_authority_mutation_disallowed_here": True,
            "existing_follow_on_paths_reference_only": True,
            "submission_authority_relation": REMEDIATION_REVIEW_NON_AUTHORITATIVE,
        },
        "source_remediation_review_submission_reference": {
            "remediation_review_packet_id": remediation_review_packet_id,
            "artifact_path": remediation_review_artifact_path,
            "ledger_path": str(GOVERNANCE_REOPEN_REMEDIATION_REVIEW_LEDGER_PATH),
            "submission_state": remediation_review_submission_state,
            "outcome_state_before": remediation_review_outcome_state_before,
            "source_escalation_id": str(source_reconciliation_escalation_reference.get("escalation_id", "")),
        },
        "source_reconciliation_escalation_reference": source_reconciliation_escalation_reference,
        "source_reconciliation_reference": source_reconciliation_reference,
        "source_promotion_outcome_reference": source_promotion_outcome_reference,
        "source_promotion_handoff_reference": source_promotion_handoff_reference,
        "source_review_outcome_reference": source_review_outcome_reference,
        "source_review_submission_reference": source_review_submission_reference,
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
            "rollback_trace": dict(rollback_ready_reference.get("rollback_trace", {})),
            "available_existing_follow_on_paths": available_existing_follow_on_paths,
            "no_rollback_invoked_here": True,
            "no_repair_invoked_here": True,
        },
        "authority_posture_at_review_time": authority_posture_at_review,
        "requested_remediation_scope": requested_remediation_scope,
        "remediation_review_decision": {
            "remediation_review_outcome_state": remediation_review_outcome_state,
            "follow_on_handoff_state": follow_on_handoff_state,
            "review_decision_reason_codes": review_decision_reason_codes,
            "authority_posture_changed_since_submission": authority_posture_changed_since_submission,
            "actionable_mismatch_present": actionable_mismatch_present,
            "rollback_ready_for_existing_path": rollback_ready_for_existing_path,
            "repeated_motion_without_new_evidence": repeated_motion_without_new_evidence,
        },
        "rollback_or_repair_handoff_contract": {
            "eligible_for_existing_follow_on_path": (
                remediation_review_outcome_state
                == REMEDIATION_REVIEW_APPROVED_FOR_EXISTING_ROLLBACK_OR_REPAIR_PATH
            ),
            "current_follow_on_handoff_state": follow_on_handoff_state,
            "available_existing_follow_on_paths": available_existing_follow_on_paths,
            "automatic_rollback_disallowed": True,
            "automatic_repair_disallowed": True,
            "explicit_existing_follow_on_path_invocation_required": True,
            "canonical_authority_mutation_disallowed_here": True,
        },
        "reviewer_source_and_audit_trace": {
            "reviewed_by_surface": "memory_summary.v4_governance_reopen_promotion_reconciliation_remediation_review_outcome_snapshot_v1",
            "reviewer_source": "governed_remediation_review_outcome_snapshot_v1",
            "branch_id": str(branch_registry.get("current_branch_id", "")),
            "branch_pause_rationale": str(branch_record.get("pause_rationale", "")),
            "directive_id": str(dict(directive_state.get("current_directive_state", {})).get("directive_id", "")),
            "bucket_id": str(dict(bucket_state.get("current_bucket_state", {})).get("bucket_id", "")),
            "governance_execution_contract_available": bool(
                intervention_analytics.get("governance_execution_contract")
                or proposal_recommendations.get("governance_execution_contract")
            ),
        },
        "provenance_and_audit_trace": {
            "canonical_authority_file": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
            "promotion_ledger_path": str(GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH),
            "promotion_outcome_ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_OUTCOME_LEDGER_PATH),
            "reconciliation_ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_LEDGER_PATH),
            "reconciliation_escalation_ledger_path": str(
                GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_ESCALATION_LEDGER_PATH
            ),
            "remediation_review_submission_ledger_path": str(GOVERNANCE_REOPEN_REMEDIATION_REVIEW_LEDGER_PATH),
            "remediation_review_outcome_ledger_path": str(
                GOVERNANCE_REOPEN_REMEDIATION_REVIEW_OUTCOME_LEDGER_PATH
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
            "escalation_ledger_entries_seen": int(len(escalation_ledger_rows)),
            "remediation_review_ledger_entries_seen": int(len(remediation_review_ledger_rows)),
            "remediation_review_outcome_ledger_entries_before_write": int(
                len(remediation_review_outcome_ledger_rows)
            ),
            "rollback_trace_mode": "explicit_remediation_review_outcome_then_existing_rollback_or_repair_path_only",
        },
        "operator_readable_conclusion": (
            "The submitted remediation-review packet now has an explicit non-authoritative remediation-review outcome. "
            + (
                "It is approved only for a separately invoked existing rollback or repair path, so no rollback, repair, or authority mutation occurs here."
                if remediation_review_outcome_state
                == REMEDIATION_REVIEW_APPROVED_FOR_EXISTING_ROLLBACK_OR_REPAIR_PATH
                else "It is rejected in remediation review, so no rollback-or-repair handoff is available and canonical authority remains unchanged."
            )
        ),
    }

    _write_json(artifact_path, payload)

    ledger_entry = {
        "event_type": "governance_reopen_remediation_review_outcome_recorded",
        "written_at": decided_at,
        "remediation_review_outcome_id": remediation_review_outcome_id,
        "source_remediation_review_packet_id": remediation_review_packet_id,
        "source_remediation_review_artifact_path": remediation_review_artifact_path,
        "source_escalation_id": str(source_reconciliation_escalation_reference.get("escalation_id", "")),
        "source_reconciliation_id": str(source_reconciliation_reference.get("reconciliation_id", "")),
        "artifact_path": str(artifact_path),
        "remediation_review_outcome_state": remediation_review_outcome_state,
        "follow_on_handoff_state": follow_on_handoff_state,
        "requested_template_name": str(requested_remediation_scope.get("requested_template_name", "")),
        "requested_template_family": str(requested_remediation_scope.get("requested_template_family", "")),
        "review_decision_reason_codes": review_decision_reason_codes,
    }
    _append_jsonl(GOVERNANCE_REOPEN_REMEDIATION_REVIEW_OUTCOME_LEDGER_PATH, ledger_entry)

    updated_self_structure = dict(self_structure_state)
    updated_summary = dict(current_state_summary)
    updated_summary.update(
        {
            "latest_governance_reopen_remediation_review_outcome_artifact_path": str(artifact_path),
            "latest_governance_reopen_remediation_review_outcome_ledger_path": str(
                GOVERNANCE_REOPEN_REMEDIATION_REVIEW_OUTCOME_LEDGER_PATH
            ),
            "latest_governance_reopen_remediation_review_state": remediation_review_outcome_state,
            "latest_governance_reopen_remediation_review_outcome_state": remediation_review_outcome_state,
            "latest_governance_reopen_remediation_follow_on_handoff_state": follow_on_handoff_state,
            "latest_governance_reopen_remediation_review_decision_reason_codes": review_decision_reason_codes,
        }
    )
    updated_self_structure["generated_at"] = _now()
    updated_self_structure["current_state_summary"] = updated_summary
    updated_self_structure["governance_reopen_remediation_review_outcome"] = {
        "schema_name": OUTCOME_SCHEMA_NAME,
        "schema_version": OUTCOME_SCHEMA_VERSION,
        "latest_remediation_review_outcome": {
            "remediation_review_outcome_id": remediation_review_outcome_id,
            "source_remediation_review_packet_id": remediation_review_packet_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_REMEDIATION_REVIEW_OUTCOME_LEDGER_PATH),
            "remediation_review_outcome_state": remediation_review_outcome_state,
            "follow_on_handoff_state": follow_on_handoff_state,
        },
    }
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure)

    _append_jsonl(
        SELF_STRUCTURE_LEDGER_PATH,
        {
            "event_id": f"governance_reopen_remediation_review_outcome::{proposal['proposal_id']}",
            "timestamp": _now(),
            "event_type": "governance_reopen_remediation_review_outcome_recorded",
            "remediation_review_outcome_id": remediation_review_outcome_id,
            "source_remediation_review_packet_id": remediation_review_packet_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_REMEDIATION_REVIEW_OUTCOME_LEDGER_PATH),
            "remediation_review_outcome_state": remediation_review_outcome_state,
            "follow_on_handoff_state": follow_on_handoff_state,
            "requested_template_name": str(requested_remediation_scope.get("requested_template_name", "")),
            "requested_template_family": str(requested_remediation_scope.get("requested_template_family", "")),
        },
    )

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: submitted remediation-review packet was materialized as an explicit governed remediation-review outcome",
        "observability_gain": {
            "passed": True,
            "reason": "future agents can now distinguish remediation-review submission from remediation-review rejection or approval for an existing rollback-or-repair path",
            "artifact_path": str(artifact_path),
            "remediation_review_outcome_ledger_path": str(
                GOVERNANCE_REOPEN_REMEDIATION_REVIEW_OUTCOME_LEDGER_PATH
            ),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "remediation-review outcomes now preserve the explicit decision seam before any separately invoked rollback-or-repair path without allowing automatic repair",
        },
        "ambiguity_reduction": {
            "passed": True,
            "reason": "remediation-review decision reason codes, mismatch evidence, and follow-on handoff eligibility are now explicit",
            "score": 0.96,
        },
        "safety_neutrality": {
            "passed": True,
            "reason": "remediation-review outcome writes only non-authoritative governance artifacts and cannot trigger rollback, repair, or authority mutation by itself",
            "scope": str(proposal.get("scope", "")),
        },
        "later_selection_usefulness": {
            "passed": True,
            "reason": "only valid submitted remediation-review packets can produce explicit remediation-review decisions, and approved outcomes still require a separate existing rollback-or-repair invocation",
            "recommended_next_template": "",
        },
        "diagnostic_conclusions": {
            "remediation_review_submission_state": SUBMITTED_FOR_REMEDIATION_REVIEW,
            "remediation_review_outcome_state": remediation_review_outcome_state,
            "follow_on_handoff_state": follow_on_handoff_state,
            "source_remediation_review_packet_id": remediation_review_packet_id,
            "recommended_next_action": "hold_and_consolidate",
            "recommended_next_template": "",
        },
        "artifact_path": str(artifact_path),
        "remediation_review_outcome_ledger_path": str(
            GOVERNANCE_REOPEN_REMEDIATION_REVIEW_OUTCOME_LEDGER_PATH
        ),
    }
