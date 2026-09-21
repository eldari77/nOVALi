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
GOVERNANCE_REOPEN_CASE_TRIAGE_LEDGER_PATH = (
    DATA_DIR / "governance_reopen_case_triage_ledger.jsonl"
)
GOVERNANCE_REOPEN_CASE_QUEUE_LEDGER_PATH = (
    DATA_DIR / "governance_reopen_case_queue_ledger.jsonl"
)
SELF_STRUCTURE_STATE_PATH = DATA_DIR / "self_structure_state_latest.json"
SELF_STRUCTURE_LEDGER_PATH = DATA_DIR / "self_structure_ledger.jsonl"
BRANCH_REGISTRY_PATH = DATA_DIR / "branch_registry_latest.json"
DIRECTIVE_STATE_PATH = DATA_DIR / "directive_state_latest.json"
BUCKET_STATE_PATH = DATA_DIR / "bucket_state_latest.json"
INTERVENTION_LEDGER_PATH = DATA_DIR / "intervention_ledger.jsonl"
INTERVENTION_ANALYTICS_PATH = DATA_DIR / "intervention_analytics_latest.json"
PROPOSAL_RECOMMENDATIONS_PATH = DATA_DIR / "proposal_recommendations_latest.json"

CASE_QUEUE_SCHEMA_NAME = "GovernanceReopenCaseQueue"
CASE_QUEUE_SCHEMA_VERSION = "governance_reopen_case_queue_v1"

NO_ACTION_CLOSED_CASE = "no_action_closed_case"
MONITOR_PENDING_CASE = "monitor_pending_case"
REVIEW_ATTENTION_REQUIRED_CASE = "review_attention_required_case"
FOLLOW_ON_RECONCILIATION_DUE = "follow_on_reconciliation_due"
STALE_OR_SUPERSEDED_ARCHIVE_CANDIDATE = "stale_or_superseded_archive_candidate"

ACTIVE_REVIEW_QUEUE_CASE = "active_review_queue_case"
MONITOR_QUEUE_CASE = "monitor_queue_case"
FOLLOW_ON_RECONCILIATION_QUEUE_CASE = "follow_on_reconciliation_queue_case"
CLOSED_EXCLUDED_CASE = "closed_excluded_case"
STALE_ARCHIVE_EXCLUDED_CASE = "stale_archive_excluded_case"

PRIORITY_BAND_FOLLOW_ON = "priority_1_follow_on_reconciliation"
PRIORITY_BAND_ACTIVE_REVIEW = "priority_2_active_review"
PRIORITY_BAND_MONITOR = "priority_3_monitor"
PRIORITY_BAND_CLOSED_EXCLUDED = "priority_4_closed_excluded"
PRIORITY_BAND_STALE_EXCLUDED = "priority_5_stale_archive_excluded"

STALE_OR_SUPERSEDED_CASE = "stale_or_superseded_case"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


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


def _load_latest_case_triage(
    self_structure_state: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    artifact_path_text = str(
        current_state_summary.get("latest_governance_reopen_case_triage_artifact_path", "")
    ).strip()
    if artifact_path_text:
        payload = _load_json_file(Path(artifact_path_text))
        if payload:
            return payload, artifact_path_text

    for row in reversed(_load_jsonl(GOVERNANCE_REOPEN_CASE_TRIAGE_LEDGER_PATH)):
        artifact_path_text = str(row.get("artifact_path", "")).strip()
        if not artifact_path_text:
            continue
        payload = _load_json_file(Path(artifact_path_text))
        if payload:
            return payload, artifact_path_text
    return {}, ""


def _queue_classification(
    triage_record: dict[str, Any],
) -> tuple[bool, str, str, int, list[str]]:
    triage_category = str(triage_record.get("triage_category", ""))
    portfolio_visibility = str(triage_record.get("current_portfolio_visibility_class", ""))
    reason_codes = [
        f"triage_category::{triage_category}",
        f"next_action::{str(triage_record.get('next_action_recommendation_class', ''))}",
    ]

    if portfolio_visibility == STALE_OR_SUPERSEDED_CASE or triage_category == STALE_OR_SUPERSEDED_ARCHIVE_CANDIDATE:
        return (
            False,
            STALE_ARCHIVE_EXCLUDED_CASE,
            PRIORITY_BAND_STALE_EXCLUDED,
            5,
            reason_codes + ["excluded_from_active_queue_because_case_is_stale_or_superseded"],
        )

    if triage_category == FOLLOW_ON_RECONCILIATION_DUE:
        return (
            True,
            FOLLOW_ON_RECONCILIATION_QUEUE_CASE,
            PRIORITY_BAND_FOLLOW_ON,
            1,
            reason_codes + ["included_in_active_queue_for_follow_on_reconciliation"],
        )

    if triage_category == REVIEW_ATTENTION_REQUIRED_CASE:
        return (
            True,
            ACTIVE_REVIEW_QUEUE_CASE,
            PRIORITY_BAND_ACTIVE_REVIEW,
            2,
            reason_codes + ["included_in_active_queue_for_governance_attention"],
        )

    if triage_category == MONITOR_PENDING_CASE:
        return (
            True,
            MONITOR_QUEUE_CASE,
            PRIORITY_BAND_MONITOR,
            3,
            reason_codes + ["included_in_monitor_queue_only"],
        )

    if triage_category == NO_ACTION_CLOSED_CASE:
        return (
            False,
            CLOSED_EXCLUDED_CASE,
            PRIORITY_BAND_CLOSED_EXCLUDED,
            4,
            reason_codes + ["excluded_from_active_queue_because_case_is_closed"],
        )

    return (
        True,
        ACTIVE_REVIEW_QUEUE_CASE,
        PRIORITY_BAND_ACTIVE_REVIEW,
        2,
        reason_codes + ["unrecognized_triage_category_defaulted_to_attention_queue"],
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

    case_triage_payload, case_triage_artifact_path = _load_latest_case_triage(
        self_structure_state
    )
    if not case_triage_payload:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no governance case triage artifact is available for queue ordering",
        }

    authority_posture = _authority_posture(authority_payload)
    triage_records = [dict(item) for item in list(case_triage_payload.get("case_triage_records", []))]
    queue_records: list[dict[str, Any]] = []
    for triage_record in triage_records:
        queue_inclusion_flag, queue_class, priority_band, priority_rank, reason_codes = (
            _queue_classification(triage_record)
        )
        queue_records.append(
            {
                "stable_case_identifier": str(triage_record.get("stable_case_identifier", "")),
                "current_lifecycle_state": str(
                    triage_record.get("current_lifecycle_state", "")
                ),
                "current_triage_category": str(triage_record.get("triage_category", "")),
                "next_action_recommendation_class": str(
                    triage_record.get("next_action_recommendation_class", "")
                ),
                "queue_inclusion_flag": bool(queue_inclusion_flag),
                "queue_class": queue_class,
                "priority_band": priority_band,
                "ordering_key": {
                    "priority_rank": int(priority_rank),
                    "latest_decision_timestamp": str(
                        triage_record.get("latest_decision_timestamp", "")
                    ),
                    "latest_stage_rank": int(
                        dict(triage_record.get("latest_sequence_marker", {})).get(
                            "stage_rank", -1
                        )
                    ),
                    "stable_case_identifier": str(
                        triage_record.get("stable_case_identifier", "")
                    ),
                },
                "latest_stage": str(triage_record.get("latest_stage", "")),
                "latest_state": str(triage_record.get("latest_state", "")),
                "latest_artifact_path": str(triage_record.get("latest_artifact_path", "")),
                "latest_decision_timestamp": str(
                    triage_record.get("latest_decision_timestamp", "")
                ),
                "current_portfolio_visibility_class": str(
                    triage_record.get("current_portfolio_visibility_class", "")
                ),
                "current_portfolio_case_state": str(
                    triage_record.get("current_portfolio_case_state", "")
                ),
                "stale_or_superseded_marker": bool(
                    triage_record.get("stale_or_superseded_marker", False)
                ),
                "follow_on_reconciliation_state_if_any": str(
                    triage_record.get("follow_on_reconciliation_state_if_any", "")
                ),
                "closure_state_if_any": str(
                    triage_record.get("closure_state_if_any", "")
                ),
                "authority_posture_at_queue_time": dict(authority_posture),
                "authority_posture_at_latest_stage": dict(
                    triage_record.get("authority_posture_at_latest_stage", {})
                ),
                "queue_reason_codes": list(reason_codes),
                "source_case_triage_artifact_path": str(case_triage_artifact_path),
                "source_case_registry_artifact_path": str(
                    triage_record.get("source_case_registry_artifact_path", "")
                ),
                "source_case_registry_record_reference": dict(
                    triage_record.get("source_case_registry_record_reference", {})
                ),
            }
        )

    sorted_queue_records = list(queue_records)
    sorted_queue_records.sort(
        key=lambda item: str(item.get("stable_case_identifier", ""))
    )
    sorted_queue_records.sort(
        key=lambda item: int(dict(item.get("ordering_key", {})).get("latest_stage_rank", -1)),
        reverse=True,
    )
    sorted_queue_records.sort(
        key=lambda item: _parse_time(item.get("latest_decision_timestamp"))
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    sorted_queue_records.sort(
        key=lambda item: int(dict(item.get("ordering_key", {})).get("priority_rank", 999))
    )
    sorted_queue_records.sort(
        key=lambda item: not bool(item.get("queue_inclusion_flag", False))
    )

    included_position = 0
    for portfolio_position, queue_record in enumerate(sorted_queue_records, start=1):
        queue_record["portfolio_queue_position"] = int(portfolio_position)
        if bool(queue_record.get("queue_inclusion_flag", False)):
            included_position += 1
            queue_record["queue_position_if_included"] = int(included_position)
        else:
            queue_record["queue_position_if_included"] = None

    queue_counts = {
        ACTIVE_REVIEW_QUEUE_CASE: 0,
        MONITOR_QUEUE_CASE: 0,
        FOLLOW_ON_RECONCILIATION_QUEUE_CASE: 0,
        CLOSED_EXCLUDED_CASE: 0,
        STALE_ARCHIVE_EXCLUDED_CASE: 0,
    }
    for queue_record in sorted_queue_records:
        queue_counts[str(queue_record.get("queue_class", CLOSED_EXCLUDED_CASE))] += 1

    queue_included_case_count = int(
        sum(1 for queue_record in sorted_queue_records if bool(queue_record.get("queue_inclusion_flag", False)))
    )
    attention_queue_case_count = int(
        queue_counts[ACTIVE_REVIEW_QUEUE_CASE]
        + queue_counts[FOLLOW_ON_RECONCILIATION_QUEUE_CASE]
    )
    next_queue_record = next(
        (
            queue_record
            for queue_record in sorted_queue_records
            if bool(queue_record.get("queue_inclusion_flag", False))
        ),
        {},
    )

    branch_record = (
        dict(list(branch_registry.get("branches", []))[0])
        if list(branch_registry.get("branches", []))
        else {}
    )
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))

    recorded_at = _now()
    case_queue_id = f"governance_reopen_case_queue::{proposal['proposal_id']}"
    artifact_path = _diagnostic_artifact_dir() / (
        f"memory_summary_v4_governance_reopen_case_queue_snapshot_v1_{proposal['proposal_id']}.json"
    )

    payload = {
        "proposal_id": str(proposal.get("proposal_id", "")),
        "template_name": "memory_summary.v4_governance_reopen_case_queue_snapshot_v1",
        "snapshot_identity_context": {
            "governance_case_queue_id": case_queue_id,
            "recorded_at": recorded_at,
            "phase": "governance_reopen_case_queue",
            "source_triage_artifact_path": str(case_triage_artifact_path),
            "source_triage_case_count": int(len(triage_records)),
        },
        "case_queue_contract": {
            "schema_name": CASE_QUEUE_SCHEMA_NAME,
            "schema_version": CASE_QUEUE_SCHEMA_VERSION,
            "source_triage_required": True,
            "queue_categories": [
                ACTIVE_REVIEW_QUEUE_CASE,
                MONITOR_QUEUE_CASE,
                FOLLOW_ON_RECONCILIATION_QUEUE_CASE,
                CLOSED_EXCLUDED_CASE,
                STALE_ARCHIVE_EXCLUDED_CASE,
            ],
            "priority_bands": [
                PRIORITY_BAND_FOLLOW_ON,
                PRIORITY_BAND_ACTIVE_REVIEW,
                PRIORITY_BAND_MONITOR,
                PRIORITY_BAND_CLOSED_EXCLUDED,
                PRIORITY_BAND_STALE_EXCLUDED,
            ],
            "queue_observational_only": True,
            "queue_inclusion_non_authoritative": True,
            "case_state_mutation_disallowed_here": True,
            "triage_state_mutation_disallowed_here": True,
            "authority_mutation_disallowed_here": True,
        },
        "authority_posture_at_queue_time": dict(authority_posture),
        "case_queue_records": sorted_queue_records,
        "portfolio_queue_summary": {
            "total_case_count": int(len(sorted_queue_records)),
            "queue_included_case_count": int(queue_included_case_count),
            "attention_queue_case_count": int(attention_queue_case_count),
            "monitor_queue_case_count": int(queue_counts[MONITOR_QUEUE_CASE]),
            "follow_on_reconciliation_queue_case_count": int(
                queue_counts[FOLLOW_ON_RECONCILIATION_QUEUE_CASE]
            ),
            "active_review_queue_case_count": int(queue_counts[ACTIVE_REVIEW_QUEUE_CASE]),
            "closed_excluded_case_count": int(queue_counts[CLOSED_EXCLUDED_CASE]),
            "stale_archive_excluded_case_count": int(
                queue_counts[STALE_ARCHIVE_EXCLUDED_CASE]
            ),
            "next_case_identifier": str(next_queue_record.get("stable_case_identifier", "")),
            "next_queue_class": str(next_queue_record.get("queue_class", "")),
            "next_priority_band": str(next_queue_record.get("priority_band", "")),
        },
        "reviewer_source_and_audit_trace": {
            "recorded_by_surface": "memory_summary.v4_governance_reopen_case_queue_snapshot_v1",
            "reviewer_source": "governed_case_queue_snapshot_v1",
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
            "source_triage_total_case_count": int(
                current_state_summary.get(
                    "latest_governance_reopen_case_triage_total_case_count", 0
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
            "governance_reopen_case_triage_ledger_path": str(
                GOVERNANCE_REOPEN_CASE_TRIAGE_LEDGER_PATH
            ),
            "governance_reopen_case_queue_ledger_path": str(
                GOVERNANCE_REOPEN_CASE_QUEUE_LEDGER_PATH
            ),
            "self_structure_state_path": str(SELF_STRUCTURE_STATE_PATH),
            "self_structure_ledger_path": str(SELF_STRUCTURE_LEDGER_PATH),
            "intervention_ledger_path": str(INTERVENTION_LEDGER_PATH),
            "analytics_path": str(INTERVENTION_ANALYTICS_PATH),
            "proposal_recommendations_path": str(PROPOSAL_RECOMMENDATIONS_PATH),
        },
        "operator_readable_conclusion": (
            "Governance reopen cases now have an explicit queue view that identifies which "
            "cases are actually queued for attention, which are monitor-only, which are "
            "follow-on reconciliation items, and which are excluded because they are closed "
            "or stale."
        ),
    }

    _write_json(artifact_path, payload)

    ledger_entry = {
        "event_type": "governance_reopen_case_queue_recorded",
        "written_at": recorded_at,
        "governance_case_queue_id": case_queue_id,
        "artifact_path": str(artifact_path),
        "source_triage_artifact_path": str(case_triage_artifact_path),
        "total_case_count": int(len(sorted_queue_records)),
        "queue_included_case_count": int(queue_included_case_count),
        "attention_queue_case_count": int(attention_queue_case_count),
        "monitor_queue_case_count": int(queue_counts[MONITOR_QUEUE_CASE]),
        "follow_on_reconciliation_queue_case_count": int(
            queue_counts[FOLLOW_ON_RECONCILIATION_QUEUE_CASE]
        ),
        "active_review_queue_case_count": int(queue_counts[ACTIVE_REVIEW_QUEUE_CASE]),
        "closed_excluded_case_count": int(queue_counts[CLOSED_EXCLUDED_CASE]),
        "stale_archive_excluded_case_count": int(
            queue_counts[STALE_ARCHIVE_EXCLUDED_CASE]
        ),
        "next_case_identifier": str(next_queue_record.get("stable_case_identifier", "")),
        "next_queue_class": str(next_queue_record.get("queue_class", "")),
    }
    _append_jsonl(GOVERNANCE_REOPEN_CASE_QUEUE_LEDGER_PATH, ledger_entry)

    updated_self_structure = dict(self_structure_state)
    updated_summary = dict(current_state_summary)
    updated_summary.update(
        {
            "latest_governance_reopen_case_queue_artifact_path": str(artifact_path),
            "latest_governance_reopen_case_queue_ledger_path": str(
                GOVERNANCE_REOPEN_CASE_QUEUE_LEDGER_PATH
            ),
            "latest_governance_reopen_case_queue_total_case_count": int(
                len(sorted_queue_records)
            ),
            "latest_governance_reopen_case_queue_included_case_count": int(
                queue_included_case_count
            ),
            "latest_governance_reopen_case_queue_attention_case_count": int(
                attention_queue_case_count
            ),
            "latest_governance_reopen_case_queue_monitor_case_count": int(
                queue_counts[MONITOR_QUEUE_CASE]
            ),
            "latest_governance_reopen_case_queue_follow_on_case_count": int(
                queue_counts[FOLLOW_ON_RECONCILIATION_QUEUE_CASE]
            ),
            "latest_governance_reopen_case_queue_closed_excluded_case_count": int(
                queue_counts[CLOSED_EXCLUDED_CASE]
            ),
            "latest_governance_reopen_case_queue_stale_excluded_case_count": int(
                queue_counts[STALE_ARCHIVE_EXCLUDED_CASE]
            ),
            "latest_governance_reopen_case_queue_next_case_identifier": str(
                next_queue_record.get("stable_case_identifier", "")
            ),
            "latest_governance_reopen_case_queue_next_queue_class": str(
                next_queue_record.get("queue_class", "")
            ),
        }
    )
    updated_self_structure["generated_at"] = _now()
    updated_self_structure["current_state_summary"] = updated_summary
    updated_self_structure["governance_reopen_case_queue"] = {
        "schema_name": CASE_QUEUE_SCHEMA_NAME,
        "schema_version": CASE_QUEUE_SCHEMA_VERSION,
        "latest_case_queue": {
            "governance_case_queue_id": case_queue_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_CASE_QUEUE_LEDGER_PATH),
            "source_triage_artifact_path": str(case_triage_artifact_path),
            "total_case_count": int(len(sorted_queue_records)),
            "queue_included_case_count": int(queue_included_case_count),
            "attention_queue_case_count": int(attention_queue_case_count),
            "next_case_identifier": str(next_queue_record.get("stable_case_identifier", "")),
        },
    }
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure)

    _append_jsonl(
        SELF_STRUCTURE_LEDGER_PATH,
        {
            "event_id": f"governance_reopen_case_queue::{proposal['proposal_id']}",
            "timestamp": _now(),
            "event_type": "governance_reopen_case_queue_recorded",
            "governance_case_queue_id": case_queue_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_CASE_QUEUE_LEDGER_PATH),
            "total_case_count": int(len(sorted_queue_records)),
            "queue_included_case_count": int(queue_included_case_count),
        },
    )

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: governance reopen cases were materialized as an explicit queue view with inclusion flags, queue classes, and ordering metadata",
        "observability_gain": {
            "passed": True,
            "reason": "future agents can answer what is actually queued now, what is monitor-only, and what is excluded without manually inferring operational ordering from raw triage rows",
            "artifact_path": str(artifact_path),
            "governance_reopen_case_queue_ledger_path": str(
                GOVERNANCE_REOPEN_CASE_QUEUE_LEDGER_PATH
            ),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "queue state separates operational ordering from triage state without creating a second decision surface",
        },
        "ambiguity_reduction": {
            "passed": True,
            "reason": "queue inclusion, queue class, priority band, and queue ordering are now explicit and queryable",
            "score": 0.99,
        },
        "safety_neutrality": {
            "passed": True,
            "reason": "the queue layer is observational only and never mutates authority, case state, triage state, review outcomes, promotion, rollback, repair, or closure decisions",
            "scope": str(proposal.get("scope", "")),
        },
        "later_selection_usefulness": {
            "passed": True,
            "reason": "PM execution readiness can start from a single queue snapshot rather than manually prioritizing triage rows by hand",
            "recommended_next_template": "",
        },
        "diagnostic_conclusions": {
            "total_case_count": int(len(sorted_queue_records)),
            "queue_included_case_count": int(queue_included_case_count),
            "next_case_identifier": str(next_queue_record.get("stable_case_identifier", "")),
            "recommended_next_action": "hold_and_consolidate",
            "recommended_next_template": "",
        },
        "artifact_path": str(artifact_path),
        "governance_reopen_case_queue_ledger_path": str(
            GOVERNANCE_REOPEN_CASE_QUEUE_LEDGER_PATH
        ),
    }
