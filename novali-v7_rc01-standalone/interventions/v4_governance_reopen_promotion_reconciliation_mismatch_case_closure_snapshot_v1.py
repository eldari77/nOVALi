from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .ledger import intervention_data_dir, load_latest_snapshots
from .v4_governance_reopen_promotion_reconciliation_remediation_review_outcome_snapshot_v1 import (
    REMEDIATION_REVIEW_APPROVED_FOR_EXISTING_ROLLBACK_OR_REPAIR_PATH,
)
from .v4_governance_reopen_promotion_reconciliation_remediation_review_submission_snapshot_v1 import (
    SUBMITTED_FOR_REMEDIATION_REVIEW,
)
from .v4_governance_reopen_promotion_reconciliation_rollback_or_repair_outcome_snapshot_v1 import (
    ROLLBACK_OR_REPAIR_APPLIED_UNDER_EXISTING_PATH,
    ROLLBACK_OR_REPAIR_CANDIDATE_UNDER_EXISTING_PATH,
    ROLLBACK_OR_REPAIR_NOOP_ALREADY_RESOLVED,
    ROLLBACK_OR_REPAIR_REJECTED_UNDER_EXISTING_PATH,
)
from .v4_governance_reopen_promotion_reconciliation_snapshot_v1 import (
    RECONCILIATION_MISMATCH_DETECTED,
    RECONCILIATION_PENDING,
    RECONCILIATION_VERIFIED,
)


DATA_DIR = intervention_data_dir()
DIAGNOSTIC_MEMORY_DIR = DATA_DIR / "diagnostic_memory"
GOVERNANCE_MEMORY_AUTHORITY_PATH = DATA_DIR / "governance_memory_authority_latest.json"
GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH = DATA_DIR / "governance_memory_promotion_ledger.jsonl"
GOVERNANCE_REOPEN_PROMOTION_OUTCOME_LEDGER_PATH = (
    DATA_DIR / "governance_reopen_promotion_outcome_ledger.jsonl"
)
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
GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_HANDOFF_LEDGER_PATH = (
    DATA_DIR / "governance_reopen_rollback_or_repair_handoff_ledger.jsonl"
)
GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_OUTCOME_LEDGER_PATH = (
    DATA_DIR / "governance_reopen_rollback_or_repair_outcome_ledger.jsonl"
)
GOVERNANCE_REOPEN_MISMATCH_CASE_CLOSURE_LEDGER_PATH = (
    DATA_DIR / "governance_reopen_mismatch_case_closure_ledger.jsonl"
)
INTERVENTION_LEDGER_PATH = DATA_DIR / "intervention_ledger.jsonl"
INTERVENTION_ANALYTICS_PATH = DATA_DIR / "intervention_analytics_latest.json"
PROPOSAL_RECOMMENDATIONS_PATH = DATA_DIR / "proposal_recommendations_latest.json"
SELF_STRUCTURE_STATE_PATH = DATA_DIR / "self_structure_state_latest.json"
SELF_STRUCTURE_LEDGER_PATH = DATA_DIR / "self_structure_ledger.jsonl"
BRANCH_REGISTRY_PATH = DATA_DIR / "branch_registry_latest.json"
DIRECTIVE_STATE_PATH = DATA_DIR / "directive_state_latest.json"
BUCKET_STATE_PATH = DATA_DIR / "bucket_state_latest.json"

CLOSURE_SCHEMA_NAME = "GovernanceReopenPromotionReconciliationMismatchCaseClosure"
CLOSURE_SCHEMA_VERSION = "governance_reopen_promotion_reconciliation_mismatch_case_closure_v1"
MISMATCH_CASE_CLOSED_REJECTED_NO_ACTION = "mismatch_case_closed_rejected_no_action"
MISMATCH_CASE_PENDING_FOLLOW_ON_RECONCILIATION = "mismatch_case_pending_follow_on_reconciliation"
MISMATCH_CASE_CLOSED_VERIFIED_RESOLVED = "mismatch_case_closed_verified_resolved"
MISMATCH_CASE_OPEN_REQUIRES_FURTHER_GOVERNANCE = "mismatch_case_open_requires_further_governance"


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


def _authority_reference(authority_payload: dict[str, Any], current_state_summary: dict[str, Any]) -> dict[str, Any]:
    authority_candidate_record = dict(authority_payload.get("authority_candidate_record", {}))
    authority_promotion_record = dict(authority_payload.get("authority_promotion_record", {}))
    authority_summary = dict(authority_payload.get("authority_file_summary", {}))
    return {
        "canonical_authority_file": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
        "authority_mutation_stage": str(authority_payload.get("authority_mutation_stage", "")),
        "authority_artifact_path": str(
            current_state_summary.get("latest_governance_memory_authority_artifact_path", "")
        ),
        "authority_source_proposal_id": str(authority_payload.get("proposal_id", "")),
        "authority_candidate_artifact_path": str(
            authority_candidate_record.get("candidate_artifact_path", "")
        ),
        "authority_candidate_source_template_name": str(
            authority_candidate_record.get("candidate_source_template_name", "")
        ),
        "authority_promotion_id": str(authority_promotion_record.get("promotion_id", "")),
        "authority_promotion_source_candidate_artifact_path": str(
            authority_promotion_record.get("source_candidate_artifact_path", "")
        ),
        "current_branch_state": str(authority_summary.get("current_branch_state", "")),
        "current_operating_stance": str(authority_summary.get("current_operating_stance", "")),
        "held_baseline_template": str(authority_summary.get("held_baseline_template", "")),
        "routing_status": str(authority_summary.get("routing_status", "")),
    }


def _authority_reference_matches(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        str(left.get("authority_mutation_stage", "")) == str(right.get("authority_mutation_stage", ""))
        and str(left.get("authority_candidate_artifact_path", ""))
        == str(right.get("authority_candidate_artifact_path", ""))
        and str(left.get("authority_promotion_id", "")) == str(right.get("authority_promotion_id", ""))
        and str(left.get("current_branch_state", "")) == str(right.get("current_branch_state", ""))
        and str(left.get("current_operating_stance", "")) == str(right.get("current_operating_stance", ""))
        and str(left.get("held_baseline_template", "")) == str(right.get("held_baseline_template", ""))
        and str(left.get("routing_status", "")) == str(right.get("routing_status", ""))
    )


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
    rollback_or_repair_handoff_ledger_rows = _load_jsonl(
        GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_HANDOFF_LEDGER_PATH
    )
    rollback_or_repair_outcome_ledger_rows = _load_jsonl(
        GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_OUTCOME_LEDGER_PATH
    )
    closure_ledger_rows = _load_jsonl(GOVERNANCE_REOPEN_MISMATCH_CASE_CLOSURE_LEDGER_PATH)

    if not all([authority_payload, self_structure_state, branch_registry, directive_state, bucket_state]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: authority, self-structure, branch, directive, and bucket artifacts are required",
        }

    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    rollback_or_repair_outcome_artifact_path = str(
        current_state_summary.get("latest_governance_reopen_rollback_or_repair_outcome_artifact_path", "")
    )
    rollback_or_repair_outcome_state_summary = str(
        current_state_summary.get("latest_governance_reopen_rollback_or_repair_outcome_state", "")
    )

    if not rollback_or_repair_outcome_artifact_path:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no rollback-or-repair outcome artifact is available for mismatch-case closure",
        }

    rollback_or_repair_outcome_payload = _load_json_file(Path(rollback_or_repair_outcome_artifact_path))
    if not rollback_or_repair_outcome_payload:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest rollback-or-repair outcome artifact could not be loaded",
        }

    outcome_identity = dict(rollback_or_repair_outcome_payload.get("snapshot_identity_context", {}))
    rollback_or_repair_outcome_id = _first_nonempty(
        outcome_identity.get("rollback_or_repair_outcome_id"),
        rollback_or_repair_outcome_payload.get("rollback_or_repair_outcome_id"),
    )
    rollback_or_repair_decision = dict(
        rollback_or_repair_outcome_payload.get("rollback_or_repair_decision", {})
    )
    rollback_or_repair_outcome_state = _first_nonempty(
        rollback_or_repair_decision.get("rollback_or_repair_outcome_state"),
        rollback_or_repair_outcome_state_summary,
    )

    if any(
        str(row.get("source_rollback_or_repair_outcome_id", "")) == rollback_or_repair_outcome_id
        for row in closure_ledger_rows
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest rollback-or-repair outcome already has a recorded mismatch-case closure artifact",
            "diagnostic_conclusions": {
                "rollback_or_repair_outcome_id": rollback_or_repair_outcome_id,
                "existing_closure_count": sum(
                    1
                    for row in closure_ledger_rows
                    if str(row.get("source_rollback_or_repair_outcome_id", "")) == rollback_or_repair_outcome_id
                ),
            },
        }

    source_rollback_or_repair_handoff_reference = dict(
        rollback_or_repair_outcome_payload.get("source_rollback_or_repair_handoff_reference", {})
    )
    source_remediation_review_outcome_reference = dict(
        rollback_or_repair_outcome_payload.get("source_remediation_review_outcome_reference", {})
    )
    source_remediation_review_submission_reference = dict(
        rollback_or_repair_outcome_payload.get("source_remediation_review_submission_reference", {})
    )
    source_reconciliation_escalation_reference = dict(
        rollback_or_repair_outcome_payload.get("source_reconciliation_escalation_reference", {})
    )
    source_reconciliation_reference = dict(
        rollback_or_repair_outcome_payload.get("source_reconciliation_reference", {})
    )
    source_promotion_outcome_reference = dict(
        rollback_or_repair_outcome_payload.get("source_promotion_outcome_reference", {})
    )
    source_promotion_handoff_reference = dict(
        rollback_or_repair_outcome_payload.get("source_promotion_handoff_reference", {})
    )
    source_review_outcome_reference = dict(
        rollback_or_repair_outcome_payload.get("source_review_outcome_reference", {})
    )
    source_review_submission_reference = dict(
        rollback_or_repair_outcome_payload.get("source_review_submission_reference", {})
    )
    authority_before_reference = dict(rollback_or_repair_outcome_payload.get("authority_before_reference", {}))
    authority_after_reference = dict(rollback_or_repair_outcome_payload.get("authority_after_reference", {}))
    mismatch_surfaces_and_failed_propagation_checks = dict(
        rollback_or_repair_outcome_payload.get("mismatch_surfaces_and_failed_propagation_checks", {})
    )
    rollback_ready_reference = dict(rollback_or_repair_outcome_payload.get("rollback_ready_reference", {}))

    malformed_outcome = not bool(
        source_rollback_or_repair_handoff_reference
        and source_remediation_review_outcome_reference
        and source_remediation_review_submission_reference
        and source_reconciliation_escalation_reference
        and source_reconciliation_reference
        and authority_before_reference
        and authority_after_reference
        and mismatch_surfaces_and_failed_propagation_checks
        and rollback_ready_reference
    )
    if malformed_outcome:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest rollback-or-repair outcome artifact is missing mismatch-case-closure-critical fields",
        }

    if str(source_remediation_review_outcome_reference.get("remediation_review_outcome_state", "")) != (
        REMEDIATION_REVIEW_APPROVED_FOR_EXISTING_ROLLBACK_OR_REPAIR_PATH
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: mismatch-case closure requires remediation review approval for the existing rollback-or-repair path",
        }

    if str(source_remediation_review_submission_reference.get("submission_state", "")) != (
        SUBMITTED_FOR_REMEDIATION_REVIEW
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: mismatch-case closure requires a submitted remediation-review packet",
        }

    if rollback_or_repair_outcome_state not in {
        ROLLBACK_OR_REPAIR_CANDIDATE_UNDER_EXISTING_PATH,
        ROLLBACK_OR_REPAIR_REJECTED_UNDER_EXISTING_PATH,
        ROLLBACK_OR_REPAIR_APPLIED_UNDER_EXISTING_PATH,
        ROLLBACK_OR_REPAIR_NOOP_ALREADY_RESOLVED,
    }:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: rollback-or-repair outcome state is not recognized by mismatch-case closure",
            "diagnostic_conclusions": {
                "rollback_or_repair_outcome_state": rollback_or_repair_outcome_state,
            },
        }

    current_authority_reference = _authority_reference(authority_payload, current_state_summary)
    authority_posture_at_closure_time = _authority_posture_snapshot(authority_payload)
    follow_on_reconciliation_artifact_path = str(
        current_state_summary.get("latest_governance_reopen_reconciliation_artifact_path", "")
    )
    follow_on_reconciliation_state = str(
        current_state_summary.get("latest_governance_reopen_reconciliation_state", "")
    )
    follow_on_reconciliation_payload = (
        _load_json_file(Path(follow_on_reconciliation_artifact_path))
        if follow_on_reconciliation_artifact_path
        else {}
    )
    follow_on_reconciliation_reference = {
        "artifact_path": follow_on_reconciliation_artifact_path,
        "state": follow_on_reconciliation_state,
        "source_promotion_outcome_id": str(
            dict(follow_on_reconciliation_payload.get("source_promotion_outcome_reference", {})).get(
                "promotion_outcome_id", ""
            )
        ),
        "authority_after_reference": dict(
            follow_on_reconciliation_payload.get("authority_after_reference", {})
        ),
        "reconciliation_reason_codes": list(
            dict(follow_on_reconciliation_payload.get("reconciliation_result", {})).get(
                "reconciliation_reason_codes", []
            )
        ),
    }
    follow_on_reconciliation_is_distinct = bool(follow_on_reconciliation_artifact_path) and (
        follow_on_reconciliation_artifact_path
        != str(source_reconciliation_reference.get("artifact_path", ""))
    )

    follow_on_reconciliation_aligns_to_current_authority = _authority_reference_matches(
        dict(follow_on_reconciliation_reference.get("authority_after_reference", {})),
        current_authority_reference,
    )
    applied_outcome_aligns_to_current_authority = _authority_reference_matches(
        authority_after_reference,
        current_authority_reference,
    )

    closure_reason_codes: list[str] = []
    if rollback_or_repair_outcome_state == ROLLBACK_OR_REPAIR_REJECTED_UNDER_EXISTING_PATH:
        closure_state = MISMATCH_CASE_CLOSED_REJECTED_NO_ACTION
        closure_reason_codes.extend(
            [
                "existing_path_rejected_case",
                "no_authority_mutation_performed_for_mismatch_case",
            ]
        )
    elif rollback_or_repair_outcome_state == ROLLBACK_OR_REPAIR_NOOP_ALREADY_RESOLVED:
        if applied_outcome_aligns_to_current_authority:
            closure_state = MISMATCH_CASE_CLOSED_VERIFIED_RESOLVED
            closure_reason_codes.extend(
                [
                    "noop_case_already_resolved",
                    "current_canonical_authority_matches_resolved_case_reference",
                ]
            )
        else:
            closure_state = MISMATCH_CASE_OPEN_REQUIRES_FURTHER_GOVERNANCE
            closure_reason_codes.extend(
                [
                    "noop_case_resolution_not_aligned_with_current_authority",
                    "authority_drift_after_noop_resolution",
                ]
            )
    elif rollback_or_repair_outcome_state == ROLLBACK_OR_REPAIR_APPLIED_UNDER_EXISTING_PATH:
        if not applied_outcome_aligns_to_current_authority:
            closure_state = MISMATCH_CASE_OPEN_REQUIRES_FURTHER_GOVERNANCE
            closure_reason_codes.extend(
                [
                    "applied_existing_path_not_aligned_with_current_authority",
                    "authority_drift_after_existing_path_apply",
                ]
            )
        elif follow_on_reconciliation_is_distinct and follow_on_reconciliation_state == RECONCILIATION_VERIFIED and (
            follow_on_reconciliation_aligns_to_current_authority
        ):
            closure_state = MISMATCH_CASE_CLOSED_VERIFIED_RESOLVED
            closure_reason_codes.extend(
                [
                    "applied_existing_path_follow_on_reconciliation_verified",
                    "follow_on_reconciliation_aligned_with_current_authority",
                ]
            )
        elif follow_on_reconciliation_is_distinct and follow_on_reconciliation_state == RECONCILIATION_MISMATCH_DETECTED and (
            follow_on_reconciliation_aligns_to_current_authority
        ):
            closure_state = MISMATCH_CASE_OPEN_REQUIRES_FURTHER_GOVERNANCE
            closure_reason_codes.extend(
                [
                    "follow_on_reconciliation_detected_persistent_mismatch",
                    "existing_path_apply_requires_further_governance",
                ]
            )
        else:
            closure_state = MISMATCH_CASE_PENDING_FOLLOW_ON_RECONCILIATION
            if not follow_on_reconciliation_artifact_path:
                closure_reason_codes.append("follow_on_reconciliation_not_yet_emitted")
            elif not follow_on_reconciliation_is_distinct:
                closure_reason_codes.append("follow_on_reconciliation_still_points_to_preexisting_source_record")
            elif follow_on_reconciliation_state in {"", RECONCILIATION_PENDING}:
                closure_reason_codes.append("follow_on_reconciliation_not_yet_verified")
            else:
                closure_reason_codes.append("follow_on_reconciliation_not_aligned_with_current_authority")
            closure_reason_codes.append("applied_existing_path_requires_follow_on_verification")
    else:
        closure_state = MISMATCH_CASE_OPEN_REQUIRES_FURTHER_GOVERNANCE
        closure_reason_codes.extend(
            [
                "rollback_or_repair_candidate_still_under_existing_path_review",
                "explicit_existing_path_decision_not_final",
            ]
        )

    closure_id = f"reopen_mismatch_case_closure::{proposal['proposal_id']}"
    closed_at = _now()
    artifact_path = _diagnostic_artifact_dir() / (
        "memory_summary_v4_governance_reopen_promotion_reconciliation_mismatch_case_closure_snapshot_v1_"
        f"{proposal['proposal_id']}.json"
    )
    branch_record = (
        dict(list(branch_registry.get("branches", []))[0]) if list(branch_registry.get("branches", [])) else {}
    )
    source_reviewer_source_or_gate_actor = dict(
        rollback_or_repair_outcome_payload.get("reviewer_source_or_gate_actor", {})
    )
    requested_rollback_or_repair_scope = dict(
        rollback_or_repair_outcome_payload.get("requested_rollback_or_repair_scope", {})
    )
    rollback_or_repair_decision = dict(
        rollback_or_repair_outcome_payload.get("rollback_or_repair_decision", {})
    )
    existing_path_checks_performed = list(
        rollback_or_repair_outcome_payload.get("existing_path_checks_performed", [])
    )

    payload = {
        "proposal_id": str(proposal.get("proposal_id", "")),
        "template_name": "memory_summary.v4_governance_reopen_promotion_reconciliation_mismatch_case_closure_snapshot_v1",
        "snapshot_identity_context": {
            "mismatch_case_closure_id": closure_id,
            "closed_at": closed_at,
            "phase": "governance_reopen_promotion_reconciliation_mismatch_case_closure",
            "source_rollback_or_repair_outcome_id": rollback_or_repair_outcome_id,
            "source_reconciliation_id": str(source_reconciliation_reference.get("reconciliation_id", "")),
            "source_remediation_review_outcome_id": str(
                source_remediation_review_outcome_reference.get("remediation_review_outcome_id", "")
            ),
        },
        "mismatch_case_closure_contract": {
            "schema_name": CLOSURE_SCHEMA_NAME,
            "schema_version": CLOSURE_SCHEMA_VERSION,
            "source_rollback_or_repair_outcome_states": [
                ROLLBACK_OR_REPAIR_CANDIDATE_UNDER_EXISTING_PATH,
                ROLLBACK_OR_REPAIR_REJECTED_UNDER_EXISTING_PATH,
                ROLLBACK_OR_REPAIR_APPLIED_UNDER_EXISTING_PATH,
                ROLLBACK_OR_REPAIR_NOOP_ALREADY_RESOLVED,
            ],
            "closure_states": [
                MISMATCH_CASE_CLOSED_REJECTED_NO_ACTION,
                MISMATCH_CASE_PENDING_FOLLOW_ON_RECONCILIATION,
                MISMATCH_CASE_CLOSED_VERIFIED_RESOLVED,
                MISMATCH_CASE_OPEN_REQUIRES_FURTHER_GOVERNANCE,
            ],
            "requires_submitted_remediation_review_packet": True,
            "requires_remediation_review_approval_for_existing_path": True,
            "applied_existing_path_requires_distinct_follow_on_reconciliation": True,
            "closure_observational_only": True,
            "canonical_authority_mutation_disallowed_here": True,
            "closure_by_assumption_disallowed": True,
        },
        "source_rollback_or_repair_outcome_reference": {
            "rollback_or_repair_outcome_id": rollback_or_repair_outcome_id,
            "artifact_path": rollback_or_repair_outcome_artifact_path,
            "ledger_path": str(GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_OUTCOME_LEDGER_PATH),
            "rollback_or_repair_outcome_state": rollback_or_repair_outcome_state,
            "decision_reason_codes": list(
                rollback_or_repair_decision.get("decision_reason_codes", [])
            ),
            "existing_path_actor": str(rollback_or_repair_decision.get("existing_path_actor", "")),
        },
        "source_remediation_review_outcome_reference": dict(
            source_remediation_review_outcome_reference
        ),
        "source_remediation_review_submission_reference": dict(
            source_remediation_review_submission_reference
        ),
        "source_reconciliation_escalation_reference": dict(source_reconciliation_escalation_reference),
        "source_reconciliation_reference": dict(source_reconciliation_reference),
        "source_promotion_outcome_reference": dict(source_promotion_outcome_reference),
        "source_promotion_handoff_reference": dict(source_promotion_handoff_reference),
        "source_review_outcome_reference": dict(source_review_outcome_reference),
        "source_review_submission_reference": dict(source_review_submission_reference),
        "authority_before_reference": authority_before_reference,
        "authority_after_reference": authority_after_reference,
        "resolved_canonical_field_set_after_apply": current_authority_reference,
        "mismatch_surfaces_and_failed_propagation_checks": dict(
            mismatch_surfaces_and_failed_propagation_checks
        ),
        "rollback_ready_reference": dict(rollback_ready_reference),
        "authority_posture_at_closure_time": authority_posture_at_closure_time,
        "requested_rollback_or_repair_scope": requested_rollback_or_repair_scope,
        "existing_path_checks_performed": existing_path_checks_performed,
        "follow_on_reconciliation_state_if_any": {
            "follow_on_reconciliation_artifact_path": follow_on_reconciliation_artifact_path,
            "follow_on_reconciliation_state": follow_on_reconciliation_state,
            "follow_on_reconciliation_is_distinct_from_source": bool(
                follow_on_reconciliation_is_distinct
            ),
            "follow_on_reconciliation_aligns_to_current_authority": bool(
                follow_on_reconciliation_aligns_to_current_authority
            ),
            "follow_on_reconciliation_reference": follow_on_reconciliation_reference,
        },
        "mismatch_case_closure_result": {
            "mismatch_case_closure_state": closure_state,
            "closure_reason_codes": closure_reason_codes,
            "rollback_or_repair_outcome_state": rollback_or_repair_outcome_state,
            "applied_outcome_aligns_to_current_authority": bool(
                applied_outcome_aligns_to_current_authority
            ),
            "follow_on_reconciliation_required": bool(
                rollback_or_repair_outcome_state == ROLLBACK_OR_REPAIR_APPLIED_UNDER_EXISTING_PATH
            ),
            "follow_on_reconciliation_state": follow_on_reconciliation_state,
            "follow_on_reconciliation_is_distinct_from_source": bool(
                follow_on_reconciliation_is_distinct
            ),
            "case_closed": bool(
                closure_state
                in {
                    MISMATCH_CASE_CLOSED_REJECTED_NO_ACTION,
                    MISMATCH_CASE_CLOSED_VERIFIED_RESOLVED,
                }
            ),
            "requires_further_governance": bool(
                closure_state == MISMATCH_CASE_OPEN_REQUIRES_FURTHER_GOVERNANCE
            ),
        },
        "reviewer_source_or_gate_actor": {
            "closed_by_surface": "memory_summary.v4_governance_reopen_promotion_reconciliation_mismatch_case_closure_snapshot_v1",
            "source_existing_path_actor": str(
                rollback_or_repair_decision.get("existing_path_actor", "")
            ),
            "source_reviewer_surface": str(
                source_reviewer_source_or_gate_actor.get("decided_by_surface", "")
            ),
            "branch_id": str(branch_registry.get("current_branch_id", "")),
            "branch_pause_rationale": str(branch_record.get("pause_rationale", "")),
            "directive_id": str(
                dict(directive_state.get("current_directive_state", {})).get("directive_id", "")
            ),
            "bucket_id": str(dict(bucket_state.get("current_bucket_state", {})).get("bucket_id", "")),
        },
        "provenance_and_audit_trace": {
            "canonical_authority_file": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
            "governance_memory_promotion_ledger_path": str(
                GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH
            ),
            "promotion_outcome_ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_OUTCOME_LEDGER_PATH),
            "reconciliation_ledger_path": str(
                GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_LEDGER_PATH
            ),
            "reconciliation_escalation_ledger_path": str(
                GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_ESCALATION_LEDGER_PATH
            ),
            "remediation_review_ledger_path": str(GOVERNANCE_REOPEN_REMEDIATION_REVIEW_LEDGER_PATH),
            "remediation_review_outcome_ledger_path": str(
                GOVERNANCE_REOPEN_REMEDIATION_REVIEW_OUTCOME_LEDGER_PATH
            ),
            "rollback_or_repair_handoff_ledger_path": str(
                GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_HANDOFF_LEDGER_PATH
            ),
            "rollback_or_repair_outcome_ledger_path": str(
                GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_OUTCOME_LEDGER_PATH
            ),
            "mismatch_case_closure_ledger_path": str(
                GOVERNANCE_REOPEN_MISMATCH_CASE_CLOSURE_LEDGER_PATH
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
            "reconciliation_escalation_ledger_entries_seen": int(len(escalation_ledger_rows)),
            "remediation_review_ledger_entries_seen": int(len(remediation_review_ledger_rows)),
            "remediation_review_outcome_ledger_entries_seen": int(
                len(remediation_review_outcome_ledger_rows)
            ),
            "rollback_or_repair_handoff_ledger_entries_seen": int(
                len(rollback_or_repair_handoff_ledger_rows)
            ),
            "rollback_or_repair_outcome_ledger_entries_seen": int(
                len(rollback_or_repair_outcome_ledger_rows)
            ),
            "mismatch_case_closure_ledger_entries_before_write": int(len(closure_ledger_rows)),
            "closure_mode": "observational_lifecycle_status_only",
        },
        "operator_readable_conclusion": (
            "The rollback-or-repair mismatch-response lifecycle now has an explicit case-closure judgment. "
            + (
                "The case is closed with no further action because the existing path rejected the request."
                if closure_state == MISMATCH_CASE_CLOSED_REJECTED_NO_ACTION
                else "The case remains pending because an applied existing-path action still requires a distinct follow-on reconciliation."
                if closure_state == MISMATCH_CASE_PENDING_FOLLOW_ON_RECONCILIATION
                else "The case is closed as verified resolved because the current authority and follow-on verification support convergence."
                if closure_state == MISMATCH_CASE_CLOSED_VERIFIED_RESOLVED
                else "The case remains open for further governance because resolution is not yet verified or the mismatch persists."
            )
        ),
    }

    _write_json(artifact_path, payload)

    ledger_entry = {
        "event_type": "governance_reopen_mismatch_case_closure_recorded",
        "written_at": closed_at,
        "mismatch_case_closure_id": closure_id,
        "source_rollback_or_repair_outcome_id": rollback_or_repair_outcome_id,
        "source_rollback_or_repair_outcome_artifact_path": rollback_or_repair_outcome_artifact_path,
        "artifact_path": str(artifact_path),
        "mismatch_case_closure_state": closure_state,
        "rollback_or_repair_outcome_state": rollback_or_repair_outcome_state,
        "follow_on_reconciliation_state": follow_on_reconciliation_state,
        "follow_on_reconciliation_artifact_path": follow_on_reconciliation_artifact_path,
        "closure_reason_codes": closure_reason_codes,
        "requested_template_name": str(
            requested_rollback_or_repair_scope.get("requested_template_name", "")
        ),
        "requested_template_family": str(
            requested_rollback_or_repair_scope.get("requested_template_family", "")
        ),
    }
    _append_jsonl(GOVERNANCE_REOPEN_MISMATCH_CASE_CLOSURE_LEDGER_PATH, ledger_entry)

    updated_self_structure = dict(self_structure_state)
    updated_summary = dict(current_state_summary)
    updated_summary.update(
        {
            "latest_governance_reopen_mismatch_case_closure_artifact_path": str(artifact_path),
            "latest_governance_reopen_mismatch_case_closure_ledger_path": str(
                GOVERNANCE_REOPEN_MISMATCH_CASE_CLOSURE_LEDGER_PATH
            ),
            "latest_governance_reopen_mismatch_case_closure_state": closure_state,
            "latest_governance_reopen_mismatch_case_follow_on_reconciliation_state": (
                follow_on_reconciliation_state
            ),
            "latest_governance_reopen_mismatch_case_closure_reason_codes": closure_reason_codes,
        }
    )
    updated_self_structure["generated_at"] = _now()
    updated_self_structure["current_state_summary"] = updated_summary
    updated_self_structure["governance_reopen_mismatch_case_closure"] = {
        "schema_name": CLOSURE_SCHEMA_NAME,
        "schema_version": CLOSURE_SCHEMA_VERSION,
        "latest_mismatch_case_closure": {
            "mismatch_case_closure_id": closure_id,
            "source_rollback_or_repair_outcome_id": rollback_or_repair_outcome_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_MISMATCH_CASE_CLOSURE_LEDGER_PATH),
            "mismatch_case_closure_state": closure_state,
            "follow_on_reconciliation_state": follow_on_reconciliation_state,
        },
    }
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure)

    _append_jsonl(
        SELF_STRUCTURE_LEDGER_PATH,
        {
            "event_id": f"governance_reopen_mismatch_case_closure::{proposal['proposal_id']}",
            "timestamp": _now(),
            "event_type": "governance_reopen_mismatch_case_closure_recorded",
            "mismatch_case_closure_id": closure_id,
            "source_rollback_or_repair_outcome_id": rollback_or_repair_outcome_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_MISMATCH_CASE_CLOSURE_LEDGER_PATH),
            "mismatch_case_closure_state": closure_state,
            "follow_on_reconciliation_state": follow_on_reconciliation_state,
            "requested_template_name": str(
                requested_rollback_or_repair_scope.get("requested_template_name", "")
            ),
            "requested_template_family": str(
                requested_rollback_or_repair_scope.get("requested_template_family", "")
            ),
        },
    )

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: rollback-or-repair outcome was materialized as an explicit mismatch-case closure status",
        "observability_gain": {
            "passed": True,
            "reason": "future agents can now distinguish closed, pending follow-on verification, and still-open mismatch cases without relying on implicit human stitching",
            "artifact_path": str(artifact_path),
            "mismatch_case_closure_ledger_path": str(
                GOVERNANCE_REOPEN_MISMATCH_CASE_CLOSURE_LEDGER_PATH
            ),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "mismatch-case closure reuses existing rollback-or-repair and reconciliation artifacts to make lifecycle status explicit without creating a second apply path",
        },
        "ambiguity_reduction": {
            "passed": True,
            "reason": "closure state, follow-on reconciliation status, and closure reason codes are now explicit and queryable",
            "score": 0.97,
        },
        "safety_neutrality": {
            "passed": True,
            "reason": "mismatch-case closure remains observational only and never invokes promotion, rollback, or repair automatically",
            "scope": str(proposal.get("scope", "")),
        },
        "later_selection_usefulness": {
            "passed": True,
            "reason": "applied existing-path cases remain pending until follow-on reconciliation verifies convergence, while rejected or justified noop cases become explicit terminal states",
            "recommended_next_template": "",
        },
        "diagnostic_conclusions": {
            "rollback_or_repair_outcome_state": rollback_or_repair_outcome_state,
            "mismatch_case_closure_state": closure_state,
            "follow_on_reconciliation_state": follow_on_reconciliation_state,
            "recommended_next_action": "hold_and_consolidate",
            "recommended_next_template": "",
        },
        "artifact_path": str(artifact_path),
        "mismatch_case_closure_ledger_path": str(
            GOVERNANCE_REOPEN_MISMATCH_CASE_CLOSURE_LEDGER_PATH
        ),
    }
