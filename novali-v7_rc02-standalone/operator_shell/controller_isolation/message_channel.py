from __future__ import annotations

import hashlib

from operator_shell.observability.redaction import redact_value

from .schemas import CrossLaneMessageEnvelope, DirectorApprovalRecord

ALLOWED_MESSAGE_TYPES = {
    "coordination_note",
    "status_summary",
    "review_request",
    "replay_reference",
    "rollback_reference",
    "proof_signal",
}
FORBIDDEN_MESSAGE_TYPES = {
    "external_action_request",
    "live_mutation_request",
    "space_engineers_action_request",
    "faction_command",
    "player_communication",
    "server_command",
    "doctrine_transfer",
    "memory_dump",
    "hidden_scratchpad_write",
}


def _message_id(source_lane_id: str, target_lane_id: str, message_type: str, payload_summary: str) -> str:
    digest = hashlib.sha1(
        "|".join([source_lane_id, target_lane_id, message_type, payload_summary]).encode("utf-8")
    ).hexdigest()[:12]
    return f"lane-message-{digest}"


def evaluate_cross_lane_message(
    *,
    source_lane_id: str,
    target_lane_id: str,
    message_type: str,
    payload_summary: str,
    allowed_scope: str,
    mediated_by_lane_id: str | None = None,
    replay_packet_id: str | None = None,
) -> tuple[CrossLaneMessageEnvelope, DirectorApprovalRecord]:
    normalized_type = str(message_type or "").strip()
    normalized_mediator = str(mediated_by_lane_id or "").strip() or "lane_director"
    review_reasons: list[str] = []
    approval_status = "proposed"
    if normalized_type in FORBIDDEN_MESSAGE_TYPES:
        approval_status = "rejected"
        review_reasons.append("forbidden_message_type")
    elif normalized_mediator != "lane_director":
        approval_status = "blocked"
        review_reasons.append("director_mediation_required")
    elif normalized_type not in ALLOWED_MESSAGE_TYPES:
        approval_status = "review_required"
        review_reasons.append("unknown_message_type")
    else:
        approval_status = "director_approved"
    message_id = _message_id(source_lane_id, target_lane_id, normalized_type, payload_summary)
    approval = DirectorApprovalRecord(
        message_id=message_id,
        approval_status=approval_status,
        review_required=bool(review_reasons),
        review_reasons=list(review_reasons),
    )
    envelope = CrossLaneMessageEnvelope(
        message_id=message_id,
        source_lane_id=source_lane_id,
        target_lane_id=target_lane_id,
        mediated_by_lane_id=normalized_mediator,
        approval_record_id=approval.approval_record_id,
        approval_status=approval_status,
        message_type=normalized_type,
        payload_summary_redacted=str(redact_value(payload_summary, key="payload_summary") or ""),
        allowed_scope=allowed_scope,
        review_required=bool(review_reasons),
        review_reasons=list(review_reasons),
        replay_packet_id=replay_packet_id,
        delivered_at=approval.created_at if approval_status == "director_approved" else None,
    )
    return envelope, approval
