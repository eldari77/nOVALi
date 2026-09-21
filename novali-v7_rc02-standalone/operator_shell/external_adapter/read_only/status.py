from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from operator_shell.observability.config import load_observability_config
from operator_shell.observability.rc83 import load_json_file
from operator_shell.observability.rc83_2 import load_portal_confirmation_status

from .observation_replay import OBSERVATION_REPLAY_SUMMARY_FILENAME, resolve_observation_replay_packets_root, resolve_rc87_artifact_root
from .review_integration import MUTATION_REFUSAL_SUMMARY_FILENAME, REVIEW_TICKET_SUMMARY_FILENAME, resolve_review_tickets_root
from .rollback import ROLLBACK_ANALYSIS_SUMMARY_FILENAME
from .schemas import DEFAULT_READ_ONLY_ADAPTER_KIND, DEFAULT_READ_ONLY_ADAPTER_NAME, ReadOnlyAdapterStatus, RC87_SCHEMA_VERSION

SUMMARY_JSON_NAME = "read_only_adapter_sandbox_summary.json"


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


def _default_status(*, package_root: Path, env: Mapping[str, str], observability_status: Mapping[str, Any] | None = None) -> dict[str, Any]:
    config = load_observability_config(env)
    telemetry_enabled = bool(dict(observability_status or {}).get("enabled", config.enabled))
    status = ReadOnlyAdapterStatus(
        enabled=True,
        mode="fixture_read_only",
        status="ready",
        adapter_name=DEFAULT_READ_ONLY_ADAPTER_NAME,
        adapter_kind=DEFAULT_READ_ONLY_ADAPTER_KIND,
        source_kind="static_fixture",
        environment_kind="generic_non_se_sandbox",
        latest_snapshot_id=None,
        latest_replay_packet_id=None,
        latest_review_ticket_id=None,
        latest_rollback_analysis_id=None,
        latest_mutation_refusal_id=None,
        validation_status="unknown",
        integrity_status="unknown",
        review_required=False,
        review_reasons=[],
        mutation_allowed=False,
        mutation_refused_count=0,
        observation_count=0,
        bad_snapshot_count=0,
        stale_snapshot_count=0,
        conflicting_observation_count=0,
        lane_id=None,
        lane_attribution_status="unknown",
        lm_portal_trace_confirmation=_portal_trace_confirmation_state(package_root),
        advisory_copy=[
            "Read-only adapter: observation only.",
            "No real external-world mutation.",
            "Observation replay packets are evidence, not authority.",
            "Controller authority and review gates remain unchanged.",
            "No Space Engineers behavior is active.",
        ],
    )
    payload = status.to_dict()
    payload["telemetry_enabled"] = telemetry_enabled
    payload["review_tickets"] = []
    return payload


def load_read_only_adapter_status(
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    observability_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    env = env or os.environ
    package_root_path = Path(package_root).resolve() if package_root is not None else Path.cwd().resolve()
    artifact_root = resolve_rc87_artifact_root(package_root_path, env=env)
    payload = _default_status(package_root=package_root_path, env=env, observability_status=observability_status)
    summary = load_json_file(artifact_root / SUMMARY_JSON_NAME)
    replay_summary = load_json_file(artifact_root / OBSERVATION_REPLAY_SUMMARY_FILENAME)
    validation_summary = load_json_file(artifact_root / "observation_validation_summary.json")
    rollback_summary = load_json_file(artifact_root / ROLLBACK_ANALYSIS_SUMMARY_FILENAME)
    review_summary = load_json_file(artifact_root / REVIEW_TICKET_SUMMARY_FILENAME)
    mutation_summary = load_json_file(artifact_root / MUTATION_REFUSAL_SUMMARY_FILENAME)
    lane_summary = load_json_file(artifact_root / "lane_attribution_summary.json")
    packets_root = resolve_observation_replay_packets_root(package_root_path, env=env)
    payload["observation_count"] = int(replay_summary.get("packet_count", 0) or 0)
    payload["mutation_refused_count"] = int(mutation_summary.get("mutation_refusal_count", 0) or 0)
    payload["latest_replay_packet_id"] = str(replay_summary.get("latest_replay_packet_id", "")).strip() or None
    payload["latest_snapshot_id"] = str(replay_summary.get("latest_snapshot_id", "")).strip() or None
    payload["latest_review_ticket_id"] = str(review_summary.get("latest_review_ticket_id", "")).strip() or None
    payload["latest_rollback_analysis_id"] = str(rollback_summary.get("latest_rollback_analysis_id", "")).strip() or None
    payload["latest_mutation_refusal_id"] = str(mutation_summary.get("latest_mutation_refusal_id", "")).strip() or None
    payload["validation_status"] = str(validation_summary.get("latest_validation_status", payload["validation_status"]) or payload["validation_status"])
    payload["integrity_status"] = str(validation_summary.get("latest_integrity_status", payload["integrity_status"]) or payload["integrity_status"])
    payload["bad_snapshot_count"] = int(validation_summary.get("bad_snapshot_count", 0) or 0)
    payload["stale_snapshot_count"] = int(validation_summary.get("stale_snapshot_count", 0) or 0)
    payload["conflicting_observation_count"] = int(validation_summary.get("conflicting_observation_count", 0) or 0)
    payload["lane_id"] = str(lane_summary.get("latest_lane_id", "")).strip() or None
    payload["lane_attribution_status"] = str(lane_summary.get("latest_lane_attribution_status", payload["lane_attribution_status"]) or payload["lane_attribution_status"])
    payload["review_required"] = bool(
        summary.get("review_required", False)
        or int(review_summary.get("review_ticket_count", 0) or 0) > 0
    )
    payload["review_reasons"] = list(summary.get("review_reasons", []) or validation_summary.get("latest_review_reasons", []) or [])
    if int(review_summary.get("blocked_count", 0) or 0) > 0 or payload["mutation_refused_count"] > 0:
        payload["status"] = "review_blocked"
    elif int(review_summary.get("review_ticket_count", 0) or 0) > 0 or payload["review_required"]:
        payload["status"] = "review_required"
    elif payload["observation_count"] > 0:
        payload["status"] = "observed"
    if summary:
        payload["status"] = str(summary.get("adapter_status", payload["status"]) or payload["status"])
    payload["artifact_path"] = str(artifact_root / SUMMARY_JSON_NAME)
    payload["replay_packets_root"] = str(packets_root)
    payload["review_tickets"] = _load_json_objects(resolve_review_tickets_root(package_root_path, env=env))[:8]
    return payload


def _queue_item_from_review_ticket(review_ticket: Mapping[str, Any]) -> dict[str, Any]:
    review_item_id = str(review_ticket.get("review_item_id", "")).strip()
    review_reasons = list(review_ticket.get("review_reasons", []) or [])
    reason_summary = ", ".join(str(reason).strip() for reason in review_reasons if str(reason).strip())
    return {
        "review_item_id": review_item_id,
        "title": "Read-only adapter review",
        "reason": reason_summary or "Read-only adapter evidence requires review.",
        "reason_summary": reason_summary or "Read-only adapter evidence requires review.",
        "reason_class": "read_only_adapter_review",
        "action_needed": str(review_ticket.get("operator_action_required", "")).strip(),
        "recommended_action": str(review_ticket.get("operator_action_required", "")).strip(),
        "recommended_action_id": "review_read_only_adapter_evidence",
        "severity": str(review_ticket.get("severity", "")).strip() or "warning",
        "blocks_continuation": str(review_ticket.get("review_status", "")).strip() in {"pending_review", "escalated", "blocked"},
        "route": "/shell",
        "surface_hint": "/shell",
        "source": "read_only_adapter",
        "replay_packet_id": str(review_ticket.get("replay_packet_id", "")).strip() or None,
    }


def merge_read_only_adapter_status(
    operator_state_payload: Mapping[str, Any],
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    observability_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    merged = dict(operator_state_payload)
    status = load_read_only_adapter_status(
        package_root=package_root,
        env=env,
        observability_status=observability_status,
    )
    merged["read_only_adapter"] = status
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
        intervention["summary"] = "Read-only adapter evidence now surfaces through the existing Review Hold path."
    if not str(intervention.get("reason", "")).strip():
        intervention["reason"] = str(added_items[0].get("reason_summary", "")).strip()
    if not str(intervention.get("recommended_action", "")).strip():
        intervention["recommended_action"] = "Review read-only adapter evidence"
    if not str(intervention.get("recommended_action_detail", "")).strip():
        intervention["recommended_action_detail"] = str(added_items[0].get("action_needed", "")).strip()
    intervention["review_required_state"] = "read_only_adapter_review"
    intervention["review_workspace_label"] = "Read-only adapter review"
    if not str(intervention.get("primary_reason_class", "")).strip():
        intervention["primary_reason_class"] = "read_only_adapter_review"
    if not str(intervention.get("current_primary_review_item_id", "")).strip():
        intervention["current_primary_review_item_id"] = str(added_items[0].get("review_item_id", "")).strip()
    if not str(intervention.get("current_primary_review_title", "")).strip():
        intervention["current_primary_review_title"] = str(added_items[0].get("title", "")).strip()
    if not str(intervention.get("next_state_after_review", "")).strip():
        intervention["next_state_after_review"] = "Read-only adapter evidence remains operator-gated until the observation issue is reviewed."
    merged["intervention"] = intervention
    operator_state = dict(merged.get("operator_state", {}))
    operator_state["review_required"] = True
    operator_state["intervention_required"] = True
    merged["operator_state"] = operator_state
    return merged
