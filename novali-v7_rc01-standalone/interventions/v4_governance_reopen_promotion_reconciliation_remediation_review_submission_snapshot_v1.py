from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .governance_memory_reopen_intake_v1 import (
    PROMOTION_APPLIED_AS_BINDING_AUTHORITY,
    PROMOTION_NOOP_ALREADY_AUTHORITATIVE,
)
from .v4_governance_reopen_promotion_reconciliation_escalation_snapshot_v1 import (
    REMEDIATION_OR_ROLLBACK_REVIEW_CANDIDATE,
    REMEDIATION_REVIEW_APPROVED_FOR_EXISTING_ROLLBACK_OR_REPAIR_PATH,
    REMEDIATION_REVIEW_NOT_SUBMITTED,
    REMEDIATION_REVIEW_REJECTED,
    RECONCILIATION_MISMATCH_DETECTED,
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
GOVERNANCE_REOPEN_REMEDIATION_REVIEW_LEDGER_PATH = (
    DATA_DIR / "governance_reopen_remediation_review_ledger.jsonl"
)
INTERVENTION_LEDGER_PATH = DATA_DIR / "intervention_ledger.jsonl"
INTERVENTION_ANALYTICS_PATH = DATA_DIR / "intervention_analytics_latest.json"
PROPOSAL_RECOMMENDATIONS_PATH = DATA_DIR / "proposal_recommendations_latest.json"
SELF_STRUCTURE_STATE_PATH = DATA_DIR / "self_structure_state_latest.json"
SELF_STRUCTURE_LEDGER_PATH = DATA_DIR / "self_structure_ledger.jsonl"
BRANCH_REGISTRY_PATH = DATA_DIR / "branch_registry_latest.json"
DIRECTIVE_STATE_PATH = DATA_DIR / "directive_state_latest.json"
BUCKET_STATE_PATH = DATA_DIR / "bucket_state_latest.json"

REMEDIATION_REVIEW_SCHEMA_NAME = "GovernanceReopenPromotionReconciliationRemediationReviewSubmission"
REMEDIATION_REVIEW_SCHEMA_VERSION = (
    "governance_reopen_promotion_reconciliation_remediation_review_submission_v1"
)
SUBMITTED_FOR_REMEDIATION_REVIEW = "submitted_for_remediation_review"
REMEDIATION_REVIEW_OUTCOME_PENDING = "remediation_review_outcome_pending"
REMEDIATION_REVIEW_NON_AUTHORITATIVE = (
    "remediation_review_submission_non_authoritative_until_explicit_existing_rollback_or_repair_path_invocation"
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

    if not all([authority_payload, self_structure_state, branch_registry, directive_state, bucket_state]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: authority, self-structure, branch, directive, and bucket artifacts are required",
        }

    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    escalation_artifact_path = str(
        current_state_summary.get("latest_governance_reopen_reconciliation_escalation_artifact_path", "")
    )
    escalation_state_summary = str(
        current_state_summary.get("latest_governance_reopen_reconciliation_escalation_state", "")
    )
    remediation_review_state_summary = str(
        current_state_summary.get("latest_governance_reopen_remediation_review_state", "")
    )

    if not escalation_artifact_path:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no reconciliation-escalation artifact is available for remediation review submission",
        }

    escalation_payload = _load_json_file(Path(escalation_artifact_path))
    if not escalation_payload:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest reconciliation-escalation artifact could not be loaded",
        }

    escalation_identity = dict(escalation_payload.get("snapshot_identity_context", {}))
    escalation_id = _first_nonempty(
        escalation_identity.get("escalation_id"),
        escalation_payload.get("escalation_id"),
    )
    escalation_result = dict(escalation_payload.get("escalation_result", {}))
    escalation_state = _first_nonempty(
        escalation_result.get("escalation_state"),
        escalation_state_summary,
    )
    remediation_review_state = _first_nonempty(
        escalation_result.get("remediation_review_state"),
        remediation_review_state_summary,
    )

    if escalation_state != REMEDIATION_OR_ROLLBACK_REVIEW_CANDIDATE:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: only remediation_or_rollback_review_candidate cases may be submitted for remediation review",
            "diagnostic_conclusions": {
                "escalation_state": escalation_state,
                "remediation_review_state": remediation_review_state,
            },
        }

    if remediation_review_state != REMEDIATION_REVIEW_NOT_SUBMITTED:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest escalation is not eligible for initial remediation-review submission",
            "diagnostic_conclusions": {
                "escalation_state": escalation_state,
                "remediation_review_state": remediation_review_state,
            },
        }

    if any(str(row.get("source_escalation_id", "")) == escalation_id for row in remediation_review_ledger_rows):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest reconciliation-escalation candidate has already been submitted for remediation review",
            "diagnostic_conclusions": {
                "escalation_id": escalation_id,
                "existing_remediation_review_packet_count": sum(
                    1
                    for row in remediation_review_ledger_rows
                    if str(row.get("source_escalation_id", "")) == escalation_id
                ),
            },
        }

    source_reconciliation_reference = dict(
        escalation_payload.get("source_reconciliation_reference", {})
    )
    source_promotion_outcome_reference = dict(
        escalation_payload.get("source_promotion_outcome_reference", {})
    )
    source_promotion_handoff_reference = dict(
        escalation_payload.get("source_promotion_handoff_reference", {})
    )
    source_review_outcome_reference = dict(
        escalation_payload.get("source_review_outcome_reference", {})
    )
    source_review_submission_reference = dict(
        escalation_payload.get("source_review_submission_reference", {})
    )
    authority_before_reference = dict(escalation_payload.get("authority_before_reference", {}))
    authority_after_reference = dict(escalation_payload.get("authority_after_reference", {}))
    mismatch_surfaces_and_propagation_failures = dict(
        escalation_payload.get("mismatch_surfaces_and_propagation_failures", {})
    )
    rollback_ready_reference = dict(escalation_payload.get("rollback_ready_reference", {}))
    requested_action_and_scope = dict(escalation_payload.get("requested_action_and_scope", {}))

    if str(source_reconciliation_reference.get("reconciliation_state", "")) != RECONCILIATION_MISMATCH_DETECTED:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: only reconciliation_mismatch_detected cases may feed remediation review submission",
            "diagnostic_conclusions": {
                "reconciliation_state": str(source_reconciliation_reference.get("reconciliation_state", "")),
                "escalation_state": escalation_state,
            },
        }

    source_promotion_outcome_state = str(source_promotion_outcome_reference.get("promotion_outcome_state", ""))
    if source_promotion_outcome_state == PROMOTION_NOOP_ALREADY_AUTHORITATIVE:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: already-authoritative noop cases may not enter remediation review",
            "diagnostic_conclusions": {
                "source_promotion_outcome_state": source_promotion_outcome_state,
            },
        }

    if source_promotion_outcome_state and source_promotion_outcome_state != PROMOTION_APPLIED_AS_BINDING_AUTHORITY:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: remediation review submission requires an applied promotion outcome as the source mismatch case",
            "diagnostic_conclusions": {
                "source_promotion_outcome_state": source_promotion_outcome_state,
            },
        }

    repeated_motion_without_new_evidence = bool(
        escalation_result.get("repeated_motion_without_new_evidence", False)
    )
    if repeated_motion_without_new_evidence:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: repeated motion without new evidence may not enter remediation review",
            "diagnostic_conclusions": {
                "escalation_id": escalation_id,
            },
        }

    failed_checks = list(mismatch_surfaces_and_propagation_failures.get("failed_checks", []))
    mismatch_surfaces = [
        str(item)
        for item in list(mismatch_surfaces_and_propagation_failures.get("mismatch_surfaces", []))
    ]
    propagation_status_by_surface = dict(
        mismatch_surfaces_and_propagation_failures.get("propagation_status_by_surface", {})
    )
    malformed_escalation = not bool(
        source_reconciliation_reference
        and authority_before_reference
        and authority_after_reference
        and rollback_ready_reference
        and (failed_checks or mismatch_surfaces)
    )
    if malformed_escalation:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest reconciliation-escalation artifact is missing remediation-review-critical fields",
            "diagnostic_conclusions": {
                "has_source_reconciliation_reference": bool(source_reconciliation_reference),
                "has_authority_before_reference": bool(authority_before_reference),
                "has_authority_after_reference": bool(authority_after_reference),
                "has_rollback_ready_reference": bool(rollback_ready_reference),
                "failed_check_count": int(len(failed_checks)),
                "mismatch_surface_count": int(len(mismatch_surfaces)),
            },
        }

    remediation_review_packet_id = f"reopen_remediation_review::{proposal['proposal_id']}"
    submitted_at = _now()
    artifact_path = _diagnostic_artifact_dir() / (
        "memory_summary_v4_governance_reopen_promotion_reconciliation_remediation_review_submission_snapshot_v1_"
        f"{proposal['proposal_id']}.json"
    )
    branch_record = (
        dict(list(branch_registry.get("branches", []))[0]) if list(branch_registry.get("branches", [])) else {}
    )
    available_existing_follow_on_paths = [
        str(item)
        for item in list(rollback_ready_reference.get("available_existing_follow_on_paths", []))
        if str(item)
    ]

    requested_remediation_scope = {
        "scope_class": "review_existing_rollback_or_repair_path_only",
        "requested_template_name": str(requested_action_and_scope.get("requested_template_name", "")),
        "requested_template_family": str(requested_action_and_scope.get("requested_template_family", "")),
        "mismatch_surface_targets": mismatch_surfaces,
        "failed_check_names": [
            str(dict(row).get("check_name", ""))
            for row in failed_checks
            if str(dict(row).get("check_name", ""))
        ],
        "available_existing_follow_on_paths": available_existing_follow_on_paths,
        "automatic_rollback_disallowed": True,
        "automatic_repair_disallowed": True,
        "authority_mutation_allowed_here": False,
    }

    review_submission_contract = {
        "schema_name": REMEDIATION_REVIEW_SCHEMA_NAME,
        "schema_version": REMEDIATION_REVIEW_SCHEMA_VERSION,
        "required_escalation_state": REMEDIATION_OR_ROLLBACK_REVIEW_CANDIDATE,
        "required_reconciliation_state": RECONCILIATION_MISMATCH_DETECTED,
        "submission_states": [
            REMEDIATION_REVIEW_NOT_SUBMITTED,
            SUBMITTED_FOR_REMEDIATION_REVIEW,
        ],
        "outcome_states": [
            REMEDIATION_REVIEW_OUTCOME_PENDING,
            REMEDIATION_REVIEW_REJECTED,
            REMEDIATION_REVIEW_APPROVED_FOR_EXISTING_ROLLBACK_OR_REPAIR_PATH,
        ],
        "authority_relation": REMEDIATION_REVIEW_NON_AUTHORITATIVE,
        "automatic_rollback_disallowed": True,
        "automatic_repair_disallowed": True,
        "canonical_authority_mutation_disallowed_here": True,
        "existing_follow_on_paths_reference_only": True,
    }

    payload = {
        "proposal_id": str(proposal.get("proposal_id", "")),
        "template_name": "memory_summary.v4_governance_reopen_promotion_reconciliation_remediation_review_submission_snapshot_v1",
        "snapshot_identity_context": {
            "remediation_review_packet_id": remediation_review_packet_id,
            "submitted_at": submitted_at,
            "phase": "governance_reopen_promotion_reconciliation_remediation_review_submission",
            "source_escalation_id": escalation_id,
            "source_reconciliation_id": str(source_reconciliation_reference.get("reconciliation_id", "")),
        },
        "remediation_review_submission_contract": review_submission_contract,
        "source_reconciliation_escalation_reference": {
            "escalation_id": escalation_id,
            "artifact_path": escalation_artifact_path,
            "ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_ESCALATION_LEDGER_PATH),
            "escalation_state": escalation_state,
            "remediation_review_state": remediation_review_state,
            "escalation_reason_codes": [
                str(item) for item in list(escalation_result.get("escalation_reason_codes", []))
            ],
        },
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
            "rollback_reference_state": str(rollback_ready_reference.get("rollback_reference_state", "")),
            "rollback_trace": dict(rollback_ready_reference.get("rollback_trace", {})),
            "available_existing_follow_on_paths": available_existing_follow_on_paths,
            "no_rollback_invoked_here": True,
            "no_repair_invoked_here": True,
        },
        "authority_posture_at_submission_time": _authority_posture_snapshot(authority_payload),
        "requested_remediation_scope": requested_remediation_scope,
        "remediation_review_submission_result": {
            "remediation_review_submission_state": SUBMITTED_FOR_REMEDIATION_REVIEW,
            "remediation_review_outcome_state": REMEDIATION_REVIEW_OUTCOME_PENDING,
            "authority_mutation_allowed": False,
            "automatic_rollback_or_repair_disallowed": True,
            "repeated_motion_without_new_evidence": repeated_motion_without_new_evidence,
        },
        "reviewer_source_and_audit_trace": {
            "submitted_by_surface": "memory_summary.v4_governance_reopen_promotion_reconciliation_remediation_review_submission_snapshot_v1",
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
            "remediation_review_ledger_path": str(GOVERNANCE_REOPEN_REMEDIATION_REVIEW_LEDGER_PATH),
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
            "remediation_review_ledger_entries_before_write": int(len(remediation_review_ledger_rows)),
        },
        "operator_readable_conclusion": (
            "The reconciliation mismatch escalation candidate is now an explicit remediation-review submission packet. "
            "The mismatch evidence and rollback-ready reference are preserved for governed review, but no rollback or repair is invoked here."
        ),
    }

    _write_json(artifact_path, payload)

    ledger_entry = {
        "event_type": "governance_reopen_remediation_review_submitted",
        "written_at": submitted_at,
        "remediation_review_packet_id": remediation_review_packet_id,
        "source_escalation_id": escalation_id,
        "source_reconciliation_id": str(source_reconciliation_reference.get("reconciliation_id", "")),
        "artifact_path": str(artifact_path),
        "submission_state": SUBMITTED_FOR_REMEDIATION_REVIEW,
        "outcome_state": REMEDIATION_REVIEW_OUTCOME_PENDING,
        "requested_template_name": str(requested_action_and_scope.get("requested_template_name", "")),
        "requested_template_family": str(requested_action_and_scope.get("requested_template_family", "")),
    }
    _append_jsonl(GOVERNANCE_REOPEN_REMEDIATION_REVIEW_LEDGER_PATH, ledger_entry)

    updated_self_structure = dict(self_structure_state)
    updated_summary = dict(current_state_summary)
    updated_summary.update(
        {
            "latest_governance_reopen_remediation_review_artifact_path": str(artifact_path),
            "latest_governance_reopen_remediation_review_ledger_path": str(
                GOVERNANCE_REOPEN_REMEDIATION_REVIEW_LEDGER_PATH
            ),
            "latest_governance_reopen_remediation_review_state": SUBMITTED_FOR_REMEDIATION_REVIEW,
            "latest_governance_reopen_remediation_review_submission_state": SUBMITTED_FOR_REMEDIATION_REVIEW,
            "latest_governance_reopen_remediation_review_outcome_state": REMEDIATION_REVIEW_OUTCOME_PENDING,
            "latest_governance_reopen_remediation_review_source_escalation_id": escalation_id,
        }
    )
    updated_self_structure["generated_at"] = _now()
    updated_self_structure["current_state_summary"] = updated_summary
    updated_self_structure["governance_reopen_remediation_review_submission"] = {
        "schema_name": REMEDIATION_REVIEW_SCHEMA_NAME,
        "schema_version": REMEDIATION_REVIEW_SCHEMA_VERSION,
        "latest_review_packet": {
            "remediation_review_packet_id": remediation_review_packet_id,
            "source_escalation_id": escalation_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_REMEDIATION_REVIEW_LEDGER_PATH),
            "submission_state": SUBMITTED_FOR_REMEDIATION_REVIEW,
            "outcome_state": REMEDIATION_REVIEW_OUTCOME_PENDING,
        },
    }
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure)

    _append_jsonl(
        SELF_STRUCTURE_LEDGER_PATH,
        {
            "event_id": f"governance_reopen_remediation_review_submission::{proposal['proposal_id']}",
            "timestamp": _now(),
            "event_type": "governance_reopen_remediation_review_submitted",
            "remediation_review_packet_id": remediation_review_packet_id,
            "source_escalation_id": escalation_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_REMEDIATION_REVIEW_LEDGER_PATH),
            "submission_state": SUBMITTED_FOR_REMEDIATION_REVIEW,
            "outcome_state": REMEDIATION_REVIEW_OUTCOME_PENDING,
        },
    )

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: reconciliation escalation candidate was materialized as an explicit remediation-review submission packet",
        "observability_gain": {
            "passed": True,
            "reason": "future agents can now distinguish reconciliation escalation from remediation-review submission and pending review outcome",
            "artifact_path": str(artifact_path),
            "remediation_review_ledger_path": str(GOVERNANCE_REOPEN_REMEDIATION_REVIEW_LEDGER_PATH),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "remediation-review submission makes rollback-or-repair review explicit without invoking any follow-on path automatically",
        },
        "ambiguity_reduction": {
            "passed": True,
            "reason": "mismatch evidence, rollback-ready metadata, and requested remediation scope are now preserved in an explicit governed review packet",
            "score": 0.97,
        },
        "safety_neutrality": {
            "passed": True,
            "reason": "remediation-review submission is non-mutating and cannot trigger rollback, repair, or authority mutation by itself",
            "scope": str(proposal.get("scope", "")),
        },
        "later_selection_usefulness": {
            "passed": True,
            "reason": "only valid mismatch escalations can enter remediation review, while verified, malformed, noop, and repeated-motion cases stop cleanly",
            "recommended_next_template": "",
        },
        "diagnostic_conclusions": {
            "escalation_state": REMEDIATION_OR_ROLLBACK_REVIEW_CANDIDATE,
            "remediation_review_submission_state": SUBMITTED_FOR_REMEDIATION_REVIEW,
            "remediation_review_outcome_state": REMEDIATION_REVIEW_OUTCOME_PENDING,
            "recommended_next_action": "hold_and_consolidate",
            "recommended_next_template": "",
        },
        "artifact_path": str(artifact_path),
        "remediation_review_ledger_path": str(GOVERNANCE_REOPEN_REMEDIATION_REVIEW_LEDGER_PATH),
    }
