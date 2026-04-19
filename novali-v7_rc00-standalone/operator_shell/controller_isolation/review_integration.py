from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from operator_shell.observability.rc83 import load_json_file, write_summary_artifacts
from operator_shell.observability.redaction import redact_value

from .schemas import (
    ControllerIsolationReplayPacket,
    ControllerIsolationReviewItem,
    IdentityBleedFinding,
)

RC86_ARTIFACT_SUBPATH = Path("artifacts/operator_proof/rc86")
LANE_ARTIFACTS_DIRNAME = "lane_artifacts"
IDENTITY_BLEED_FINDINGS_DIRNAME = "identity_bleed_findings"
REVIEW_TICKETS_DIRNAME = "review_tickets"
REPLAY_PACKETS_DIRNAME = "replay_packets"
IDENTITY_BLEED_SUMMARY_FILENAME = "identity_bleed_summary.json"
REVIEW_TICKET_SUMMARY_FILENAME = "review_ticket_summary.json"
REPLAY_PACKET_SUMMARY_FILENAME = "replay_packet_summary.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _redact_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): redact_value(value, key=str(key)) for key, value in payload.items()}


def resolve_rc86_artifact_root(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    env = env or os.environ
    configured = str(env.get("RC86_PROOF_ARTIFACT_ROOT") or "").strip()
    base_root = Path(package_root).resolve() if package_root is not None else None
    if configured:
        configured_path = Path(configured)
        if configured_path.is_absolute():
            return configured_path.resolve()
        if base_root is not None:
            return (base_root / configured_path).resolve()
        return configured_path.resolve()
    if base_root is not None:
        return (base_root / RC86_ARTIFACT_SUBPATH).resolve()
    return RC86_ARTIFACT_SUBPATH.resolve()


def resolve_lane_artifacts_root(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    return resolve_rc86_artifact_root(package_root, env=env) / LANE_ARTIFACTS_DIRNAME


def resolve_identity_bleed_findings_root(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    return resolve_rc86_artifact_root(package_root, env=env) / IDENTITY_BLEED_FINDINGS_DIRNAME


def resolve_review_tickets_root(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    return resolve_rc86_artifact_root(package_root, env=env) / REVIEW_TICKETS_DIRNAME


def resolve_replay_packets_root(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    return resolve_rc86_artifact_root(package_root, env=env) / REPLAY_PACKETS_DIRNAME


def clear_rc86_artifacts(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> None:
    artifact_root = resolve_rc86_artifact_root(package_root, env=env)
    if artifact_root.exists():
        shutil.rmtree(artifact_root)
    artifact_root.mkdir(parents=True, exist_ok=True)


def copy_lane_artifact(
    source_path: str | Path,
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    target_name: str | None = None,
) -> str:
    source = Path(source_path).resolve()
    target = resolve_lane_artifacts_root(package_root, env=env) / (target_name or source.name)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return str(target)


def build_review_ticket_from_finding(
    finding: IdentityBleedFinding,
    *,
    replay_packet_id: str | None = None,
    replay_packet_path_hint: str | None = None,
    message_id: str | None = None,
    evidence_integrity_status: str = "clean",
) -> ControllerIsolationReviewItem:
    review_status = "pending_review"
    if finding.severity == "high":
        review_status = "escalated"
    if finding.severity == "critical":
        review_status = "blocked"
    digest = hashlib.sha1(
        "|".join([finding.finding_id, finding.finding_type, finding.severity]).encode("utf-8")
    ).hexdigest()[:12]
    operator_action_required = (
        "Inspect the lane-isolation evidence, keep the lanes inactive, and clear the finding before continuing."
    )
    return ControllerIsolationReviewItem(
        review_ticket_id=f"isolation-review-{digest}",
        finding_id=finding.finding_id,
        finding_type=finding.finding_type,
        lane_id=finding.source_lane_id,
        source_lane_id=finding.source_lane_id,
        target_lane_id=finding.target_lane_id,
        review_trigger=finding.finding_type,
        review_status=review_status,
        severity=finding.severity,
        operator_action_required=operator_action_required,
        review_reasons=[finding.finding_type, finding.evidence_summary_redacted],
        replay_packet_id=str(replay_packet_id or "") or None,
        replay_packet_path_hint=str(replay_packet_path_hint or "") or None,
        message_id=str(message_id or "") or None,
        evidence_integrity_status=evidence_integrity_status,
    )


def build_replay_packet(
    *,
    lane_id: str,
    source_lane_id: str,
    target_lane_id: str | None,
    intended_effect: str,
    status: str,
    result_summary: str,
    review_required: bool,
    review_reasons: list[str],
    evidence_integrity_status: str,
    message_id: str | None = None,
    finding_id: str | None = None,
    review_ticket_id: str | None = None,
) -> ControllerIsolationReplayPacket:
    digest = hashlib.sha1(
        "|".join(
            [
                lane_id,
                source_lane_id,
                str(target_lane_id or ""),
                status,
                intended_effect,
                str(message_id or ""),
                str(finding_id or ""),
            ]
        ).encode("utf-8")
    ).hexdigest()[:12]
    return ControllerIsolationReplayPacket(
        replay_packet_id=f"isolation-replay-{digest}",
        lane_id=lane_id,
        source_lane_id=source_lane_id,
        target_lane_id=target_lane_id,
        message_id=str(message_id or "") or None,
        finding_id=str(finding_id or "") or None,
        review_ticket_id=str(review_ticket_id or "") or None,
        intended_effect=intended_effect,
        status=status,
        result_summary_redacted=str(redact_value(result_summary, key="result_summary") or ""),
        review_required=bool(review_required),
        review_reasons=list(review_reasons),
        evidence_integrity_status=evidence_integrity_status,
    )


def write_identity_bleed_finding(
    finding: IdentityBleedFinding,
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    root = resolve_identity_bleed_findings_root(package_root, env=env)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{finding.finding_id}.json"
    path.write_text(json.dumps(_redact_payload(finding.to_dict()), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def write_review_ticket(
    review_ticket: ControllerIsolationReviewItem,
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    root = resolve_review_tickets_root(package_root, env=env)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{review_ticket.review_ticket_id}.json"
    path.write_text(json.dumps(_redact_payload(review_ticket.to_dict()), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def write_replay_packet(
    replay_packet: ControllerIsolationReplayPacket,
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    root = resolve_replay_packets_root(package_root, env=env)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{replay_packet.replay_packet_id}.json"
    path.write_text(json.dumps(_redact_payload(replay_packet.to_dict()), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def _load_json_objects(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    payloads: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        payload = load_json_file(path)
        if payload:
            payloads.append(payload)
    return payloads


def summarize_identity_bleed_findings(
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    artifact_root = resolve_rc86_artifact_root(package_root, env=env)
    findings_root = resolve_identity_bleed_findings_root(package_root, env=env)
    findings = _load_json_objects(findings_root)
    latest = max(findings, key=lambda item: str(item.get("created_at", "")), default={})
    high_count = sum(1 for item in findings if str(item.get("severity", "")).strip() == "high")
    critical_count = sum(1 for item in findings if str(item.get("severity", "")).strip() == "critical")
    summary = {
        "schema_name": "novali_rc86_identity_bleed_summary_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "finding_count": len(findings),
        "high_count": high_count,
        "critical_count": critical_count,
        "latest_finding_id": str(latest.get("finding_id", "")).strip() or None,
        "latest_review_ticket_id": str(latest.get("review_ticket_id", "")).strip() or None,
        "findings_root": str(findings_root),
    }
    markdown = "\n".join(
        [
            "# rc86 Identity Bleed Summary",
            "",
            f"- Finding count: {summary['finding_count']}",
            f"- High count: {summary['high_count']}",
            f"- Critical count: {summary['critical_count']}",
            f"- Latest finding id: {summary['latest_finding_id'] or '<none>'}",
        ]
    )
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=IDENTITY_BLEED_SUMMARY_FILENAME,
        markdown_name="identity_bleed_summary.md",
        summary=summary,
        markdown=markdown,
    )
    return summary


def summarize_review_tickets(
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    artifact_root = resolve_rc86_artifact_root(package_root, env=env)
    review_root = resolve_review_tickets_root(package_root, env=env)
    tickets = _load_json_objects(review_root)
    latest = max(tickets, key=lambda item: str(item.get("updated_at", "") or item.get("created_at", "")), default={})
    pending_count = sum(1 for item in tickets if str(item.get("review_status", "")).strip() == "pending_review")
    escalated_count = sum(1 for item in tickets if str(item.get("review_status", "")).strip() == "escalated")
    blocked_count = sum(1 for item in tickets if str(item.get("review_status", "")).strip() == "blocked")
    summary = {
        "schema_name": "novali_rc86_review_ticket_summary_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "review_ticket_count": len(tickets),
        "pending_count": pending_count,
        "escalated_count": escalated_count,
        "blocked_count": blocked_count,
        "latest_review_ticket_id": str(latest.get("review_ticket_id", "")).strip() or None,
        "latest_finding_id": str(latest.get("finding_id", "")).strip() or None,
        "latest_replay_packet_id": str(latest.get("replay_packet_id", "")).strip() or None,
        "review_tickets_root": str(review_root),
    }
    markdown = "\n".join(
        [
            "# rc86 Review Ticket Summary",
            "",
            f"- Review ticket count: {summary['review_ticket_count']}",
            f"- Pending count: {summary['pending_count']}",
            f"- Escalated count: {summary['escalated_count']}",
            f"- Blocked count: {summary['blocked_count']}",
            f"- Latest review ticket id: {summary['latest_review_ticket_id'] or '<none>'}",
        ]
    )
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=REVIEW_TICKET_SUMMARY_FILENAME,
        markdown_name="review_ticket_summary.md",
        summary=summary,
        markdown=markdown,
    )
    return summary


def summarize_replay_packets(
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    artifact_root = resolve_rc86_artifact_root(package_root, env=env)
    replay_root = resolve_replay_packets_root(package_root, env=env)
    packets = _load_json_objects(replay_root)
    latest = max(packets, key=lambda item: str(item.get("created_at", "")), default={})
    blocked_count = sum(1 for item in packets if str(item.get("status", "")).strip() == "blocked")
    review_required_count = sum(
        1 for item in packets if str(item.get("status", "")).strip() == "review_required"
    )
    approved_count = sum(
        1 for item in packets if str(item.get("status", "")).strip() == "delivered_mock_only"
    )
    summary = {
        "schema_name": "novali_rc86_replay_packet_summary_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "replay_packet_count": len(packets),
        "approved_count": approved_count,
        "blocked_count": blocked_count,
        "review_required_count": review_required_count,
        "latest_replay_packet_id": str(latest.get("replay_packet_id", "")).strip() or None,
        "latest_review_ticket_id": str(latest.get("review_ticket_id", "")).strip() or None,
        "replay_packets_root": str(replay_root),
    }
    markdown = "\n".join(
        [
            "# rc86 Replay Packet Summary",
            "",
            f"- Replay packet count: {summary['replay_packet_count']}",
            f"- Approved count: {summary['approved_count']}",
            f"- Blocked count: {summary['blocked_count']}",
            f"- Review-required count: {summary['review_required_count']}",
            f"- Latest replay packet id: {summary['latest_replay_packet_id'] or '<none>'}",
        ]
    )
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=REPLAY_PACKET_SUMMARY_FILENAME,
        markdown_name="replay_packet_summary.md",
        summary=summary,
        markdown=markdown,
    )
    return summary
