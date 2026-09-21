from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from operator_shell.observability.rc83 import load_json_file
from operator_shell.observability.rc83_2 import load_portal_confirmation_status

from .lane_registry import build_default_lane_registry, resolve_controller_isolation_data_root
from .review_integration import (
    IDENTITY_BLEED_SUMMARY_FILENAME,
    REPLAY_PACKET_SUMMARY_FILENAME,
    REVIEW_TICKET_SUMMARY_FILENAME,
    resolve_identity_bleed_findings_root,
    resolve_rc86_artifact_root,
    resolve_replay_packets_root,
    resolve_review_tickets_root,
)
from .schemas import ControllerIsolationReviewItem


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


def _default_isolation_checks() -> dict[str, str]:
    return {
        "namespace_separation": "pass",
        "no_hidden_shared_scratchpad": "pass",
        "director_channel_required": "pass",
        "telemetry_lane_identity": "pass",
    }


def load_controller_isolation_status(
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = env or os.environ
    package_root_path = Path(package_root).resolve() if package_root is not None else Path.cwd().resolve()
    artifact_root = resolve_rc86_artifact_root(package_root_path, env=env)
    proof_summary = load_json_file(artifact_root / "dual_controller_isolation_summary.json")
    namespace_summary = load_json_file(artifact_root / "lane_namespace_summary.json")
    message_summary = load_json_file(artifact_root / "cross_lane_message_summary.json")
    telemetry_summary = load_json_file(artifact_root / "telemetry_identity_summary.json")
    finding_summary = load_json_file(artifact_root / IDENTITY_BLEED_SUMMARY_FILENAME)
    review_summary = load_json_file(artifact_root / REVIEW_TICKET_SUMMARY_FILENAME)
    replay_summary = load_json_file(artifact_root / REPLAY_PACKET_SUMMARY_FILENAME)
    registry_payload = load_json_file(artifact_root / "lane_registry.json")
    if not registry_payload:
        registry_payload = load_json_file(resolve_controller_isolation_data_root(package_root_path) / "lane_registry.json")
    registry = registry_payload or build_default_lane_registry(package_root_path).to_dict()
    lanes = [
        {
            "lane_id": str(lane.get("lane_id", "")).strip(),
            "lane_role": str(lane.get("lane_role", "")).strip(),
            "active": bool(lane.get("active", False)),
            "mode": str(lane.get("mode", "mock_only") or "mock_only"),
            "adoption_authority": bool(lane.get("adoption_authority", False)),
            "coordination_authority": bool(lane.get("coordination_authority", False)),
            "doctrine_namespace": str(lane.get("doctrine_namespace", "")).strip(),
            "memory_namespace": str(lane.get("memory_namespace", "")).strip(),
            "summary_namespace": str(lane.get("summary_namespace", "")).strip(),
            "intervention_namespace": str(lane.get("intervention_namespace", "")).strip(),
            "replay_namespace": str(lane.get("replay_namespace", "")).strip(),
            "review_namespace": str(lane.get("review_namespace", "")).strip(),
        }
        for lane in list(registry.get("lanes", []) or [])
    ]
    review_tickets = [
        ControllerIsolationReviewItem(**ticket).to_dict()
        for ticket in _load_json_objects(resolve_review_tickets_root(package_root_path, env=env))
    ]
    finding_count = int(finding_summary.get("finding_count", len(_load_json_objects(resolve_identity_bleed_findings_root(package_root_path, env=env)))) or 0)
    high_count = int(finding_summary.get("high_count", 0) or 0)
    critical_count = int(finding_summary.get("critical_count", 0) or 0)
    isolation_checks = {
        **_default_isolation_checks(),
        "namespace_separation": str(namespace_summary.get("namespace_separation", "pass") or "pass"),
        "no_hidden_shared_scratchpad": str(namespace_summary.get("no_hidden_shared_scratchpad", "pass") or "pass"),
        "director_channel_required": str(message_summary.get("director_channel_required", "pass") or "pass"),
        "telemetry_lane_identity": str(telemetry_summary.get("telemetry_lane_identity", "pass") or "pass"),
    }
    status = "ready"
    if critical_count > 0:
        status = "review_blocked"
    elif finding_count > 0 or int(review_summary.get("review_ticket_count", 0) or 0) > 0:
        status = "review_required"
    if proof_summary and str(proof_summary.get("result", "")).strip() == "failure":
        status = "failed" if critical_count == 0 else "review_blocked"
    payload = {
        "enabled": True,
        "mode": "mock_only",
        "status": status,
        "schema_version": "rc86.v1",
        "lanes": lanes,
        "lane_count": len(lanes),
        "isolation_checks": isolation_checks,
        "identity_bleed": {
            "finding_count": finding_count,
            "high_count": high_count,
            "critical_count": critical_count,
            "latest_finding_id": str(finding_summary.get("latest_finding_id", "")).strip() or None,
            "latest_review_ticket_id": str(finding_summary.get("latest_review_ticket_id", "")).strip()
            or str(review_summary.get("latest_review_ticket_id", "")).strip()
            or None,
        },
        "cross_lane_messages": {
            "proposed_count": int(message_summary.get("proposed_count", 0) or 0),
            "approved_count": int(message_summary.get("approved_count", 0) or 0),
            "blocked_count": int(message_summary.get("blocked_count", 0) or 0),
            "unauthorized_count": int(message_summary.get("unauthorized_count", 0) or 0),
            "latest_message_id": str(message_summary.get("latest_message_id", "")).strip() or None,
        },
        "last_proof_result": str(proof_summary.get("result", "unknown") or "unknown"),
        "latest_review_ticket_id": str(review_summary.get("latest_review_ticket_id", "")).strip() or None,
        "latest_replay_packet_id": str(replay_summary.get("latest_replay_packet_id", "")).strip() or None,
        "review_tickets": review_tickets[:8],
        "artifact_path": str(artifact_root / "dual_controller_isolation_summary.json"),
        "review_tickets_root": str(resolve_review_tickets_root(package_root_path, env=env)),
        "replay_packets_root": str(resolve_replay_packets_root(package_root_path, env=env)),
        "lm_portal_trace_confirmation": _portal_trace_confirmation_state(package_root_path),
        "advisory_copy": [
            "Identity lanes are isolation scaffolding, not independent controllers.",
            "No new adoption authority is created.",
            "Cross-lane communication must be Director-mediated and replayable.",
            "No Space Engineers behavior is active.",
        ],
    }
    return payload


def _queue_item_from_review_ticket(review_ticket: Mapping[str, Any]) -> dict[str, Any]:
    review_ticket_id = str(review_ticket.get("review_ticket_id", "")).strip()
    finding_type = str(review_ticket.get("finding_type", "")).strip() or "controller_isolation"
    review_status = str(review_ticket.get("review_status", "")).strip() or "pending_review"
    review_reasons = list(review_ticket.get("review_reasons", []) or [])
    reason_summary = ", ".join(str(reason).strip() for reason in review_reasons if str(reason).strip())
    return {
        "review_item_id": review_ticket_id,
        "title": f"Controller isolation review: {finding_type}",
        "reason": reason_summary or "Controller isolation evidence requires review.",
        "reason_summary": reason_summary or "Controller isolation evidence requires review.",
        "reason_class": "controller_isolation_review",
        "action_needed": str(review_ticket.get("operator_action_required", "")).strip(),
        "recommended_action": str(review_ticket.get("operator_action_required", "")).strip(),
        "recommended_action_id": "review_controller_isolation_evidence",
        "severity": str(review_ticket.get("severity", "")).strip() or "warning",
        "blocks_continuation": review_status in {"pending_review", "escalated", "blocked"},
        "route": "/shell",
        "surface_hint": "/shell",
        "source": "controller_isolation",
        "finding_type": finding_type,
        "source_lane_id": str(review_ticket.get("source_lane_id", "")).strip(),
        "target_lane_id": str(review_ticket.get("target_lane_id", "")).strip() or None,
        "replay_packet_id": str(review_ticket.get("replay_packet_id", "")).strip() or None,
    }


def merge_controller_isolation_status(
    operator_state_payload: Mapping[str, Any],
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    merged = dict(operator_state_payload)
    status = load_controller_isolation_status(package_root=package_root, env=env)
    merged["controller_isolation"] = status
    review_tickets = list(status.get("review_tickets", []) or [])
    if not review_tickets:
        return merged

    intervention = dict(merged.get("intervention", {}))
    queue_items = [dict(item) for item in list(intervention.get("queue_items", []) or [])]
    existing_ids = {
        str(item.get("review_item_id", "")).strip()
        for item in queue_items
        if str(item.get("review_item_id", "")).strip()
    }
    added_items: list[dict[str, Any]] = []
    for review_ticket in review_tickets:
        queue_item = _queue_item_from_review_ticket(review_ticket)
        review_item_id = str(queue_item.get("review_item_id", "")).strip()
        if not review_item_id or review_item_id in existing_ids:
            continue
        existing_ids.add(review_item_id)
        added_items.append(queue_item)
    if not added_items:
        return merged

    queue_items.extend(added_items)
    intervention["queue_items"] = queue_items
    intervention["required"] = True
    intervention["pending_review_count"] = int(intervention.get("pending_review_count", 0) or 0) + len(added_items)
    intervention["blocking_review_count"] = int(intervention.get("blocking_review_count", 0) or 0) + sum(
        1 for item in added_items if bool(item.get("blocks_continuation", False))
    )
    intervention["total_review_item_count"] = int(
        intervention.get("total_review_item_count", len(queue_items) - len(added_items)) or 0
    ) + len(added_items)
    if not str(intervention.get("summary", "")).strip():
        intervention["summary"] = (
            "Controller isolation findings now surface through the existing Review Hold evidence path."
        )
    if not str(intervention.get("reason", "")).strip():
        intervention["reason"] = str(added_items[0].get("reason_summary", "")).strip()
    if not str(intervention.get("recommended_action", "")).strip():
        intervention["recommended_action"] = "Review controller isolation evidence"
    if not str(intervention.get("recommended_action_detail", "")).strip():
        intervention["recommended_action_detail"] = str(
            added_items[0].get("action_needed", "")
        ).strip()
    intervention["review_required_state"] = "controller_isolation_review"
    intervention["review_workspace_label"] = "Controller isolation review"
    if not str(intervention.get("primary_reason_class", "")).strip():
        intervention["primary_reason_class"] = "controller_isolation_review"
    if not str(intervention.get("current_primary_review_item_id", "")).strip():
        intervention["current_primary_review_item_id"] = str(
            added_items[0].get("review_item_id", "")
        ).strip()
    if not str(intervention.get("current_primary_review_title", "")).strip():
        intervention["current_primary_review_title"] = str(
            added_items[0].get("title", "")
        ).strip()
    if not str(intervention.get("next_state_after_review", "")).strip():
        intervention["next_state_after_review"] = (
            "Controller isolation evidence remains operator-gated until the lane-bleed findings are reviewed."
        )
    merged["intervention"] = intervention

    operator_state = dict(merged.get("operator_state", {}))
    operator_state["review_required"] = True
    operator_state["intervention_required"] = True
    merged["operator_state"] = operator_state
    return merged
