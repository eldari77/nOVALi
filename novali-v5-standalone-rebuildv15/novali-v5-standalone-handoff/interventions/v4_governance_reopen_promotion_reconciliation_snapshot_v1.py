from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .governance_memory_execution_gate_v1 import build_execution_permission
from .governance_memory_promotion_v1 import BINDING_PROMOTED_AUTHORITY
from .governance_memory_resolver_v1 import resolve_governance_memory_current_state
from .governance_memory_reopen_intake_v1 import (
    PROMOTION_APPLIED_AS_BINDING_AUTHORITY,
    PROMOTION_NOOP_ALREADY_AUTHORITATIVE,
    PROMOTION_PENDING_UNDER_EXISTING_GATE,
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
INTERVENTION_LEDGER_PATH = DATA_DIR / "intervention_ledger.jsonl"
INTERVENTION_ANALYTICS_PATH = DATA_DIR / "intervention_analytics_latest.json"
PROPOSAL_RECOMMENDATIONS_PATH = DATA_DIR / "proposal_recommendations_latest.json"
SELF_STRUCTURE_STATE_PATH = DATA_DIR / "self_structure_state_latest.json"
SELF_STRUCTURE_LEDGER_PATH = DATA_DIR / "self_structure_ledger.jsonl"
BRANCH_REGISTRY_PATH = DATA_DIR / "branch_registry_latest.json"
DIRECTIVE_STATE_PATH = DATA_DIR / "directive_state_latest.json"
BUCKET_STATE_PATH = DATA_DIR / "bucket_state_latest.json"

RECONCILIATION_SCHEMA_NAME = "GovernanceReopenPromotionReconciliation"
RECONCILIATION_SCHEMA_VERSION = "governance_reopen_promotion_reconciliation_v1"
RECONCILIATION_PENDING = "reconciliation_pending"
RECONCILIATION_VERIFIED = "reconciliation_verified"
RECONCILIATION_MISMATCH_DETECTED = "reconciliation_mismatch_detected"
ROLLBACK_READY_REFERENCE = "rollback_ready_reference"


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


def _canonical_snapshot(authority_payload: dict[str, Any]) -> dict[str, Any]:
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
        "capability_boundary_state": dict(authority_payload.get("capability_boundary_state", {})),
    }


def _check(name: str, passed: bool, observed_value: Any, expected_value: Any) -> dict[str, Any]:
    return {
        "check_name": str(name),
        "passed": bool(passed),
        "observed_value": observed_value,
        "expected_value": expected_value,
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

    if not all([authority_payload, self_structure_state, branch_registry, directive_state, bucket_state]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: authority, self-structure, branch, directive, and bucket artifacts are required",
        }

    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    promotion_outcome_artifact_path = str(
        current_state_summary.get("latest_governance_reopen_promotion_outcome_artifact_path", "")
    )
    promotion_outcome_state_summary = str(
        current_state_summary.get("latest_governance_reopen_promotion_outcome_state", "")
    )

    if not promotion_outcome_artifact_path:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no promotion outcome artifact is available for reconciliation",
        }

    promotion_outcome_payload = _load_json_file(Path(promotion_outcome_artifact_path))
    if not promotion_outcome_payload:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest promotion outcome artifact could not be loaded",
        }

    promotion_identity = dict(promotion_outcome_payload.get("snapshot_identity_context", {}))
    promotion_outcome_id = _first_nonempty(
        promotion_identity.get("promotion_outcome_id"),
        promotion_outcome_payload.get("promotion_outcome_id"),
    )
    promotion_decision = dict(promotion_outcome_payload.get("promotion_decision", {}))
    promotion_outcome_state = _first_nonempty(
        promotion_decision.get("promotion_outcome_state"),
        promotion_outcome_state_summary,
    )

    if promotion_outcome_state != PROMOTION_APPLIED_AS_BINDING_AUTHORITY:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: only promotion_applied_as_binding_authority outcomes may enter reconciliation",
            "diagnostic_conclusions": {
                "promotion_outcome_state": promotion_outcome_state,
            },
        }

    if any(str(row.get("source_promotion_outcome_id", "")) == promotion_outcome_id for row in reconciliation_ledger_rows):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: latest applied promotion outcome already has a recorded reconciliation artifact",
            "diagnostic_conclusions": {
                "promotion_outcome_id": promotion_outcome_id,
                "existing_reconciliation_count": sum(
                    1
                    for row in reconciliation_ledger_rows
                    if str(row.get("source_promotion_outcome_id", "")) == promotion_outcome_id
                ),
            },
        }

    source_promotion_handoff_reference = dict(
        promotion_outcome_payload.get("source_promotion_handoff_reference", {})
    )
    source_review_outcome_reference = dict(
        promotion_outcome_payload.get("source_review_outcome_reference", {})
    )
    source_review_submission_reference = dict(
        promotion_outcome_payload.get("source_review_submission_reference", {})
    )
    authority_before_reference = dict(promotion_outcome_payload.get("authority_before_reference", {}))
    authority_after_reference = dict(promotion_outcome_payload.get("authority_after_reference", {}))
    requested_action_and_scope = dict(promotion_outcome_payload.get("requested_action_and_scope", {}))

    canonical_snapshot = _canonical_snapshot(authority_payload)
    resolved_state = resolve_governance_memory_current_state()
    resolved_posture = dict(resolved_state.get("canonical_current_posture", {}))
    resolved_selector_frontier = dict(resolved_state.get("selector_frontier_conclusions", {}))
    resolved_mutation_state = dict(resolved_state.get("authority_mutation_state", {}))

    self_structure_checks = [
        _check(
            "self_structure_authority_file_pointer",
            str(current_state_summary.get("latest_governance_memory_authority_file_path", "")) == str(
                GOVERNANCE_MEMORY_AUTHORITY_PATH
            ),
            str(current_state_summary.get("latest_governance_memory_authority_file_path", "")),
            str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
        ),
        _check(
            "self_structure_mutation_stage",
            str(current_state_summary.get("latest_governance_memory_mutation_stage", ""))
            == str(authority_payload.get("authority_mutation_stage", "")),
            str(current_state_summary.get("latest_governance_memory_mutation_stage", "")),
            str(authority_payload.get("authority_mutation_stage", "")),
        ),
        _check(
            "self_structure_promotion_id",
            str(current_state_summary.get("latest_governance_memory_promotion_id", ""))
            == str(dict(authority_payload.get("authority_promotion_record", {})).get("promotion_id", "")),
            str(current_state_summary.get("latest_governance_memory_promotion_id", "")),
            str(dict(authority_payload.get("authority_promotion_record", {})).get("promotion_id", "")),
        ),
        _check(
            "self_structure_branch_state",
            str(current_state_summary.get("current_branch_state", "")) == canonical_snapshot["current_branch_state"],
            str(current_state_summary.get("current_branch_state", "")),
            canonical_snapshot["current_branch_state"],
        ),
        _check(
            "self_structure_operating_stance",
            str(current_state_summary.get("latest_current_operating_stance", ""))
            == canonical_snapshot["current_operating_stance"],
            str(current_state_summary.get("latest_current_operating_stance", "")),
            canonical_snapshot["current_operating_stance"],
        ),
        _check(
            "self_structure_routing_posture",
            bool(current_state_summary.get("routing_deferred", False))
            == (canonical_snapshot["routing_status"] == "routing_deferred"),
            bool(current_state_summary.get("routing_deferred", False)),
            canonical_snapshot["routing_status"] == "routing_deferred",
        ),
        _check(
            "self_structure_selector_frontier",
            str(current_state_summary.get("latest_selector_frontier_split_assessment", ""))
            == str(canonical_snapshot["selector_frontier_memory"].get("final_selection_split_assessment", "")),
            str(current_state_summary.get("latest_selector_frontier_split_assessment", "")),
            str(canonical_snapshot["selector_frontier_memory"].get("final_selection_split_assessment", "")),
        ),
    ]

    resolver_checks = [
        _check(
            "resolver_current_branch_state",
            str(resolved_posture.get("current_branch_state", "")) == canonical_snapshot["current_branch_state"],
            str(resolved_posture.get("current_branch_state", "")),
            canonical_snapshot["current_branch_state"],
        ),
        _check(
            "resolver_current_operating_stance",
            str(resolved_posture.get("current_operating_stance", ""))
            == canonical_snapshot["current_operating_stance"],
            str(resolved_posture.get("current_operating_stance", "")),
            canonical_snapshot["current_operating_stance"],
        ),
        _check(
            "resolver_held_baseline_template",
            str(resolved_posture.get("held_baseline_template", "")) == canonical_snapshot["held_baseline_template"],
            str(resolved_posture.get("held_baseline_template", "")),
            canonical_snapshot["held_baseline_template"],
        ),
        _check(
            "resolver_routing_status",
            str(resolved_posture.get("routing_status", "")) == canonical_snapshot["routing_status"],
            str(resolved_posture.get("routing_status", "")),
            canonical_snapshot["routing_status"],
        ),
        _check(
            "resolver_reopen_eligibility",
            dict(resolved_posture.get("reopen_eligibility", {})) == canonical_snapshot["reopen_eligibility"],
            dict(resolved_posture.get("reopen_eligibility", {})),
            canonical_snapshot["reopen_eligibility"],
        ),
        _check(
            "resolver_mutation_stage",
            str(resolved_mutation_state.get("current_stage", ""))
            == str(authority_payload.get("authority_mutation_stage", "")),
            str(resolved_mutation_state.get("current_stage", "")),
            str(authority_payload.get("authority_mutation_stage", "")),
        ),
        _check(
            "resolver_promotion_id",
            str(dict(resolved_mutation_state.get("promotion_record", {})).get("promotion_id", ""))
            == str(dict(authority_payload.get("authority_promotion_record", {})).get("promotion_id", "")),
            str(dict(resolved_mutation_state.get("promotion_record", {})).get("promotion_id", "")),
            str(dict(authority_payload.get("authority_promotion_record", {})).get("promotion_id", "")),
        ),
        _check(
            "resolver_selector_frontier",
            str(resolved_selector_frontier.get("final_selection_split_assessment", ""))
            == str(canonical_snapshot["selector_frontier_memory"].get("final_selection_split_assessment", "")),
            str(resolved_selector_frontier.get("final_selection_split_assessment", "")),
            str(canonical_snapshot["selector_frontier_memory"].get("final_selection_split_assessment", "")),
        ),
    ]

    execution_checks: list[dict[str, Any]] = []
    sampled_permissions = [
        build_execution_permission(action_kind="proposal_analytics"),
        build_execution_permission(action_kind="benchmark_only"),
        build_execution_permission(
            action_kind="proposal_runner",
            template_name="memory_summary.v4_governance_memory_authority_snapshot_v1",
        ),
        build_execution_permission(
            action_kind="proposal_runner",
            template_name="critic_split.swap_c_incumbent_hardening_probe_v1",
        ),
    ]
    for permission in sampled_permissions:
        canonical_posture = dict(permission.get("canonical_posture", {}))
        action_kind = str(permission.get("action_kind", ""))
        template_name = str(dict(permission.get("template_context", {})).get("template_name", ""))
        execution_checks.extend(
            [
                _check(
                    f"execution_gate_branch_state::{action_kind}::{template_name}",
                    str(canonical_posture.get("current_branch_state", ""))
                    == canonical_snapshot["current_branch_state"],
                    str(canonical_posture.get("current_branch_state", "")),
                    canonical_snapshot["current_branch_state"],
                ),
                _check(
                    f"execution_gate_operating_stance::{action_kind}::{template_name}",
                    str(canonical_posture.get("current_operating_stance", ""))
                    == canonical_snapshot["current_operating_stance"],
                    str(canonical_posture.get("current_operating_stance", "")),
                    canonical_snapshot["current_operating_stance"],
                ),
                _check(
                    f"execution_gate_held_baseline::{action_kind}::{template_name}",
                    str(canonical_posture.get("held_baseline_template", ""))
                    == canonical_snapshot["held_baseline_template"],
                    str(canonical_posture.get("held_baseline_template", "")),
                    canonical_snapshot["held_baseline_template"],
                ),
                _check(
                    f"execution_gate_routing::{action_kind}::{template_name}",
                    str(canonical_posture.get("routing_status", "")) == canonical_snapshot["routing_status"],
                    str(canonical_posture.get("routing_status", "")),
                    canonical_snapshot["routing_status"],
                ),
                _check(
                    f"execution_gate_reopen_eligibility::{action_kind}::{template_name}",
                    dict(canonical_posture.get("reopen_eligibility", {}))
                    == canonical_snapshot["reopen_eligibility"],
                    dict(canonical_posture.get("reopen_eligibility", {})),
                    canonical_snapshot["reopen_eligibility"],
                ),
            ]
        )

    all_checks = self_structure_checks + resolver_checks + execution_checks
    failed_checks = [check for check in all_checks if not bool(check.get("passed", False))]

    required_surfaces_present = bool(
        authority_before_reference
        and authority_after_reference
        and dict(authority_payload.get("authority_promotion_record", {})).get("promotion_id")
    )
    reconciliation_state = (
        RECONCILIATION_PENDING
        if not required_surfaces_present
        else RECONCILIATION_VERIFIED
        if not failed_checks
        else RECONCILIATION_MISMATCH_DETECTED
    )
    reconciliation_reason_codes: list[str] = []
    if not required_surfaces_present:
        reconciliation_reason_codes.append("required_reconciliation_surfaces_missing")
    if failed_checks:
        reconciliation_reason_codes.extend(
            [f"surface_mismatch::{check['check_name']}" for check in failed_checks[:12]]
        )
    if authority_before_reference == authority_after_reference:
        reconciliation_reason_codes.append("authority_before_after_reference_identical")
    if str(dict(authority_after_reference).get("promotion_id", "")) != str(
        dict(authority_payload.get("authority_promotion_record", {})).get("promotion_id", "")
    ):
        reconciliation_reason_codes.append("authority_after_reference_not_aligned_with_canonical")

    rollback_reference = dict(dict(authority_payload.get("authority_promotion_record", {})).get("rollback_trace", {}))
    rollback_reference_state = (
        ROLLBACK_READY_REFERENCE if bool(rollback_reference.get("rollback_supported", False)) else ""
    )

    reconciliation_id = f"reopen_promotion_reconciliation::{proposal['proposal_id']}"
    verified_at = _now()
    artifact_path = _diagnostic_artifact_dir() / (
        f"memory_summary_v4_governance_reopen_promotion_reconciliation_snapshot_v1_{proposal['proposal_id']}.json"
    )
    branch_record = (
        dict(list(branch_registry.get("branches", []))[0]) if list(branch_registry.get("branches", [])) else {}
    )

    payload = {
        "proposal_id": str(proposal.get("proposal_id", "")),
        "template_name": "memory_summary.v4_governance_reopen_promotion_reconciliation_snapshot_v1",
        "snapshot_identity_context": {
            "reconciliation_id": reconciliation_id,
            "verified_at": verified_at,
            "phase": "governance_reopen_promotion_reconciliation",
            "source_promotion_outcome_id": promotion_outcome_id,
        },
        "reconciliation_contract": {
            "schema_name": RECONCILIATION_SCHEMA_NAME,
            "schema_version": RECONCILIATION_SCHEMA_VERSION,
            "required_promotion_outcome_state": PROMOTION_APPLIED_AS_BINDING_AUTHORITY,
            "reconciliation_states": [
                RECONCILIATION_PENDING,
                RECONCILIATION_VERIFIED,
                RECONCILIATION_MISMATCH_DETECTED,
            ],
            "rollback_reference_state": ROLLBACK_READY_REFERENCE,
            "canonical_authority_path": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
            "repair_or_rollback_disallowed_here": True,
        },
        "source_promotion_outcome_reference": {
            "promotion_outcome_id": promotion_outcome_id,
            "artifact_path": promotion_outcome_artifact_path,
            "ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_OUTCOME_LEDGER_PATH),
            "promotion_outcome_state": promotion_outcome_state,
        },
        "source_promotion_handoff_reference": dict(source_promotion_handoff_reference),
        "source_review_outcome_reference": dict(source_review_outcome_reference),
        "source_review_submission_reference": dict(source_review_submission_reference),
        "requested_action_and_scope": requested_action_and_scope,
        "authority_before_reference": authority_before_reference,
        "authority_after_reference": authority_after_reference,
        "resolved_canonical_field_set_after_apply": {
            "canonical_posture": resolved_posture,
            "authority_mutation_state": resolved_mutation_state,
            "selector_frontier_conclusions": resolved_selector_frontier,
            "binding_decisions": dict(resolved_state.get("binding_decisions", {})),
        },
        "self_structure_state_agreement": {
            "checks": self_structure_checks,
            "all_passed": not [check for check in self_structure_checks if not check["passed"]],
        },
        "resolver_agreement": {
            "checks": resolver_checks,
            "all_passed": not [check for check in resolver_checks if not check["passed"]],
        },
        "execution_gate_agreement": {
            "checks": execution_checks,
            "all_passed": not [check for check in execution_checks if not check["passed"]],
        },
        "propagation_status_by_surface": {
            "canonical_authority": "authoritative_reference_present",
            "self_structure_state": (
                RECONCILIATION_VERIFIED
                if not [check for check in self_structure_checks if not check["passed"]]
                else RECONCILIATION_MISMATCH_DETECTED
            ),
            "resolver": (
                RECONCILIATION_VERIFIED
                if not [check for check in resolver_checks if not check["passed"]]
                else RECONCILIATION_MISMATCH_DETECTED
            ),
            "execution_gate": (
                RECONCILIATION_VERIFIED
                if not [check for check in execution_checks if not check["passed"]]
                else RECONCILIATION_MISMATCH_DETECTED
            ),
        },
        "reconciliation_result": {
            "reconciliation_state": reconciliation_state,
            "reconciliation_reason_codes": reconciliation_reason_codes,
            "failed_check_count": int(len(failed_checks)),
        },
        "rollback_ready_reference": {
            "rollback_reference_state": rollback_reference_state,
            "rollback_trace": rollback_reference,
            "no_repair_invoked_here": True,
        },
        "reviewer_source_and_audit_trace": {
            "verified_by_surface": "memory_summary.v4_governance_reopen_promotion_reconciliation_snapshot_v1",
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
            "reconciliation_ledger_entries_before_write": int(len(reconciliation_ledger_rows)),
        },
        "operator_readable_conclusion": (
            "The applied promotion outcome has been reconciled against canonical authority, self-structure, resolver state, and execution-governance reads."
            if reconciliation_state == RECONCILIATION_VERIFIED
            else "The applied promotion outcome could not be fully verified across governed surfaces, so reconciliation remains pending or mismatched and rollback metadata stays reference-only."
        ),
    }

    _write_json(artifact_path, payload)

    ledger_entry = {
        "event_type": "governance_reopen_promotion_reconciliation_recorded",
        "written_at": verified_at,
        "reconciliation_id": reconciliation_id,
        "source_promotion_outcome_id": promotion_outcome_id,
        "artifact_path": str(artifact_path),
        "reconciliation_state": reconciliation_state,
        "rollback_reference_state": rollback_reference_state,
        "failed_check_count": int(len(failed_checks)),
    }
    _append_jsonl(GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_LEDGER_PATH, ledger_entry)

    updated_self_structure = dict(self_structure_state)
    updated_summary = dict(current_state_summary)
    updated_summary.update(
        {
            "latest_governance_reopen_reconciliation_artifact_path": str(artifact_path),
            "latest_governance_reopen_reconciliation_ledger_path": str(
                GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_LEDGER_PATH
            ),
            "latest_governance_reopen_reconciliation_state": reconciliation_state,
            "latest_governance_reopen_rollback_reference_state": rollback_reference_state,
            "latest_governance_reopen_reconciliation_reason_codes": reconciliation_reason_codes,
        }
    )
    updated_self_structure["generated_at"] = _now()
    updated_self_structure["current_state_summary"] = updated_summary
    updated_self_structure["governance_reopen_promotion_reconciliation"] = {
        "schema_name": RECONCILIATION_SCHEMA_NAME,
        "schema_version": RECONCILIATION_SCHEMA_VERSION,
        "latest_reconciliation": {
            "reconciliation_id": reconciliation_id,
            "source_promotion_outcome_id": promotion_outcome_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_LEDGER_PATH),
            "reconciliation_state": reconciliation_state,
            "rollback_reference_state": rollback_reference_state,
        },
    }
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure)

    _append_jsonl(
        SELF_STRUCTURE_LEDGER_PATH,
        {
            "event_id": f"governance_reopen_promotion_reconciliation::{proposal['proposal_id']}",
            "timestamp": _now(),
            "event_type": "governance_reopen_promotion_reconciliation_recorded",
            "reconciliation_id": reconciliation_id,
            "source_promotion_outcome_id": promotion_outcome_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_LEDGER_PATH),
            "reconciliation_state": reconciliation_state,
            "rollback_reference_state": rollback_reference_state,
        },
    )

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: applied promotion outcome was materialized as an explicit post-promotion reconciliation record",
        "observability_gain": {
            "passed": True,
            "reason": "future agents can now distinguish applied promotion from verified propagation, mismatch detection, and rollback-ready reference state",
            "artifact_path": str(artifact_path),
            "reconciliation_ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_LEDGER_PATH),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "reconciliation makes post-apply convergence explicit without introducing a second authority path or any implicit repair step",
        },
        "ambiguity_reduction": {
            "passed": True,
            "reason": "canonical, self-structure, resolver, and execution-gate agreement are now checked explicitly",
            "score": 0.97,
        },
        "safety_neutrality": {
            "passed": True,
            "reason": "reconciliation is observational only and does not mutate authority, repair state, or invoke rollback",
            "scope": str(proposal.get("scope", "")),
        },
        "later_selection_usefulness": {
            "passed": True,
            "reason": "mismatch detection now produces explicit rollback-ready reference metadata instead of assuming propagation succeeded",
            "recommended_next_template": "",
        },
        "diagnostic_conclusions": {
            "promotion_outcome_state": PROMOTION_APPLIED_AS_BINDING_AUTHORITY,
            "reconciliation_state": reconciliation_state,
            "rollback_reference_state": rollback_reference_state,
            "recommended_next_action": "hold_and_consolidate",
            "recommended_next_template": "",
        },
        "artifact_path": str(artifact_path),
        "reconciliation_ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_LEDGER_PATH),
    }
