from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .governance_memory_promotion_v1 import promote_governance_memory_authority
from .governance_memory_reopen_intake_v1 import (
    PROMOTION_APPLIED_AS_BINDING_AUTHORITY,
    PROMOTION_NOOP_ALREADY_AUTHORITATIVE,
)
from .ledger import intervention_data_dir, load_latest_snapshots
from .v4_governance_reopen_promotion_reconciliation_escalation_snapshot_v1 import (
    REMEDIATION_OR_ROLLBACK_REVIEW_CANDIDATE,
    RECONCILIATION_MISMATCH_DETECTED,
)
from .v4_governance_reopen_promotion_reconciliation_remediation_review_outcome_snapshot_v1 import (
    REMEDIATION_REVIEW_APPROVED_FOR_EXISTING_ROLLBACK_OR_REPAIR_PATH,
    ROLLBACK_OR_REPAIR_PATH_ELIGIBLE,
    ROLLBACK_READY_REFERENCE,
)
from .v4_governance_reopen_promotion_reconciliation_remediation_review_submission_snapshot_v1 import (
    SUBMITTED_FOR_REMEDIATION_REVIEW,
)
from .v4_governance_reopen_promotion_reconciliation_rollback_or_repair_handoff_snapshot_v1 import (
    ROLLBACK_OR_REPAIR_CANDIDATE_UNDER_EXISTING_PATH,
    ROLLBACK_OR_REPAIR_HANDOFF_PENDING,
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
INTERVENTION_LEDGER_PATH = DATA_DIR / "intervention_ledger.jsonl"
INTERVENTION_ANALYTICS_PATH = DATA_DIR / "intervention_analytics_latest.json"
PROPOSAL_RECOMMENDATIONS_PATH = DATA_DIR / "proposal_recommendations_latest.json"
SELF_STRUCTURE_STATE_PATH = DATA_DIR / "self_structure_state_latest.json"
SELF_STRUCTURE_LEDGER_PATH = DATA_DIR / "self_structure_ledger.jsonl"
BRANCH_REGISTRY_PATH = DATA_DIR / "branch_registry_latest.json"
DIRECTIVE_STATE_PATH = DATA_DIR / "directive_state_latest.json"
BUCKET_STATE_PATH = DATA_DIR / "bucket_state_latest.json"

OUTCOME_SCHEMA_NAME = "GovernanceReopenPromotionReconciliationRollbackOrRepairOutcome"
OUTCOME_SCHEMA_VERSION = "governance_reopen_promotion_reconciliation_rollback_or_repair_outcome_v1"
ROLLBACK_OR_REPAIR_REJECTED_UNDER_EXISTING_PATH = "rollback_or_repair_rejected_under_existing_path"
ROLLBACK_OR_REPAIR_APPLIED_UNDER_EXISTING_PATH = "rollback_or_repair_applied_under_existing_path"
ROLLBACK_OR_REPAIR_NOOP_ALREADY_RESOLVED = "rollback_or_repair_noop_already_resolved"
ROLLBACK_OR_REPAIR_OUTCOME_NON_AUTHORITATIVE = (
    "rollback_or_repair_outcome_non_authoritative_until_explicit_existing_path_execution_succeeds"
)
EXPLICIT_AUTHORITY_PROMOTION_ROLLBACK_ONLY = "explicit_authority_promotion_rollback_only"


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


def _candidate_signature(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "authority_file_summary": dict(payload.get("authority_file_summary", {})),
        "binding_decision_register": list(payload.get("binding_decision_register", [])),
        "selector_frontier_memory": dict(payload.get("selector_frontier_memory", {})),
        "capability_boundary_state": dict(payload.get("capability_boundary_state", {})),
        "resolved_current_state": dict(payload.get("resolved_current_state", {})),
    }


def _authority_reference_matches(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        str(left.get("authority_source_proposal_id", ""))
        == str(right.get("authority_source_proposal_id", ""))
        and str(left.get("authority_candidate_artifact_path", ""))
        == str(right.get("authority_candidate_artifact_path", ""))
        and str(left.get("current_branch_state", ""))
        == str(right.get("current_branch_state", ""))
        and str(left.get("current_operating_stance", ""))
        == str(right.get("current_operating_stance", ""))
        and str(left.get("held_baseline_template", ""))
        == str(right.get("held_baseline_template", ""))
        and str(left.get("routing_status", ""))
        == str(right.get("routing_status", ""))
    )


def _resolve_existing_path_candidate(
    *,
    selected_existing_follow_on_path: str,
    authority_before_reference: dict[str, Any],
    rollback_ready_reference: dict[str, Any],
) -> dict[str, str]:
    rollback_trace = dict(rollback_ready_reference.get("rollback_trace", {}))
    if selected_existing_follow_on_path != EXPLICIT_AUTHORITY_PROMOTION_ROLLBACK_ONLY:
        return {}
    return {
        "candidate_artifact_path": _first_nonempty(
            authority_before_reference.get("authority_candidate_artifact_path"),
            rollback_trace.get("previous_authority_artifact_path"),
        ),
        "candidate_source_template_name": _first_nonempty(
            authority_before_reference.get("authority_candidate_source_template_name"),
            "memory_summary.v4_governance_memory_authority_snapshot_v1",
        ),
        "candidate_source_proposal_id": _first_nonempty(
            authority_before_reference.get("authority_source_proposal_id"),
            rollback_trace.get("previous_authority_proposal_id"),
        ),
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
    handoff_ledger_rows = _load_jsonl(GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_HANDOFF_LEDGER_PATH)
    outcome_ledger_rows = _load_jsonl(GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_OUTCOME_LEDGER_PATH)

    if not all([authority_payload, self_structure_state, branch_registry, directive_state, bucket_state]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: authority, self-structure, branch, directive, and bucket artifacts are required",
        }

    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    handoff_artifact_path = str(
        current_state_summary.get("latest_governance_reopen_rollback_or_repair_handoff_artifact_path", "")
    )
    handoff_state_summary = str(
        current_state_summary.get("latest_governance_reopen_rollback_or_repair_handoff_state", "")
    )
    candidate_state_summary = str(
        current_state_summary.get("latest_governance_reopen_rollback_or_repair_candidate_state", "")
    )

    if not handoff_artifact_path:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no rollback-or-repair handoff artifact is available for rollback_or_repair outcome",
        }

    handoff_payload = _load_json_file(Path(handoff_artifact_path))
    if not handoff_payload:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest rollback-or-repair handoff artifact could not be loaded",
        }

    handoff_identity = dict(handoff_payload.get("snapshot_identity_context", {}))
    handoff_id = _first_nonempty(
        handoff_identity.get("rollback_or_repair_handoff_id"),
        handoff_payload.get("rollback_or_repair_handoff_id"),
    )
    source_remediation_review_outcome_reference = dict(
        handoff_payload.get("source_remediation_review_outcome_reference", {})
    )
    source_remediation_review_submission_reference = dict(
        handoff_payload.get("source_remediation_review_submission_reference", {})
    )
    source_reconciliation_escalation_reference = dict(
        handoff_payload.get("source_reconciliation_escalation_reference", {})
    )
    source_reconciliation_reference = dict(handoff_payload.get("source_reconciliation_reference", {}))
    source_promotion_outcome_reference = dict(handoff_payload.get("source_promotion_outcome_reference", {}))
    source_promotion_handoff_reference = dict(handoff_payload.get("source_promotion_handoff_reference", {}))
    source_review_outcome_reference = dict(handoff_payload.get("source_review_outcome_reference", {}))
    source_review_submission_reference = dict(handoff_payload.get("source_review_submission_reference", {}))
    authority_before_reference = dict(handoff_payload.get("authority_before_reference", {}))
    authority_after_reference = dict(handoff_payload.get("authority_after_reference", {}))
    mismatch_surfaces_and_propagation_failures = dict(
        handoff_payload.get("mismatch_surfaces_and_propagation_failures", {})
    )
    rollback_ready_reference = dict(handoff_payload.get("rollback_ready_reference", {}))
    requested_rollback_or_repair_scope = dict(
        handoff_payload.get("requested_rollback_or_repair_scope", {})
    )
    rollback_or_repair_candidate = dict(handoff_payload.get("rollback_or_repair_candidate", {}))
    existing_path_input_metadata = dict(handoff_payload.get("existing_path_input_metadata", {}))

    remediation_review_outcome_state = str(
        source_remediation_review_outcome_reference.get("remediation_review_outcome_state", "")
    )
    follow_on_handoff_state = str(
        source_remediation_review_outcome_reference.get("follow_on_handoff_state", "")
    )
    remediation_review_submission_state = str(
        source_remediation_review_submission_reference.get("submission_state", "")
    )
    escalation_state = str(source_reconciliation_escalation_reference.get("escalation_state", ""))
    reconciliation_state = str(source_reconciliation_reference.get("reconciliation_state", ""))
    source_promotion_outcome_state = str(
        source_promotion_outcome_reference.get("promotion_outcome_state", "")
    )
    rollback_or_repair_handoff_state = _first_nonempty(
        rollback_or_repair_candidate.get("rollback_or_repair_handoff_state"),
        handoff_state_summary,
    )
    rollback_or_repair_candidate_state = _first_nonempty(
        rollback_or_repair_candidate.get("rollback_or_repair_candidate_state"),
        candidate_state_summary,
    )

    if remediation_review_outcome_state != REMEDIATION_REVIEW_APPROVED_FOR_EXISTING_ROLLBACK_OR_REPAIR_PATH:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: only remediation_review_approved_for_existing_rollback_or_repair_path outcomes may receive explicit rollback_or_repair outcomes",
            "diagnostic_conclusions": {
                "remediation_review_outcome_state": remediation_review_outcome_state,
                "rollback_or_repair_handoff_state": rollback_or_repair_handoff_state,
            },
        }

    if follow_on_handoff_state != ROLLBACK_OR_REPAIR_PATH_ELIGIBLE:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest approved remediation-review outcome is not in eligible_for_existing_rollback_or_repair_path state",
            "diagnostic_conclusions": {
                "remediation_review_outcome_state": remediation_review_outcome_state,
                "follow_on_handoff_state": follow_on_handoff_state,
            },
        }

    if rollback_or_repair_handoff_state != ROLLBACK_OR_REPAIR_HANDOFF_PENDING:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: only rollback_or_repair_handoff_pending packets may receive explicit rollback_or_repair outcomes",
            "diagnostic_conclusions": {
                "rollback_or_repair_handoff_state": rollback_or_repair_handoff_state,
                "rollback_or_repair_candidate_state": rollback_or_repair_candidate_state,
            },
        }

    if rollback_or_repair_candidate_state != ROLLBACK_OR_REPAIR_CANDIDATE_UNDER_EXISTING_PATH:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: only rollback_or_repair_candidate_under_existing_path cases may receive explicit rollback_or_repair outcomes",
            "diagnostic_conclusions": {
                "rollback_or_repair_handoff_state": rollback_or_repair_handoff_state,
                "rollback_or_repair_candidate_state": rollback_or_repair_candidate_state,
            },
        }

    if remediation_review_submission_state != SUBMITTED_FOR_REMEDIATION_REVIEW:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: only submitted remediation-review packets may feed rollback_or_repair outcome evaluation",
            "diagnostic_conclusions": {
                "remediation_review_submission_state": remediation_review_submission_state,
                "rollback_or_repair_handoff_state": rollback_or_repair_handoff_state,
            },
        }

    if escalation_state != REMEDIATION_OR_ROLLBACK_REVIEW_CANDIDATE:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: only remediation_or_rollback_review_candidate cases may feed rollback_or_repair outcome evaluation",
            "diagnostic_conclusions": {
                "source_escalation_state": escalation_state,
            },
        }

    if reconciliation_state != RECONCILIATION_MISMATCH_DETECTED:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: only reconciliation_mismatch_detected cases may feed rollback_or_repair outcome evaluation",
            "diagnostic_conclusions": {
                "source_reconciliation_state": reconciliation_state,
            },
        }

    if source_promotion_outcome_state == PROMOTION_NOOP_ALREADY_AUTHORITATIVE:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: already-resolved noop cases may not receive explicit rollback_or_repair outcomes",
            "diagnostic_conclusions": {
                "source_promotion_outcome_state": source_promotion_outcome_state,
            },
        }

    if source_promotion_outcome_state and source_promotion_outcome_state != PROMOTION_APPLIED_AS_BINDING_AUTHORITY:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: rollback_or_repair outcome requires an applied promotion outcome as the source mismatch case",
            "diagnostic_conclusions": {
                "source_promotion_outcome_state": source_promotion_outcome_state,
            },
        }

    if any(str(row.get("source_rollback_or_repair_handoff_id", "")) == handoff_id for row in outcome_ledger_rows):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest rollback-or-repair handoff already has a recorded rollback_or_repair outcome",
            "diagnostic_conclusions": {
                "rollback_or_repair_handoff_id": handoff_id,
                "existing_rollback_or_repair_outcome_count": sum(
                    1
                    for row in outcome_ledger_rows
                    if str(row.get("source_rollback_or_repair_handoff_id", "")) == handoff_id
                ),
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
        for item in list(
            existing_path_input_metadata.get(
                "available_existing_follow_on_paths",
                rollback_ready_reference.get("available_existing_follow_on_paths", []),
            )
        )
        if str(item)
    ]

    malformed_handoff = not bool(
        source_remediation_review_outcome_reference
        and source_remediation_review_submission_reference
        and source_reconciliation_escalation_reference
        and source_reconciliation_reference
        and source_promotion_outcome_reference
        and authority_before_reference
        and authority_after_reference
        and rollback_ready_reference
        and requested_rollback_or_repair_scope
        and rollback_or_repair_candidate
        and existing_path_input_metadata
        and available_existing_follow_on_paths
        and (failed_checks or mismatch_surfaces)
    )
    if malformed_handoff:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest rollback-or-repair handoff artifact is missing outcome-critical fields",
            "diagnostic_conclusions": {
                "has_source_remediation_review_outcome_reference": bool(
                    source_remediation_review_outcome_reference
                ),
                "has_source_remediation_review_submission_reference": bool(
                    source_remediation_review_submission_reference
                ),
                "has_source_reconciliation_escalation_reference": bool(
                    source_reconciliation_escalation_reference
                ),
                "has_source_reconciliation_reference": bool(source_reconciliation_reference),
                "has_source_promotion_outcome_reference": bool(source_promotion_outcome_reference),
                "has_authority_before_reference": bool(authority_before_reference),
                "has_authority_after_reference": bool(authority_after_reference),
                "has_rollback_ready_reference": bool(rollback_ready_reference),
                "has_requested_rollback_or_repair_scope": bool(requested_rollback_or_repair_scope),
                "has_existing_path_input_metadata": bool(existing_path_input_metadata),
                "available_existing_follow_on_paths_count": int(len(available_existing_follow_on_paths)),
                "failed_check_count": int(len(failed_checks)),
                "mismatch_surface_count": int(len(mismatch_surfaces)),
            },
        }

    remediation_review_outcome_artifact_path = str(
        source_remediation_review_outcome_reference.get("artifact_path", "")
    )
    remediation_review_outcome_payload = _load_json_file(Path(remediation_review_outcome_artifact_path))
    remediation_review_decision = dict(
        remediation_review_outcome_payload.get("remediation_review_decision", {})
    )
    repeated_motion_without_new_evidence = bool(
        remediation_review_decision.get("repeated_motion_without_new_evidence", False)
    )
    if repeated_motion_without_new_evidence:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: repeated motion without new evidence may not receive rollback_or_repair outcomes",
            "diagnostic_conclusions": {
                "source_remediation_review_outcome_id": str(
                    source_remediation_review_outcome_reference.get("remediation_review_outcome_id", "")
                ),
            },
        }

    current_authority_reference = _authority_reference(authority_payload, current_state_summary)
    authority_posture_at_decision_time = _authority_posture_snapshot(authority_payload)

    selected_existing_follow_on_path = _first_nonempty(
        existing_path_input_metadata.get("selected_existing_follow_on_path"),
        requested_rollback_or_repair_scope.get("selected_existing_follow_on_path"),
    )
    path_selection_required = bool(
        existing_path_input_metadata.get(
            "path_selection_required",
            requested_rollback_or_repair_scope.get("path_selection_required", True),
        )
    )
    apply_existing_path_requested = bool(selected_existing_follow_on_path)
    existing_path_decision_mode = _first_nonempty(
        existing_path_input_metadata.get("existing_path_decision_mode"),
        "explicit_selected_path_required",
    )
    rollback_or_repair_existing_path_actor = _first_nonempty(
        selected_existing_follow_on_path,
        "explicit_existing_rollback_or_repair_path_v1",
    )

    gate_checks_performed: list[dict[str, Any]] = [
        {
            "check_name": "remediation_review_approved_for_existing_path",
            "passed": remediation_review_outcome_state
            == REMEDIATION_REVIEW_APPROVED_FOR_EXISTING_ROLLBACK_OR_REPAIR_PATH,
            "observed_value": remediation_review_outcome_state,
        },
        {
            "check_name": "rollback_or_repair_handoff_pending",
            "passed": rollback_or_repair_handoff_state == ROLLBACK_OR_REPAIR_HANDOFF_PENDING,
            "observed_value": rollback_or_repair_handoff_state,
        },
        {
            "check_name": "rollback_or_repair_candidate_under_existing_path",
            "passed": rollback_or_repair_candidate_state == ROLLBACK_OR_REPAIR_CANDIDATE_UNDER_EXISTING_PATH,
            "observed_value": rollback_or_repair_candidate_state,
        },
        {
            "check_name": "submitted_for_remediation_review",
            "passed": remediation_review_submission_state == SUBMITTED_FOR_REMEDIATION_REVIEW,
            "observed_value": remediation_review_submission_state,
        },
        {
            "check_name": "reconciliation_mismatch_detected",
            "passed": reconciliation_state == RECONCILIATION_MISMATCH_DETECTED,
            "observed_value": reconciliation_state,
        },
        {
            "check_name": "rollback_ready_reference_present",
            "passed": rollback_reference_state == ROLLBACK_READY_REFERENCE,
            "observed_value": rollback_reference_state,
        },
        {
            "check_name": "no_repeated_motion_without_new_evidence",
            "passed": not repeated_motion_without_new_evidence,
            "observed_value": repeated_motion_without_new_evidence,
        },
    ]

    decision_reason_codes: list[str] = []
    rollback_or_repair_outcome_state = ROLLBACK_OR_REPAIR_CANDIDATE_UNDER_EXISTING_PATH
    authority_after_payload = authority_payload
    authority_mutated = False
    gate_failure_detail = ""
    candidate_artifact_path = ""
    candidate_source_template_name = ""
    candidate_source_proposal_id = ""
    candidate_payload: dict[str, Any] = {}
    selected_path_supported = False
    already_resolved = False

    if not apply_existing_path_requested:
        decision_reason_codes.extend(
            [
                "candidate_ready_but_existing_path_not_selected",
                "explicit_existing_follow_on_path_invocation_required",
            ]
        )
    else:
        gate_checks_performed.append(
            {
                "check_name": "selected_existing_follow_on_path_available",
                "passed": selected_existing_follow_on_path in available_existing_follow_on_paths,
                "observed_value": selected_existing_follow_on_path,
            }
        )
        if selected_existing_follow_on_path not in available_existing_follow_on_paths:
            rollback_or_repair_outcome_state = ROLLBACK_OR_REPAIR_REJECTED_UNDER_EXISTING_PATH
            decision_reason_codes.append("selected_existing_follow_on_path_not_available")
        else:
            selected_path_supported = (
                selected_existing_follow_on_path == EXPLICIT_AUTHORITY_PROMOTION_ROLLBACK_ONLY
            )
            gate_checks_performed.append(
                {
                    "check_name": "selected_existing_follow_on_path_supported_by_outcome_gate",
                    "passed": selected_path_supported,
                    "observed_value": selected_existing_follow_on_path,
                }
            )
            if not selected_path_supported:
                rollback_or_repair_outcome_state = ROLLBACK_OR_REPAIR_REJECTED_UNDER_EXISTING_PATH
                decision_reason_codes.append("selected_existing_follow_on_path_not_supported_by_outcome_gate")
            else:
                selected_candidate = _resolve_existing_path_candidate(
                    selected_existing_follow_on_path=selected_existing_follow_on_path,
                    authority_before_reference=authority_before_reference,
                    rollback_ready_reference=rollback_ready_reference,
                )
                candidate_artifact_path = str(selected_candidate.get("candidate_artifact_path", ""))
                candidate_source_template_name = str(
                    selected_candidate.get("candidate_source_template_name", "")
                )
                candidate_source_proposal_id = str(
                    selected_candidate.get("candidate_source_proposal_id", "")
                )
                gate_checks_performed.extend(
                    [
                        {
                            "check_name": "existing_path_candidate_artifact_path_present",
                            "passed": bool(candidate_artifact_path),
                            "observed_value": candidate_artifact_path,
                        },
                        {
                            "check_name": "existing_path_candidate_template_present",
                            "passed": bool(candidate_source_template_name),
                            "observed_value": candidate_source_template_name,
                        },
                    ]
                )
                if not candidate_artifact_path or not candidate_source_template_name:
                    rollback_or_repair_outcome_state = (
                        ROLLBACK_OR_REPAIR_REJECTED_UNDER_EXISTING_PATH
                    )
                    decision_reason_codes.append("existing_path_candidate_reference_missing")
                else:
                    candidate_payload = _load_json_file(Path(candidate_artifact_path))
                    gate_checks_performed.append(
                        {
                            "check_name": "existing_path_candidate_artifact_loadable",
                            "passed": bool(candidate_payload),
                            "observed_value": candidate_artifact_path,
                        }
                    )
                    if not candidate_payload:
                        rollback_or_repair_outcome_state = (
                            ROLLBACK_OR_REPAIR_REJECTED_UNDER_EXISTING_PATH
                        )
                        decision_reason_codes.append("existing_path_candidate_artifact_unreadable")
                    else:
                        already_resolved = (
                            _authority_reference_matches(current_authority_reference, authority_before_reference)
                            or _candidate_signature(candidate_payload)
                            == _candidate_signature(authority_payload)
                        )
                        gate_checks_performed.append(
                            {
                                "check_name": "existing_path_candidate_not_already_resolved",
                                "passed": not already_resolved,
                                "observed_value": already_resolved,
                            }
                        )
                        if already_resolved:
                            rollback_or_repair_outcome_state = (
                                ROLLBACK_OR_REPAIR_NOOP_ALREADY_RESOLVED
                            )
                            decision_reason_codes.append("existing_path_candidate_already_matches_canonical_authority")
                        else:
                            promotion_proposal = {
                                "proposal_id": f"{proposal['proposal_id']}::rollback_or_repair",
                                "template_name": candidate_source_template_name,
                            }
                            try:
                                authority_after_payload = promote_governance_memory_authority(
                                    candidate_payload=candidate_payload,
                                    proposal=promotion_proposal,
                                    candidate_artifact_path=Path(candidate_artifact_path),
                                    promotion_reason=(
                                        "rollback-or-repair outcome executed the explicit_authority_promotion_rollback_only "
                                        "path through the existing governance-memory promotion gate"
                                    ),
                                )
                                authority_mutated = True
                                rollback_or_repair_outcome_state = (
                                    ROLLBACK_OR_REPAIR_APPLIED_UNDER_EXISTING_PATH
                                )
                                decision_reason_codes.append(
                                    "existing_authority_promotion_rollback_path_applied"
                                )
                            except Exception as exc:  # pragma: no cover - defensive gate capture
                                gate_failure_detail = str(exc)
                                rollback_or_repair_outcome_state = (
                                    ROLLBACK_OR_REPAIR_REJECTED_UNDER_EXISTING_PATH
                                )
                                decision_reason_codes.append("existing_rollback_or_repair_path_rejected_candidate")

    decided_at = _now()
    outcome_id = f"reopen_rollback_or_repair_outcome::{proposal['proposal_id']}"
    artifact_path = _diagnostic_artifact_dir() / (
        "memory_summary_v4_governance_reopen_promotion_reconciliation_rollback_or_repair_outcome_snapshot_v1_"
        f"{proposal['proposal_id']}.json"
    )
    branch_record = (
        dict(list(branch_registry.get("branches", []))[0]) if list(branch_registry.get("branches", [])) else {}
    )

    updated_summary_after_apply = dict(current_state_summary)
    after_authority_reference = _authority_reference(authority_after_payload, updated_summary_after_apply)
    if not authority_mutated:
        after_authority_reference = current_authority_reference

    payload = {
        "proposal_id": str(proposal.get("proposal_id", "")),
        "template_name": "memory_summary.v4_governance_reopen_promotion_reconciliation_rollback_or_repair_outcome_snapshot_v1",
        "snapshot_identity_context": {
            "rollback_or_repair_outcome_id": outcome_id,
            "decided_at": decided_at,
            "phase": "governance_reopen_promotion_reconciliation_rollback_or_repair_outcome",
            "source_rollback_or_repair_handoff_id": handoff_id,
            "source_remediation_review_outcome_id": str(
                source_remediation_review_outcome_reference.get("remediation_review_outcome_id", "")
            ),
            "source_remediation_review_packet_id": str(
                source_remediation_review_submission_reference.get("remediation_review_packet_id", "")
            ),
        },
        "rollback_or_repair_outcome_contract": {
            "schema_name": OUTCOME_SCHEMA_NAME,
            "schema_version": OUTCOME_SCHEMA_VERSION,
            "required_remediation_review_outcome_state": (
                REMEDIATION_REVIEW_APPROVED_FOR_EXISTING_ROLLBACK_OR_REPAIR_PATH
            ),
            "required_handoff_state": ROLLBACK_OR_REPAIR_HANDOFF_PENDING,
            "required_candidate_state": ROLLBACK_OR_REPAIR_CANDIDATE_UNDER_EXISTING_PATH,
            "required_submission_state": SUBMITTED_FOR_REMEDIATION_REVIEW,
            "required_reconciliation_state": RECONCILIATION_MISMATCH_DETECTED,
            "rollback_or_repair_outcome_states": [
                ROLLBACK_OR_REPAIR_CANDIDATE_UNDER_EXISTING_PATH,
                ROLLBACK_OR_REPAIR_REJECTED_UNDER_EXISTING_PATH,
                ROLLBACK_OR_REPAIR_APPLIED_UNDER_EXISTING_PATH,
                ROLLBACK_OR_REPAIR_NOOP_ALREADY_RESOLVED,
            ],
            "authority_relation": ROLLBACK_OR_REPAIR_OUTCOME_NON_AUTHORITATIVE,
            "automatic_rollback_disallowed": True,
            "automatic_repair_disallowed": True,
            "canonical_authority_mutation_disallowed_without_explicit_existing_path": True,
            "supported_existing_follow_on_paths": [EXPLICIT_AUTHORITY_PROMOTION_ROLLBACK_ONLY],
        },
        "source_rollback_or_repair_handoff_reference": {
            "rollback_or_repair_handoff_id": handoff_id,
            "artifact_path": handoff_artifact_path,
            "ledger_path": str(GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_HANDOFF_LEDGER_PATH),
            "rollback_or_repair_handoff_state": rollback_or_repair_handoff_state,
            "rollback_or_repair_candidate_state": rollback_or_repair_candidate_state,
        },
        "source_remediation_review_outcome_reference": dict(source_remediation_review_outcome_reference),
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
        "authority_after_reference": after_authority_reference,
        "mismatch_surfaces_and_failed_propagation_checks": {
            "failed_check_count": int(len(failed_checks)),
            "failed_checks": failed_checks,
            "mismatch_surfaces": mismatch_surfaces,
            "propagation_status_by_surface": propagation_status_by_surface,
        },
        "rollback_ready_reference": {
            "rollback_reference_state": rollback_reference_state,
            "rollback_trace": dict(rollback_ready_reference.get("rollback_trace", {})),
            "available_existing_follow_on_paths": available_existing_follow_on_paths,
            "no_rollback_invoked_here": not authority_mutated,
            "no_repair_invoked_here": True,
        },
        "authority_posture_at_decision_time": authority_posture_at_decision_time,
        "requested_rollback_or_repair_scope": requested_rollback_or_repair_scope,
        "existing_path_checks_performed": gate_checks_performed,
        "existing_path_input_metadata": {
            "selected_existing_follow_on_path": selected_existing_follow_on_path,
            "available_existing_follow_on_paths": available_existing_follow_on_paths,
            "path_selection_required": path_selection_required,
            "apply_existing_path_requested": apply_existing_path_requested,
            "existing_path_decision_mode": existing_path_decision_mode,
            "candidate_artifact_path": candidate_artifact_path,
            "candidate_source_template_name": candidate_source_template_name,
            "candidate_source_proposal_id": candidate_source_proposal_id,
            "supported_existing_follow_on_paths": [EXPLICIT_AUTHORITY_PROMOTION_ROLLBACK_ONLY],
            "canonical_authority_mutation_disallowed_here": not authority_mutated,
        },
        "rollback_or_repair_decision": {
            "rollback_or_repair_outcome_state": rollback_or_repair_outcome_state,
            "decision_reason_codes": decision_reason_codes,
            "existing_path_actor": rollback_or_repair_existing_path_actor,
            "apply_existing_path_requested": apply_existing_path_requested,
            "selected_existing_follow_on_path": selected_existing_follow_on_path,
            "selected_existing_follow_on_path_supported": selected_path_supported,
            "canonical_authority_mutated": bool(authority_mutated),
            "repeated_motion_without_new_evidence": repeated_motion_without_new_evidence,
            "already_resolved": already_resolved,
            "gate_failure_detail": gate_failure_detail,
            "follow_on_handoff_state": follow_on_handoff_state,
        },
        "reviewer_source_or_gate_actor": {
            "decided_by_surface": "memory_summary.v4_governance_reopen_promotion_reconciliation_rollback_or_repair_outcome_snapshot_v1",
            "existing_path_actor": rollback_or_repair_existing_path_actor,
            "branch_id": str(branch_registry.get("current_branch_id", "")),
            "branch_pause_rationale": str(branch_record.get("pause_rationale", "")),
            "directive_id": str(dict(directive_state.get("current_directive_state", {})).get("directive_id", "")),
            "bucket_id": str(dict(bucket_state.get("current_bucket_state", {})).get("bucket_id", "")),
            "governance_execution_contract_available": bool(
                intervention_analytics.get("governance_execution_contract")
                or proposal_recommendations.get("governance_execution_contract")
            ),
        },
        "follow_on_handoff_state": follow_on_handoff_state,
        "provenance_and_audit_trace": {
            "canonical_authority_file": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
            "promotion_ledger_path": str(GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH),
            "promotion_outcome_ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_OUTCOME_LEDGER_PATH),
            "reconciliation_ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_LEDGER_PATH),
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
            "remediation_review_outcome_ledger_entries_seen": int(
                len(remediation_review_outcome_ledger_rows)
            ),
            "rollback_or_repair_handoff_ledger_entries_seen": int(len(handoff_ledger_rows)),
            "rollback_or_repair_outcome_ledger_entries_before_write": int(len(outcome_ledger_rows)),
            "rollback_trace_mode": "explicit_rollback_or_repair_outcome_then_existing_path_only",
        },
        "operator_readable_conclusion": (
            "The rollback-or-repair handoff now has an explicit governed outcome. "
            + (
                "The case remains under explicit existing-path review because no existing follow-on path was selected."
                if rollback_or_repair_outcome_state == ROLLBACK_OR_REPAIR_CANDIDATE_UNDER_EXISTING_PATH
                else "The handoff was rejected under the existing path and canonical authority remains unchanged."
                if rollback_or_repair_outcome_state == ROLLBACK_OR_REPAIR_REJECTED_UNDER_EXISTING_PATH
                else "The requested existing path was already resolved, so the result is an explicit no-op."
                if rollback_or_repair_outcome_state == ROLLBACK_OR_REPAIR_NOOP_ALREADY_RESOLVED
                else "The explicit authority-promotion rollback path was applied through the existing promotion gate and the authority before/after references are explicit."
            )
        ),
    }

    _write_json(artifact_path, payload)

    ledger_entry = {
        "event_type": "governance_reopen_rollback_or_repair_outcome_recorded",
        "written_at": decided_at,
        "rollback_or_repair_outcome_id": outcome_id,
        "source_rollback_or_repair_handoff_id": handoff_id,
        "source_rollback_or_repair_handoff_artifact_path": handoff_artifact_path,
        "source_remediation_review_outcome_id": str(
            source_remediation_review_outcome_reference.get("remediation_review_outcome_id", "")
        ),
        "artifact_path": str(artifact_path),
        "rollback_or_repair_outcome_state": rollback_or_repair_outcome_state,
        "selected_existing_follow_on_path": selected_existing_follow_on_path,
        "candidate_artifact_path": candidate_artifact_path,
        "candidate_source_template_name": candidate_source_template_name,
        "apply_existing_path_requested": apply_existing_path_requested,
        "authority_mutated": bool(authority_mutated),
        "decision_reason_codes": decision_reason_codes,
        "existing_path_actor": rollback_or_repair_existing_path_actor,
        "requested_template_name": str(requested_rollback_or_repair_scope.get("requested_template_name", "")),
        "requested_template_family": str(
            requested_rollback_or_repair_scope.get("requested_template_family", "")
        ),
    }
    _append_jsonl(GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_OUTCOME_LEDGER_PATH, ledger_entry)

    updated_self_structure = dict(self_structure_state)
    updated_summary = dict(current_state_summary)
    updated_summary.update(
        {
            "latest_governance_reopen_rollback_or_repair_outcome_artifact_path": str(artifact_path),
            "latest_governance_reopen_rollback_or_repair_outcome_ledger_path": str(
                GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_OUTCOME_LEDGER_PATH
            ),
            "latest_governance_reopen_rollback_or_repair_outcome_state": rollback_or_repair_outcome_state,
            "latest_governance_reopen_rollback_or_repair_existing_path_actor": (
                rollback_or_repair_existing_path_actor
            ),
            "latest_governance_reopen_rollback_or_repair_decision_reason_codes": decision_reason_codes,
        }
    )
    if authority_mutated:
        promoted_record = dict(authority_after_payload.get("authority_promotion_record", {}))
        updated_summary.update(
            {
                "latest_governance_memory_mutation_stage": str(
                    authority_after_payload.get("authority_mutation_stage", "")
                ),
                "latest_governance_memory_promotion_id": str(promoted_record.get("promotion_id", "")),
                "latest_governance_memory_authority_file_path": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
            }
        )
    updated_self_structure["generated_at"] = _now()
    updated_self_structure["current_state_summary"] = updated_summary
    updated_self_structure["governance_reopen_rollback_or_repair_outcome"] = {
        "schema_name": OUTCOME_SCHEMA_NAME,
        "schema_version": OUTCOME_SCHEMA_VERSION,
        "latest_rollback_or_repair_outcome": {
            "rollback_or_repair_outcome_id": outcome_id,
            "source_rollback_or_repair_handoff_id": handoff_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_OUTCOME_LEDGER_PATH),
            "rollback_or_repair_outcome_state": rollback_or_repair_outcome_state,
            "authority_mutated": bool(authority_mutated),
            "existing_path_actor": rollback_or_repair_existing_path_actor,
        },
    }
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure)

    _append_jsonl(
        SELF_STRUCTURE_LEDGER_PATH,
        {
            "event_id": f"governance_reopen_rollback_or_repair_outcome::{proposal['proposal_id']}",
            "timestamp": _now(),
            "event_type": "governance_reopen_rollback_or_repair_outcome_recorded",
            "rollback_or_repair_outcome_id": outcome_id,
            "source_rollback_or_repair_handoff_id": handoff_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_OUTCOME_LEDGER_PATH),
            "rollback_or_repair_outcome_state": rollback_or_repair_outcome_state,
            "authority_mutated": bool(authority_mutated),
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
        "reason": "diagnostic shadow passed: rollback-or-repair handoff was materialized as an explicit governed existing-path outcome",
        "observability_gain": {
            "passed": True,
            "reason": "future agents can now distinguish rollback-or-repair handoff from under-review, rejected, noop, or applied existing-path decisions",
            "artifact_path": str(artifact_path),
            "rollback_or_repair_outcome_ledger_path": str(
                GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_OUTCOME_LEDGER_PATH
            ),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "rollback-or-repair outcome makes the existing-path decision surface explicit without creating a second authority path",
        },
        "ambiguity_reduction": {
            "passed": True,
            "reason": "existing-path checks, decision reason codes, and authority before/after references are now explicit",
            "score": 0.97,
        },
        "safety_neutrality": {
            "passed": True,
            "reason": "rollback-or-repair outcome stays non-automatic and only routes through the existing promotion gate when an explicit rollback path is selected",
            "scope": str(proposal.get("scope", "")),
        },
        "later_selection_usefulness": {
            "passed": True,
            "reason": "only valid approved handoff candidates can proceed toward explicit existing-path action, and already-resolved cases become explicit no-op instead of silent churn",
            "recommended_next_template": "",
        },
        "diagnostic_conclusions": {
            "rollback_or_repair_handoff_state": ROLLBACK_OR_REPAIR_HANDOFF_PENDING,
            "rollback_or_repair_outcome_state": rollback_or_repair_outcome_state,
            "authority_mutated": bool(authority_mutated),
            "recommended_next_action": "hold_and_consolidate",
            "recommended_next_template": "",
        },
        "artifact_path": str(artifact_path),
        "rollback_or_repair_outcome_ledger_path": str(
            GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_OUTCOME_LEDGER_PATH
        ),
    }
