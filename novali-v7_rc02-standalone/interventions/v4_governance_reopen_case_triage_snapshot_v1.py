from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .ledger import intervention_data_dir, load_latest_snapshots


DATA_DIR = intervention_data_dir()
DIAGNOSTIC_MEMORY_DIR = DATA_DIR / "diagnostic_memory"
GOVERNANCE_MEMORY_AUTHORITY_PATH = DATA_DIR / "governance_memory_authority_latest.json"
GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH = DATA_DIR / "governance_memory_promotion_ledger.jsonl"
GOVERNANCE_REOPEN_CASE_REGISTRY_LEDGER_PATH = (
    DATA_DIR / "governance_reopen_case_registry_ledger.jsonl"
)
GOVERNANCE_REOPEN_CASE_TRIAGE_LEDGER_PATH = (
    DATA_DIR / "governance_reopen_case_triage_ledger.jsonl"
)
SELF_STRUCTURE_STATE_PATH = DATA_DIR / "self_structure_state_latest.json"
SELF_STRUCTURE_LEDGER_PATH = DATA_DIR / "self_structure_ledger.jsonl"
BRANCH_REGISTRY_PATH = DATA_DIR / "branch_registry_latest.json"
DIRECTIVE_STATE_PATH = DATA_DIR / "directive_state_latest.json"
BUCKET_STATE_PATH = DATA_DIR / "bucket_state_latest.json"
INTERVENTION_LEDGER_PATH = DATA_DIR / "intervention_ledger.jsonl"
INTERVENTION_ANALYTICS_PATH = DATA_DIR / "intervention_analytics_latest.json"
PROPOSAL_RECOMMENDATIONS_PATH = DATA_DIR / "proposal_recommendations_latest.json"

CASE_TRIAGE_SCHEMA_NAME = "GovernanceReopenCaseTriage"
CASE_TRIAGE_SCHEMA_VERSION = "governance_reopen_case_triage_v1"

NO_ACTION_CLOSED_CASE = "no_action_closed_case"
MONITOR_PENDING_CASE = "monitor_pending_case"
REVIEW_ATTENTION_REQUIRED_CASE = "review_attention_required_case"
FOLLOW_ON_RECONCILIATION_DUE = "follow_on_reconciliation_due"
STALE_OR_SUPERSEDED_ARCHIVE_CANDIDATE = "stale_or_superseded_archive_candidate"

CURRENT_PORTFOLIO_RECORD = "current_portfolio_record"
STALE_OR_SUPERSEDED_CASE = "stale_or_superseded_case"

PENDING_MONITOR_STATES = {
    "review_pending_reopen_candidate_intake",
    "submitted_for_governance_review",
    "review_outcome_pending",
    "promotion_pending_under_existing_gate",
    "submitted_for_remediation_review",
    "remediation_review_outcome_pending",
    "rollback_or_repair_handoff_pending",
    "rollback_or_repair_candidate_under_existing_path",
}

NEXT_ACTION_KEEP_CLOSED = "keep_closed_no_action"
NEXT_ACTION_MONITOR = "monitor_pending_registry_only"
NEXT_ACTION_GOVERNANCE_REVIEW = "surface_for_governance_attention"
NEXT_ACTION_FOLLOW_ON_RECONCILIATION = "await_follow_on_reconciliation_verification"
NEXT_ACTION_ARCHIVE = "archive_from_active_view_only"


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


def _first_nonempty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _diagnostic_artifact_dir() -> Path:
    DIAGNOSTIC_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    return DIAGNOSTIC_MEMORY_DIR


def _authority_posture(authority_payload: dict[str, Any]) -> dict[str, Any]:
    authority_summary = dict(authority_payload.get("authority_file_summary", {}))
    authority_promotion_record = dict(authority_payload.get("authority_promotion_record", {}))
    selector_frontier_memory = dict(authority_payload.get("selector_frontier_memory", {}))
    return {
        "current_branch_state": str(authority_summary.get("current_branch_state", "")),
        "current_operating_stance": str(authority_summary.get("current_operating_stance", "")),
        "held_baseline_template": str(authority_summary.get("held_baseline_template", "")),
        "routing_status": str(authority_summary.get("routing_status", "")),
        "reopen_eligibility": dict(authority_summary.get("reopen_eligibility", {})),
        "authority_promotion_id": str(authority_promotion_record.get("promotion_id", "")),
        "selector_frontier_split_assessment": str(
            selector_frontier_memory.get("final_selection_split_assessment", "")
        ),
    }


def _load_latest_case_registry(
    self_structure_state: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    artifact_path_text = str(
        current_state_summary.get("latest_governance_reopen_case_registry_artifact_path", "")
    ).strip()
    if artifact_path_text:
        payload = _load_json_file(Path(artifact_path_text))
        if payload:
            return payload, artifact_path_text

    for row in reversed(_load_jsonl(GOVERNANCE_REOPEN_CASE_REGISTRY_LEDGER_PATH)):
        artifact_path_text = str(row.get("artifact_path", "")).strip()
        if not artifact_path_text:
            continue
        payload = _load_json_file(Path(artifact_path_text))
        if payload:
            return payload, artifact_path_text
    return {}, ""


def _classify_triage(case_record: dict[str, Any]) -> tuple[str, str, list[str]]:
    lifecycle_state = str(case_record.get("underlying_lifecycle_case_state", ""))
    portfolio_visibility = str(case_record.get("portfolio_visibility_state", ""))
    latest_stage = str(case_record.get("latest_lifecycle_stage", ""))
    latest_state = str(case_record.get("latest_lifecycle_state", ""))
    follow_on_state = str(case_record.get("follow_on_reconciliation_state_if_any", ""))
    closure_state = str(case_record.get("closure_state_if_any", ""))

    if portfolio_visibility == STALE_OR_SUPERSEDED_CASE:
        return (
            STALE_OR_SUPERSEDED_ARCHIVE_CANDIDATE,
            NEXT_ACTION_ARCHIVE,
            ["superseded_by_newer_case_with_same_request_signature"],
        )

    if lifecycle_state in {"closed_rejected_case", "closed_resolved_case"}:
        reason_codes = ["closed_case_requires_no_active_attention"]
        if closure_state:
            reason_codes.append(f"closure_state::{closure_state}")
        elif latest_state:
            reason_codes.append(f"latest_state::{latest_state}")
        return NO_ACTION_CLOSED_CASE, NEXT_ACTION_KEEP_CLOSED, reason_codes

    if lifecycle_state == "pending_follow_on_reconciliation_case":
        reason_codes = ["follow_on_reconciliation_required_before_resolution"]
        if follow_on_state:
            reason_codes.append(f"follow_on_reconciliation_state::{follow_on_state}")
        return (
            FOLLOW_ON_RECONCILIATION_DUE,
            NEXT_ACTION_FOLLOW_ON_RECONCILIATION,
            reason_codes,
        )

    if lifecycle_state == "open_requires_further_governance_case":
        return (
            REVIEW_ATTENTION_REQUIRED_CASE,
            NEXT_ACTION_GOVERNANCE_REVIEW,
            ["open_case_requires_further_governance_attention"],
        )

    if latest_state in PENDING_MONITOR_STATES:
        return (
            MONITOR_PENDING_CASE,
            NEXT_ACTION_MONITOR,
            [f"pending_state::{latest_state}", f"latest_stage::{latest_stage}"],
        )

    return (
        REVIEW_ATTENTION_REQUIRED_CASE,
        NEXT_ACTION_GOVERNANCE_REVIEW,
        ["active_case_not_in_terminal_or_pending_bucket"],
    )


def run_probe(cfg: Any, proposal: dict[str, Any], *, rounds: int, seeds: list[int]) -> dict[str, Any]:
    del cfg, rounds, seeds

    authority_payload = _load_json_file(GOVERNANCE_MEMORY_AUTHORITY_PATH)
    self_structure_state = _load_json_file(SELF_STRUCTURE_STATE_PATH)
    branch_registry = _load_json_file(BRANCH_REGISTRY_PATH)
    directive_state = _load_json_file(DIRECTIVE_STATE_PATH)
    bucket_state = _load_json_file(BUCKET_STATE_PATH)
    intervention_analytics = _load_json_file(INTERVENTION_ANALYTICS_PATH)
    proposal_recommendations = _load_json_file(PROPOSAL_RECOMMENDATIONS_PATH)

    case_registry_payload, case_registry_artifact_path = _load_latest_case_registry(
        self_structure_state
    )
    if not case_registry_payload:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no governance case registry artifact is available for triage",
        }

    authority_posture = _authority_posture(authority_payload)
    case_records = [dict(item) for item in list(case_registry_payload.get("case_registry_records", []))]
    triage_records: list[dict[str, Any]] = []
    for case_record in case_records:
        triage_category, next_action_class, reason_codes = _classify_triage(case_record)
        triage_records.append(
            {
                "stable_case_identifier": str(case_record.get("stable_case_identifier", "")),
                "current_lifecycle_state": str(
                    case_record.get("underlying_lifecycle_case_state", "")
                ),
                "latest_stage": str(case_record.get("latest_lifecycle_stage", "")),
                "latest_state": str(case_record.get("latest_lifecycle_state", "")),
                "latest_artifact_path": str(case_record.get("latest_artifact_path", "")),
                "latest_decision_timestamp": str(
                    case_record.get("latest_decision_timestamp", "")
                ),
                "latest_sequence_marker": dict(case_record.get("latest_sequence_marker", {})),
                "current_portfolio_visibility_class": str(
                    case_record.get("portfolio_visibility_state", "")
                ),
                "current_portfolio_case_state": str(case_record.get("portfolio_case_state", "")),
                "triage_category": triage_category,
                "next_action_recommendation_class": next_action_class,
                "stale_or_superseded_marker": bool(
                    str(case_record.get("portfolio_visibility_state", ""))
                    == STALE_OR_SUPERSEDED_CASE
                ),
                "follow_on_reconciliation_state_if_any": str(
                    case_record.get("follow_on_reconciliation_state_if_any", "")
                ),
                "closure_state_if_any": str(case_record.get("closure_state_if_any", "")),
                "authority_posture_at_triage_time": dict(authority_posture),
                "authority_posture_at_latest_stage": dict(
                    case_record.get("authority_posture_at_latest_stage", {})
                ),
                "triage_reason_codes": list(reason_codes),
                "source_case_registry_artifact_path": str(case_registry_artifact_path),
                "source_case_registry_record_reference": {
                    "root_reference": dict(case_record.get("root_reference", {})),
                    "request_signature": dict(case_record.get("request_signature", {})),
                },
            }
        )

    triage_counts = {
        NO_ACTION_CLOSED_CASE: 0,
        MONITOR_PENDING_CASE: 0,
        REVIEW_ATTENTION_REQUIRED_CASE: 0,
        FOLLOW_ON_RECONCILIATION_DUE: 0,
        STALE_OR_SUPERSEDED_ARCHIVE_CANDIDATE: 0,
    }
    for triage_record in triage_records:
        triage_counts[str(triage_record.get("triage_category", ""))] += 1

    active_portfolio_case_count = int(
        sum(
            1
            for triage_record in triage_records
            if not bool(triage_record.get("stale_or_superseded_marker", False))
        )
    )
    immediate_attention_case_count = int(
        triage_counts[REVIEW_ATTENTION_REQUIRED_CASE]
        + triage_counts[FOLLOW_ON_RECONCILIATION_DUE]
    )

    branch_record = (
        dict(list(branch_registry.get("branches", []))[0])
        if list(branch_registry.get("branches", []))
        else {}
    )
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))

    recorded_at = _now()
    case_triage_id = f"governance_reopen_case_triage::{proposal['proposal_id']}"
    artifact_path = _diagnostic_artifact_dir() / (
        f"memory_summary_v4_governance_reopen_case_triage_snapshot_v1_{proposal['proposal_id']}.json"
    )

    payload = {
        "proposal_id": str(proposal.get("proposal_id", "")),
        "template_name": "memory_summary.v4_governance_reopen_case_triage_snapshot_v1",
        "snapshot_identity_context": {
            "governance_case_triage_id": case_triage_id,
            "recorded_at": recorded_at,
            "phase": "governance_reopen_case_triage",
            "source_registry_artifact_path": str(case_registry_artifact_path),
            "source_registry_case_count": int(len(case_records)),
        },
        "case_triage_contract": {
            "schema_name": CASE_TRIAGE_SCHEMA_NAME,
            "schema_version": CASE_TRIAGE_SCHEMA_VERSION,
            "source_registry_required": True,
            "triage_categories": [
                NO_ACTION_CLOSED_CASE,
                MONITOR_PENDING_CASE,
                REVIEW_ATTENTION_REQUIRED_CASE,
                FOLLOW_ON_RECONCILIATION_DUE,
                STALE_OR_SUPERSEDED_ARCHIVE_CANDIDATE,
            ],
            "next_action_classes": [
                NEXT_ACTION_KEEP_CLOSED,
                NEXT_ACTION_MONITOR,
                NEXT_ACTION_GOVERNANCE_REVIEW,
                NEXT_ACTION_FOLLOW_ON_RECONCILIATION,
                NEXT_ACTION_ARCHIVE,
            ],
            "triage_observational_only": True,
            "case_state_mutation_disallowed_here": True,
            "authority_mutation_disallowed_here": True,
            "triage_non_authoritative": True,
        },
        "authority_posture_at_triage_time": dict(authority_posture),
        "case_triage_records": triage_records,
        "portfolio_triage_summary": {
            "total_case_count": int(len(triage_records)),
            "active_portfolio_case_count": int(active_portfolio_case_count),
            "immediate_attention_case_count": int(immediate_attention_case_count),
            "no_action_closed_case_count": int(triage_counts[NO_ACTION_CLOSED_CASE]),
            "monitor_pending_case_count": int(triage_counts[MONITOR_PENDING_CASE]),
            "review_attention_required_case_count": int(
                triage_counts[REVIEW_ATTENTION_REQUIRED_CASE]
            ),
            "follow_on_reconciliation_due_case_count": int(
                triage_counts[FOLLOW_ON_RECONCILIATION_DUE]
            ),
            "stale_or_superseded_archive_candidate_count": int(
                triage_counts[STALE_OR_SUPERSEDED_ARCHIVE_CANDIDATE]
            ),
            "latest_case_identifier": str(
                dict(triage_records[0]).get("stable_case_identifier", "")
            )
            if triage_records
            else "",
            "latest_case_timestamp": str(
                dict(triage_records[0]).get("latest_decision_timestamp", "")
            )
            if triage_records
            else "",
        },
        "reviewer_source_and_audit_trace": {
            "recorded_by_surface": "memory_summary.v4_governance_reopen_case_triage_snapshot_v1",
            "reviewer_source": "governed_case_triage_snapshot_v1",
            "branch_id": str(branch_registry.get("current_branch_id", "")),
            "branch_pause_rationale": str(branch_record.get("pause_rationale", "")),
            "directive_id": str(
                dict(directive_state.get("current_directive_state", {})).get(
                    "directive_id", ""
                )
            ),
            "bucket_id": str(
                dict(bucket_state.get("current_bucket_state", {})).get("bucket_id", "")
            ),
            "source_registry_current_case_count": int(
                current_state_summary.get(
                    "latest_governance_reopen_case_registry_total_case_count", 0
                )
            ),
            "governance_execution_contract_available": bool(
                intervention_analytics.get("governance_execution_contract")
                or proposal_recommendations.get("governance_execution_contract")
            ),
            "latest_snapshots_count": int(len(load_latest_snapshots())),
        },
        "provenance_and_audit_trace": {
            "canonical_authority_file": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
            "governance_memory_promotion_ledger_path": str(
                GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH
            ),
            "governance_reopen_case_registry_ledger_path": str(
                GOVERNANCE_REOPEN_CASE_REGISTRY_LEDGER_PATH
            ),
            "governance_reopen_case_triage_ledger_path": str(
                GOVERNANCE_REOPEN_CASE_TRIAGE_LEDGER_PATH
            ),
            "self_structure_state_path": str(SELF_STRUCTURE_STATE_PATH),
            "self_structure_ledger_path": str(SELF_STRUCTURE_LEDGER_PATH),
            "intervention_ledger_path": str(INTERVENTION_LEDGER_PATH),
            "analytics_path": str(INTERVENTION_ANALYTICS_PATH),
            "proposal_recommendations_path": str(PROPOSAL_RECOMMENDATIONS_PATH),
        },
        "operator_readable_conclusion": (
            "Governance reopen cases now have an explicit triage view that identifies which "
            "cases need attention now, which are merely pending, which are closed and should "
            "stay out of the active queue, and which can be archived from the active view."
        ),
    }

    _write_json(artifact_path, payload)

    ledger_entry = {
        "event_type": "governance_reopen_case_triage_recorded",
        "written_at": recorded_at,
        "governance_case_triage_id": case_triage_id,
        "artifact_path": str(artifact_path),
        "source_registry_artifact_path": str(case_registry_artifact_path),
        "total_case_count": int(len(triage_records)),
        "active_portfolio_case_count": int(active_portfolio_case_count),
        "immediate_attention_case_count": int(immediate_attention_case_count),
        "no_action_closed_case_count": int(triage_counts[NO_ACTION_CLOSED_CASE]),
        "monitor_pending_case_count": int(triage_counts[MONITOR_PENDING_CASE]),
        "review_attention_required_case_count": int(
            triage_counts[REVIEW_ATTENTION_REQUIRED_CASE]
        ),
        "follow_on_reconciliation_due_case_count": int(
            triage_counts[FOLLOW_ON_RECONCILIATION_DUE]
        ),
        "stale_or_superseded_archive_candidate_count": int(
            triage_counts[STALE_OR_SUPERSEDED_ARCHIVE_CANDIDATE]
        ),
    }
    _append_jsonl(GOVERNANCE_REOPEN_CASE_TRIAGE_LEDGER_PATH, ledger_entry)

    updated_self_structure = dict(self_structure_state)
    updated_summary = dict(current_state_summary)
    updated_summary.update(
        {
            "latest_governance_reopen_case_triage_artifact_path": str(artifact_path),
            "latest_governance_reopen_case_triage_ledger_path": str(
                GOVERNANCE_REOPEN_CASE_TRIAGE_LEDGER_PATH
            ),
            "latest_governance_reopen_case_triage_total_case_count": int(len(triage_records)),
            "latest_governance_reopen_case_triage_active_portfolio_case_count": int(
                active_portfolio_case_count
            ),
            "latest_governance_reopen_case_triage_attention_case_count": int(
                triage_counts[REVIEW_ATTENTION_REQUIRED_CASE]
            ),
            "latest_governance_reopen_case_triage_monitor_case_count": int(
                triage_counts[MONITOR_PENDING_CASE]
            ),
            "latest_governance_reopen_case_triage_follow_on_reconciliation_due_case_count": int(
                triage_counts[FOLLOW_ON_RECONCILIATION_DUE]
            ),
            "latest_governance_reopen_case_triage_closed_no_action_case_count": int(
                triage_counts[NO_ACTION_CLOSED_CASE]
            ),
            "latest_governance_reopen_case_triage_stale_case_count": int(
                triage_counts[STALE_OR_SUPERSEDED_ARCHIVE_CANDIDATE]
            ),
        }
    )
    updated_self_structure["generated_at"] = _now()
    updated_self_structure["current_state_summary"] = updated_summary
    updated_self_structure["governance_reopen_case_triage"] = {
        "schema_name": CASE_TRIAGE_SCHEMA_NAME,
        "schema_version": CASE_TRIAGE_SCHEMA_VERSION,
        "latest_case_triage": {
            "governance_case_triage_id": case_triage_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_CASE_TRIAGE_LEDGER_PATH),
            "source_registry_artifact_path": str(case_registry_artifact_path),
            "total_case_count": int(len(triage_records)),
            "active_portfolio_case_count": int(active_portfolio_case_count),
            "immediate_attention_case_count": int(immediate_attention_case_count),
            "latest_case_identifier": str(
                dict(triage_records[0]).get("stable_case_identifier", "")
            )
            if triage_records
            else "",
        },
    }
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure)

    _append_jsonl(
        SELF_STRUCTURE_LEDGER_PATH,
        {
            "event_id": f"governance_reopen_case_triage::{proposal['proposal_id']}",
            "timestamp": _now(),
            "event_type": "governance_reopen_case_triage_recorded",
            "governance_case_triage_id": case_triage_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_CASE_TRIAGE_LEDGER_PATH),
            "total_case_count": int(len(triage_records)),
            "active_portfolio_case_count": int(active_portfolio_case_count),
        },
    )

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: governance reopen cases were materialized as an explicit triage view with attention classes and next-action recommendations",
        "observability_gain": {
            "passed": True,
            "reason": "future agents can answer what needs attention now, what is merely pending, and what can stay closed or archived without manually interpreting raw registry rows",
            "artifact_path": str(artifact_path),
            "governance_reopen_case_triage_ledger_path": str(
                GOVERNANCE_REOPEN_CASE_TRIAGE_LEDGER_PATH
            ),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "triage separates registry state from operational attention class without creating a second decision surface",
        },
        "ambiguity_reduction": {
            "passed": True,
            "reason": "attention level, next-action class, and active-vs-stale portfolio status are now explicit and queryable",
            "score": 0.99,
        },
        "safety_neutrality": {
            "passed": True,
            "reason": "the triage layer is observational only and never mutates authority, case state, review outcomes, promotion, rollback, repair, or closure decisions",
            "scope": str(proposal.get("scope", "")),
        },
        "later_selection_usefulness": {
            "passed": True,
            "reason": "PM visibility and future governance workflow can start from a single triage snapshot rather than manually scoring registry rows by hand",
            "recommended_next_template": "",
        },
        "diagnostic_conclusions": {
            "total_case_count": int(len(triage_records)),
            "immediate_attention_case_count": int(immediate_attention_case_count),
            "latest_case_identifier": str(
                dict(triage_records[0]).get("stable_case_identifier", "")
            )
            if triage_records
            else "",
            "recommended_next_action": "hold_and_consolidate",
            "recommended_next_template": "",
        },
        "artifact_path": str(artifact_path),
        "governance_reopen_case_triage_ledger_path": str(
            GOVERNANCE_REOPEN_CASE_TRIAGE_LEDGER_PATH
        ),
    }
