from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from operator_shell.observability.rc83 import load_json_file
from operator_shell.observability.rc83_2 import load_portal_confirmation_status

from .alert_lifecycle import resolve_alerts_root, summarize_alerts
from .evidence import resolve_evidence_bundles_root
from .schemas import OperatorAlertCandidate


def _portal_trace_confirmation_state(package_root: str | Path | None = None) -> str:
    portal_confirmation = load_portal_confirmation_status(package_root=package_root)
    state = str(portal_confirmation.get("confirmation_state", "not_recorded") or "not_recorded")
    if state == "confirmed":
        return "operator_confirmed"
    if state == "not_confirmed":
        return "not_confirmed"
    return "not_recorded"


def _load_json_objects(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    payloads: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        payload = load_json_file(path)
        if payload:
            payloads.append(payload)
    return payloads


def _default_status(package_root: Path) -> dict[str, Any]:
    return {
        "enabled": True,
        "mode": "local_evidence_only",
        "status": "clear",
        "schema_version": "rc88.v1",
        "alert_count": 0,
        "raised_count": 0,
        "acknowledged_count": 0,
        "reviewed_count": 0,
        "blocked_count": 0,
        "critical_count": 0,
        "high_count": 0,
        "warning_count": 0,
        "latest_alert_id": None,
        "latest_alert_type": None,
        "latest_evidence_bundle_id": None,
        "latest_operator_action_required": None,
        "read_only_alert_count": 0,
        "telemetry_alert_candidate_count": 0,
        "telemetry_shutdown_alert_count": 0,
        "latest_telemetry_shutdown_alert_id": None,
        "identity_bleed_alert_count": 0,
        "lm_portal_trace_confirmation": _portal_trace_confirmation_state(package_root),
        "alerts": [],
        "available_actions": [],
        "advisory_copy": [
            "Alerts are evidence signals, not authority.",
            "Acknowledgement is not approval.",
            "No real external-world mutation.",
            "Telemetry shutdown status is evidence only.",
            "Exporter timeout does not approve or block work by itself.",
            "Controller authority and review gates remain unchanged.",
            "No Space Engineers behavior is active.",
        ],
    }


def _available_actions_for(alert: Mapping[str, Any] | None) -> list[dict[str, str]]:
    if not alert:
        return []
    alert_id = str(alert.get("alert_id", "")).strip()
    status = str(alert.get("status", "")).strip() or "raised"
    actions: list[dict[str, str]] = []
    if status in {"raised", "blocked_waiting_operator"}:
        actions.append({"action_id": "acknowledge_operator_alert", "label": "acknowledge", "alert_id": alert_id})
    if status in {"raised", "acknowledged", "blocked_waiting_operator"}:
        actions.append({"action_id": "review_operator_alert", "label": "mark reviewed", "alert_id": alert_id})
    if status == "reviewed":
        actions.append({"action_id": "close_operator_alert_evidence_only", "label": "close evidence-only", "alert_id": alert_id})
    if status in {"raised", "acknowledged"}:
        actions.append({"action_id": "supersede_operator_alert", "label": "supersede", "alert_id": alert_id})
    return actions


def _select_focus_alert(alerts: list[dict[str, Any]]) -> dict[str, Any]:
    priority = {
        "blocked_waiting_operator": 0,
        "raised": 1,
        "acknowledged": 2,
        "reviewed": 3,
    }
    focused = sorted(
        (
            alert
            for alert in alerts
            if str(alert.get("status", "")).strip() in priority
        ),
        key=lambda alert: (
            priority.get(str(alert.get("status", "")).strip(), 99),
            str(alert.get("updated_at", "") or alert.get("created_at", "")),
        ),
    )
    if focused:
        return focused[0]
    return alerts[0] if alerts else {}


def load_operator_alerts_status(
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = env or os.environ
    package_root_path = Path(package_root).resolve() if package_root is not None else Path.cwd().resolve()
    payload = _default_status(package_root_path)
    alerts_root = resolve_alerts_root(package_root_path, env=env)
    alerts = _load_json_objects(alerts_root)
    if not alerts:
        return payload
    alerts = sorted(
        alerts,
        key=lambda item: str(item.get("updated_at", "") or item.get("created_at", "")),
        reverse=True,
    )
    summary = summarize_alerts(package_root=package_root_path, env=env)
    latest = _select_focus_alert(alerts)
    payload.update(summary.to_dict())
    payload["alerts"] = [OperatorAlertCandidate(**alert).to_dict() for alert in alerts[:8]]
    payload["latest_alert_id"] = str(latest.get("alert_id", "")).strip() or None
    payload["latest_alert_type"] = str(latest.get("alert_type", "")).strip() or None
    payload["latest_evidence_bundle_id"] = str(latest.get("evidence_bundle_id", "")).strip() or None
    payload["latest_operator_action_required"] = str(
        latest.get("operator_action_required", "")
    ).strip() or None
    payload["latest_status"] = str(latest.get("status", "")).strip() or None
    payload["latest_severity"] = str(latest.get("severity", "")).strip() or None
    payload["latest_acknowledged_at"] = str(latest.get("acknowledged_at", "")).strip() or None
    payload["latest_reviewed_at"] = str(latest.get("reviewed_at", "")).strip() or None
    payload["available_actions"] = _available_actions_for(latest)
    return payload


def merge_operator_alerts_status(
    operator_state_payload: Mapping[str, Any],
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    merged = dict(operator_state_payload)
    merged["operator_alerts"] = load_operator_alerts_status(package_root=package_root, env=env)
    return merged
