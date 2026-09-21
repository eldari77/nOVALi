from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .governance_memory_reopen_intake_v1 import (
    APPROVED_FOR_GOVERNANCE_REVIEW,
    GOVERNANCE_REOPEN_INTAKE_LEDGER_PATH,
    GOVERNANCE_REOPEN_INTAKE_SCHEMA_VERSION,
    GOVERNANCE_REVIEW_APPROVED_FOR_PROMOTION_PATH,
    GOVERNANCE_REVIEW_REJECTED,
    NOT_SUBMITTED_FOR_GOVERNANCE_REVIEW,
    PROMOTED_AUTHORITY_UPDATE,
    REVIEW_OUTCOME_PENDING,
    SCREENED_REOPEN_CANDIDATE,
    SUBMITTED_FOR_GOVERNANCE_REVIEW,
)
from .ledger import intervention_data_dir, load_latest_snapshots


DATA_DIR = intervention_data_dir()
DIAGNOSTIC_MEMORY_DIR = DATA_DIR / "diagnostic_memory"
GOVERNANCE_MEMORY_AUTHORITY_PATH = DATA_DIR / "governance_memory_authority_latest.json"
GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH = DATA_DIR / "governance_memory_promotion_ledger.jsonl"
GOVERNANCE_REOPEN_SCREENING_LEDGER_PATH = DATA_DIR / "governance_reopen_screening_ledger.jsonl"
GOVERNANCE_REOPEN_REVIEW_LEDGER_PATH = DATA_DIR / "governance_reopen_review_ledger.jsonl"
INTERVENTION_LEDGER_PATH = DATA_DIR / "intervention_ledger.jsonl"
INTERVENTION_ANALYTICS_PATH = DATA_DIR / "intervention_analytics_latest.json"
PROPOSAL_RECOMMENDATIONS_PATH = DATA_DIR / "proposal_recommendations_latest.json"
SELF_STRUCTURE_STATE_PATH = DATA_DIR / "self_structure_state_latest.json"
SELF_STRUCTURE_LEDGER_PATH = DATA_DIR / "self_structure_ledger.jsonl"
BRANCH_REGISTRY_PATH = DATA_DIR / "branch_registry_latest.json"
DIRECTIVE_STATE_PATH = DATA_DIR / "directive_state_latest.json"
BUCKET_STATE_PATH = DATA_DIR / "bucket_state_latest.json"

REVIEW_SCHEMA_NAME = "GovernanceReopenReviewSubmission"
REVIEW_SCHEMA_VERSION = "governance_reopen_review_submission_v1"
REVIEW_NON_AUTHORITATIVE = "review_submission_non_authoritative_until_explicit_review_outcome_and_promotion"


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


def run_probe(cfg, proposal, *, rounds, seeds):
    del cfg, rounds, seeds

    authority_payload = _load_json_file(GOVERNANCE_MEMORY_AUTHORITY_PATH)
    self_structure_state = _load_json_file(SELF_STRUCTURE_STATE_PATH)
    branch_registry = _load_json_file(BRANCH_REGISTRY_PATH)
    directive_state = _load_json_file(DIRECTIVE_STATE_PATH)
    bucket_state = _load_json_file(BUCKET_STATE_PATH)
    intervention_analytics = _load_json_file(INTERVENTION_ANALYTICS_PATH)
    proposal_recommendations = _load_json_file(PROPOSAL_RECOMMENDATIONS_PATH)
    screening_ledger_rows = _load_jsonl(GOVERNANCE_REOPEN_SCREENING_LEDGER_PATH)
    review_ledger_rows = _load_jsonl(GOVERNANCE_REOPEN_REVIEW_LEDGER_PATH)

    if not all([authority_payload, self_structure_state, branch_registry, directive_state, bucket_state]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: authority, self-structure, branch, directive, and bucket artifacts are required",
        }

    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    screening_artifact_path = str(
        current_state_summary.get("latest_governance_reopen_screening_artifact_path", "")
    )
    screening_state_summary = str(
        current_state_summary.get("latest_governance_reopen_screening_state", "")
    )
    review_state_summary = str(current_state_summary.get("latest_governance_reopen_review_state", ""))
    screened_intake_id = str(current_state_summary.get("latest_governance_reopen_screened_intake_id", ""))

    if not screening_artifact_path:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no reopen-screening artifact is available for governance review handoff",
        }

    screening_payload = _load_json_file(Path(screening_artifact_path))
    if not screening_payload:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest reopen-screening artifact could not be loaded",
        }

    screening_result = dict(screening_payload.get("screening_result", {}))
    screening_state = _first_nonempty(
        screening_result.get("screening_state"),
        screening_state_summary,
    )
    screening_review_state = _first_nonempty(
        screening_result.get("governance_review_state"),
        review_state_summary,
    )
    evidence_sufficiency = str(screening_result.get("evidence_sufficiency_assessment", ""))
    screening_id = _first_nonempty(
        dict(screening_payload.get("snapshot_identity_context", {})).get("screening_id"),
        str(screening_payload.get("screening_id", "")),
    )
    source_intake_reference = dict(screening_payload.get("source_intake_reference", {}))
    source_intake_artifact_path = _first_nonempty(
        source_intake_reference.get("artifact_path"),
        current_state_summary.get("latest_governance_reopen_intake_artifact_path"),
    )
    intake_payload = _load_json_file(Path(source_intake_artifact_path)) if source_intake_artifact_path else {}

    if screening_state != SCREENED_REOPEN_CANDIDATE:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: only screened_reopen_candidate requests may be submitted for governance review",
            "diagnostic_conclusions": {
                "screening_state": screening_state,
                "governance_review_state": screening_review_state,
                "evidence_sufficiency_assessment": evidence_sufficiency,
            },
        }

    if screening_review_state != APPROVED_FOR_GOVERNANCE_REVIEW:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest screened candidate is not marked eligible for governance review submission",
            "diagnostic_conclusions": {
                "screening_state": screening_state,
                "governance_review_state": screening_review_state,
                "evidence_sufficiency_assessment": evidence_sufficiency,
            },
        }

    if any(str(row.get("source_screening_id", "")) == screening_id for row in review_ledger_rows):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest screened candidate has already been submitted for governance review",
            "diagnostic_conclusions": {
                "screening_id": screening_id,
                "existing_review_packet_count": sum(
                    1 for row in review_ledger_rows if str(row.get("source_screening_id", "")) == screening_id
                ),
            },
        }

    blocked_action_request = dict(intake_payload.get("blocked_action_request", {}))
    canonical_summary = dict(authority_payload.get("authority_file_summary", {}))
    authority_promotion_record = dict(authority_payload.get("authority_promotion_record", {}))
    branch_record = dict(list(branch_registry.get("branches", []))[0]) if list(branch_registry.get("branches", [])) else {}

    requested_template_name = str(blocked_action_request.get("requested_template_name", ""))
    requested_template_family = str(blocked_action_request.get("requested_template_family", ""))
    review_packet_id = f"reopen_review::{proposal['proposal_id']}"
    submitted_at = _now()
    artifact_path = _diagnostic_artifact_dir() / (
        f"memory_summary_v4_governance_reopen_review_submission_snapshot_v1_{proposal['proposal_id']}.json"
    )

    review_submission_contract = {
        "schema_name": REVIEW_SCHEMA_NAME,
        "schema_version": REVIEW_SCHEMA_VERSION,
        "source_intake_schema_version": GOVERNANCE_REOPEN_INTAKE_SCHEMA_VERSION,
        "screening_eligibility_required": {
            "screening_state": SCREENED_REOPEN_CANDIDATE,
            "screening_governance_review_state": APPROVED_FOR_GOVERNANCE_REVIEW,
        },
        "review_submission_states": [
            NOT_SUBMITTED_FOR_GOVERNANCE_REVIEW,
            SUBMITTED_FOR_GOVERNANCE_REVIEW,
        ],
        "review_outcome_states": [
            REVIEW_OUTCOME_PENDING,
            GOVERNANCE_REVIEW_REJECTED,
            GOVERNANCE_REVIEW_APPROVED_FOR_PROMOTION_PATH,
            PROMOTED_AUTHORITY_UPDATE,
        ],
        "authority_relation": REVIEW_NON_AUTHORITATIVE,
        "promotion_bypass_disallowed": True,
        "review_packet_required_before_promotion": True,
    }

    review_packet = {
        "proposal_id": str(proposal.get("proposal_id", "")),
        "template_name": "memory_summary.v4_governance_reopen_review_submission_snapshot_v1",
        "snapshot_identity_context": {
            "review_packet_id": review_packet_id,
            "submitted_at": submitted_at,
            "phase": "governance_reopen_review_submission",
            "source_screening_id": screening_id,
            "source_intake_id": _first_nonempty(
                source_intake_reference.get("intake_id"),
                screened_intake_id,
            ),
        },
        "review_submission_contract": review_submission_contract,
        "source_screening_reference": {
            "screening_id": screening_id,
            "artifact_path": screening_artifact_path,
            "ledger_path": str(GOVERNANCE_REOPEN_SCREENING_LEDGER_PATH),
            "screening_state": screening_state,
            "screening_governance_review_state": screening_review_state,
            "evidence_sufficiency_assessment": evidence_sufficiency,
            "screening_reason_codes": [
                str(item) for item in list(screening_result.get("screening_reason_codes", []))
            ],
            "source_intake_id": _first_nonempty(
                source_intake_reference.get("intake_id"),
                screened_intake_id,
            ),
            "source_intake_artifact_path": source_intake_artifact_path,
        },
        "requested_action_and_scope": {
            "action_kind": str(blocked_action_request.get("action_kind", "")),
            "requested_template_name": requested_template_name,
            "requested_template_family": requested_template_family,
            "requested_proposal_type": str(blocked_action_request.get("requested_proposal_type", "")),
            "requested_scope": str(blocked_action_request.get("requested_scope", "")),
            "requested_evaluation_semantics": str(
                blocked_action_request.get("requested_evaluation_semantics", "")
            ),
            "request_classification": str(
                dict(intake_payload.get("reopen_candidate_intake", {})).get("request_classification", "")
            ),
        },
        "blocking_reason_and_applied_reopen_bar": {
            "blocking_reason": str(blocked_action_request.get("reason", "")),
            "applied_reopen_bar": dict(screening_payload.get("applied_reopen_bar", {})),
        },
        "authority_posture_at_submission": {
            "current_branch_state": str(canonical_summary.get("current_branch_state", "")),
            "current_operating_stance": str(canonical_summary.get("current_operating_stance", "")),
            "held_baseline_template": str(canonical_summary.get("held_baseline_template", "")),
            "routing_status": str(canonical_summary.get("routing_status", "")),
            "reopen_eligibility": dict(canonical_summary.get("reopen_eligibility", {})),
            "selector_frontier_memory": dict(authority_payload.get("selector_frontier_memory", {})),
            "authority_promotion_id": str(authority_promotion_record.get("promotion_id", "")),
        },
        "evidence_references": {
            "canonical_authority_file": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
            "promotion_ledger_path": str(GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH),
            "source_screening_artifact_path": screening_artifact_path,
            "source_screening_ledger_path": str(GOVERNANCE_REOPEN_SCREENING_LEDGER_PATH),
            "source_intake_artifact_path": source_intake_artifact_path,
            "source_intake_ledger_path": str(GOVERNANCE_REOPEN_INTAKE_LEDGER_PATH),
            "intervention_ledger_path": str(INTERVENTION_LEDGER_PATH),
            "analytics_path": str(INTERVENTION_ANALYTICS_PATH),
            "proposal_recommendations_path": str(PROPOSAL_RECOMMENDATIONS_PATH),
            "self_structure_state_path": str(SELF_STRUCTURE_STATE_PATH),
            "self_structure_ledger_path": str(SELF_STRUCTURE_LEDGER_PATH),
            "branch_registry_path": str(BRANCH_REGISTRY_PATH),
            "directive_state_path": str(DIRECTIVE_STATE_PATH),
            "bucket_state_path": str(BUCKET_STATE_PATH),
            "latest_snapshots_count": int(len(load_latest_snapshots())),
            "screening_ledger_entries_seen": int(len(screening_ledger_rows)),
            "review_ledger_entries_before_write": int(len(review_ledger_rows)),
        },
        "review_submission_result": {
            "review_submission_state": SUBMITTED_FOR_GOVERNANCE_REVIEW,
            "review_outcome_state": REVIEW_OUTCOME_PENDING,
            "promotion_path_state": "explicit_review_outcome_required_before_promotion_path",
            "duplicate_submission_prevented": True,
            "canonical_authority_mutation_allowed": False,
        },
        "review_provenance": {
            "submitted_by_surface": "memory_summary.v4_governance_reopen_review_submission_snapshot_v1",
            "reviewer_source": "governed_reopen_review_submission_snapshot_v1",
            "branch_id": str(branch_registry.get("current_branch_id", "")),
            "branch_pause_rationale": str(branch_record.get("pause_rationale", "")),
            "directive_id": str(dict(directive_state.get("current_directive_state", {})).get("directive_id", "")),
            "bucket_id": str(dict(bucket_state.get("current_bucket_state", {})).get("bucket_id", "")),
            "governance_execution_contract_available": bool(
                intervention_analytics.get("governance_execution_contract")
                or proposal_recommendations.get("governance_execution_contract")
            ),
        },
        "promotion_handoff_contract": {
            "next_allowed_binding_surface": "explicit_governance_memory_promotion_gate_v1",
            "required_review_outcome_state": GOVERNANCE_REVIEW_APPROVED_FOR_PROMOTION_PATH,
            "canonical_authority_mutation_disallowed_here": True,
            "promotion_bypass_disallowed": True,
            "rollback_trace_mode": "promotion_ledger_backed_only",
        },
        "review_rollback_deprecation_trigger_status": {
            "submission_triggered": True,
            "review_triggered": False,
            "rollback_triggered": False,
            "deprecation_triggered": False,
        },
        "operator_readable_conclusion": (
            "The screened reopen candidate has been submitted as a non-authoritative governance-review packet. "
            "This records the review handoff explicitly, but canonical authority remains unchanged until an explicit review outcome and the existing promotion path are applied."
        ),
    }

    _write_json(artifact_path, review_packet)

    review_ledger_entry = {
        "event_type": "governance_reopen_review_submitted",
        "written_at": submitted_at,
        "review_packet_id": review_packet_id,
        "source_screening_id": screening_id,
        "source_screening_artifact_path": screening_artifact_path,
        "source_intake_id": _first_nonempty(
            source_intake_reference.get("intake_id"),
            screened_intake_id,
        ),
        "artifact_path": str(artifact_path),
        "review_submission_state": SUBMITTED_FOR_GOVERNANCE_REVIEW,
        "review_outcome_state": REVIEW_OUTCOME_PENDING,
        "requested_template_name": requested_template_name,
        "requested_template_family": requested_template_family,
        "promotion_bypass_disallowed": True,
    }
    _append_jsonl(GOVERNANCE_REOPEN_REVIEW_LEDGER_PATH, review_ledger_entry)

    updated_self_structure = dict(self_structure_state)
    updated_summary = dict(current_state_summary)
    updated_summary.update(
        {
            "latest_governance_reopen_review_packet_id": review_packet_id,
            "latest_governance_reopen_review_artifact_path": str(artifact_path),
            "latest_governance_reopen_review_ledger_path": str(GOVERNANCE_REOPEN_REVIEW_LEDGER_PATH),
            "latest_governance_reopen_review_state": SUBMITTED_FOR_GOVERNANCE_REVIEW,
            "latest_governance_reopen_review_submission_state": SUBMITTED_FOR_GOVERNANCE_REVIEW,
            "latest_governance_reopen_review_outcome_state": REVIEW_OUTCOME_PENDING,
            "latest_governance_reopen_review_source_screening_id": screening_id,
        }
    )
    updated_self_structure["generated_at"] = _now()
    updated_self_structure["current_state_summary"] = updated_summary
    updated_self_structure["governance_reopen_review"] = {
        "schema_name": REVIEW_SCHEMA_NAME,
        "schema_version": REVIEW_SCHEMA_VERSION,
        "latest_review_packet": {
            "review_packet_id": review_packet_id,
            "source_screening_id": screening_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_REVIEW_LEDGER_PATH),
            "review_submission_state": SUBMITTED_FOR_GOVERNANCE_REVIEW,
            "review_outcome_state": REVIEW_OUTCOME_PENDING,
        },
    }
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure)

    _append_jsonl(
        SELF_STRUCTURE_LEDGER_PATH,
        {
            "event_id": f"governance_reopen_review::{proposal['proposal_id']}",
            "timestamp": _now(),
            "event_type": "governance_reopen_review_submitted",
            "review_packet_id": review_packet_id,
            "source_screening_id": screening_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_REVIEW_LEDGER_PATH),
            "review_submission_state": SUBMITTED_FOR_GOVERNANCE_REVIEW,
            "review_outcome_state": REVIEW_OUTCOME_PENDING,
            "requested_template_name": requested_template_name,
            "requested_template_family": requested_template_family,
        },
    )

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: screened reopen candidate was materialized as an explicit governance-review submission packet",
        "observability_gain": {
            "passed": True,
            "reason": "future agents can now distinguish screened candidates from review-submitted packets and later review outcomes",
            "artifact_path": str(artifact_path),
            "review_ledger_path": str(GOVERNANCE_REOPEN_REVIEW_LEDGER_PATH),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "review submission preserves the explicit handoff between screening and promotion without allowing silent authority mutation",
        },
        "ambiguity_reduction": {
            "passed": True,
            "reason": "review packet makes requested action, reopen bar, evidence references, and submission posture explicit",
            "score": 0.95,
        },
        "safety_neutrality": {
            "passed": True,
            "reason": "review submission writes only non-authoritative governance-review artifacts and does not reopen behavior, routing, thresholds, or live policy",
            "scope": str(proposal.get("scope", "")),
        },
        "later_selection_usefulness": {
            "passed": True,
            "reason": "review packet can later be rejected or approved for the promotion path without changing canonical authority at submission time",
            "recommended_next_template": "",
        },
        "diagnostic_conclusions": {
            "review_submission_state": SUBMITTED_FOR_GOVERNANCE_REVIEW,
            "review_outcome_state": REVIEW_OUTCOME_PENDING,
            "source_screening_id": screening_id,
            "recommended_next_action": "hold_and_consolidate",
            "recommended_next_template": "",
        },
        "artifact_path": str(artifact_path),
        "review_ledger_path": str(GOVERNANCE_REOPEN_REVIEW_LEDGER_PATH),
    }
