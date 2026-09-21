from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .governance_memory_reopen_intake_v1 import (
    APPROVED_FOR_GOVERNANCE_REVIEW,
    GOVERNANCE_REOPEN_INTAKE_SCHEMA_VERSION,
    GOVERNANCE_REVIEW_APPROVED_FOR_PROMOTION_PATH,
    GOVERNANCE_REVIEW_REJECTED,
    PROMOTION_PENDING_UNDER_EXISTING_GATE,
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
GOVERNANCE_REOPEN_REVIEW_OUTCOME_LEDGER_PATH = DATA_DIR / "governance_reopen_review_outcome_ledger.jsonl"
INTERVENTION_LEDGER_PATH = DATA_DIR / "intervention_ledger.jsonl"
INTERVENTION_ANALYTICS_PATH = DATA_DIR / "intervention_analytics_latest.json"
PROPOSAL_RECOMMENDATIONS_PATH = DATA_DIR / "proposal_recommendations_latest.json"
SELF_STRUCTURE_STATE_PATH = DATA_DIR / "self_structure_state_latest.json"
SELF_STRUCTURE_LEDGER_PATH = DATA_DIR / "self_structure_ledger.jsonl"
BRANCH_REGISTRY_PATH = DATA_DIR / "branch_registry_latest.json"
DIRECTIVE_STATE_PATH = DATA_DIR / "directive_state_latest.json"
BUCKET_STATE_PATH = DATA_DIR / "bucket_state_latest.json"

OUTCOME_SCHEMA_NAME = "GovernanceReopenReviewOutcome"
OUTCOME_SCHEMA_VERSION = "governance_reopen_review_outcome_v1"
OUTCOME_NON_AUTHORITATIVE = "review_outcome_non_authoritative_until_explicit_promotion_gate_execution"


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
    review_ledger_rows = _load_jsonl(GOVERNANCE_REOPEN_REVIEW_LEDGER_PATH)
    review_outcome_ledger_rows = _load_jsonl(GOVERNANCE_REOPEN_REVIEW_OUTCOME_LEDGER_PATH)

    if not all([authority_payload, self_structure_state, branch_registry, directive_state, bucket_state]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: authority, self-structure, branch, directive, and bucket artifacts are required",
        }

    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    review_artifact_path = str(current_state_summary.get("latest_governance_reopen_review_artifact_path", ""))
    review_submission_state_summary = str(
        current_state_summary.get("latest_governance_reopen_review_submission_state", "")
    )
    review_outcome_state_summary = str(
        current_state_summary.get("latest_governance_reopen_review_outcome_state", "")
    )

    if not review_artifact_path:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no governance-review submission artifact is available for review outcome",
        }

    review_payload = _load_json_file(Path(review_artifact_path))
    if not review_payload:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest governance-review submission artifact could not be loaded",
        }

    review_submission_result = dict(review_payload.get("review_submission_result", {}))
    review_submission_state = _first_nonempty(
        review_submission_result.get("review_submission_state"),
        review_submission_state_summary,
    )
    review_outcome_state_before = _first_nonempty(
        review_submission_result.get("review_outcome_state"),
        review_outcome_state_summary,
    )
    review_packet_id = _first_nonempty(
        dict(review_payload.get("snapshot_identity_context", {})).get("review_packet_id"),
        str(review_payload.get("review_packet_id", "")),
    )
    source_screening_reference = dict(review_payload.get("source_screening_reference", {}))
    screening_state = str(source_screening_reference.get("screening_state", ""))
    screening_governance_review_state = str(
        source_screening_reference.get("screening_governance_review_state", "")
    )
    screening_reason_codes = [str(item) for item in list(source_screening_reference.get("screening_reason_codes", []))]
    source_screening_id = _first_nonempty(
        source_screening_reference.get("screening_id"),
        current_state_summary.get("latest_governance_reopen_review_source_screening_id"),
    )

    if review_submission_state != SUBMITTED_FOR_GOVERNANCE_REVIEW:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: only submitted governance-review packets may receive explicit review outcomes",
            "diagnostic_conclusions": {
                "review_submission_state": review_submission_state,
                "review_outcome_state": review_outcome_state_before,
            },
        }

    if review_outcome_state_before not in {"", REVIEW_OUTCOME_PENDING}:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest governance-review packet already has a review outcome",
            "diagnostic_conclusions": {
                "review_packet_id": review_packet_id,
                "review_outcome_state": review_outcome_state_before,
            },
        }

    if (
        screening_state != SCREENED_REOPEN_CANDIDATE
        or screening_governance_review_state != APPROVED_FOR_GOVERNANCE_REVIEW
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: only screened and governance-review-eligible submissions may receive a review decision",
            "diagnostic_conclusions": {
                "screening_state": screening_state,
                "screening_governance_review_state": screening_governance_review_state,
            },
        }

    if any(str(row.get("source_review_packet_id", "")) == review_packet_id for row in review_outcome_ledger_rows):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest governance-review packet already has a recorded outcome",
            "diagnostic_conclusions": {
                "review_packet_id": review_packet_id,
                "existing_review_outcome_count": sum(
                    1
                    for row in review_outcome_ledger_rows
                    if str(row.get("source_review_packet_id", "")) == review_packet_id
                ),
            },
        }

    positive_signal_present = any(
        code in {
            "materially_new_evidence_present",
            "materially_different_bounded_candidate_present",
            "control_evidence_contradiction_present",
            "fresh_upstream_selector_result_present",
        }
        for code in screening_reason_codes
    )
    repeated_motion_without_new_evidence = (
        "repeated_template_motion" in screening_reason_codes
        and "same_family_motion_without_new_evidence" in screening_reason_codes
        and not positive_signal_present
    )

    authority_summary = dict(authority_payload.get("authority_file_summary", {}))
    authority_posture_at_review = {
        "current_branch_state": str(authority_summary.get("current_branch_state", "")),
        "current_operating_stance": str(authority_summary.get("current_operating_stance", "")),
        "held_baseline_template": str(authority_summary.get("held_baseline_template", "")),
        "routing_status": str(authority_summary.get("routing_status", "")),
        "reopen_eligibility": dict(authority_summary.get("reopen_eligibility", {})),
        "selector_frontier_memory": dict(authority_payload.get("selector_frontier_memory", {})),
        "authority_promotion_record": dict(authority_payload.get("authority_promotion_record", {})),
    }
    authority_posture_at_submission = dict(review_payload.get("authority_posture_at_submission", {}))
    authority_posture_changed_since_submission = any(
        authority_posture_at_submission.get(key) != authority_posture_at_review.get(key)
        for key in [
            "current_branch_state",
            "current_operating_stance",
            "held_baseline_template",
            "routing_status",
        ]
    )

    if positive_signal_present and not repeated_motion_without_new_evidence and not authority_posture_changed_since_submission:
        review_outcome_state = GOVERNANCE_REVIEW_APPROVED_FOR_PROMOTION_PATH
        promotion_handoff_state = PROMOTION_PENDING_UNDER_EXISTING_GATE
        review_decision_reason_codes = [
            "screening_basis_clears_review_bar",
            "explicit_promotion_gate_handoff_required",
        ]
        if positive_signal_present:
            review_decision_reason_codes.append("materially_new_or_bounded_signal_confirmed")
    else:
        review_outcome_state = GOVERNANCE_REVIEW_REJECTED
        promotion_handoff_state = "not_eligible_for_promotion_path"
        review_decision_reason_codes = []
        if repeated_motion_without_new_evidence:
            review_decision_reason_codes.append("repeated_motion_without_new_evidence")
        if authority_posture_changed_since_submission:
            review_decision_reason_codes.append("authority_posture_changed_since_submission")
        if not positive_signal_present:
            review_decision_reason_codes.append("screening_basis_did_not_clear_review_bar")

    outcome_id = f"reopen_review_outcome::{proposal['proposal_id']}"
    decided_at = _now()
    artifact_path = _diagnostic_artifact_dir() / (
        f"memory_summary_v4_governance_reopen_review_outcome_snapshot_v1_{proposal['proposal_id']}.json"
    )

    branch_record = dict(list(branch_registry.get("branches", []))[0]) if list(branch_registry.get("branches", [])) else {}
    requested_action_and_scope = dict(review_payload.get("requested_action_and_scope", {}))

    outcome_contract = {
        "schema_name": OUTCOME_SCHEMA_NAME,
        "schema_version": OUTCOME_SCHEMA_VERSION,
        "source_intake_schema_version": GOVERNANCE_REOPEN_INTAKE_SCHEMA_VERSION,
        "required_review_submission_state": SUBMITTED_FOR_GOVERNANCE_REVIEW,
        "review_outcome_states": [
            GOVERNANCE_REVIEW_REJECTED,
            GOVERNANCE_REVIEW_APPROVED_FOR_PROMOTION_PATH,
        ],
        "promotion_handoff_states": [
            "not_eligible_for_promotion_path",
            PROMOTION_PENDING_UNDER_EXISTING_GATE,
            PROMOTED_AUTHORITY_UPDATE,
        ],
        "authority_relation": OUTCOME_NON_AUTHORITATIVE,
        "promotion_bypass_disallowed": True,
        "promotion_gate_dependency": "explicit_governance_memory_promotion_gate_v1",
    }

    outcome_payload = {
        "proposal_id": str(proposal.get("proposal_id", "")),
        "template_name": "memory_summary.v4_governance_reopen_review_outcome_snapshot_v1",
        "snapshot_identity_context": {
            "review_outcome_id": outcome_id,
            "decided_at": decided_at,
            "phase": "governance_reopen_review_outcome",
            "source_review_packet_id": review_packet_id,
            "source_screening_id": source_screening_id,
        },
        "review_outcome_contract": outcome_contract,
        "source_review_submission_reference": {
            "review_packet_id": review_packet_id,
            "artifact_path": review_artifact_path,
            "ledger_path": str(GOVERNANCE_REOPEN_REVIEW_LEDGER_PATH),
            "review_submission_state": review_submission_state,
            "review_outcome_state_before": review_outcome_state_before,
            "source_screening_id": source_screening_id,
            "source_screening_artifact_path": str(source_screening_reference.get("artifact_path", "")),
            "source_intake_id": str(source_screening_reference.get("source_intake_id", "")),
        },
        "requested_action_and_scope": requested_action_and_scope,
        "screening_basis_and_reopen_bar": {
            "screening_state": screening_state,
            "screening_governance_review_state": screening_governance_review_state,
            "screening_reason_codes": screening_reason_codes,
            "blocking_reason_and_applied_reopen_bar": dict(
                review_payload.get("blocking_reason_and_applied_reopen_bar", {})
            ),
        },
        "authority_posture_at_review": authority_posture_at_review,
        "review_decision": {
            "review_outcome_state": review_outcome_state,
            "promotion_handoff_state": promotion_handoff_state,
            "review_decision_reason_codes": review_decision_reason_codes,
            "authority_posture_changed_since_submission": authority_posture_changed_since_submission,
            "repeated_motion_without_new_evidence": repeated_motion_without_new_evidence,
            "positive_signal_present": positive_signal_present,
        },
        "review_provenance": {
            "reviewed_by_surface": "memory_summary.v4_governance_reopen_review_outcome_snapshot_v1",
            "reviewer_source": "governed_reopen_review_outcome_snapshot_v1",
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
            "review_submission_ledger_path": str(GOVERNANCE_REOPEN_REVIEW_LEDGER_PATH),
            "review_outcome_ledger_path": str(GOVERNANCE_REOPEN_REVIEW_OUTCOME_LEDGER_PATH),
            "intervention_ledger_path": str(INTERVENTION_LEDGER_PATH),
            "analytics_path": str(INTERVENTION_ANALYTICS_PATH),
            "proposal_recommendations_path": str(PROPOSAL_RECOMMENDATIONS_PATH),
            "self_structure_state_path": str(SELF_STRUCTURE_STATE_PATH),
            "self_structure_ledger_path": str(SELF_STRUCTURE_LEDGER_PATH),
            "branch_registry_path": str(BRANCH_REGISTRY_PATH),
            "directive_state_path": str(DIRECTIVE_STATE_PATH),
            "bucket_state_path": str(BUCKET_STATE_PATH),
            "latest_snapshots_count": int(len(load_latest_snapshots())),
            "review_ledger_entries_seen": int(len(review_ledger_rows)),
            "review_outcome_ledger_entries_before_write": int(len(review_outcome_ledger_rows)),
            "rollback_trace_mode": "explicit_review_outcome_ledger_then_existing_promotion_gate_only",
        },
        "promotion_handoff_contract": {
            "next_allowed_binding_surface": "explicit_governance_memory_promotion_gate_v1",
            "eligible_for_promotion_gate": review_outcome_state == GOVERNANCE_REVIEW_APPROVED_FOR_PROMOTION_PATH,
            "required_review_outcome_state": GOVERNANCE_REVIEW_APPROVED_FOR_PROMOTION_PATH,
            "current_promotion_handoff_state": promotion_handoff_state,
            "canonical_authority_mutation_disallowed_here": True,
            "promotion_bypass_disallowed": True,
        },
        "review_rollback_deprecation_trigger_status": {
            "review_outcome_triggered": True,
            "promotion_handoff_triggered": review_outcome_state == GOVERNANCE_REVIEW_APPROVED_FOR_PROMOTION_PATH,
            "rollback_triggered": False,
            "deprecation_triggered": False,
        },
        "operator_readable_conclusion": (
            "The submitted governance-review packet now has an explicit non-authoritative review outcome. "
            + (
                "It is approved only for the existing promotion path, so canonical authority remains unchanged until that separate gate executes."
                if review_outcome_state == GOVERNANCE_REVIEW_APPROVED_FOR_PROMOTION_PATH
                else "It is rejected in review, so there is no promotion-path handoff and canonical authority remains unchanged."
            )
        ),
    }

    _write_json(artifact_path, outcome_payload)

    outcome_ledger_entry = {
        "event_type": "governance_reopen_review_outcome_recorded",
        "written_at": decided_at,
        "review_outcome_id": outcome_id,
        "source_review_packet_id": review_packet_id,
        "source_review_artifact_path": review_artifact_path,
        "source_screening_id": source_screening_id,
        "artifact_path": str(artifact_path),
        "review_outcome_state": review_outcome_state,
        "promotion_handoff_state": promotion_handoff_state,
        "requested_template_name": str(requested_action_and_scope.get("requested_template_name", "")),
        "requested_template_family": str(requested_action_and_scope.get("requested_template_family", "")),
        "review_decision_reason_codes": review_decision_reason_codes,
        "promotion_bypass_disallowed": True,
    }
    _append_jsonl(GOVERNANCE_REOPEN_REVIEW_OUTCOME_LEDGER_PATH, outcome_ledger_entry)

    updated_self_structure = dict(self_structure_state)
    updated_summary = dict(current_state_summary)
    updated_summary.update(
        {
            "latest_governance_reopen_review_outcome_artifact_path": str(artifact_path),
            "latest_governance_reopen_review_outcome_ledger_path": str(
                GOVERNANCE_REOPEN_REVIEW_OUTCOME_LEDGER_PATH
            ),
            "latest_governance_reopen_review_state": review_outcome_state,
            "latest_governance_reopen_review_outcome_state": review_outcome_state,
            "latest_governance_reopen_promotion_handoff_state": promotion_handoff_state,
            "latest_governance_reopen_review_decision_reason_codes": review_decision_reason_codes,
        }
    )
    updated_self_structure["generated_at"] = _now()
    updated_self_structure["current_state_summary"] = updated_summary
    updated_self_structure["governance_reopen_review_outcome"] = {
        "schema_name": OUTCOME_SCHEMA_NAME,
        "schema_version": OUTCOME_SCHEMA_VERSION,
        "latest_review_outcome": {
            "review_outcome_id": outcome_id,
            "source_review_packet_id": review_packet_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_REVIEW_OUTCOME_LEDGER_PATH),
            "review_outcome_state": review_outcome_state,
            "promotion_handoff_state": promotion_handoff_state,
        },
    }
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure)

    _append_jsonl(
        SELF_STRUCTURE_LEDGER_PATH,
        {
            "event_id": f"governance_reopen_review_outcome::{proposal['proposal_id']}",
            "timestamp": _now(),
            "event_type": "governance_reopen_review_outcome_recorded",
            "review_outcome_id": outcome_id,
            "source_review_packet_id": review_packet_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_REVIEW_OUTCOME_LEDGER_PATH),
            "review_outcome_state": review_outcome_state,
            "promotion_handoff_state": promotion_handoff_state,
            "requested_template_name": str(requested_action_and_scope.get("requested_template_name", "")),
            "requested_template_family": str(requested_action_and_scope.get("requested_template_family", "")),
        },
    )

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: submitted governance-review packet was materialized as an explicit governed review outcome",
        "observability_gain": {
            "passed": True,
            "reason": "future agents can now distinguish review submission from review rejection or promotion-path approval",
            "artifact_path": str(artifact_path),
            "review_outcome_ledger_path": str(GOVERNANCE_REOPEN_REVIEW_OUTCOME_LEDGER_PATH),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "review outcomes now preserve the explicit decision seam before the existing promotion gate without allowing silent authority mutation",
        },
        "ambiguity_reduction": {
            "passed": True,
            "reason": "review decision reason codes, authority posture, and promotion handoff state are now explicit",
            "score": 0.95,
        },
        "safety_neutrality": {
            "passed": True,
            "reason": "review outcome writes only non-authoritative governance artifacts and leaves routing, thresholds, live policy, and benchmark semantics unchanged",
            "scope": str(proposal.get("scope", "")),
        },
        "later_selection_usefulness": {
            "passed": True,
            "reason": "only approved review outcomes can hand off to the existing promotion gate, and canonical authority remains unchanged until that separate gate executes",
            "recommended_next_template": "",
        },
        "diagnostic_conclusions": {
            "review_outcome_state": review_outcome_state,
            "promotion_handoff_state": promotion_handoff_state,
            "source_review_packet_id": review_packet_id,
            "recommended_next_action": "hold_and_consolidate",
            "recommended_next_template": "",
        },
        "artifact_path": str(artifact_path),
        "review_outcome_ledger_path": str(GOVERNANCE_REOPEN_REVIEW_OUTCOME_LEDGER_PATH),
    }
