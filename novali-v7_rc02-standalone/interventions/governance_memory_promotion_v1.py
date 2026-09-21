from __future__ import annotations

from pathlib import Path
from typing import Any

from .governance_substrate_v1 import _append_jsonl, _now, _write_json
from .governance_memory_resolver_v1 import (
    READ_CONTRACT_SCHEMA_VERSION,
    resolve_governance_memory_current_state,
)
from .ledger import intervention_data_dir
from .v4_first_hypothesis_landscape_snapshot_v1 import _load_json_file


GOVERNANCE_MEMORY_AUTHORITY_PATH = intervention_data_dir() / "governance_memory_authority_latest.json"
GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH = intervention_data_dir() / "governance_memory_promotion_ledger.jsonl"

PROMOTION_CONTRACT_SCHEMA_NAME = "GovernanceMemoryPromotionContract"
PROMOTION_CONTRACT_SCHEMA_VERSION = "governance_memory_promotion_contract_v1"

OBSERVATIONAL_EVIDENCE = "observational_evidence"
RECOMMENDED_CHANGE = "recommended_change"
REVIEW_PENDING_CANDIDATE_AUTHORITY_UPDATE = "review_pending_candidate_authority_update"
BINDING_PROMOTED_AUTHORITY = "binding_promoted_authority"
REQUIRED_AUTHORITY_CANDIDATE_TOP_LEVEL_FIELDS = [
    "authority_contract",
    "authority_surface",
    "authority_file_summary",
    "binding_decision_register",
    "resolved_current_state",
    "diagnostic_conclusions",
    "authority_candidate_record",
]

ALLOWED_AUTHORITY_PROMOTER_TEMPLATES = [
    "memory_summary.v4_governance_memory_authority_snapshot_v1",
]


def build_governance_memory_promotion_contract() -> dict[str, Any]:
    return {
        "schema_name": PROMOTION_CONTRACT_SCHEMA_NAME,
        "schema_version": PROMOTION_CONTRACT_SCHEMA_VERSION,
        "canonical_authority_file": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
        "promotion_ledger_path": str(GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH),
        "authority_states": [
            OBSERVATIONAL_EVIDENCE,
            RECOMMENDED_CHANGE,
            REVIEW_PENDING_CANDIDATE_AUTHORITY_UPDATE,
            BINDING_PROMOTED_AUTHORITY,
        ],
        "promotion_candidate_states": [
            "promotion_candidate_under_review",
        ],
        "promotion_outcome_states": [
            "promotion_rejected_under_existing_gate",
            "promotion_applied_as_binding_authority",
            "promotion_noop_already_authoritative",
        ],
        "observational_surfaces_allowed_to_propose": [
            "diagnostic_memory_artifacts",
            "proposal_recommendations_latest",
            "intervention_analytics_latest",
            "intervention_ledger",
            "self_structure_ledger",
            "directive_history",
        ],
        "allowed_binding_promoter_templates": list(ALLOWED_AUTHORITY_PROMOTER_TEMPLATES),
        "required_candidate_top_level_fields": list(REQUIRED_AUTHORITY_CANDIDATE_TOP_LEVEL_FIELDS),
        "promotion_requirements": [
            "candidate update must come from an explicitly allowed governance-memory promoter template",
            "candidate update must carry authority_contract, authority_surface, authority_file_summary, and resolved_current_state",
            "candidate update must keep runtime recommendations and analytics explicitly non-authoritative",
            "promotion must occur through the explicit governance-memory promotion gate rather than direct overwrite",
            "promotion must append a provenance-tagged ledger record with rollback trace",
        ],
        "governed_reopen_handoff_requirements": [
            "source governance-review outcome must be governance_review_approved_for_promotion_path",
            "promotion handoff must be promotion_pending_under_existing_gate before candidate preparation",
            "promotion candidate must remain promotion_candidate_under_review until explicit promotion gate execution",
            "canonical authority remains unchanged until the explicit promotion gate writes binding_promoted_authority",
        ],
        "gate_actor": "explicit_governance_memory_promotion_gate_v1",
        "non_authoritative_surfaces_never_promote_directly": [
            "proposal_recommendations_latest",
            "intervention_analytics_latest",
            "intervention_ledger",
            "self_structure_ledger",
        ],
        "rollback_rule": {
            "rollback_supported": True,
            "rollback_mode": "explicit_authority_promotion_rollback_only",
            "silent_replacement_disallowed": True,
        },
        "read_contract_dependency": READ_CONTRACT_SCHEMA_VERSION,
    }


def build_review_pending_authority_candidate(
    *,
    proposal: dict[str, Any],
    candidate_artifact_path: Path,
    promotion_reason: str,
) -> dict[str, Any]:
    return {
        "candidate_update_id": f"authority_candidate::{proposal['proposal_id']}",
        "candidate_generated_at": _now(),
        "candidate_state": REVIEW_PENDING_CANDIDATE_AUTHORITY_UPDATE,
        "candidate_source_template_name": str(proposal.get("template_name", "")),
        "candidate_source_proposal_id": str(proposal.get("proposal_id", "")),
        "candidate_artifact_path": str(candidate_artifact_path),
        "proposed_by_surface": "memory_summary.v4_governance_memory_authority_snapshot_v1",
        "review_status": "governance_review_pending",
        "promotion_reason": str(promotion_reason),
        "mutation_kind": "canonical_refresh_same_posture_or_explicit_governance_state_update",
    }


def _require_candidate_readiness(candidate_payload: dict[str, Any], proposal: dict[str, Any]) -> None:
    template_name = str(proposal.get("template_name", ""))
    if template_name not in ALLOWED_AUTHORITY_PROMOTER_TEMPLATES:
        raise ValueError(f"template {template_name} is not allowed to promote canonical governance authority")

    missing = [field for field in REQUIRED_AUTHORITY_CANDIDATE_TOP_LEVEL_FIELDS if field not in candidate_payload]
    if missing:
        raise ValueError(f"candidate authority update is missing required fields: {missing}")

    runtime_surfaces = dict(dict(candidate_payload.get("authority_surface", {})).get("non_authoritative_runtime_surfaces", {}))
    if bool(runtime_surfaces.get("runtime_loop_code_is_authority", True)):
        raise ValueError("candidate authority update cannot promote while runtime_loop_code_is_authority is true")


def promote_governance_memory_authority(
    *,
    candidate_payload: dict[str, Any],
    proposal: dict[str, Any],
    candidate_artifact_path: Path,
    promotion_reason: str,
) -> dict[str, Any]:
    _require_candidate_readiness(candidate_payload, proposal)
    contract = build_governance_memory_promotion_contract()
    previous_authority = _load_json_file(GOVERNANCE_MEMORY_AUTHORITY_PATH)
    previous_promotion_record = dict(previous_authority.get("authority_promotion_record", {}))

    promoted_payload = dict(candidate_payload)
    promoted_payload["authority_mutation_stage"] = BINDING_PROMOTED_AUTHORITY
    promoted_payload["authority_promotion_contract"] = contract

    promotion_record = {
        "promotion_id": f"authority_promotion::{proposal['proposal_id']}",
        "promoted_at": _now(),
        "promotion_state": BINDING_PROMOTED_AUTHORITY,
        "review_status": "governance_review_passed",
        "promoted_by_surface": "explicit_governance_memory_promotion_gate_v1",
        "source_template_name": str(proposal.get("template_name", "")),
        "source_proposal_id": str(proposal.get("proposal_id", "")),
        "source_candidate_artifact_path": str(candidate_artifact_path),
        "promotion_reason": str(promotion_reason),
        "mutation_kind": "canonical_refresh_same_posture_or_explicit_governance_state_update",
        "canonical_authority_file": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
        "previous_promotion_id": str(previous_promotion_record.get("promotion_id", "")),
        "previous_authority_stage": str(previous_authority.get("authority_mutation_stage", "")),
        "rollback_trace": {
            "rollback_supported": True,
            "rollback_mode": "explicit_authority_promotion_rollback_only",
            "previous_authority_file": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
            "previous_authority_proposal_id": str(previous_authority.get("proposal_id", "")),
            "previous_authority_artifact_path": str(previous_promotion_record.get("source_candidate_artifact_path", "")),
        },
    }
    promoted_payload["authority_promotion_record"] = promotion_record

    candidate_record = dict(promoted_payload.get("authority_candidate_record", {}))
    candidate_record["review_status"] = "governance_review_completed_promoted"
    promoted_payload["authority_candidate_record"] = candidate_record
    promoted_payload["resolved_current_state"] = resolve_governance_memory_current_state(
        governance_memory_authority_override=promoted_payload
    )

    _write_json(GOVERNANCE_MEMORY_AUTHORITY_PATH, promoted_payload)
    _append_jsonl(GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH, promotion_record)
    return promoted_payload
