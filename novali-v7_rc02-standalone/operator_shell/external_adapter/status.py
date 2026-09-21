from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from operator_shell.observability.config import load_observability_config
from operator_shell.observability.rc83 import load_json_file
from operator_shell.observability.rc83_2 import load_portal_confirmation_status

from .replay import (
    REPLAY_SUMMARY_FILENAME,
    resolve_rc84_artifact_root,
    resolve_rc85_artifact_root,
    resolve_replay_packets_root,
)
from .review_integration import (
    REVIEW_ITEM_LEDGER_SUMMARY_FILENAME,
    load_external_adapter_review_status,
    merge_external_adapter_review_into_snapshot,
)
from .schemas import (
    DEFAULT_ADAPTER_KIND,
    DEFAULT_ADAPTER_NAME,
    RC85_SCHEMA_VERSION,
)

RC84_EXTERNAL_ADAPTER_SUMMARY_NAME = "external_adapter_mock_proof_summary.json"
RC85_EXTERNAL_ADAPTER_SUMMARY_NAME = "review_rollback_integration_summary.json"
EXTERNAL_ADAPTER_SUMMARY_NAME = RC84_EXTERNAL_ADAPTER_SUMMARY_NAME


def _portal_trace_confirmation_state(package_root: str | Path | None = None) -> str:
    portal_confirmation = load_portal_confirmation_status(package_root=package_root)
    state = str(portal_confirmation.get("confirmation_state", "not_recorded") or "not_recorded")
    if state == "confirmed":
        return "operator_confirmed"
    if state == "not_confirmed":
        return "not_confirmed"
    return "not_recorded"


def _first_existing_summary(*paths: Path) -> tuple[Path | None, dict[str, Any]]:
    for path in paths:
        payload = load_json_file(path)
        if payload:
            return path, payload
    return None, {}


def load_external_adapter_status(
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    observability_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    env = env or os.environ
    rc85_artifact_root = resolve_rc85_artifact_root(package_root, env=env)
    rc84_artifact_root = resolve_rc84_artifact_root(package_root, env=env)
    summary_path, summary = _first_existing_summary(
        rc85_artifact_root / RC85_EXTERNAL_ADAPTER_SUMMARY_NAME,
        rc84_artifact_root / RC84_EXTERNAL_ADAPTER_SUMMARY_NAME,
    )
    replay_summary_path, replay_summary = _first_existing_summary(
        rc85_artifact_root / REPLAY_SUMMARY_FILENAME,
        rc84_artifact_root / REPLAY_SUMMARY_FILENAME,
    )
    review_summary_path = rc85_artifact_root / REVIEW_ITEM_LEDGER_SUMMARY_FILENAME
    review_status = load_external_adapter_review_status(package_root=package_root, env=env)
    replay_packets_root = (
        resolve_replay_packets_root(package_root, env=env, version="rc85")
        if (rc85_artifact_root / REPLAY_SUMMARY_FILENAME).exists()
        or (rc85_artifact_root / "replay_packets").exists()
        else resolve_replay_packets_root(package_root, env=env, version="rc84")
    )
    replay_packet_paths = (
        sorted(path for path in replay_packets_root.glob("*.json"))
        if replay_packets_root.exists()
        else []
    )
    config = load_observability_config(env)
    telemetry_enabled = bool(dict(observability_status or {}).get("enabled", config.enabled))
    payload = {
        "enabled": True,
        "mode": "mock_only",
        "status": "ready",
        "adapter_name": DEFAULT_ADAPTER_NAME,
        "adapter_kind": DEFAULT_ADAPTER_KIND,
        "schema_version": RC85_SCHEMA_VERSION,
        "last_proof_result": "unknown",
        "last_action_status": None,
        "last_review_required": False,
        "review_reasons": [],
        "last_replay_packet_id": None,
        "replay_packet_count": len(replay_packet_paths),
        "kill_switch_state": "inactive",
        "telemetry_enabled": telemetry_enabled,
        "lm_portal_trace_confirmation": _portal_trace_confirmation_state(package_root),
        "artifact_path": str(summary_path or review_summary_path),
        "replay_packets_root": str(replay_packets_root),
        "last_review_item_id": str(review_status.get("last_review_item_id", "")).strip() or None,
        "last_rollback_analysis_id": str(review_status.get("last_rollback_analysis_id", "")).strip() or None,
    }
    if summary:
        payload.update(
            {
                "enabled": bool(summary.get("adapter_enabled", summary.get("external_adapter_enabled", payload["enabled"]))),
                "mode": str(summary.get("adapter_mode", summary.get("mode", payload["mode"])) or payload["mode"]),
                "status": str(summary.get("adapter_status", summary.get("adapter_review_status", payload["status"])) or payload["status"]),
                "adapter_name": str(summary.get("adapter_name", payload["adapter_name"]) or payload["adapter_name"]),
                "adapter_kind": str(summary.get("adapter_kind", payload["adapter_kind"]) or payload["adapter_kind"]),
                "schema_version": str(summary.get("schema_version", payload["schema_version"]) or payload["schema_version"]),
                "last_proof_result": str(summary.get("result", payload["last_proof_result"]) or payload["last_proof_result"]),
                "last_action_status": str(summary.get("last_action_status", "")).strip() or None,
                "last_review_required": bool(summary.get("last_review_required", payload["last_review_required"])),
                "review_reasons": list(summary.get("review_reasons", payload["review_reasons"]) or []),
                "last_replay_packet_id": str(summary.get("last_replay_packet_id", "")).strip() or None,
                "kill_switch_state": str(summary.get("kill_switch_state", payload["kill_switch_state"]) or payload["kill_switch_state"]),
            }
        )
    if replay_summary:
        payload["replay_packet_count"] = int(
            replay_summary.get("packet_count", payload["replay_packet_count"]) or payload["replay_packet_count"]
        )
        payload["last_replay_packet_id"] = (
            str(replay_summary.get("last_replay_packet_id", payload["last_replay_packet_id"] or "")).strip()
            or payload["last_replay_packet_id"]
        )
    if review_status.get("status") in {"pending_review", "escalated", "blocked"}:
        payload["status"] = "kill_switch_triggered" if review_status.get("status") == "blocked" and payload["kill_switch_state"] == "triggered" else "review_required"
    if review_status.get("last_review_item_id"):
        payload["last_review_item_id"] = str(review_status.get("last_review_item_id"))
        payload["last_rollback_analysis_id"] = str(review_status.get("last_rollback_analysis_id") or "") or None
        if not payload["last_review_required"]:
            payload["last_review_required"] = review_status.get("status") in {"pending_review", "escalated", "blocked"}
        if not payload["review_reasons"]:
            latest_item = next(iter(review_status.get("review_items", []) or []), {})
            payload["review_reasons"] = list(latest_item.get("review_reasons", []) or [])
    return payload


def merge_external_adapter_status(
    operator_state_payload: Mapping[str, Any],
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    observability_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    merged = dict(operator_state_payload)
    merged["external_adapter"] = load_external_adapter_status(
        package_root=package_root,
        env=env,
        observability_status=observability_status,
    )
    return merge_external_adapter_review_into_snapshot(
        merged,
        package_root=package_root,
        env=env,
    )
