from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .governance_memory_promotion_v1 import build_governance_memory_promotion_contract
from .governance_memory_reopen_intake_v1 import (
    GOVERNANCE_REOPEN_INTAKE_SCHEMA_VERSION,
    GOVERNANCE_REVIEW_APPROVED_FOR_PROMOTION_PATH,
    PROMOTION_CANDIDATE_UNDER_REVIEW,
    PROMOTION_PENDING_UNDER_EXISTING_GATE,
    SCREENED_REOPEN_CANDIDATE,
    SUBMITTED_FOR_GOVERNANCE_REVIEW,
)
from .ledger import intervention_data_dir, load_latest_snapshots


DATA_DIR = intervention_data_dir()
DIAGNOSTIC_MEMORY_DIR = DATA_DIR / "diagnostic_memory"
GOVERNANCE_MEMORY_AUTHORITY_PATH = DATA_DIR / "governance_memory_authority_latest.json"
GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH = DATA_DIR / "governance_memory_promotion_ledger.jsonl"
GOVERNANCE_REOPEN_REVIEW_LEDGER_PATH = DATA_DIR / "governance_reopen_review_ledger.jsonl"
GOVERNANCE_REOPEN_REVIEW_OUTCOME_LEDGER_PATH = DATA_DIR / "governance_reopen_review_outcome_ledger.jsonl"
GOVERNANCE_REOPEN_PROMOTION_HANDOFF_LEDGER_PATH = DATA_DIR / "governance_reopen_promotion_handoff_ledger.jsonl"
INTERVENTION_LEDGER_PATH = DATA_DIR / "intervention_ledger.jsonl"
INTERVENTION_ANALYTICS_PATH = DATA_DIR / "intervention_analytics_latest.json"
PROPOSAL_RECOMMENDATIONS_PATH = DATA_DIR / "proposal_recommendations_latest.json"
SELF_STRUCTURE_STATE_PATH = DATA_DIR / "self_structure_state_latest.json"
SELF_STRUCTURE_LEDGER_PATH = DATA_DIR / "self_structure_ledger.jsonl"
BRANCH_REGISTRY_PATH = DATA_DIR / "branch_registry_latest.json"
DIRECTIVE_STATE_PATH = DATA_DIR / "directive_state_latest.json"
BUCKET_STATE_PATH = DATA_DIR / "bucket_state_latest.json"

HANDOFF_SCHEMA_NAME = "GovernanceReopenPromotionHandoff"
HANDOFF_SCHEMA_VERSION = "governance_reopen_promotion_handoff_v1"
HANDOFF_NON_AUTHORITATIVE = "promotion_handoff_non_authoritative_until_explicit_governance_memory_promotion_gate_execution"


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
    promotion_handoff_ledger_rows = _load_jsonl(GOVERNANCE_REOPEN_PROMOTION_HANDOFF_LEDGER_PATH)

    if not all([authority_payload, self_structure_state, branch_registry, directive_state, bucket_state]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: authority, self-structure, branch, directive, and bucket artifacts are required",
        }

    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    review_outcome_artifact_path = str(
        current_state_summary.get("latest_governance_reopen_review_outcome_artifact_path", "")
    )
    review_outcome_state_summary = str(
        current_state_summary.get("latest_governance_reopen_review_outcome_state", "")
    )
    promotion_handoff_state_summary = str(
        current_state_summary.get("latest_governance_reopen_promotion_handoff_state", "")
    )

    if not review_outcome_artifact_path:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no governance-review outcome artifact is available for promotion handoff",
        }

    review_outcome_payload = _load_json_file(Path(review_outcome_artifact_path))
    if not review_outcome_payload:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest governance-review outcome artifact could not be loaded",
        }

    review_decision = dict(review_outcome_payload.get("review_decision", {}))
    review_outcome_state = _first_nonempty(
        review_decision.get("review_outcome_state"),
        review_outcome_state_summary,
    )
    promotion_handoff_state = _first_nonempty(
        review_decision.get("promotion_handoff_state"),
        promotion_handoff_state_summary,
    )
    review_outcome_id = _first_nonempty(
        dict(review_outcome_payload.get("snapshot_identity_context", {})).get("review_outcome_id"),
        str(review_outcome_payload.get("review_outcome_id", "")),
    )
    source_review_submission_reference = dict(
        review_outcome_payload.get("source_review_submission_reference", {})
    )
    review_submission_state = str(source_review_submission_reference.get("review_submission_state", ""))
    source_review_packet_id = _first_nonempty(
        source_review_submission_reference.get("review_packet_id"),
        current_state_summary.get("latest_governance_reopen_review_packet_id"),
    )
    screening_basis = dict(review_outcome_payload.get("screening_basis_and_reopen_bar", {}))
    screening_state = str(screening_basis.get("screening_state", ""))
    screening_reason_codes = [str(item) for item in list(screening_basis.get("screening_reason_codes", []))]

    if review_outcome_state != GOVERNANCE_REVIEW_APPROVED_FOR_PROMOTION_PATH:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: only governance_review_approved_for_promotion_path outcomes may enter promotion handoff",
            "diagnostic_conclusions": {
                "review_outcome_state": review_outcome_state,
                "promotion_handoff_state": promotion_handoff_state,
            },
        }

    if promotion_handoff_state != PROMOTION_PENDING_UNDER_EXISTING_GATE:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest approved review outcome is not in promotion_pending_under_existing_gate state",
            "diagnostic_conclusions": {
                "review_outcome_state": review_outcome_state,
                "promotion_handoff_state": promotion_handoff_state,
            },
        }

    if review_submission_state != SUBMITTED_FOR_GOVERNANCE_REVIEW:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: only submitted governance-review packets may enter promotion handoff",
            "diagnostic_conclusions": {
                "review_submission_state": review_submission_state,
                "review_outcome_state": review_outcome_state,
            },
        }

    if screening_state != SCREENED_REOPEN_CANDIDATE:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: only screened reopen candidates may enter promotion handoff",
            "diagnostic_conclusions": {
                "screening_state": screening_state,
                "review_outcome_state": review_outcome_state,
            },
        }

    if "repeated_motion_without_new_evidence" in screening_reason_codes:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: repeated motion without new evidence cannot enter promotion handoff",
            "diagnostic_conclusions": {
                "review_outcome_state": review_outcome_state,
                "screening_reason_codes": screening_reason_codes,
            },
        }

    if any(str(row.get("source_review_outcome_id", "")) == review_outcome_id for row in promotion_handoff_ledger_rows):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest approved review outcome already has a promotion handoff artifact",
            "diagnostic_conclusions": {
                "review_outcome_id": review_outcome_id,
                "existing_handoff_count": sum(
                    1
                    for row in promotion_handoff_ledger_rows
                    if str(row.get("source_review_outcome_id", "")) == review_outcome_id
                ),
            },
        }

    requested_action_and_scope = dict(review_outcome_payload.get("requested_action_and_scope", {}))
    authority_summary = dict(authority_payload.get("authority_file_summary", {}))
    branch_record = dict(list(branch_registry.get("branches", []))[0]) if list(branch_registry.get("branches", [])) else {}
    promotion_contract = build_governance_memory_promotion_contract()

    handoff_id = f"reopen_promotion_handoff::{proposal['proposal_id']}"
    handed_off_at = _now()
    artifact_path = _diagnostic_artifact_dir() / (
        f"memory_summary_v4_governance_reopen_promotion_handoff_snapshot_v1_{proposal['proposal_id']}.json"
    )

    handoff_contract = {
        "schema_name": HANDOFF_SCHEMA_NAME,
        "schema_version": HANDOFF_SCHEMA_VERSION,
        "source_intake_schema_version": GOVERNANCE_REOPEN_INTAKE_SCHEMA_VERSION,
        "required_review_outcome_state": GOVERNANCE_REVIEW_APPROVED_FOR_PROMOTION_PATH,
        "required_promotion_handoff_state": PROMOTION_PENDING_UNDER_EXISTING_GATE,
        "promotion_candidate_states": [
            PROMOTION_CANDIDATE_UNDER_REVIEW,
            "binding_promoted_authority",
        ],
        "authority_relation": HANDOFF_NON_AUTHORITATIVE,
        "promotion_bypass_disallowed": True,
        "promotion_gate_dependency": "explicit_governance_memory_promotion_gate_v1",
    }

    handoff_payload = {
        "proposal_id": str(proposal.get("proposal_id", "")),
        "template_name": "memory_summary.v4_governance_reopen_promotion_handoff_snapshot_v1",
        "snapshot_identity_context": {
            "promotion_handoff_id": handoff_id,
            "handed_off_at": handed_off_at,
            "phase": "governance_reopen_promotion_handoff",
            "source_review_outcome_id": review_outcome_id,
            "source_review_packet_id": source_review_packet_id,
        },
        "promotion_handoff_contract": handoff_contract,
        "source_review_outcome_reference": {
            "review_outcome_id": review_outcome_id,
            "artifact_path": review_outcome_artifact_path,
            "ledger_path": str(GOVERNANCE_REOPEN_REVIEW_OUTCOME_LEDGER_PATH),
            "review_outcome_state": review_outcome_state,
            "promotion_handoff_state": promotion_handoff_state,
            "review_decision_reason_codes": [
                str(item) for item in list(review_decision.get("review_decision_reason_codes", []))
            ],
        },
        "source_review_submission_reference": {
            "review_packet_id": source_review_packet_id,
            "artifact_path": str(source_review_submission_reference.get("artifact_path", "")),
            "ledger_path": str(GOVERNANCE_REOPEN_REVIEW_LEDGER_PATH),
            "review_submission_state": review_submission_state,
            "source_screening_id": str(source_review_submission_reference.get("source_screening_id", "")),
        },
        "requested_action_and_scope": requested_action_and_scope,
        "screening_basis_and_applied_reopen_bar": screening_basis,
        "authority_posture_at_handoff": {
            "current_branch_state": str(authority_summary.get("current_branch_state", "")),
            "current_operating_stance": str(authority_summary.get("current_operating_stance", "")),
            "held_baseline_template": str(authority_summary.get("held_baseline_template", "")),
            "routing_status": str(authority_summary.get("routing_status", "")),
            "reopen_eligibility": dict(authority_summary.get("reopen_eligibility", {})),
            "authority_promotion_record": dict(authority_payload.get("authority_promotion_record", {})),
        },
        "promotion_candidate": {
            "promotion_candidate_state": PROMOTION_CANDIDATE_UNDER_REVIEW,
            "promotion_handoff_state": PROMOTION_PENDING_UNDER_EXISTING_GATE,
            "canonical_authority_mutation_allowed": False,
            "candidate_artifact_path": "",
            "candidate_source_template_name": "",
            "candidate_ready_for_existing_gate": False,
            "candidate_readiness_reason": "no_allowed_binding_promoter_candidate_artifact_prepared",
            "apply_binding_authority_requested": False,
            "promotion_gate_decision_mode": "explicit_execute_flag_required",
            "allowed_binding_promoter_templates": list(
                promotion_contract.get("allowed_binding_promoter_templates", [])
            ),
            "required_candidate_top_level_fields": list(
                promotion_contract.get("required_candidate_top_level_fields", [])
            ),
            "promotion_reason": (
                "governance review approved the request for explicit promotion-path consideration; "
                "binding authority remains unchanged until the existing governance memory promotion gate is executed"
            ),
        },
        "promotion_gate_input_contract": {
            "canonical_authority_file": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
            "promotion_ledger_path": str(GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH),
            "required_review_outcome_state": GOVERNANCE_REVIEW_APPROVED_FOR_PROMOTION_PATH,
            "required_handoff_state": PROMOTION_PENDING_UNDER_EXISTING_GATE,
            "required_promotion_candidate_state": PROMOTION_CANDIDATE_UNDER_REVIEW,
            "candidate_artifact_path": "",
            "candidate_source_template_name": "",
            "candidate_ready_for_existing_gate": False,
            "apply_binding_authority_requested": False,
            "promotion_gate_decision_mode": "explicit_execute_flag_required",
            "allowed_binding_promoter_templates": list(
                promotion_contract.get("allowed_binding_promoter_templates", [])
            ),
            "required_candidate_top_level_fields": list(
                promotion_contract.get("required_candidate_top_level_fields", [])
            ),
            "governed_reopen_handoff_requirements": list(
                promotion_contract.get("governed_reopen_handoff_requirements", [])
            ),
            "canonical_authority_mutation_disallowed_here": True,
            "promotion_bypass_disallowed": True,
        },
        "review_provenance": {
            "handoff_by_surface": "memory_summary.v4_governance_reopen_promotion_handoff_snapshot_v1",
            "reviewer_source": "governed_reopen_promotion_handoff_snapshot_v1",
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
            "review_ledger_path": str(GOVERNANCE_REOPEN_REVIEW_LEDGER_PATH),
            "review_outcome_ledger_path": str(GOVERNANCE_REOPEN_REVIEW_OUTCOME_LEDGER_PATH),
            "promotion_handoff_ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_HANDOFF_LEDGER_PATH),
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
            "review_outcome_ledger_entries_seen": int(len(review_outcome_ledger_rows)),
            "promotion_handoff_ledger_entries_before_write": int(len(promotion_handoff_ledger_rows)),
            "rollback_trace_mode": "promotion_handoff_ledger_then_existing_promotion_gate_only",
        },
        "review_rollback_deprecation_trigger_status": {
            "promotion_handoff_triggered": True,
            "promotion_gate_ready": True,
            "rollback_triggered": False,
            "deprecation_triggered": False,
        },
        "operator_readable_conclusion": (
            "The governance-review-approved outcome has been handed off as a non-authoritative promotion candidate. "
            "It is now explicit that the request is promotion-pending under the existing gate, but canonical authority remains unchanged until that separate gate executes."
        ),
    }

    _write_json(artifact_path, handoff_payload)

    handoff_ledger_entry = {
        "event_type": "governance_reopen_promotion_handoff_materialized",
        "written_at": handed_off_at,
        "promotion_handoff_id": handoff_id,
        "source_review_outcome_id": review_outcome_id,
        "source_review_outcome_artifact_path": review_outcome_artifact_path,
        "source_review_packet_id": source_review_packet_id,
        "artifact_path": str(artifact_path),
        "promotion_handoff_state": PROMOTION_PENDING_UNDER_EXISTING_GATE,
        "promotion_candidate_state": PROMOTION_CANDIDATE_UNDER_REVIEW,
        "requested_template_name": str(requested_action_and_scope.get("requested_template_name", "")),
        "requested_template_family": str(requested_action_and_scope.get("requested_template_family", "")),
        "promotion_bypass_disallowed": True,
    }
    _append_jsonl(GOVERNANCE_REOPEN_PROMOTION_HANDOFF_LEDGER_PATH, handoff_ledger_entry)

    updated_self_structure = dict(self_structure_state)
    updated_summary = dict(current_state_summary)
    updated_summary.update(
        {
            "latest_governance_reopen_promotion_handoff_artifact_path": str(artifact_path),
            "latest_governance_reopen_promotion_handoff_ledger_path": str(
                GOVERNANCE_REOPEN_PROMOTION_HANDOFF_LEDGER_PATH
            ),
            "latest_governance_reopen_promotion_handoff_state": PROMOTION_PENDING_UNDER_EXISTING_GATE,
            "latest_governance_reopen_promotion_candidate_state": PROMOTION_CANDIDATE_UNDER_REVIEW,
            "latest_governance_reopen_promotion_source_review_outcome_id": review_outcome_id,
        }
    )
    updated_self_structure["generated_at"] = _now()
    updated_self_structure["current_state_summary"] = updated_summary
    updated_self_structure["governance_reopen_promotion_handoff"] = {
        "schema_name": HANDOFF_SCHEMA_NAME,
        "schema_version": HANDOFF_SCHEMA_VERSION,
        "latest_promotion_handoff": {
            "promotion_handoff_id": handoff_id,
            "source_review_outcome_id": review_outcome_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_HANDOFF_LEDGER_PATH),
            "promotion_handoff_state": PROMOTION_PENDING_UNDER_EXISTING_GATE,
            "promotion_candidate_state": PROMOTION_CANDIDATE_UNDER_REVIEW,
        },
    }
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure)

    _append_jsonl(
        SELF_STRUCTURE_LEDGER_PATH,
        {
            "event_id": f"governance_reopen_promotion_handoff::{proposal['proposal_id']}",
            "timestamp": _now(),
            "event_type": "governance_reopen_promotion_handoff_materialized",
            "promotion_handoff_id": handoff_id,
            "source_review_outcome_id": review_outcome_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_HANDOFF_LEDGER_PATH),
            "promotion_handoff_state": PROMOTION_PENDING_UNDER_EXISTING_GATE,
            "promotion_candidate_state": PROMOTION_CANDIDATE_UNDER_REVIEW,
            "requested_template_name": str(requested_action_and_scope.get("requested_template_name", "")),
            "requested_template_family": str(requested_action_and_scope.get("requested_template_family", "")),
        },
    )

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: governance-review-approved outcome was materialized as an explicit promotion handoff without mutating canonical authority",
        "observability_gain": {
            "passed": True,
            "reason": "future agents can now distinguish review approval from promotion-pending handoff and promotion-candidate preparation",
            "artifact_path": str(artifact_path),
            "promotion_handoff_ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_HANDOFF_LEDGER_PATH),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "promotion handoff now preserves the seam between review approval and the existing promotion gate instead of relying on implicit escalation",
        },
        "ambiguity_reduction": {
            "passed": True,
            "reason": "promotion-gate input requirements, handoff state, and candidate-under-review state are explicit",
            "score": 0.96,
        },
        "safety_neutrality": {
            "passed": True,
            "reason": "promotion handoff writes only non-authoritative governance artifacts and does not execute the promotion gate or mutate canonical authority",
            "scope": str(proposal.get("scope", "")),
        },
        "later_selection_usefulness": {
            "passed": True,
            "reason": "handoff leaves canonical authority unchanged until the separate explicit promotion path is invoked",
            "recommended_next_template": "",
        },
        "diagnostic_conclusions": {
            "review_outcome_state": GOVERNANCE_REVIEW_APPROVED_FOR_PROMOTION_PATH,
            "promotion_handoff_state": PROMOTION_PENDING_UNDER_EXISTING_GATE,
            "promotion_candidate_state": PROMOTION_CANDIDATE_UNDER_REVIEW,
            "recommended_next_action": "hold_and_consolidate",
            "recommended_next_template": "",
        },
        "artifact_path": str(artifact_path),
        "promotion_handoff_ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_HANDOFF_LEDGER_PATH),
    }
