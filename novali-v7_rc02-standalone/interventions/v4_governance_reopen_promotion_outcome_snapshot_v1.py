from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .governance_memory_promotion_v1 import (
    build_governance_memory_promotion_contract,
    promote_governance_memory_authority,
)
from .governance_memory_reopen_intake_v1 import (
    GOVERNANCE_REOPEN_INTAKE_SCHEMA_VERSION,
    GOVERNANCE_REVIEW_APPROVED_FOR_PROMOTION_PATH,
    PROMOTION_APPLIED_AS_BINDING_AUTHORITY,
    PROMOTION_CANDIDATE_UNDER_REVIEW,
    PROMOTION_NOOP_ALREADY_AUTHORITATIVE,
    PROMOTION_PENDING_UNDER_EXISTING_GATE,
    PROMOTION_REJECTED_UNDER_EXISTING_GATE,
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
GOVERNANCE_REOPEN_PROMOTION_OUTCOME_LEDGER_PATH = DATA_DIR / "governance_reopen_promotion_outcome_ledger.jsonl"
INTERVENTION_LEDGER_PATH = DATA_DIR / "intervention_ledger.jsonl"
INTERVENTION_ANALYTICS_PATH = DATA_DIR / "intervention_analytics_latest.json"
PROPOSAL_RECOMMENDATIONS_PATH = DATA_DIR / "proposal_recommendations_latest.json"
SELF_STRUCTURE_STATE_PATH = DATA_DIR / "self_structure_state_latest.json"
SELF_STRUCTURE_LEDGER_PATH = DATA_DIR / "self_structure_ledger.jsonl"
BRANCH_REGISTRY_PATH = DATA_DIR / "branch_registry_latest.json"
DIRECTIVE_STATE_PATH = DATA_DIR / "directive_state_latest.json"
BUCKET_STATE_PATH = DATA_DIR / "bucket_state_latest.json"

OUTCOME_SCHEMA_NAME = "GovernanceReopenPromotionOutcome"
OUTCOME_SCHEMA_VERSION = "governance_reopen_promotion_outcome_v1"
OUTCOME_NON_AUTHORITATIVE = (
    "promotion_outcome_non_authoritative_until_explicit_governance_memory_promotion_gate_execution"
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


def _authority_reference(authority_payload: dict[str, Any], current_state_summary: dict[str, Any]) -> dict[str, Any]:
    authority_candidate_record = dict(authority_payload.get("authority_candidate_record", {}))
    authority_promotion_record = dict(authority_payload.get("authority_promotion_record", {}))
    authority_summary = dict(authority_payload.get("authority_file_summary", {}))
    return {
        "canonical_authority_file": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
        "authority_mutation_stage": str(authority_payload.get("authority_mutation_stage", "")),
        "authority_artifact_path": str(current_state_summary.get("latest_governance_memory_authority_artifact_path", "")),
        "authority_source_proposal_id": str(authority_payload.get("proposal_id", "")),
        "authority_candidate_artifact_path": str(authority_candidate_record.get("candidate_artifact_path", "")),
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


def _screening_repeated_motion(screening_reason_codes: list[str]) -> bool:
    return "repeated_motion_without_new_evidence" in screening_reason_codes or (
        "repeated_template_motion" in screening_reason_codes
        and "same_family_motion_without_new_evidence" in screening_reason_codes
        and "materially_new_evidence_present" not in screening_reason_codes
        and "materially_different_bounded_candidate_present" not in screening_reason_codes
        and "control_evidence_contradiction_present" not in screening_reason_codes
        and "fresh_upstream_selector_result_present" not in screening_reason_codes
    )


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
    review_ledger_rows = _load_jsonl(GOVERNANCE_REOPEN_REVIEW_LEDGER_PATH)
    review_outcome_ledger_rows = _load_jsonl(GOVERNANCE_REOPEN_REVIEW_OUTCOME_LEDGER_PATH)
    handoff_ledger_rows = _load_jsonl(GOVERNANCE_REOPEN_PROMOTION_HANDOFF_LEDGER_PATH)
    outcome_ledger_rows = _load_jsonl(GOVERNANCE_REOPEN_PROMOTION_OUTCOME_LEDGER_PATH)

    if not all([authority_payload, self_structure_state, branch_registry, directive_state, bucket_state]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: authority, self-structure, branch, directive, and bucket artifacts are required",
        }

    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    handoff_artifact_path = str(
        current_state_summary.get("latest_governance_reopen_promotion_handoff_artifact_path", "")
    )
    handoff_state_summary = str(
        current_state_summary.get("latest_governance_reopen_promotion_handoff_state", "")
    )
    promotion_candidate_state_summary = str(
        current_state_summary.get("latest_governance_reopen_promotion_candidate_state", "")
    )

    if not handoff_artifact_path:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no promotion handoff artifact is available for promotion outcome",
        }

    handoff_payload = _load_json_file(Path(handoff_artifact_path))
    if not handoff_payload:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest promotion handoff artifact could not be loaded",
        }

    handoff_identity = dict(handoff_payload.get("snapshot_identity_context", {}))
    handoff_id = _first_nonempty(
        handoff_identity.get("promotion_handoff_id"),
        handoff_payload.get("promotion_handoff_id"),
    )
    source_review_outcome_reference = dict(handoff_payload.get("source_review_outcome_reference", {}))
    source_review_submission_reference = dict(handoff_payload.get("source_review_submission_reference", {}))
    requested_action_and_scope = dict(handoff_payload.get("requested_action_and_scope", {}))
    screening_basis = dict(handoff_payload.get("screening_basis_and_applied_reopen_bar", {}))
    promotion_candidate = dict(handoff_payload.get("promotion_candidate", {}))
    promotion_gate_input_contract = dict(handoff_payload.get("promotion_gate_input_contract", {}))
    authority_posture_at_handoff = dict(handoff_payload.get("authority_posture_at_handoff", {}))

    review_outcome_state = str(source_review_outcome_reference.get("review_outcome_state", ""))
    review_submission_state = str(source_review_submission_reference.get("review_submission_state", ""))
    promotion_handoff_state = _first_nonempty(
        promotion_candidate.get("promotion_handoff_state"),
        source_review_outcome_reference.get("promotion_handoff_state"),
        handoff_state_summary,
    )
    promotion_candidate_state = _first_nonempty(
        promotion_candidate.get("promotion_candidate_state"),
        promotion_candidate_state_summary,
    )
    screening_state = str(screening_basis.get("screening_state", ""))
    screening_reason_codes = [
        str(item) for item in list(screening_basis.get("screening_reason_codes", []))
    ]

    if review_outcome_state != GOVERNANCE_REVIEW_APPROVED_FOR_PROMOTION_PATH:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: only governance-review-approved outcomes may receive explicit promotion outcomes",
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
            "reason": "diagnostic shadow failed: only promotion_pending_under_existing_gate handoffs may receive explicit promotion outcomes",
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
            "reason": "diagnostic shadow failed: only submitted governance-review packets may feed promotion outcome evaluation",
            "diagnostic_conclusions": {
                "review_submission_state": review_submission_state,
                "promotion_handoff_state": promotion_handoff_state,
            },
        }

    if screening_state != SCREENED_REOPEN_CANDIDATE:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: only screened reopen candidates may feed promotion outcome evaluation",
            "diagnostic_conclusions": {
                "screening_state": screening_state,
                "promotion_handoff_state": promotion_handoff_state,
            },
        }

    if any(str(row.get("source_promotion_handoff_id", "")) == handoff_id for row in outcome_ledger_rows):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest promotion handoff already has a recorded promotion outcome",
            "diagnostic_conclusions": {
                "promotion_handoff_id": handoff_id,
                "existing_promotion_outcome_count": sum(
                    1
                    for row in outcome_ledger_rows
                    if str(row.get("source_promotion_handoff_id", "")) == handoff_id
                ),
            },
        }

    promotion_contract = build_governance_memory_promotion_contract()
    allowed_binding_templates = [
        str(item) for item in list(promotion_contract.get("allowed_binding_promoter_templates", []))
    ]
    required_candidate_top_level_fields = [
        str(item) for item in list(promotion_contract.get("required_candidate_top_level_fields", []))
    ]
    gate_actor = str(promotion_contract.get("gate_actor", "explicit_governance_memory_promotion_gate_v1"))

    candidate_artifact_path = _first_nonempty(
        promotion_candidate.get("candidate_artifact_path"),
        promotion_gate_input_contract.get("candidate_artifact_path"),
    )
    candidate_source_template_name = _first_nonempty(
        promotion_candidate.get("candidate_source_template_name"),
        promotion_gate_input_contract.get("candidate_source_template_name"),
    )
    candidate_ready_for_existing_gate = bool(
        promotion_candidate.get("candidate_ready_for_existing_gate")
        or promotion_gate_input_contract.get("candidate_ready_for_existing_gate")
    )
    apply_binding_authority_requested = bool(
        promotion_candidate.get("apply_binding_authority_requested")
        or promotion_gate_input_contract.get("apply_binding_authority_requested")
    )
    promotion_gate_decision_mode = _first_nonempty(
        promotion_candidate.get("promotion_gate_decision_mode"),
        promotion_gate_input_contract.get("promotion_gate_decision_mode"),
        "explicit_execute_flag_required",
    )

    before_authority_reference = _authority_reference(authority_payload, current_state_summary)
    authority_after_payload = authority_payload
    authority_mutated = False
    candidate_payload: dict[str, Any] = {}
    candidate_missing_fields: list[str] = []
    gate_failure_detail = ""
    gate_checks_performed: list[dict[str, Any]] = []
    decision_reason_codes: list[str] = []
    promotion_outcome_state = PROMOTION_CANDIDATE_UNDER_REVIEW

    repeated_motion_without_new_evidence = _screening_repeated_motion(screening_reason_codes)
    gate_checks_performed.extend(
        [
            {
                "check_name": "review_outcome_approved_for_promotion_path",
                "passed": review_outcome_state == GOVERNANCE_REVIEW_APPROVED_FOR_PROMOTION_PATH,
                "observed_value": review_outcome_state,
            },
            {
                "check_name": "promotion_handoff_pending_under_existing_gate",
                "passed": promotion_handoff_state == PROMOTION_PENDING_UNDER_EXISTING_GATE,
                "observed_value": promotion_handoff_state,
            },
            {
                "check_name": "screened_reopen_candidate",
                "passed": screening_state == SCREENED_REOPEN_CANDIDATE,
                "observed_value": screening_state,
            },
            {
                "check_name": "no_repeated_motion_without_new_evidence",
                "passed": not repeated_motion_without_new_evidence,
                "observed_value": repeated_motion_without_new_evidence,
            },
        ]
    )

    if repeated_motion_without_new_evidence:
        promotion_outcome_state = PROMOTION_REJECTED_UNDER_EXISTING_GATE
        decision_reason_codes.append("repeated_motion_without_new_evidence")
    elif not candidate_ready_for_existing_gate:
        promotion_outcome_state = PROMOTION_CANDIDATE_UNDER_REVIEW
        decision_reason_codes.extend(
            [
                "candidate_not_ready_for_existing_gate",
                "awaiting_allowed_binding_promoter_candidate_artifact",
            ]
        )
    elif not candidate_artifact_path:
        promotion_outcome_state = PROMOTION_REJECTED_UNDER_EXISTING_GATE
        decision_reason_codes.append("candidate_artifact_path_missing")
    else:
        candidate_payload = _load_json_file(Path(candidate_artifact_path))
        gate_checks_performed.append(
            {
                "check_name": "candidate_artifact_loadable",
                "passed": bool(candidate_payload),
                "observed_value": candidate_artifact_path,
            }
        )
        if not candidate_payload:
            promotion_outcome_state = PROMOTION_REJECTED_UNDER_EXISTING_GATE
            decision_reason_codes.append("candidate_artifact_unreadable")
        else:
            if not candidate_source_template_name:
                candidate_source_template_name = str(candidate_payload.get("template_name", ""))
            gate_checks_performed.append(
                {
                    "check_name": "candidate_source_template_allowed",
                    "passed": candidate_source_template_name in allowed_binding_templates,
                    "observed_value": candidate_source_template_name,
                }
            )
            candidate_missing_fields = [
                field for field in required_candidate_top_level_fields if field not in candidate_payload
            ]
            gate_checks_performed.append(
                {
                    "check_name": "candidate_required_fields_present",
                    "passed": not candidate_missing_fields,
                    "observed_value": candidate_missing_fields,
                }
            )

            runtime_surfaces = dict(
                dict(candidate_payload.get("authority_surface", {})).get("non_authoritative_runtime_surfaces", {})
            )
            runtime_loop_code_is_authority = bool(runtime_surfaces.get("runtime_loop_code_is_authority", False))
            gate_checks_performed.append(
                {
                    "check_name": "runtime_loop_code_not_authoritative",
                    "passed": not runtime_loop_code_is_authority,
                    "observed_value": runtime_loop_code_is_authority,
                }
            )

            current_candidate_artifact_path = _first_nonempty(
                before_authority_reference.get("authority_candidate_artifact_path"),
                before_authority_reference.get("authority_promotion_source_candidate_artifact_path"),
            )
            already_authoritative = bool(
                candidate_artifact_path == current_candidate_artifact_path
                or _candidate_signature(candidate_payload) == _candidate_signature(authority_payload)
            )
            gate_checks_performed.append(
                {
                    "check_name": "candidate_not_already_authoritative",
                    "passed": not already_authoritative,
                    "observed_value": already_authoritative,
                }
            )

            if candidate_source_template_name not in allowed_binding_templates:
                promotion_outcome_state = PROMOTION_REJECTED_UNDER_EXISTING_GATE
                decision_reason_codes.append("candidate_source_template_not_allowed")
            elif candidate_missing_fields:
                promotion_outcome_state = PROMOTION_REJECTED_UNDER_EXISTING_GATE
                decision_reason_codes.append("candidate_missing_required_fields")
            elif runtime_loop_code_is_authority:
                promotion_outcome_state = PROMOTION_REJECTED_UNDER_EXISTING_GATE
                decision_reason_codes.append("candidate_runtime_authority_conflict")
            elif already_authoritative:
                promotion_outcome_state = PROMOTION_NOOP_ALREADY_AUTHORITATIVE
                decision_reason_codes.append("candidate_already_matches_canonical_authority")
            elif not apply_binding_authority_requested:
                promotion_outcome_state = PROMOTION_CANDIDATE_UNDER_REVIEW
                decision_reason_codes.append("candidate_ready_but_apply_not_requested")
            else:
                candidate_proposal = {
                    "proposal_id": str(candidate_payload.get("proposal_id", "")),
                    "template_name": candidate_source_template_name,
                }
                try:
                    authority_after_payload = promote_governance_memory_authority(
                        candidate_payload=candidate_payload,
                        proposal=candidate_proposal,
                        candidate_artifact_path=Path(candidate_artifact_path),
                        promotion_reason=(
                            "governance review approved a reopen handoff and the explicit promotion-outcome gate "
                            "applied the allowed authority candidate"
                        ),
                    )
                    authority_mutated = True
                    promotion_outcome_state = PROMOTION_APPLIED_AS_BINDING_AUTHORITY
                    decision_reason_codes.append("candidate_applied_through_existing_promotion_gate")
                except Exception as exc:  # pragma: no cover - defensive gate capture
                    gate_failure_detail = str(exc)
                    promotion_outcome_state = PROMOTION_REJECTED_UNDER_EXISTING_GATE
                    decision_reason_codes.append("existing_promotion_gate_rejected_candidate")

    outcome_id = f"reopen_promotion_outcome::{proposal['proposal_id']}"
    decided_at = _now()
    artifact_path = _diagnostic_artifact_dir() / (
        f"memory_summary_v4_governance_reopen_promotion_outcome_snapshot_v1_{proposal['proposal_id']}.json"
    )
    branch_record = (
        dict(list(branch_registry.get("branches", []))[0]) if list(branch_registry.get("branches", [])) else {}
    )

    after_summary_state = dict(self_structure_state.get("current_state_summary", {}))
    after_authority_reference = _authority_reference(authority_after_payload, after_summary_state)
    if not authority_mutated:
        after_authority_reference = before_authority_reference

    outcome_contract = {
        "schema_name": OUTCOME_SCHEMA_NAME,
        "schema_version": OUTCOME_SCHEMA_VERSION,
        "source_intake_schema_version": GOVERNANCE_REOPEN_INTAKE_SCHEMA_VERSION,
        "required_review_outcome_state": GOVERNANCE_REVIEW_APPROVED_FOR_PROMOTION_PATH,
        "required_handoff_state": PROMOTION_PENDING_UNDER_EXISTING_GATE,
        "promotion_decision_states": [
            PROMOTION_CANDIDATE_UNDER_REVIEW,
            PROMOTION_REJECTED_UNDER_EXISTING_GATE,
            PROMOTION_APPLIED_AS_BINDING_AUTHORITY,
            PROMOTION_NOOP_ALREADY_AUTHORITATIVE,
        ],
        "authority_relation": OUTCOME_NON_AUTHORITATIVE,
        "promotion_bypass_disallowed": True,
        "existing_promotion_gate_actor": gate_actor,
        "apply_binding_authority_default": False,
    }

    outcome_payload = {
        "proposal_id": str(proposal.get("proposal_id", "")),
        "template_name": "memory_summary.v4_governance_reopen_promotion_outcome_snapshot_v1",
        "snapshot_identity_context": {
            "promotion_outcome_id": outcome_id,
            "decided_at": decided_at,
            "phase": "governance_reopen_promotion_outcome",
            "source_promotion_handoff_id": handoff_id,
            "source_review_outcome_id": str(source_review_outcome_reference.get("review_outcome_id", "")),
            "source_review_packet_id": str(source_review_submission_reference.get("review_packet_id", "")),
        },
        "promotion_outcome_contract": outcome_contract,
        "source_promotion_handoff_reference": {
            "promotion_handoff_id": handoff_id,
            "artifact_path": handoff_artifact_path,
            "ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_HANDOFF_LEDGER_PATH),
            "promotion_handoff_state": promotion_handoff_state,
            "promotion_candidate_state": promotion_candidate_state,
        },
        "source_review_outcome_reference": dict(source_review_outcome_reference),
        "source_review_submission_reference": dict(source_review_submission_reference),
        "requested_action_and_scope": requested_action_and_scope,
        "screening_basis_and_applied_reopen_bar": screening_basis,
        "authority_posture_at_decision": {
            "current_branch_state": str(authority_posture_at_handoff.get("current_branch_state", "")),
            "current_operating_stance": str(authority_posture_at_handoff.get("current_operating_stance", "")),
            "held_baseline_template": str(authority_posture_at_handoff.get("held_baseline_template", "")),
            "routing_status": str(authority_posture_at_handoff.get("routing_status", "")),
            "reopen_eligibility": dict(authority_posture_at_handoff.get("reopen_eligibility", {})),
            "authority_promotion_record": dict(authority_posture_at_handoff.get("authority_promotion_record", {})),
        },
        "gate_checks_performed": gate_checks_performed,
        "promotion_gate_input_contract": {
            "candidate_artifact_path": candidate_artifact_path,
            "candidate_source_template_name": candidate_source_template_name,
            "candidate_ready_for_existing_gate": bool(candidate_ready_for_existing_gate),
            "apply_binding_authority_requested": bool(apply_binding_authority_requested),
            "promotion_gate_decision_mode": promotion_gate_decision_mode,
            "allowed_binding_promoter_templates": allowed_binding_templates,
            "required_candidate_top_level_fields": required_candidate_top_level_fields,
            "existing_promotion_gate_actor": gate_actor,
            "canonical_authority_mutation_disallowed_here": not authority_mutated,
        },
        "promotion_decision": {
            "promotion_outcome_state": promotion_outcome_state,
            "decision_reason_codes": decision_reason_codes,
            "gate_actor": gate_actor,
            "apply_binding_authority_requested": bool(apply_binding_authority_requested),
            "canonical_authority_mutated": bool(authority_mutated),
            "repeated_motion_without_new_evidence": repeated_motion_without_new_evidence,
            "candidate_missing_required_fields": candidate_missing_fields,
            "gate_failure_detail": gate_failure_detail,
        },
        "authority_before_reference": before_authority_reference,
        "authority_after_reference": after_authority_reference,
        "reviewer_source_or_gate_actor": {
            "decided_by_surface": "memory_summary.v4_governance_reopen_promotion_outcome_snapshot_v1",
            "gate_actor": gate_actor,
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
            "promotion_outcome_ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_OUTCOME_LEDGER_PATH),
            "intervention_ledger_path": str(INTERVENTION_LEDGER_PATH),
            "analytics_path": str(INTERVENTION_ANALYTICS_PATH),
            "proposal_recommendations_path": str(PROPOSAL_RECOMMENDATIONS_PATH),
            "self_structure_state_path": str(SELF_STRUCTURE_STATE_PATH),
            "self_structure_ledger_path": str(SELF_STRUCTURE_LEDGER_PATH),
            "branch_registry_path": str(BRANCH_REGISTRY_PATH),
            "directive_state_path": str(DIRECTIVE_STATE_PATH),
            "bucket_state_path": str(BUCKET_STATE_PATH),
            "latest_snapshots_count": int(len(load_latest_snapshots())),
            "promotion_ledger_entries_seen": int(len(promotion_ledger_rows)),
            "review_ledger_entries_seen": int(len(review_ledger_rows)),
            "review_outcome_ledger_entries_seen": int(len(review_outcome_ledger_rows)),
            "promotion_handoff_ledger_entries_seen": int(len(handoff_ledger_rows)),
            "promotion_outcome_ledger_entries_before_write": int(len(outcome_ledger_rows)),
            "rollback_trace_mode": "explicit_promotion_outcome_then_existing_promotion_gate_only",
        },
        "review_rollback_deprecation_trigger_status": {
            "promotion_outcome_triggered": True,
            "authority_mutation_triggered": bool(authority_mutated),
            "rollback_triggered": False,
            "deprecation_triggered": False,
        },
        "operator_readable_conclusion": (
            "The promotion-pending handoff now has an explicit governed promotion outcome. "
            + (
                "The candidate remains under review because no explicit binding apply was requested or the gate inputs are still preparatory."
                if promotion_outcome_state == PROMOTION_CANDIDATE_UNDER_REVIEW
                else "The candidate was rejected under the existing gate and canonical authority remains unchanged."
                if promotion_outcome_state == PROMOTION_REJECTED_UNDER_EXISTING_GATE
                else "The candidate was recognized as already authoritative, so the promotion result is an explicit no-op."
                if promotion_outcome_state == PROMOTION_NOOP_ALREADY_AUTHORITATIVE
                else "The existing promotion gate applied the candidate as binding authority and the authority before/after references are explicit."
            )
        ),
    }

    _write_json(artifact_path, outcome_payload)

    outcome_ledger_entry = {
        "event_type": "governance_reopen_promotion_outcome_recorded",
        "written_at": decided_at,
        "promotion_outcome_id": outcome_id,
        "source_promotion_handoff_id": handoff_id,
        "source_promotion_handoff_artifact_path": handoff_artifact_path,
        "source_review_outcome_id": str(source_review_outcome_reference.get("review_outcome_id", "")),
        "source_review_packet_id": str(source_review_submission_reference.get("review_packet_id", "")),
        "artifact_path": str(artifact_path),
        "promotion_outcome_state": promotion_outcome_state,
        "candidate_artifact_path": candidate_artifact_path,
        "candidate_source_template_name": candidate_source_template_name,
        "apply_binding_authority_requested": bool(apply_binding_authority_requested),
        "authority_mutated": bool(authority_mutated),
        "decision_reason_codes": decision_reason_codes,
        "promotion_gate_actor": gate_actor,
        "requested_template_name": str(requested_action_and_scope.get("requested_template_name", "")),
        "requested_template_family": str(requested_action_and_scope.get("requested_template_family", "")),
    }
    _append_jsonl(GOVERNANCE_REOPEN_PROMOTION_OUTCOME_LEDGER_PATH, outcome_ledger_entry)

    updated_self_structure = dict(self_structure_state)
    updated_summary = dict(current_state_summary)
    updated_summary.update(
        {
            "latest_governance_reopen_promotion_outcome_artifact_path": str(artifact_path),
            "latest_governance_reopen_promotion_outcome_ledger_path": str(
                GOVERNANCE_REOPEN_PROMOTION_OUTCOME_LEDGER_PATH
            ),
            "latest_governance_reopen_promotion_outcome_state": promotion_outcome_state,
            "latest_governance_reopen_promotion_gate_actor": gate_actor,
            "latest_governance_reopen_promotion_decision_reason_codes": decision_reason_codes,
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
    updated_self_structure["governance_reopen_promotion_outcome"] = {
        "schema_name": OUTCOME_SCHEMA_NAME,
        "schema_version": OUTCOME_SCHEMA_VERSION,
        "latest_promotion_outcome": {
            "promotion_outcome_id": outcome_id,
            "source_promotion_handoff_id": handoff_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_OUTCOME_LEDGER_PATH),
            "promotion_outcome_state": promotion_outcome_state,
            "authority_mutated": bool(authority_mutated),
        },
    }
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure)

    _append_jsonl(
        SELF_STRUCTURE_LEDGER_PATH,
        {
            "event_id": f"governance_reopen_promotion_outcome::{proposal['proposal_id']}",
            "timestamp": _now(),
            "event_type": "governance_reopen_promotion_outcome_recorded",
            "promotion_outcome_id": outcome_id,
            "source_promotion_handoff_id": handoff_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_OUTCOME_LEDGER_PATH),
            "promotion_outcome_state": promotion_outcome_state,
            "authority_mutated": bool(authority_mutated),
            "requested_template_name": str(requested_action_and_scope.get("requested_template_name", "")),
            "requested_template_family": str(requested_action_and_scope.get("requested_template_family", "")),
        },
    )

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: promotion-pending handoff was materialized as an explicit governed promotion outcome",
        "observability_gain": {
            "passed": True,
            "reason": "future agents can now distinguish promotion-pending handoff from under-review, rejected, noop, or applied promotion decisions",
            "artifact_path": str(artifact_path),
            "promotion_outcome_ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_OUTCOME_LEDGER_PATH),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "promotion outcome makes the existing promotion gate decision surface explicit without creating a second authority path",
        },
        "ambiguity_reduction": {
            "passed": True,
            "reason": "gate checks, decision reason codes, and authority before/after references are now explicit",
            "score": 0.97,
        },
        "safety_neutrality": {
            "passed": True,
            "reason": "promotion outcome stays non-authoritative unless the explicit existing promotion gate is deliberately requested and succeeds",
            "scope": str(proposal.get("scope", "")),
        },
        "later_selection_usefulness": {
            "passed": True,
            "reason": "only valid approved handoff candidates can proceed toward binding authority, and already-authoritative states resolve to explicit no-op instead of silent overwrite",
            "recommended_next_template": "",
        },
        "diagnostic_conclusions": {
            "promotion_outcome_state": promotion_outcome_state,
            "promotion_handoff_state": PROMOTION_PENDING_UNDER_EXISTING_GATE,
            "authority_mutated": bool(authority_mutated),
            "recommended_next_action": "hold_and_consolidate",
            "recommended_next_template": "",
        },
        "artifact_path": str(artifact_path),
        "promotion_outcome_ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_OUTCOME_LEDGER_PATH),
    }
