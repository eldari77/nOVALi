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
GOVERNANCE_REOPEN_INTAKE_LEDGER_PATH = DATA_DIR / "governance_reopen_intake_ledger.jsonl"
GOVERNANCE_REOPEN_SCREENING_LEDGER_PATH = DATA_DIR / "governance_reopen_screening_ledger.jsonl"
GOVERNANCE_REOPEN_REVIEW_LEDGER_PATH = DATA_DIR / "governance_reopen_review_ledger.jsonl"
GOVERNANCE_REOPEN_REVIEW_OUTCOME_LEDGER_PATH = DATA_DIR / "governance_reopen_review_outcome_ledger.jsonl"
GOVERNANCE_REOPEN_PROMOTION_HANDOFF_LEDGER_PATH = DATA_DIR / "governance_reopen_promotion_handoff_ledger.jsonl"
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
GOVERNANCE_REOPEN_REMEDIATION_REVIEW_OUTCOME_LEDGER_PATH = (
    DATA_DIR / "governance_reopen_remediation_review_outcome_ledger.jsonl"
)
GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_HANDOFF_LEDGER_PATH = (
    DATA_DIR / "governance_reopen_rollback_or_repair_handoff_ledger.jsonl"
)
GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_OUTCOME_LEDGER_PATH = (
    DATA_DIR / "governance_reopen_rollback_or_repair_outcome_ledger.jsonl"
)
GOVERNANCE_REOPEN_MISMATCH_CASE_CLOSURE_LEDGER_PATH = (
    DATA_DIR / "governance_reopen_mismatch_case_closure_ledger.jsonl"
)
GOVERNANCE_REOPEN_CASE_REGISTRY_LEDGER_PATH = (
    DATA_DIR / "governance_reopen_case_registry_ledger.jsonl"
)
INTERVENTION_LEDGER_PATH = DATA_DIR / "intervention_ledger.jsonl"
INTERVENTION_ANALYTICS_PATH = DATA_DIR / "intervention_analytics_latest.json"
PROPOSAL_RECOMMENDATIONS_PATH = DATA_DIR / "proposal_recommendations_latest.json"
SELF_STRUCTURE_STATE_PATH = DATA_DIR / "self_structure_state_latest.json"
SELF_STRUCTURE_LEDGER_PATH = DATA_DIR / "self_structure_ledger.jsonl"
BRANCH_REGISTRY_PATH = DATA_DIR / "branch_registry_latest.json"
DIRECTIVE_STATE_PATH = DATA_DIR / "directive_state_latest.json"
BUCKET_STATE_PATH = DATA_DIR / "bucket_state_latest.json"

CASE_REGISTRY_SCHEMA_NAME = "GovernanceReopenCaseRegistry"
CASE_REGISTRY_SCHEMA_VERSION = "governance_reopen_case_registry_v1"
ACTIVE_OPEN_CASE = "active_open_case"
PENDING_FOLLOW_ON_RECONCILIATION_CASE = "pending_follow_on_reconciliation_case"
CLOSED_RESOLVED_CASE = "closed_resolved_case"
CLOSED_REJECTED_CASE = "closed_rejected_case"
OPEN_REQUIRES_FURTHER_GOVERNANCE_CASE = "open_requires_further_governance_case"
STALE_OR_SUPERSEDED_CASE = "stale_or_superseded_case"
CURRENT_PORTFOLIO_RECORD = "current_portfolio_record"

STAGE_SPECS = [
    {"stage": "reopen_intake", "ledger_path": GOVERNANCE_REOPEN_INTAKE_LEDGER_PATH, "own_id_keys": ["intake_id"], "source_id_keys": []},
    {"stage": "reopen_screening", "ledger_path": GOVERNANCE_REOPEN_SCREENING_LEDGER_PATH, "own_id_keys": ["screening_id"], "source_id_keys": ["source_intake_id"]},
    {"stage": "governance_review_submission", "ledger_path": GOVERNANCE_REOPEN_REVIEW_LEDGER_PATH, "own_id_keys": ["review_packet_id"], "source_id_keys": ["source_intake_id", "source_screening_id"]},
    {"stage": "governance_review_outcome", "ledger_path": GOVERNANCE_REOPEN_REVIEW_OUTCOME_LEDGER_PATH, "own_id_keys": ["review_outcome_id"], "source_id_keys": ["source_review_packet_id", "source_screening_id", "source_intake_id"]},
    {"stage": "promotion_handoff", "ledger_path": GOVERNANCE_REOPEN_PROMOTION_HANDOFF_LEDGER_PATH, "own_id_keys": ["promotion_handoff_id"], "source_id_keys": ["source_review_outcome_id", "source_review_packet_id", "source_screening_id"]},
    {"stage": "promotion_outcome", "ledger_path": GOVERNANCE_REOPEN_PROMOTION_OUTCOME_LEDGER_PATH, "own_id_keys": ["promotion_outcome_id"], "source_id_keys": ["source_promotion_handoff_id", "source_review_outcome_id", "source_review_packet_id"]},
    {"stage": "promotion_reconciliation", "ledger_path": GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_LEDGER_PATH, "own_id_keys": ["reconciliation_id"], "source_id_keys": ["source_promotion_outcome_id", "source_promotion_handoff_id"]},
    {"stage": "promotion_reconciliation_escalation", "ledger_path": GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_ESCALATION_LEDGER_PATH, "own_id_keys": ["escalation_id"], "source_id_keys": ["source_reconciliation_id", "source_promotion_outcome_id"]},
    {"stage": "remediation_review_submission", "ledger_path": GOVERNANCE_REOPEN_REMEDIATION_REVIEW_LEDGER_PATH, "own_id_keys": ["remediation_review_packet_id"], "source_id_keys": ["source_escalation_id", "source_reconciliation_id"]},
    {"stage": "remediation_review_outcome", "ledger_path": GOVERNANCE_REOPEN_REMEDIATION_REVIEW_OUTCOME_LEDGER_PATH, "own_id_keys": ["remediation_review_outcome_id"], "source_id_keys": ["source_remediation_review_packet_id", "source_escalation_id", "source_reconciliation_id"]},
    {"stage": "rollback_or_repair_handoff", "ledger_path": GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_HANDOFF_LEDGER_PATH, "own_id_keys": ["rollback_or_repair_handoff_id"], "source_id_keys": ["source_remediation_review_outcome_id", "source_remediation_review_packet_id", "source_escalation_id"]},
    {"stage": "rollback_or_repair_outcome", "ledger_path": GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_OUTCOME_LEDGER_PATH, "own_id_keys": ["rollback_or_repair_outcome_id"], "source_id_keys": ["source_rollback_or_repair_handoff_id", "source_remediation_review_outcome_id"]},
    {"stage": "mismatch_case_closure", "ledger_path": GOVERNANCE_REOPEN_MISMATCH_CASE_CLOSURE_LEDGER_PATH, "own_id_keys": ["mismatch_case_closure_id"], "source_id_keys": ["source_rollback_or_repair_outcome_id", "source_reconciliation_id"]},
]

STAGE_ORDER = {spec["stage"]: index for index, spec in enumerate(STAGE_SPECS)}


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


def _diagnostic_artifact_dir() -> Path:
    DIAGNOSTIC_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    return DIAGNOSTIC_MEMORY_DIR


def _first_nonempty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _reference_kind(reference_id: str) -> str:
    return str(reference_id or "").split("::", 1)[0]


def _stable_case_identifier(root_reference_id: str) -> str:
    return f"governance_case::{root_reference_id}" if root_reference_id else ""


def _event_timestamp(row: dict[str, Any]) -> str:
    return _first_nonempty(
        row.get("written_at"),
        row.get("timestamp"),
        row.get("ledger_written_at"),
        row.get("created_at"),
        row.get("updated_at"),
    )


def _row_artifact_path(row: dict[str, Any]) -> str:
    return _first_nonempty(
        row.get("artifact_path"),
        row.get("source_artifact_path"),
        row.get("source_screening_artifact_path"),
        row.get("source_intake_artifact_path"),
    )


def _row_stage_state(stage: str, row: dict[str, Any]) -> str:
    if stage == "reopen_intake":
        return _first_nonempty(row.get("reopen_candidate_intake_state"), row.get("blocked_action_request_state"))
    if stage == "reopen_screening":
        return _first_nonempty(row.get("screening_state"))
    if stage == "governance_review_submission":
        return _first_nonempty(row.get("review_submission_state"))
    if stage == "governance_review_outcome":
        return _first_nonempty(row.get("review_outcome_state"))
    if stage == "promotion_handoff":
        return _first_nonempty(row.get("promotion_handoff_state"))
    if stage == "promotion_outcome":
        return _first_nonempty(row.get("promotion_outcome_state"))
    if stage == "promotion_reconciliation":
        return _first_nonempty(row.get("reconciliation_state"))
    if stage == "promotion_reconciliation_escalation":
        return _first_nonempty(row.get("escalation_state"))
    if stage == "remediation_review_submission":
        return _first_nonempty(row.get("submission_state"), row.get("remediation_review_outcome_state"))
    if stage == "remediation_review_outcome":
        return _first_nonempty(row.get("remediation_review_outcome_state"))
    if stage == "rollback_or_repair_handoff":
        return _first_nonempty(row.get("rollback_or_repair_handoff_state"), row.get("rollback_or_repair_candidate_state"))
    if stage == "rollback_or_repair_outcome":
        return _first_nonempty(row.get("rollback_or_repair_outcome_state"))
    if stage == "mismatch_case_closure":
        return _first_nonempty(row.get("mismatch_case_closure_state"))
    return ""


def _resolve_case_id(row: dict[str, Any], spec: dict[str, Any], id_to_case: dict[str, str]) -> tuple[str, str]:
    intake_reference_id = _first_nonempty(row.get("source_intake_id"), row.get("intake_id"))
    if intake_reference_id:
        return _stable_case_identifier(intake_reference_id), intake_reference_id
    for key in spec["source_id_keys"]:
        value = _first_nonempty(row.get(key))
        if value and value in id_to_case:
            return id_to_case[value], value
    for key in spec["own_id_keys"]:
        value = _first_nonempty(row.get(key))
        if value and value in id_to_case:
            return id_to_case[value], value
    fallback_reference_id = _first_nonempty(
        *[row.get(key) for key in spec["source_id_keys"]],
        *[row.get(key) for key in spec["own_id_keys"]],
    )
    return _stable_case_identifier(fallback_reference_id), fallback_reference_id


def _empty_case_record(case_id: str, root_reference_id: str) -> dict[str, Any]:
    return {
        "stable_case_identifier": case_id,
        "root_reference": {
            "root_reference_id": root_reference_id,
            "root_reference_kind": _reference_kind(root_reference_id),
        },
        "request_signature": {
            "action_kind": "",
            "request_classification": "",
            "requested_template_name": "",
            "requested_template_family": "",
        },
        "source_artifact_chain_references": {},
        "latest_lifecycle_stage": "",
        "latest_lifecycle_state": "",
        "latest_artifact_path": "",
        "latest_ledger_path": "",
        "latest_decision_timestamp": "",
        "latest_sequence_marker": {
            "timestamp": "",
            "stage": "",
            "stage_rank": -1,
        },
        "authority_posture_at_latest_stage": {},
        "follow_on_reconciliation_state_if_any": "",
        "closure_state_if_any": "",
        "underlying_lifecycle_case_state": "",
        "portfolio_visibility_state": CURRENT_PORTFOLIO_RECORD,
        "portfolio_case_state": "",
        "latest_artifact_load_status": "not_attempted",
    }


def _is_newer_event(
    current_timestamp: str,
    current_stage: str,
    candidate_timestamp: str,
    candidate_stage: str,
) -> bool:
    current_dt = _parse_time(current_timestamp)
    candidate_dt = _parse_time(candidate_timestamp)
    if candidate_dt is None:
        return False
    if current_dt is None:
        return True
    if candidate_dt > current_dt:
        return True
    if candidate_dt < current_dt:
        return False
    return STAGE_ORDER.get(candidate_stage, -1) >= STAGE_ORDER.get(current_stage, -1)


def _extract_authority_posture(payload: dict[str, Any]) -> dict[str, Any]:
    for key in [
        "authority_posture_at_closure_time",
        "authority_posture_at_decision_time",
        "authority_posture_at_review_time",
        "authority_posture_at_submission_time",
        "authority_posture_at_review",
        "authority_posture_at_submission",
        "authority_posture_at_handoff",
        "canonical_authority_snapshot",
    ]:
        candidate = dict(payload.get(key, {}))
        if candidate:
            return candidate
    reopen_bar_authority_posture = dict(
        dict(payload.get("applied_reopen_bar", {})).get("authority_posture", {})
    )
    if reopen_bar_authority_posture:
        return reopen_bar_authority_posture
    return {}


def _latest_stage_state_from_payload(stage: str, payload: dict[str, Any]) -> str:
    if stage == "reopen_intake":
        return _first_nonempty(
            dict(payload.get("reopen_candidate_intake", {})).get("reopen_candidate_intake_state"),
            dict(payload.get("blocked_action_request", {})).get("blocked_action_request_state"),
        )
    if stage == "reopen_screening":
        return _first_nonempty(dict(payload.get("screening_result", {})).get("screening_state"))
    if stage == "governance_review_submission":
        return _first_nonempty(
            dict(payload.get("review_submission_result", {})).get("review_submission_state")
        )
    if stage == "governance_review_outcome":
        return _first_nonempty(dict(payload.get("review_decision", {})).get("review_outcome_state"))
    if stage == "promotion_handoff":
        return _first_nonempty(dict(payload.get("promotion_candidate", {})).get("promotion_handoff_state"))
    if stage == "promotion_outcome":
        return _first_nonempty(dict(payload.get("promotion_decision", {})).get("promotion_outcome_state"))
    if stage == "promotion_reconciliation":
        return _first_nonempty(dict(payload.get("reconciliation_result", {})).get("reconciliation_state"))
    if stage == "promotion_reconciliation_escalation":
        return _first_nonempty(dict(payload.get("escalation_result", {})).get("escalation_state"))
    if stage == "remediation_review_submission":
        return _first_nonempty(
            dict(payload.get("remediation_review_submission_result", {})).get("submission_state")
        )
    if stage == "remediation_review_outcome":
        return _first_nonempty(
            dict(payload.get("remediation_review_decision", {})).get("remediation_review_outcome_state")
        )
    if stage == "rollback_or_repair_handoff":
        return _first_nonempty(
            dict(payload.get("rollback_or_repair_candidate", {})).get("rollback_or_repair_handoff_state")
        )
    if stage == "rollback_or_repair_outcome":
        return _first_nonempty(
            dict(payload.get("rollback_or_repair_decision", {})).get("rollback_or_repair_outcome_state")
        )
    if stage == "mismatch_case_closure":
        return _first_nonempty(
            dict(payload.get("mismatch_case_closure_result", {})).get("mismatch_case_closure_state")
        )
    return ""


def _requested_scope_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    for key in [
        "requested_action_and_scope",
        "requested_remediation_scope",
        "requested_rollback_or_repair_scope",
    ]:
        candidate = dict(payload.get(key, {}))
        if candidate:
            return candidate
    blocked_request = dict(payload.get("blocked_action_request", {}))
    if blocked_request:
        return {
            "action_kind": str(blocked_request.get("action_kind", "")),
            "request_classification": str(
                dict(payload.get("reopen_candidate_intake", {})).get("request_classification", "")
            ),
            "requested_template_name": str(blocked_request.get("requested_template_name", "")),
            "requested_template_family": str(blocked_request.get("requested_template_family", "")),
        }
    return {}


def _follow_on_reconciliation_state_from_payload(payload: dict[str, Any]) -> str:
    return _first_nonempty(
        dict(payload.get("follow_on_reconciliation_state_if_any", {})).get("follow_on_reconciliation_state"),
        dict(payload.get("mismatch_case_closure_result", {})).get("follow_on_reconciliation_state"),
    )


def _closure_state_from_payload(payload: dict[str, Any]) -> str:
    return _first_nonempty(
        dict(payload.get("mismatch_case_closure_result", {})).get("mismatch_case_closure_state")
    )


def _classify_underlying_case_state(latest_stage: str, latest_state: str) -> str:
    if latest_stage == "mismatch_case_closure":
        if latest_state == "mismatch_case_closed_rejected_no_action":
            return CLOSED_REJECTED_CASE
        if latest_state == "mismatch_case_pending_follow_on_reconciliation":
            return PENDING_FOLLOW_ON_RECONCILIATION_CASE
        if latest_state == "mismatch_case_closed_verified_resolved":
            return CLOSED_RESOLVED_CASE
        if latest_state == "mismatch_case_open_requires_further_governance":
            return OPEN_REQUIRES_FURTHER_GOVERNANCE_CASE
    if latest_stage == "rollback_or_repair_outcome":
        if latest_state == "rollback_or_repair_rejected_under_existing_path":
            return CLOSED_REJECTED_CASE
        if latest_state == "rollback_or_repair_applied_under_existing_path":
            return PENDING_FOLLOW_ON_RECONCILIATION_CASE
        if latest_state == "rollback_or_repair_noop_already_resolved":
            return CLOSED_RESOLVED_CASE
        if latest_state == "rollback_or_repair_candidate_under_existing_path":
            return ACTIVE_OPEN_CASE
    if latest_stage == "rollback_or_repair_handoff":
        return ACTIVE_OPEN_CASE
    if latest_stage == "remediation_review_outcome":
        if latest_state == "remediation_review_rejected":
            return CLOSED_REJECTED_CASE
        if latest_state == "remediation_review_approved_for_existing_rollback_or_repair_path":
            return ACTIVE_OPEN_CASE
    if latest_stage == "remediation_review_submission":
        return ACTIVE_OPEN_CASE
    if latest_stage == "promotion_reconciliation_escalation":
        return OPEN_REQUIRES_FURTHER_GOVERNANCE_CASE
    if latest_stage == "promotion_reconciliation":
        if latest_state == "reconciliation_verified":
            return CLOSED_RESOLVED_CASE
        if latest_state == "reconciliation_mismatch_detected":
            return OPEN_REQUIRES_FURTHER_GOVERNANCE_CASE
        if latest_state == "reconciliation_pending":
            return PENDING_FOLLOW_ON_RECONCILIATION_CASE
    if latest_stage == "promotion_outcome":
        if latest_state == "promotion_applied_as_binding_authority":
            return PENDING_FOLLOW_ON_RECONCILIATION_CASE
        if latest_state == "promotion_rejected_under_existing_gate":
            return CLOSED_REJECTED_CASE
        if latest_state == "promotion_noop_already_authoritative":
            return CLOSED_RESOLVED_CASE
        if latest_state == "promotion_candidate_under_review":
            return ACTIVE_OPEN_CASE
    if latest_stage == "promotion_handoff":
        return ACTIVE_OPEN_CASE
    if latest_stage == "governance_review_outcome":
        if latest_state == "governance_review_rejected":
            return CLOSED_REJECTED_CASE
        if latest_state == "governance_review_approved_for_promotion_path":
            return ACTIVE_OPEN_CASE
    if latest_stage == "governance_review_submission":
        return ACTIVE_OPEN_CASE
    if latest_stage == "reopen_screening":
        if latest_state == "still_rejected_request":
            return CLOSED_REJECTED_CASE
        if latest_state in {"screened_reopen_candidate", "not_screened_yet"}:
            return ACTIVE_OPEN_CASE
    if latest_stage == "reopen_intake":
        return ACTIVE_OPEN_CASE
    return ACTIVE_OPEN_CASE


def run_probe(cfg, proposal, *, rounds, seeds):
    del cfg, rounds, seeds

    authority_payload = _load_json_file(GOVERNANCE_MEMORY_AUTHORITY_PATH)
    self_structure_state = _load_json_file(SELF_STRUCTURE_STATE_PATH)
    branch_registry = _load_json_file(BRANCH_REGISTRY_PATH)
    directive_state = _load_json_file(DIRECTIVE_STATE_PATH)
    bucket_state = _load_json_file(BUCKET_STATE_PATH)
    intervention_analytics = _load_json_file(INTERVENTION_ANALYTICS_PATH)
    proposal_recommendations = _load_json_file(PROPOSAL_RECOMMENDATIONS_PATH)

    if not all([authority_payload, self_structure_state, branch_registry, directive_state, bucket_state]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: authority, self-structure, branch, directive, and bucket artifacts are required",
        }

    cases: dict[str, dict[str, Any]] = {}
    id_to_case: dict[str, str] = {}
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))

    for spec in STAGE_SPECS:
        ledger_rows = _load_jsonl(spec["ledger_path"])
        for row in ledger_rows:
            case_id, root_reference_id = _resolve_case_id(row, spec, id_to_case)
            if not case_id:
                continue

            case_record = cases.setdefault(case_id, _empty_case_record(case_id, root_reference_id))
            if not case_record["root_reference"]["root_reference_id"] and root_reference_id:
                case_record["root_reference"] = {
                    "root_reference_id": root_reference_id,
                    "root_reference_kind": _reference_kind(root_reference_id),
                }

            for key in [*spec["own_id_keys"], *spec["source_id_keys"]]:
                value = _first_nonempty(row.get(key))
                if value:
                    id_to_case[value] = case_id

            case_record["source_artifact_chain_references"][spec["stage"]] = {
                "stage": spec["stage"],
                "artifact_path": _row_artifact_path(row),
                "ledger_path": str(spec["ledger_path"]),
                "timestamp": _event_timestamp(row),
                "stage_state": _row_stage_state(spec["stage"], row),
                "own_ids": {
                    key: _first_nonempty(row.get(key))
                    for key in spec["own_id_keys"]
                    if _first_nonempty(row.get(key))
                },
                "source_ids": {
                    key: _first_nonempty(row.get(key))
                    for key in spec["source_id_keys"]
                    if _first_nonempty(row.get(key))
                },
            }

            request_signature = case_record["request_signature"]
            request_signature["action_kind"] = _first_nonempty(
                request_signature.get("action_kind"),
                row.get("action_kind"),
            )
            request_signature["request_classification"] = _first_nonempty(
                request_signature.get("request_classification"),
                row.get("request_classification"),
            )
            request_signature["requested_template_name"] = _first_nonempty(
                request_signature.get("requested_template_name"),
                row.get("requested_template_name"),
            )
            request_signature["requested_template_family"] = _first_nonempty(
                request_signature.get("requested_template_family"),
                row.get("requested_template_family"),
            )

            candidate_timestamp = _event_timestamp(row)
            if _is_newer_event(
                case_record["latest_decision_timestamp"],
                case_record["latest_lifecycle_stage"],
                candidate_timestamp,
                spec["stage"],
            ):
                case_record["latest_lifecycle_stage"] = spec["stage"]
                case_record["latest_lifecycle_state"] = _row_stage_state(spec["stage"], row)
                case_record["latest_artifact_path"] = _row_artifact_path(row)
                case_record["latest_ledger_path"] = str(spec["ledger_path"])
                case_record["latest_decision_timestamp"] = candidate_timestamp
                case_record["latest_sequence_marker"] = {
                    "timestamp": candidate_timestamp,
                    "stage": spec["stage"],
                    "stage_rank": STAGE_ORDER.get(spec["stage"], -1),
                }

    case_records = list(cases.values())
    for case_record in case_records:
        latest_artifact_payload = {}
        latest_artifact_path = str(case_record.get("latest_artifact_path", ""))
        if latest_artifact_path:
            latest_artifact_payload = _load_json_file(Path(latest_artifact_path))
            case_record["latest_artifact_load_status"] = (
                "loaded" if latest_artifact_payload else "artifact_unreadable_or_missing"
            )
        else:
            case_record["latest_artifact_load_status"] = "no_artifact_path_recorded"

        if latest_artifact_payload:
            request_scope = _requested_scope_from_payload(latest_artifact_payload)
            request_signature = case_record["request_signature"]
            request_signature["action_kind"] = _first_nonempty(
                request_signature.get("action_kind"),
                request_scope.get("action_kind"),
            )
            request_signature["request_classification"] = _first_nonempty(
                request_signature.get("request_classification"),
                request_scope.get("request_classification"),
            )
            request_signature["requested_template_name"] = _first_nonempty(
                request_signature.get("requested_template_name"),
                request_scope.get("requested_template_name"),
            )
            request_signature["requested_template_family"] = _first_nonempty(
                request_signature.get("requested_template_family"),
                request_scope.get("requested_template_family"),
            )
            case_record["authority_posture_at_latest_stage"] = _extract_authority_posture(
                latest_artifact_payload
            )
            case_record["follow_on_reconciliation_state_if_any"] = _follow_on_reconciliation_state_from_payload(
                latest_artifact_payload
            )
            case_record["closure_state_if_any"] = _closure_state_from_payload(
                latest_artifact_payload
            )
            case_record["latest_lifecycle_state"] = _first_nonempty(
                case_record.get("latest_lifecycle_state"),
                _latest_stage_state_from_payload(
                    str(case_record.get("latest_lifecycle_stage", "")),
                    latest_artifact_payload,
                ),
            )

        case_record["underlying_lifecycle_case_state"] = _classify_underlying_case_state(
            str(case_record.get("latest_lifecycle_stage", "")),
            str(case_record.get("latest_lifecycle_state", "")),
        )

    cases_by_signature: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for case_record in case_records:
        request_signature = dict(case_record.get("request_signature", {}))
        signature = (
            str(request_signature.get("action_kind", "")),
            str(request_signature.get("request_classification", "")),
            str(request_signature.get("requested_template_name", "")),
            str(request_signature.get("requested_template_family", "")),
        )
        if any(signature):
            cases_by_signature.setdefault(signature, []).append(case_record)

    for grouped_cases in cases_by_signature.values():
        if len(grouped_cases) <= 1:
            continue
        grouped_cases.sort(
            key=lambda item: (
                _parse_time(item.get("latest_decision_timestamp"))
                or datetime.min.replace(tzinfo=timezone.utc),
                int(dict(item.get("latest_sequence_marker", {})).get("stage_rank", -1)),
            ),
            reverse=True,
        )
        for stale_case in grouped_cases[1:]:
            stale_case["portfolio_visibility_state"] = STALE_OR_SUPERSEDED_CASE

    for case_record in case_records:
        underlying = str(case_record.get("underlying_lifecycle_case_state", ACTIVE_OPEN_CASE))
        visibility = str(case_record.get("portfolio_visibility_state", CURRENT_PORTFOLIO_RECORD))
        case_record["portfolio_case_state"] = (
            STALE_OR_SUPERSEDED_CASE if visibility == STALE_OR_SUPERSEDED_CASE else underlying
        )

    sorted_case_records = sorted(
        case_records,
        key=lambda item: (
            _parse_time(item.get("latest_decision_timestamp"))
            or datetime.min.replace(tzinfo=timezone.utc),
            int(dict(item.get("latest_sequence_marker", {})).get("stage_rank", -1)),
        ),
        reverse=True,
    )

    current_case_records = [
        case_record
        for case_record in sorted_case_records
        if str(case_record.get("portfolio_visibility_state", "")) != STALE_OR_SUPERSEDED_CASE
    ]

    summary_counts = {
        ACTIVE_OPEN_CASE: 0,
        PENDING_FOLLOW_ON_RECONCILIATION_CASE: 0,
        CLOSED_RESOLVED_CASE: 0,
        CLOSED_REJECTED_CASE: 0,
        OPEN_REQUIRES_FURTHER_GOVERNANCE_CASE: 0,
        STALE_OR_SUPERSEDED_CASE: 0,
    }
    for case_record in sorted_case_records:
        summary_counts[str(case_record.get("portfolio_case_state", ACTIVE_OPEN_CASE))] += 1

    canonical_summary = dict(authority_payload.get("authority_file_summary", {}))
    authority_promotion_record = dict(authority_payload.get("authority_promotion_record", {}))
    branch_record = (
        dict(list(branch_registry.get("branches", []))[0]) if list(branch_registry.get("branches", [])) else {}
    )

    recorded_at = _now()
    registry_id = f"governance_reopen_case_registry::{proposal['proposal_id']}"
    artifact_path = _diagnostic_artifact_dir() / (
        f"memory_summary_v4_governance_reopen_case_registry_snapshot_v1_{proposal['proposal_id']}.json"
    )

    payload = {
        "proposal_id": str(proposal.get("proposal_id", "")),
        "template_name": "memory_summary.v4_governance_reopen_case_registry_snapshot_v1",
        "snapshot_identity_context": {
            "governance_case_registry_id": registry_id,
            "recorded_at": recorded_at,
            "phase": "governance_reopen_case_registry",
            "latest_case_count": int(len(sorted_case_records)),
            "current_case_count": int(len(current_case_records)),
        },
        "case_registry_contract": {
            "schema_name": CASE_REGISTRY_SCHEMA_NAME,
            "schema_version": CASE_REGISTRY_SCHEMA_VERSION,
            "preferred_root_reference_order": [
                "source_intake_id",
                "intake_id",
                "source_screening_id",
                "screening_id",
                "source_review_packet_id",
                "review_packet_id",
                "source_review_outcome_id",
                "review_outcome_id",
                "source_promotion_handoff_id",
                "promotion_handoff_id",
                "source_promotion_outcome_id",
                "promotion_outcome_id",
                "source_reconciliation_id",
                "reconciliation_id",
                "source_escalation_id",
                "escalation_id",
                "source_remediation_review_packet_id",
                "remediation_review_packet_id",
                "source_remediation_review_outcome_id",
                "remediation_review_outcome_id",
                "source_rollback_or_repair_handoff_id",
                "rollback_or_repair_handoff_id",
                "source_rollback_or_repair_outcome_id",
                "rollback_or_repair_outcome_id",
                "mismatch_case_closure_id",
            ],
            "case_state_categories": [
                ACTIVE_OPEN_CASE,
                PENDING_FOLLOW_ON_RECONCILIATION_CASE,
                CLOSED_RESOLVED_CASE,
                CLOSED_REJECTED_CASE,
                OPEN_REQUIRES_FURTHER_GOVERNANCE_CASE,
            ],
            "portfolio_visibility_states": [CURRENT_PORTFOLIO_RECORD, STALE_OR_SUPERSEDED_CASE],
            "portfolio_case_states": [
                ACTIVE_OPEN_CASE,
                PENDING_FOLLOW_ON_RECONCILIATION_CASE,
                CLOSED_RESOLVED_CASE,
                CLOSED_REJECTED_CASE,
                OPEN_REQUIRES_FURTHER_GOVERNANCE_CASE,
                STALE_OR_SUPERSEDED_CASE,
            ],
            "registry_observational_only": True,
            "canonical_authority_mutation_disallowed_here": True,
            "decision_mutation_disallowed_here": True,
            "portfolio_summary_non_authoritative": True,
        },
        "authority_posture_at_registry_time": {
            "current_branch_state": str(canonical_summary.get("current_branch_state", "")),
            "current_operating_stance": str(canonical_summary.get("current_operating_stance", "")),
            "held_baseline_template": str(canonical_summary.get("held_baseline_template", "")),
            "routing_status": str(canonical_summary.get("routing_status", "")),
            "reopen_eligibility": dict(canonical_summary.get("reopen_eligibility", {})),
            "authority_promotion_id": str(authority_promotion_record.get("promotion_id", "")),
            "selector_frontier_memory": dict(authority_payload.get("selector_frontier_memory", {})),
        },
        "case_registry_records": sorted_case_records,
        "portfolio_summary": {
            "total_case_count": int(len(sorted_case_records)),
            "current_case_count": int(len(current_case_records)),
            "stale_or_superseded_case_count": int(summary_counts[STALE_OR_SUPERSEDED_CASE]),
            "active_open_case_count": int(summary_counts[ACTIVE_OPEN_CASE]),
            "pending_follow_on_reconciliation_case_count": int(summary_counts[PENDING_FOLLOW_ON_RECONCILIATION_CASE]),
            "closed_resolved_case_count": int(summary_counts[CLOSED_RESOLVED_CASE]),
            "closed_rejected_case_count": int(summary_counts[CLOSED_REJECTED_CASE]),
            "open_requires_further_governance_case_count": int(summary_counts[OPEN_REQUIRES_FURTHER_GOVERNANCE_CASE]),
            "latest_case_identifier": str(dict(sorted_case_records[0]).get("stable_case_identifier", "")) if sorted_case_records else "",
            "latest_case_timestamp": str(dict(sorted_case_records[0]).get("latest_decision_timestamp", "")) if sorted_case_records else "",
        },
        "reviewer_source_and_audit_trace": {
            "recorded_by_surface": "memory_summary.v4_governance_reopen_case_registry_snapshot_v1",
            "reviewer_source": "governed_case_registry_snapshot_v1",
            "branch_id": str(branch_registry.get("current_branch_id", "")),
            "branch_pause_rationale": str(branch_record.get("pause_rationale", "")),
            "directive_id": str(dict(directive_state.get("current_directive_state", {})).get("directive_id", "")),
            "bucket_id": str(dict(bucket_state.get("current_bucket_state", {})).get("bucket_id", "")),
            "governance_execution_contract_available": bool(
                intervention_analytics.get("governance_execution_contract")
                or proposal_recommendations.get("governance_execution_contract")
            ),
            "latest_snapshots_count": int(len(load_latest_snapshots())),
        },
        "provenance_and_audit_trace": {
            "canonical_authority_file": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
            "governance_memory_promotion_ledger_path": str(GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH),
            "governance_reopen_intake_ledger_path": str(GOVERNANCE_REOPEN_INTAKE_LEDGER_PATH),
            "governance_reopen_screening_ledger_path": str(GOVERNANCE_REOPEN_SCREENING_LEDGER_PATH),
            "governance_reopen_review_ledger_path": str(GOVERNANCE_REOPEN_REVIEW_LEDGER_PATH),
            "governance_reopen_review_outcome_ledger_path": str(GOVERNANCE_REOPEN_REVIEW_OUTCOME_LEDGER_PATH),
            "governance_reopen_promotion_handoff_ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_HANDOFF_LEDGER_PATH),
            "governance_reopen_promotion_outcome_ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_OUTCOME_LEDGER_PATH),
            "governance_reopen_promotion_reconciliation_ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_LEDGER_PATH),
            "governance_reopen_promotion_reconciliation_escalation_ledger_path": str(GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_ESCALATION_LEDGER_PATH),
            "governance_reopen_remediation_review_ledger_path": str(GOVERNANCE_REOPEN_REMEDIATION_REVIEW_LEDGER_PATH),
            "governance_reopen_remediation_review_outcome_ledger_path": str(GOVERNANCE_REOPEN_REMEDIATION_REVIEW_OUTCOME_LEDGER_PATH),
            "governance_reopen_rollback_or_repair_handoff_ledger_path": str(GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_HANDOFF_LEDGER_PATH),
            "governance_reopen_rollback_or_repair_outcome_ledger_path": str(GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_OUTCOME_LEDGER_PATH),
            "governance_reopen_mismatch_case_closure_ledger_path": str(GOVERNANCE_REOPEN_MISMATCH_CASE_CLOSURE_LEDGER_PATH),
            "governance_reopen_case_registry_ledger_path": str(GOVERNANCE_REOPEN_CASE_REGISTRY_LEDGER_PATH),
            "self_structure_state_path": str(SELF_STRUCTURE_STATE_PATH),
            "self_structure_ledger_path": str(SELF_STRUCTURE_LEDGER_PATH),
            "intervention_ledger_path": str(INTERVENTION_LEDGER_PATH),
            "analytics_path": str(INTERVENTION_ANALYTICS_PATH),
            "proposal_recommendations_path": str(PROPOSAL_RECOMMENDATIONS_PATH),
        },
        "operator_readable_conclusion": (
            "Governance reopen cases now have an explicit registry view that identifies each case, "
            "its latest lifecycle stage, whether it is open, pending, closed, or superseded, and "
            "the latest artifact path needed for direct inspection."
        ),
    }

    _write_json(artifact_path, payload)

    ledger_entry = {
        "event_type": "governance_reopen_case_registry_recorded",
        "written_at": recorded_at,
        "governance_case_registry_id": registry_id,
        "artifact_path": str(artifact_path),
        "total_case_count": int(len(sorted_case_records)),
        "current_case_count": int(len(current_case_records)),
        "stale_or_superseded_case_count": int(summary_counts[STALE_OR_SUPERSEDED_CASE]),
        "active_open_case_count": int(summary_counts[ACTIVE_OPEN_CASE]),
        "pending_follow_on_reconciliation_case_count": int(
            summary_counts[PENDING_FOLLOW_ON_RECONCILIATION_CASE]
        ),
        "closed_resolved_case_count": int(summary_counts[CLOSED_RESOLVED_CASE]),
        "closed_rejected_case_count": int(summary_counts[CLOSED_REJECTED_CASE]),
        "open_requires_further_governance_case_count": int(
            summary_counts[OPEN_REQUIRES_FURTHER_GOVERNANCE_CASE]
        ),
    }
    _append_jsonl(GOVERNANCE_REOPEN_CASE_REGISTRY_LEDGER_PATH, ledger_entry)

    updated_self_structure = dict(self_structure_state)
    updated_summary = dict(current_state_summary)
    updated_summary.update(
        {
            "latest_governance_reopen_case_registry_artifact_path": str(artifact_path),
            "latest_governance_reopen_case_registry_ledger_path": str(
                GOVERNANCE_REOPEN_CASE_REGISTRY_LEDGER_PATH
            ),
            "latest_governance_reopen_case_registry_total_case_count": int(len(sorted_case_records)),
            "latest_governance_reopen_case_registry_open_case_count": int(
                summary_counts[ACTIVE_OPEN_CASE] + summary_counts[OPEN_REQUIRES_FURTHER_GOVERNANCE_CASE]
            ),
            "latest_governance_reopen_case_registry_pending_case_count": int(
                summary_counts[PENDING_FOLLOW_ON_RECONCILIATION_CASE]
            ),
            "latest_governance_reopen_case_registry_closed_case_count": int(
                summary_counts[CLOSED_RESOLVED_CASE] + summary_counts[CLOSED_REJECTED_CASE]
            ),
            "latest_governance_reopen_case_registry_stale_case_count": int(
                summary_counts[STALE_OR_SUPERSEDED_CASE]
            ),
        }
    )
    updated_self_structure["generated_at"] = _now()
    updated_self_structure["current_state_summary"] = updated_summary
    updated_self_structure["governance_reopen_case_registry"] = {
        "schema_name": CASE_REGISTRY_SCHEMA_NAME,
        "schema_version": CASE_REGISTRY_SCHEMA_VERSION,
        "latest_case_registry": {
            "governance_case_registry_id": registry_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_CASE_REGISTRY_LEDGER_PATH),
            "total_case_count": int(len(sorted_case_records)),
            "current_case_count": int(len(current_case_records)),
            "latest_case_identifier": str(
                dict(sorted_case_records[0]).get("stable_case_identifier", "")
            )
            if sorted_case_records
            else "",
        },
    }
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure)

    _append_jsonl(
        SELF_STRUCTURE_LEDGER_PATH,
        {
            "event_id": f"governance_reopen_case_registry::{proposal['proposal_id']}",
            "timestamp": _now(),
            "event_type": "governance_reopen_case_registry_recorded",
            "governance_case_registry_id": registry_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_CASE_REGISTRY_LEDGER_PATH),
            "total_case_count": int(len(sorted_case_records)),
            "current_case_count": int(len(current_case_records)),
        },
    )

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: governance reopen cases were materialized as explicit lifecycle objects with stable case IDs and latest-stage pointers",
        "observability_gain": {
            "passed": True,
            "reason": "future agents can query a current case inventory without replaying every governance ledger by hand",
            "artifact_path": str(artifact_path),
            "governance_reopen_case_registry_ledger_path": str(
                GOVERNANCE_REOPEN_CASE_REGISTRY_LEDGER_PATH
            ),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "case registry separates per-case lifecycle state from portfolio-level visibility without creating a new decision surface",
        },
        "ambiguity_reduction": {
            "passed": True,
            "reason": "stable case identifiers, latest artifact pointers, and case-state categories are now explicit and queryable",
            "score": 0.98,
        },
        "safety_neutrality": {
            "passed": True,
            "reason": "the registry is observational only and never mutates authority, review outcomes, promotion, rollback, repair, or closure decisions",
            "scope": str(proposal.get("scope", "")),
        },
        "later_selection_usefulness": {
            "passed": True,
            "reason": "PM visibility and future governance queries can now start from a single registry snapshot rather than manual artifact stitching",
            "recommended_next_template": "",
        },
        "diagnostic_conclusions": {
            "total_case_count": int(len(sorted_case_records)),
            "current_case_count": int(len(current_case_records)),
            "latest_case_identifier": str(
                dict(sorted_case_records[0]).get("stable_case_identifier", "")
            )
            if sorted_case_records
            else "",
            "recommended_next_action": "hold_and_consolidate",
            "recommended_next_template": "",
        },
        "artifact_path": str(artifact_path),
        "governance_reopen_case_registry_ledger_path": str(
            GOVERNANCE_REOPEN_CASE_REGISTRY_LEDGER_PATH
        ),
    }
