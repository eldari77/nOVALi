from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .ledger import intervention_data_dir


GOVERNANCE_REOPEN_INTAKE_SCHEMA_NAME = "GovernanceReopenIntake"
GOVERNANCE_REOPEN_INTAKE_SCHEMA_VERSION = "governance_reopen_intake_v1"

BLOCKED_ACTION_REQUEST = "blocked_action_request"
REVIEW_PENDING_REOPEN_CANDIDATE_INTAKE = "review_pending_reopen_candidate_intake"
NOT_SCREENED_YET = "not_screened_yet"
SCREENED_REOPEN_CANDIDATE = "screened_reopen_candidate"
STILL_REJECTED_REQUEST = "still_rejected_request"
NOT_SUBMITTED_FOR_GOVERNANCE_REVIEW = "not_submitted_for_governance_review"
APPROVED_FOR_GOVERNANCE_REVIEW = "approved_for_governance_review"
SUBMITTED_FOR_GOVERNANCE_REVIEW = "submitted_for_governance_review"
REVIEW_OUTCOME_PENDING = "review_outcome_pending"
GOVERNANCE_REVIEW_REJECTED = "governance_review_rejected"
GOVERNANCE_REVIEW_APPROVED_FOR_PROMOTION_PATH = "governance_review_approved_for_promotion_path"
PROMOTION_PENDING_UNDER_EXISTING_GATE = "promotion_pending_under_existing_gate"
PROMOTION_CANDIDATE_UNDER_REVIEW = "promotion_candidate_under_review"
PROMOTION_REJECTED_UNDER_EXISTING_GATE = "promotion_rejected_under_existing_gate"
PROMOTION_APPLIED_AS_BINDING_AUTHORITY = "promotion_applied_as_binding_authority"
PROMOTION_NOOP_ALREADY_AUTHORITATIVE = "promotion_noop_already_authoritative"
PROMOTED_AUTHORITY_UPDATE = "promoted_authority_update"


DATA_DIR = intervention_data_dir()
DIAGNOSTIC_MEMORY_DIR = DATA_DIR / "diagnostic_memory"
GOVERNANCE_MEMORY_AUTHORITY_PATH = DATA_DIR / "governance_memory_authority_latest.json"
GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH = DATA_DIR / "governance_memory_promotion_ledger.jsonl"
GOVERNANCE_REOPEN_INTAKE_LEDGER_PATH = DATA_DIR / "governance_reopen_intake_ledger.jsonl"
SELF_STRUCTURE_STATE_PATH = DATA_DIR / "self_structure_state_latest.json"
SELF_STRUCTURE_LEDGER_PATH = DATA_DIR / "self_structure_ledger.jsonl"
BRANCH_REGISTRY_PATH = DATA_DIR / "branch_registry_latest.json"
DIRECTIVE_STATE_PATH = DATA_DIR / "directive_state_latest.json"
BUCKET_STATE_PATH = DATA_DIR / "bucket_state_latest.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}


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


def _template_family(template_name: str) -> str:
    if "." in str(template_name):
        return str(template_name).split(".", 1)[0]
    return str(template_name)


def _request_classification(*, action_kind: str, template_name: str, proposal_type: str) -> str:
    action = str(action_kind)
    template = str(template_name)
    proposal = str(proposal_type)
    if action in {"proposal_analytics", "proposal_recommend"}:
        return "observational_only_request"
    if action in {"training_loop", "compare_live_ab"}:
        return "branch_runtime_reopen_request"
    if "governed_work_loop" in template:
        return "governed_work_loop_reentry_request"
    if "capability_use" in template or "capability_use" in proposal:
        return "capability_use_request"
    if "governed_skill" in template or "skill_" in template:
        return "capability_acquisition_request"
    return "branch_reopen_request"


def _capability_boundary_relation(request_classification: str) -> dict[str, Any]:
    request_class = str(request_classification)
    return {
        "request_classification": request_class,
        "capability_use_request": request_class == "capability_use_request",
        "capability_acquisition_request": request_class == "capability_acquisition_request",
        "governed_work_loop_reentry_request": request_class == "governed_work_loop_reentry_request",
        "branch_reopen_request": request_class in {
            "branch_reopen_request",
            "branch_runtime_reopen_request",
            "governed_work_loop_reentry_request",
        },
    }


def emit_governance_reopen_intake(
    *,
    permission: dict[str, Any],
    requested_by_surface: str,
) -> dict[str, Any]:
    authority_payload = _load_json_file(GOVERNANCE_MEMORY_AUTHORITY_PATH)
    self_structure_state = _load_json_file(SELF_STRUCTURE_STATE_PATH)
    branch_registry = _load_json_file(BRANCH_REGISTRY_PATH)
    directive_state = _load_json_file(DIRECTIVE_STATE_PATH)
    bucket_state = _load_json_file(BUCKET_STATE_PATH)

    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    template_context = dict(permission.get("template_context", {}))
    canonical_posture = dict(permission.get("canonical_posture", {}))
    selector_frontier_conclusions = dict(permission.get("selector_frontier_conclusions", {}))
    binding_decisions = dict(permission.get("binding_decisions", {}))

    action_kind = str(permission.get("action_kind", ""))
    template_name = str(template_context.get("template_name", ""))
    proposal_type = str(template_context.get("proposal_type", ""))
    request_classification = _request_classification(
        action_kind=action_kind,
        template_name=template_name,
        proposal_type=proposal_type,
    )
    capability_boundary_relation = _capability_boundary_relation(request_classification)

    intake_id = f"reopen_intake::{uuid4()}"
    emitted_at = _now()
    artifact_path = _diagnostic_artifact_dir() / (
        f"governance_reopen_intake_v1_{intake_id.split('::', 1)[1]}.json"
    )

    contract = {
        "schema_name": GOVERNANCE_REOPEN_INTAKE_SCHEMA_NAME,
        "schema_version": GOVERNANCE_REOPEN_INTAKE_SCHEMA_VERSION,
        "blocked_action_request_states": [BLOCKED_ACTION_REQUEST],
        "reopen_candidate_intake_states": [REVIEW_PENDING_REOPEN_CANDIDATE_INTAKE],
        "reopen_screening_states": [
            NOT_SCREENED_YET,
            SCREENED_REOPEN_CANDIDATE,
            STILL_REJECTED_REQUEST,
        ],
        "governance_review_states": [
            NOT_SUBMITTED_FOR_GOVERNANCE_REVIEW,
            APPROVED_FOR_GOVERNANCE_REVIEW,
            SUBMITTED_FOR_GOVERNANCE_REVIEW,
            REVIEW_OUTCOME_PENDING,
            GOVERNANCE_REVIEW_REJECTED,
            GOVERNANCE_REVIEW_APPROVED_FOR_PROMOTION_PATH,
        ],
        "promotion_handoff_states": [
            PROMOTION_PENDING_UNDER_EXISTING_GATE,
            PROMOTION_CANDIDATE_UNDER_REVIEW,
            PROMOTED_AUTHORITY_UPDATE,
        ],
        "promotion_outcome_states": [
            PROMOTION_REJECTED_UNDER_EXISTING_GATE,
            PROMOTION_APPLIED_AS_BINDING_AUTHORITY,
            PROMOTION_NOOP_ALREADY_AUTHORITATIVE,
        ],
        "authority_relation": "non_authoritative_until_explicit_governance_review_and_promotion",
        "promotion_bypass_disallowed": True,
    }

    authority_promotion_record = dict(authority_payload.get("authority_promotion_record", {}))
    authority_candidate_record = dict(authority_payload.get("authority_candidate_record", {}))
    authority_mutation_stage = str(authority_payload.get("authority_mutation_stage", ""))

    blocked_action_request = {
        "request_state": BLOCKED_ACTION_REQUEST,
        "action_kind": action_kind,
        "permission_state": str(permission.get("permission_state", "")),
        "reason": str(permission.get("reason", "")),
        "conflict_tags": [str(item) for item in list(permission.get("conflict_tags", []))],
        "requested_template_name": template_name,
        "requested_template_family": _template_family(template_name),
        "requested_proposal_type": proposal_type,
        "requested_evaluation_semantics": str(template_context.get("evaluation_semantics", "")),
        "requested_scope": str(template_context.get("scope", "")),
        "requested_by_surface": str(requested_by_surface),
        "resolution_error": permission.get("resolution_error"),
    }

    reopen_candidate_intake = {
        "intake_state": REVIEW_PENDING_REOPEN_CANDIDATE_INTAKE,
        "screening_state": NOT_SCREENED_YET,
        "governance_review_state": NOT_SUBMITTED_FOR_GOVERNANCE_REVIEW,
        "request_classification": request_classification,
        "capability_boundary_relation": capability_boundary_relation,
        "reopen_supported_now": False,
        "authority_mutation_allowed": False,
    }

    authority_evidence_references = {
        "canonical_authority_file": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
        "promotion_ledger_path": str(GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH),
        "self_structure_state_path": str(SELF_STRUCTURE_STATE_PATH),
        "self_structure_ledger_path": str(SELF_STRUCTURE_LEDGER_PATH),
        "branch_registry_path": str(BRANCH_REGISTRY_PATH),
        "directive_state_path": str(DIRECTIVE_STATE_PATH),
        "bucket_state_path": str(BUCKET_STATE_PATH),
        "latest_authority_artifact_path": str(
            current_state_summary.get("latest_governance_memory_authority_artifact_path", "")
        ),
        "latest_authority_promotion_id": str(
            current_state_summary.get("latest_governance_memory_promotion_id", "")
        ),
    }

    artifact_payload = {
        "schema_name": GOVERNANCE_REOPEN_INTAKE_SCHEMA_NAME,
        "schema_version": GOVERNANCE_REOPEN_INTAKE_SCHEMA_VERSION,
        "intake_id": intake_id,
        "emitted_at": emitted_at,
        "intake_contract": contract,
        "blocked_action_request": blocked_action_request,
        "reopen_candidate_intake": reopen_candidate_intake,
        "canonical_authority_snapshot": {
            "current_operating_stance": str(canonical_posture.get("current_operating_stance", "")),
            "current_branch_state": str(canonical_posture.get("current_branch_state", "")),
            "held_baseline_template": str(canonical_posture.get("held_baseline_template", "")),
            "routing_status": str(canonical_posture.get("routing_status", "")),
            "reopen_eligibility": dict(canonical_posture.get("reopen_eligibility", {})),
            "authority_mutation_stage": authority_mutation_stage,
            "authority_candidate_record": authority_candidate_record,
            "authority_promotion_record": authority_promotion_record,
        },
        "selector_frontier_snapshot": selector_frontier_conclusions,
        "binding_decisions_snapshot": binding_decisions,
        "evidence_references": authority_evidence_references,
        "supporting_context": {
            "directive_id": str(dict(directive_state.get("current_directive_state", {})).get("directive_id", "")),
            "bucket_id": str(dict(bucket_state.get("current_bucket_state", {})).get("bucket_id", "")),
            "branch_id": str(branch_registry.get("current_branch_id", "")),
            "latest_current_operating_stance": str(
                current_state_summary.get("latest_current_operating_stance", "")
            ),
            "latest_branch_reopen_eligibility": str(
                current_state_summary.get("latest_branch_reopen_eligibility", "")
            ),
            "latest_selector_frontier_split_assessment": str(
                current_state_summary.get("latest_selector_frontier_split_assessment", "")
            ),
        },
        "review_provenance": {
            "emitted_by_surface": "governance_memory_execution_gate_v1",
            "requested_by_surface": str(requested_by_surface),
            "reviewer_source": "governed_runtime_preflight",
            "current_screening_state": NOT_SCREENED_YET,
        },
        "operator_readable_conclusion": (
            "Execution remained blocked under canonical authority, but the request has been captured as a non-authoritative reopen-intake artifact for governed review rather than disappearing as an untracked failure."
        ),
    }

    _write_json(artifact_path, artifact_payload)

    ledger_entry = {
        "intake_id": intake_id,
        "written_at": emitted_at,
        "event_type": "governance_reopen_intake_emitted",
        "artifact_path": str(artifact_path),
        "action_kind": action_kind,
        "requested_template_name": template_name,
        "requested_template_family": _template_family(template_name),
        "request_classification": request_classification,
        "blocked_action_request_state": BLOCKED_ACTION_REQUEST,
        "reopen_candidate_intake_state": REVIEW_PENDING_REOPEN_CANDIDATE_INTAKE,
        "reopen_screening_state": NOT_SCREENED_YET,
        "governance_review_state": NOT_SUBMITTED_FOR_GOVERNANCE_REVIEW,
        "blocking_reason": str(permission.get("reason", "")),
        "authority_file": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
        "promotion_bypass_disallowed": True,
    }
    _append_jsonl(GOVERNANCE_REOPEN_INTAKE_LEDGER_PATH, ledger_entry)

    updated_self_structure = dict(self_structure_state)
    updated_summary = dict(current_state_summary)
    updated_summary.update(
        {
            "latest_governance_reopen_intake_id": intake_id,
            "latest_governance_reopen_intake_artifact_path": str(artifact_path),
            "latest_governance_reopen_intake_ledger_path": str(GOVERNANCE_REOPEN_INTAKE_LEDGER_PATH),
            "latest_governance_reopen_request_action_kind": action_kind,
            "latest_governance_reopen_request_template_name": template_name,
            "latest_governance_reopen_request_family": _template_family(template_name),
            "latest_governance_reopen_request_classification": request_classification,
            "latest_governance_reopen_blocking_reason": str(permission.get("reason", "")),
            "latest_governance_reopen_intake_state": REVIEW_PENDING_REOPEN_CANDIDATE_INTAKE,
            "latest_governance_reopen_screening_state": NOT_SCREENED_YET,
            "latest_governance_reopen_review_state": NOT_SUBMITTED_FOR_GOVERNANCE_REVIEW,
        }
    )
    updated_self_structure["generated_at"] = _now()
    updated_self_structure["current_state_summary"] = updated_summary
    updated_self_structure["governance_reopen_intake"] = {
        "schema_name": GOVERNANCE_REOPEN_INTAKE_SCHEMA_NAME,
        "schema_version": GOVERNANCE_REOPEN_INTAKE_SCHEMA_VERSION,
        "latest_intake": {
            "intake_id": intake_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_INTAKE_LEDGER_PATH),
            "request_classification": request_classification,
            "blocked_action_request_state": BLOCKED_ACTION_REQUEST,
            "reopen_candidate_intake_state": REVIEW_PENDING_REOPEN_CANDIDATE_INTAKE,
            "reopen_screening_state": NOT_SCREENED_YET,
            "governance_review_state": NOT_SUBMITTED_FOR_GOVERNANCE_REVIEW,
        },
    }
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure)

    _append_jsonl(
        SELF_STRUCTURE_LEDGER_PATH,
        {
            "event_id": f"governance_reopen_intake::{intake_id}",
            "timestamp": _now(),
            "event_type": "governance_reopen_intake_emitted",
            "intake_id": intake_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_INTAKE_LEDGER_PATH),
            "action_kind": action_kind,
            "template_name": template_name,
            "request_classification": request_classification,
            "intake_state": REVIEW_PENDING_REOPEN_CANDIDATE_INTAKE,
            "screening_state": NOT_SCREENED_YET,
            "governance_review_state": NOT_SUBMITTED_FOR_GOVERNANCE_REVIEW,
            "blocked_reason": str(permission.get("reason", "")),
        },
    )

    return {
        "intake_id": intake_id,
        "artifact_path": str(artifact_path),
        "ledger_path": str(GOVERNANCE_REOPEN_INTAKE_LEDGER_PATH),
        "request_classification": request_classification,
        "intake_state": REVIEW_PENDING_REOPEN_CANDIDATE_INTAKE,
        "screening_state": NOT_SCREENED_YET,
        "governance_review_state": NOT_SUBMITTED_FOR_GOVERNANCE_REVIEW,
    }
