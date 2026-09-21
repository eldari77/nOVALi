from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from operator_shell.external_adapter.schemas import ExternalAdapterReviewItem
from operator_shell.observability.rc83 import load_json_file, write_summary_artifacts
from operator_shell.observability.redaction import redact_value

from .observation_replay import resolve_rc87_artifact_root
from .schemas import (
    DEFAULT_READ_ONLY_ADAPTER_KIND,
    DEFAULT_READ_ONLY_ADAPTER_NAME,
    ReadOnlyAdapterReviewContext,
    ReadOnlyMutationRefusal,
)

REVIEW_TICKETS_DIRNAME = "review_tickets"
MUTATION_REFUSALS_DIRNAME = "mutation_refusals"
REVIEW_TICKET_SUMMARY_FILENAME = "review_ticket_summary.json"
REVIEW_TICKET_SUMMARY_MARKDOWN = "review_ticket_summary.md"
MUTATION_REFUSAL_SUMMARY_FILENAME = "mutation_refusal_summary.json"
MUTATION_REFUSAL_SUMMARY_MARKDOWN = "mutation_refusal_summary.md"

WARNING_TRIGGERS = {"read_only_stale_snapshot"}
HIGH_TRIGGERS = {
    "read_only_schema_missing_field",
    "read_only_schema_invalid",
    "read_only_conflicting_observation",
    "read_only_wrong_lane_attribution",
    "read_only_replay_missing",
    "read_only_rollback_ambiguity",
    "read_only_source_unavailable",
    "read_only_integrity_failed",
}
CRITICAL_TRIGGERS = {
    "read_only_mutation_requested",
    "read_only_forbidden_domain_term",
    "read_only_secret_detected",
    "external_mutation_requested",
    "external_command_requested",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _redact_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): redact_value(value, key=str(key)) for key, value in payload.items()}


def resolve_review_tickets_root(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    return resolve_rc87_artifact_root(package_root, env=env) / REVIEW_TICKETS_DIRNAME


def resolve_mutation_refusals_root(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    return resolve_rc87_artifact_root(package_root, env=env) / MUTATION_REFUSALS_DIRNAME


def _severity_for(review_reasons: list[str]) -> str:
    if any(reason in CRITICAL_TRIGGERS for reason in review_reasons):
        return "critical"
    if any(reason in HIGH_TRIGGERS for reason in review_reasons):
        return "high"
    if any(reason in WARNING_TRIGGERS for reason in review_reasons):
        return "warning"
    return "warning" if review_reasons else "info"


def _review_status_for(severity: str, *, evidence_missing: bool = False) -> str:
    if evidence_missing:
        return "evidence_missing"
    if severity == "critical":
        return "blocked"
    if severity == "high":
        return "escalated"
    return "pending_review"


def _operator_action_for(review_reasons: list[str], severity: str) -> str:
    if "read_only_mutation_requested" in review_reasons:
        return (
            "Refuse the mutation path, keep the adapter in read-only mode, and review the bounded proof evidence before continuing."
        )
    if "read_only_forbidden_domain_term" in review_reasons:
        return (
            "Remove forbidden domain content from the snapshot source and preserve the failed evidence packet for review."
        )
    if "read_only_secret_detected" in review_reasons:
        return (
            "Treat the snapshot as compromised evidence, preserve the artifact, and clear the secret-bearing content before any further proof runs."
        )
    if "read_only_wrong_lane_attribution" in review_reasons:
        return (
            "Keep read-only observations attributed to lane_director in rc87 and inspect the lane-isolation evidence before continuing."
        )
    if "read_only_conflicting_observation" in review_reasons:
        return (
            "Inspect the conflicting observation evidence and confirm whether the prior-good snapshot should remain authoritative."
        )
    if severity == "warning":
        return "Inspect the bounded read-only evidence before continuing the sandbox proof."
    return (
        "Review the observation replay, rollback evidence, and validation findings before continuing; no mutation is permitted in rc87."
    )


def build_review_context(
    *,
    review_trigger: str,
    review_reasons: list[str],
    lane_id: str,
    action_id: str,
    action_type: str,
    action_status: str,
    source_ref_hint: str,
    telemetry_trace_hint: str | None = None,
) -> ReadOnlyAdapterReviewContext:
    deduped = list(dict.fromkeys([reason for reason in review_reasons if str(reason).strip()]))
    severity = _severity_for(deduped)
    return ReadOnlyAdapterReviewContext(
        review_trigger=review_trigger,
        severity=severity,
        review_required=bool(deduped),
        review_reasons=deduped,
        lane_id=lane_id,
        action_id=action_id,
        action_type=action_type,
        action_status=action_status,
        source_ref_hint=source_ref_hint,
        operator_action_required=_operator_action_for(deduped, severity),
        telemetry_trace_hint=telemetry_trace_hint,
    )


def build_read_only_review_ticket(
    context: ReadOnlyAdapterReviewContext,
    *,
    governing_directive_ref: str,
    replay_packet_id: str | None = None,
    replay_packet_path_hint: str | None = None,
    rollback_analysis_id: str | None = None,
    rollback_analysis_path_hint: str | None = None,
    checkpoint_ref: str | None = None,
    prior_stable_state_ref: str | None = None,
    evidence_integrity_status: str = "warning",
    package_version: str = "rc87",
) -> ExternalAdapterReviewItem:
    digest = hashlib.sha1(
        "|".join(
            [
                context.action_id,
                context.action_type,
                context.review_trigger,
                ",".join(context.review_reasons),
            ]
        ).encode("utf-8")
    ).hexdigest()[:12]
    review_status = _review_status_for(context.severity)
    return ExternalAdapterReviewItem(
        review_item_id=f"read-only-review-{digest}",
        source="read_only_adapter",
        adapter_name=DEFAULT_READ_ONLY_ADAPTER_NAME,
        adapter_kind=DEFAULT_READ_ONLY_ADAPTER_KIND,
        action_id=context.action_id,
        action_type=context.action_type,
        action_status=context.action_status,
        review_status=review_status,
        review_reasons=list(context.review_reasons),
        severity=context.severity,
        operator_action_required=context.operator_action_required,
        governing_directive_ref=governing_directive_ref,
        replay_packet_id=str(replay_packet_id or "") or None,
        replay_packet_path_hint=str(replay_packet_path_hint or "") or None,
        rollback_analysis_id=str(rollback_analysis_id or "") or None,
        rollback_analysis_path_hint=str(rollback_analysis_path_hint or "") or None,
        checkpoint_ref=str(checkpoint_ref or "") or None,
        prior_stable_state_ref=str(prior_stable_state_ref or "") or None,
        kill_switch_state="inactive",
        created_at=_now_iso(),
        updated_at=_now_iso(),
        telemetry_trace_hint=str(context.telemetry_trace_hint or "") or None,
        evidence_integrity_status=evidence_integrity_status,
        escalation_status=review_status,
        escalation_reasons=list(context.review_reasons),
        package_version=package_version,
    )


def write_review_ticket(
    review_ticket: ExternalAdapterReviewItem,
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    root = resolve_review_tickets_root(package_root, env=env)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{review_ticket.review_item_id}.json"
    path.write_text(json.dumps(_redact_payload(review_ticket.to_dict()), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def write_mutation_refusal(
    refusal: ReadOnlyMutationRefusal,
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    root = resolve_mutation_refusals_root(package_root, env=env)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{refusal.refusal_id}.json"
    path.write_text(json.dumps(_redact_payload(refusal.to_dict()), indent=2, sort_keys=True) + "\n", encoding="utf-8")
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


def summarize_review_tickets(
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    artifact_root = resolve_rc87_artifact_root(package_root, env=env)
    review_root = resolve_review_tickets_root(package_root, env=env)
    tickets = _load_json_objects(review_root)
    latest = max(tickets, key=lambda item: str(item.get("updated_at", "") or item.get("created_at", "")), default={})
    pending_count = sum(1 for item in tickets if str(item.get("review_status", "")).strip() == "pending_review")
    escalated_count = sum(1 for item in tickets if str(item.get("review_status", "")).strip() == "escalated")
    blocked_count = sum(1 for item in tickets if str(item.get("review_status", "")).strip() == "blocked")
    summary = {
        "schema_name": "novali_rc87_review_ticket_summary_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "review_ticket_count": len(tickets),
        "pending_count": pending_count,
        "escalated_count": escalated_count,
        "blocked_count": blocked_count,
        "latest_review_ticket_id": str(latest.get("review_item_id", "")).strip() or None,
        "latest_replay_packet_id": str(latest.get("replay_packet_id", "")).strip() or None,
        "latest_rollback_analysis_id": str(latest.get("rollback_analysis_id", "")).strip() or None,
        "latest_review_reasons": list(latest.get("review_reasons", []) or []),
        "review_tickets_root": str(review_root),
    }
    markdown = "\n".join(
        [
            "# rc87 Review Ticket Summary",
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
        markdown_name=REVIEW_TICKET_SUMMARY_MARKDOWN,
        summary=summary,
        markdown=markdown,
    )
    return summary


def summarize_mutation_refusals(
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    artifact_root = resolve_rc87_artifact_root(package_root, env=env)
    refusal_root = resolve_mutation_refusals_root(package_root, env=env)
    refusals = _load_json_objects(refusal_root)
    latest = max(refusals, key=lambda item: str(item.get("created_at", "")), default={})
    summary = {
        "schema_name": "novali_rc87_mutation_refusal_summary_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "mutation_refusal_count": len(refusals),
        "latest_mutation_refusal_id": str(latest.get("refusal_id", "")).strip() or None,
        "latest_review_ticket_id": str(latest.get("review_ticket_id", "")).strip() or None,
        "latest_replay_packet_id": str(latest.get("replay_packet_id", "")).strip() or None,
        "refusals_root": str(refusal_root),
    }
    markdown = "\n".join(
        [
            "# rc87 Mutation Refusal Summary",
            "",
            f"- Mutation refusal count: {summary['mutation_refusal_count']}",
            f"- Latest mutation refusal id: {summary['latest_mutation_refusal_id'] or '<none>'}",
        ]
    )
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=MUTATION_REFUSAL_SUMMARY_FILENAME,
        markdown_name=MUTATION_REFUSAL_SUMMARY_MARKDOWN,
        summary=summary,
        markdown=markdown,
    )
    return summary
