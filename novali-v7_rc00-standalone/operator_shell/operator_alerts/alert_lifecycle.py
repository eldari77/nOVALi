from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from operator_shell.observability.rc83 import load_json_file
from operator_shell.observability.redaction import redact_value

from .evidence import resolve_rc88_artifact_root, write_evidence_bundle
from .schemas import (
    OperatorAlertCandidate,
    OperatorAlertEvidenceBundle,
    OperatorAlertLifecycleEvent,
    OperatorAlertSummary,
)

ALERTS_DIRNAME = "alerts"
LIFECYCLE_EVENTS_DIRNAME = "lifecycle_events"
ALERT_CANDIDATES_LEDGER = "alert_candidates.jsonl"
ALERT_LIFECYCLE_LEDGER = "alert_lifecycle.jsonl"

ALLOWED_TRANSITIONS = {
    "raised": {"acknowledged", "blocked_waiting_operator", "superseded"},
    "acknowledged": {"reviewed", "superseded"},
    "reviewed": {"evidence_only_closed"},
    "blocked_waiting_operator": {"acknowledged", "reviewed"},
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _redact_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): redact_value(value, key=str(key)) for key, value in payload.items()}


def resolve_operator_alert_data_root(package_root: str | Path | None = None) -> Path:
    base_root = Path(package_root).resolve() if package_root is not None else Path.cwd().resolve()
    return (base_root / "data" / "operator_alerts").resolve()


def resolve_alert_candidates_ledger_path(package_root: str | Path | None = None) -> Path:
    return resolve_operator_alert_data_root(package_root) / ALERT_CANDIDATES_LEDGER


def resolve_alert_lifecycle_ledger_path(package_root: str | Path | None = None) -> Path:
    return resolve_operator_alert_data_root(package_root) / ALERT_LIFECYCLE_LEDGER


def resolve_alerts_root(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    return resolve_rc88_artifact_root(package_root, env=env) / ALERTS_DIRNAME


def resolve_lifecycle_events_root(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    return resolve_rc88_artifact_root(package_root, env=env) / LIFECYCLE_EVENTS_DIRNAME


def clear_operator_alert_state(
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    artifact_root = resolve_rc88_artifact_root(package_root, env=env)
    if artifact_root.exists():
        shutil.rmtree(artifact_root)
    artifact_root.mkdir(parents=True, exist_ok=True)
    data_root = resolve_operator_alert_data_root(package_root)
    if data_root.exists():
        shutil.rmtree(data_root)


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_redact_payload(payload), sort_keys=True) + "\n")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_redact_payload(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_alerts(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    payloads: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        payload = load_json_file(path)
        if payload:
            payloads.append(payload)
    return payloads


def load_alert_candidate(
    alert_id: str,
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any] | None:
    path = resolve_alerts_root(package_root, env=env) / f"{alert_id}.json"
    return load_json_file(path)


def raise_alert(
    candidate: OperatorAlertCandidate,
    evidence_bundle: OperatorAlertEvidenceBundle,
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> OperatorAlertCandidate:
    write_evidence_bundle(evidence_bundle, package_root=package_root, env=env)
    alerts_root = resolve_alerts_root(package_root, env=env)
    alert_path = alerts_root / f"{candidate.alert_id}.json"
    _write_json(alert_path, candidate.to_dict())
    _append_jsonl(resolve_alert_candidates_ledger_path(package_root), candidate.to_dict())
    return candidate


def _validate_transition(current_status: str, new_status: str) -> tuple[bool, str]:
    if current_status == new_status:
        return True, ""
    allowed = ALLOWED_TRANSITIONS.get(current_status, set())
    if new_status in allowed:
        return True, ""
    return False, f"Invalid operator alert transition: {current_status} -> {new_status}"


def _write_lifecycle_event(
    event: OperatorAlertLifecycleEvent,
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    path = resolve_lifecycle_events_root(package_root, env=env) / f"{event.event_id}.json"
    _write_json(path, event.to_dict())
    _append_jsonl(resolve_alert_lifecycle_ledger_path(package_root), event.to_dict())
    return str(path)


def _transition_alert(
    *,
    alert_id: str,
    new_status: str,
    action: str,
    actor: str,
    note_redacted: str | None = None,
    replacement_alert_id: str | None = None,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    closure_reason: str | None = None,
) -> dict[str, Any]:
    existing = load_alert_candidate(alert_id, package_root=package_root, env=env)
    if not existing:
        return {
            "ok": False,
            "headline": "The requested operator alert does not exist.",
            "details": [f"Alert id: {alert_id or '<missing>'}"],
        }
    previous_status = str(existing.get("status", "raised") or "raised").strip()
    valid, detail = _validate_transition(previous_status, new_status)
    if not valid:
        return {
            "ok": False,
            "headline": "The requested operator alert action is not valid for the current state.",
            "details": [detail],
        }
    now = _now_iso()
    updated = dict(existing)
    updated["status"] = new_status
    updated["updated_at"] = now
    if new_status == "acknowledged":
        updated["acknowledged_at"] = now
        updated["acknowledged_by"] = actor
    if new_status == "reviewed":
        updated["reviewed_at"] = now
        updated["reviewed_by"] = actor
    if new_status == "evidence_only_closed":
        updated["closure_reason"] = str(closure_reason or note_redacted or "evidence_only_closed").strip()
    if new_status == "superseded":
        updated["superseded_by_alert_id"] = str(replacement_alert_id or "").strip() or None
        updated["closure_reason"] = str(closure_reason or note_redacted or "superseded").strip()
    alert_path = resolve_alerts_root(package_root, env=env) / f"{alert_id}.json"
    _write_json(alert_path, updated)
    event = OperatorAlertLifecycleEvent(
        event_id=f"alert-event-{uuid.uuid4().hex[:12]}",
        alert_id=alert_id,
        action=action,
        previous_status=previous_status,
        new_status=new_status,
        actor=actor,
        note_redacted=str(note_redacted or "").strip() or None,
        replacement_alert_id=str(replacement_alert_id or "").strip() or None,
        created_at=now,
    )
    event_path = _write_lifecycle_event(event, package_root=package_root, env=env)
    return {
        "ok": True,
        "headline": "Operator alert lifecycle event recorded.",
        "details": [
            f"Alert id: {alert_id}",
            f"Action: {action}",
            f"Status: {previous_status} -> {new_status}",
            f"Actor: {actor}",
        ],
        "event_path": event_path,
        "alert": updated,
    }


def acknowledge_alert(
    alert_id: str,
    *,
    actor: str = "operator",
    note_redacted: str | None = None,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    return _transition_alert(
        alert_id=alert_id,
        new_status="acknowledged",
        action="acknowledge",
        actor=actor,
        note_redacted=note_redacted,
        package_root=package_root,
        env=env,
    )


def mark_alert_reviewed(
    alert_id: str,
    *,
    actor: str = "operator",
    note_redacted: str | None = None,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    return _transition_alert(
        alert_id=alert_id,
        new_status="reviewed",
        action="mark_reviewed",
        actor=actor,
        note_redacted=note_redacted,
        package_root=package_root,
        env=env,
    )


def close_alert_evidence_only(
    alert_id: str,
    *,
    actor: str = "operator",
    reason_redacted: str | None = None,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    return _transition_alert(
        alert_id=alert_id,
        new_status="evidence_only_closed",
        action="close_evidence_only",
        actor=actor,
        note_redacted=reason_redacted,
        closure_reason=reason_redacted,
        package_root=package_root,
        env=env,
    )


def supersede_alert(
    alert_id: str,
    *,
    replacement_alert_id: str,
    actor: str = "operator",
    reason_redacted: str | None = None,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    return _transition_alert(
        alert_id=alert_id,
        new_status="superseded",
        action="supersede",
        actor=actor,
        note_redacted=reason_redacted,
        replacement_alert_id=replacement_alert_id,
        closure_reason=reason_redacted,
        package_root=package_root,
        env=env,
    )


def summarize_alerts(
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> OperatorAlertSummary:
    alerts = _load_alerts(resolve_alerts_root(package_root, env=env))
    latest = max(alerts, key=lambda item: str(item.get("updated_at", "") or item.get("created_at", "")), default={})
    statuses = [str(item.get("status", "raised")).strip() or "raised" for item in alerts]
    severities = [str(item.get("severity", "warning")).strip() or "warning" for item in alerts]
    status = "clear"
    if any(item == "blocked_waiting_operator" for item in statuses):
        status = "blocked_waiting_operator"
    elif any(item == "raised" for item in statuses):
        status = "raised"
    elif any(item == "acknowledged" for item in statuses):
        status = "acknowledged"
    elif any(item == "reviewed" for item in statuses):
        status = "reviewed"
    summary = OperatorAlertSummary(
        alert_count=len(alerts),
        raised_count=sum(1 for item in statuses if item == "raised"),
        acknowledged_count=sum(1 for item in statuses if item == "acknowledged"),
        reviewed_count=sum(1 for item in statuses if item == "reviewed"),
        blocked_count=sum(1 for item in statuses if item == "blocked_waiting_operator"),
        critical_count=sum(1 for item in severities if item == "critical"),
        high_count=sum(1 for item in severities if item == "high"),
        warning_count=sum(1 for item in severities if item == "warning"),
        latest_alert_id=str(latest.get("alert_id", "")).strip() or None,
        latest_alert_type=str(latest.get("alert_type", "")).strip() or None,
        latest_evidence_bundle_id=str(latest.get("evidence_bundle_id", "")).strip() or None,
        latest_operator_action_required=str(latest.get("operator_action_required", "")).strip() or None,
        read_only_alert_count=sum(
            1
            for item in alerts
            if str(item.get("source", "")).strip() in {"read_only_adapter", "read_only_adapter_proof"}
        ),
        telemetry_alert_candidate_count=sum(
            1
            for item in alerts
            if str(item.get("source", "")).strip() in {"observability", "telemetry", "runtime_candidate"}
        ),
        telemetry_shutdown_alert_count=sum(
            1
            for item in alerts
            if str(item.get("alert_type", "")).strip()
            in {
                "telemetry_shutdown_timeout",
                "telemetry_export_unavailable",
                "telemetry_unexpected_shutdown_exception",
            }
        ),
        identity_bleed_alert_count=sum(
            1
            for item in alerts
            if str(item.get("alert_type", "")).strip() == "controller_identity_bleed"
        ),
        latest_telemetry_shutdown_alert_id=next(
            (
                str(item.get("alert_id", "")).strip() or None
                for item in alerts
                if str(item.get("alert_type", "")).strip()
                in {
                    "telemetry_shutdown_timeout",
                    "telemetry_export_unavailable",
                    "telemetry_unexpected_shutdown_exception",
                }
            ),
            None,
        ),
        status=status,
    )
    return summary
