from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from operator_shell.observability.rc83 import load_json_file, write_summary_artifacts
from operator_shell.observability.redaction import redact_value

from .review import escalation_for_review
from .schemas import (
    DEFAULT_ADAPTER_KIND,
    DEFAULT_ADAPTER_NAME,
    EvidenceIntegrityResult,
    ExternalAdapterReviewItem,
    ReviewHoldStatusSummary,
    RollbackAnalysis,
)

RC85_ARTIFACT_SUBPATH = Path("artifacts/operator_proof/rc85")
REVIEW_ITEMS_DIRNAME = "review_items"
ROLLBACK_ANALYSIS_DIRNAME = "rollback_analysis"
REVIEW_ITEM_LEDGER_SUMMARY_FILENAME = "review_item_ledger_summary.json"
REVIEW_ITEM_LEDGER_MARKDOWN = "review_item_ledger_summary.md"
ROLLBACK_ANALYSIS_SUMMARY_FILENAME = "rollback_analysis_summary.json"
ROLLBACK_ANALYSIS_MARKDOWN = "rollback_analysis_summary.md"
EVIDENCE_INTEGRITY_SUMMARY_FILENAME = "evidence_integrity_summary.json"
EVIDENCE_INTEGRITY_MARKDOWN = "evidence_integrity_summary.md"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _artifact_hint(path: str | Path | None, *, package_root: str | Path | None = None) -> str | None:
    if not path:
        return None
    candidate = Path(path)
    if package_root is not None:
        try:
            return str(candidate.resolve().relative_to(Path(package_root).resolve()))
        except ValueError:
            return candidate.name
    return candidate.name


def _redact_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): redact_value(value, key=str(key)) for key, value in payload.items()}


def _as_payload(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict"):
        return dict(value.to_dict())
    return dict(value or {})


def resolve_rc85_artifact_root(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    env = env or os.environ
    configured = str(env.get("RC85_PROOF_ARTIFACT_ROOT") or "").strip()
    base_root = Path(package_root).resolve() if package_root is not None else None
    if configured:
        configured_path = Path(configured)
        if configured_path.is_absolute():
            return configured_path.resolve()
        if base_root is not None:
            return (base_root / configured_path).resolve()
        return configured_path.resolve()
    if base_root is not None:
        return (base_root / RC85_ARTIFACT_SUBPATH).resolve()
    return RC85_ARTIFACT_SUBPATH.resolve()


def resolve_review_items_root(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    return resolve_rc85_artifact_root(package_root, env=env) / REVIEW_ITEMS_DIRNAME


def resolve_rollback_analysis_root(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    return resolve_rc85_artifact_root(package_root, env=env) / ROLLBACK_ANALYSIS_DIRNAME


def build_review_item(
    *,
    action_id: str,
    action_type: str,
    action_status: str,
    review_reasons: Iterable[str] | None,
    governing_directive_ref: str,
    adapter_name: str = DEFAULT_ADAPTER_NAME,
    adapter_kind: str = DEFAULT_ADAPTER_KIND,
    replay_packet_id: str | None = None,
    replay_packet_path_hint: str | None = None,
    rollback_analysis_id: str | None = None,
    rollback_analysis_path_hint: str | None = None,
    checkpoint_ref: str | None = None,
    prior_stable_state_ref: str | None = None,
    kill_switch_state: str = "inactive",
    telemetry_trace_hint: str | None = None,
    evidence_integrity_status: str = "warning",
    evidence_missing: bool = False,
    created_at: str | None = None,
    updated_at: str | None = None,
) -> ExternalAdapterReviewItem:
    created = str(created_at or _now_iso())
    updated = str(updated_at or created)
    escalation = escalation_for_review(review_reasons, evidence_missing=evidence_missing)
    digest = hashlib.sha1(
        "|".join(
            [
                str(action_id or ""),
                str(action_type or ""),
                created,
                ",".join(escalation.escalation_reasons),
            ]
        ).encode("utf-8")
    ).hexdigest()[:12]
    return ExternalAdapterReviewItem(
        review_item_id=f"ext-review-{digest}",
        adapter_name=str(adapter_name or DEFAULT_ADAPTER_NAME),
        adapter_kind=str(adapter_kind or DEFAULT_ADAPTER_KIND),
        action_id=str(action_id or ""),
        action_type=str(action_type or ""),
        action_status=str(action_status or ""),
        review_status=escalation.escalation_status,
        review_reasons=list(escalation.escalation_reasons),
        severity=escalation.severity,
        operator_action_required=escalation.operator_action_required,
        governing_directive_ref=str(governing_directive_ref or ""),
        replay_packet_id=str(replay_packet_id or "") or None,
        replay_packet_path_hint=str(replay_packet_path_hint or "") or None,
        rollback_analysis_id=str(rollback_analysis_id or "") or None,
        rollback_analysis_path_hint=str(rollback_analysis_path_hint or "") or None,
        checkpoint_ref=str(checkpoint_ref or "") or None,
        prior_stable_state_ref=str(prior_stable_state_ref or "") or None,
        kill_switch_state=str(kill_switch_state or "inactive"),
        created_at=created,
        updated_at=updated,
        telemetry_trace_hint=str(telemetry_trace_hint or "") or None,
        evidence_integrity_status=str(evidence_integrity_status or "warning"),
        escalation_status=escalation.escalation_status,
        escalation_reasons=list(escalation.escalation_reasons),
    )


def write_review_item(
    review_item: ExternalAdapterReviewItem,
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    review_items_root = resolve_review_items_root(package_root, env=env)
    review_items_root.mkdir(parents=True, exist_ok=True)
    path = review_items_root / f"{review_item.review_item_id}.json"
    payload = _redact_payload(review_item.to_dict())
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def write_rollback_analysis(
    analysis: RollbackAnalysis,
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    rollback_root = resolve_rollback_analysis_root(package_root, env=env)
    rollback_root.mkdir(parents=True, exist_ok=True)
    path = rollback_root / f"{analysis.rollback_analysis_id}.json"
    payload = _redact_payload(analysis.to_dict())
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def load_review_item(path: str | Path) -> dict[str, Any]:
    return load_json_file(path)


def _load_json_objects(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    payloads: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        payload = load_json_file(path)
        if payload:
            payloads.append(payload)
    return payloads


def summarize_review_items(
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    artifact_root = resolve_rc85_artifact_root(package_root, env=env)
    review_items_root = resolve_review_items_root(package_root, env=env)
    review_items = _load_json_objects(review_items_root)
    latest = max(
        review_items,
        key=lambda item: str(item.get("updated_at", "") or item.get("created_at", "") or ""),
        default={},
    )
    pending_count = sum(
        1 for item in review_items if str(item.get("review_status", "")).strip() == "pending_review"
    )
    escalated_count = sum(
        1 for item in review_items if str(item.get("review_status", "")).strip() == "escalated"
    )
    evidence_missing_count = sum(
        1 for item in review_items if str(item.get("review_status", "")).strip() == "evidence_missing"
    )
    blocked_count = sum(
        1 for item in review_items if str(item.get("review_status", "")).strip() == "blocked"
    )
    summary = {
        "schema_name": "novali_rc85_review_item_ledger_summary_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "review_item_count": len(review_items),
        "pending_count": pending_count,
        "escalated_count": escalated_count,
        "evidence_missing_count": evidence_missing_count,
        "blocked_count": blocked_count,
        "last_review_item_id": str(latest.get("review_item_id", "")).strip() or None,
        "last_replay_packet_id": str(latest.get("replay_packet_id", "")).strip() or None,
        "last_rollback_analysis_id": str(latest.get("rollback_analysis_id", "")).strip() or None,
        "review_items_root": str(review_items_root),
    }
    markdown = "\n".join(
        [
            "# rc85 Review Item Ledger Summary",
            "",
            f"- Review item count: {summary['review_item_count']}",
            f"- Pending count: {summary['pending_count']}",
            f"- Escalated count: {summary['escalated_count']}",
            f"- Evidence-missing count: {summary['evidence_missing_count']}",
            f"- Last review item id: {summary['last_review_item_id'] or '<none>'}",
            f"- Review items root: {summary['review_items_root']}",
        ]
    )
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=REVIEW_ITEM_LEDGER_SUMMARY_FILENAME,
        markdown_name=REVIEW_ITEM_LEDGER_MARKDOWN,
        summary=summary,
        markdown=markdown,
    )
    return summary


def summarize_rollback_analyses(
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    artifact_root = resolve_rc85_artifact_root(package_root, env=env)
    rollback_root = resolve_rollback_analysis_root(package_root, env=env)
    analyses = _load_json_objects(rollback_root)
    latest = max(
        analyses,
        key=lambda item: str(item.get("created_at", "") or ""),
        default={},
    )
    ambiguity_count = sum(
        1
        for item in analyses
        if str(item.get("ambiguity_level", "")).strip().lower() not in {"", "low", "none"}
    )
    summary = {
        "schema_name": "novali_rc85_rollback_analysis_summary_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "rollback_analysis_count": len(analyses),
        "ambiguity_count": ambiguity_count,
        "last_rollback_analysis_id": str(latest.get("rollback_analysis_id", "")).strip() or None,
        "last_replay_packet_id": str(latest.get("replay_packet_id", "")).strip() or None,
        "last_checkpoint_ref": str(latest.get("checkpoint_ref", "")).strip() or None,
        "last_ambiguity_level": str(latest.get("ambiguity_level", "")).strip() or None,
        "rollback_analysis_root": str(rollback_root),
    }
    markdown = "\n".join(
        [
            "# rc85 Rollback Analysis Summary",
            "",
            f"- Rollback analysis count: {summary['rollback_analysis_count']}",
            f"- Ambiguity count: {summary['ambiguity_count']}",
            f"- Last rollback analysis id: {summary['last_rollback_analysis_id'] or '<none>'}",
            f"- Last checkpoint ref: {summary['last_checkpoint_ref'] or '<none>'}",
            f"- Rollback analysis root: {summary['rollback_analysis_root']}",
        ]
    )
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=ROLLBACK_ANALYSIS_SUMMARY_FILENAME,
        markdown_name=ROLLBACK_ANALYSIS_MARKDOWN,
        summary=summary,
        markdown=markdown,
    )
    return summary


def evaluate_evidence_integrity(
    *,
    replay_packet: Mapping[str, Any] | Any | None,
    rollback_analysis: Mapping[str, Any] | Any | None = None,
    review_item: Mapping[str, Any] | Any | None = None,
    required_paths: Iterable[str | Path] | None = None,
    fake_seeds: Iterable[str] | None = None,
) -> EvidenceIntegrityResult:
    packet = _as_payload(replay_packet)
    rollback = _as_payload(rollback_analysis)
    review = _as_payload(review_item)
    findings: list[str] = []
    status = "clean"

    def _warn(message: str) -> None:
        nonlocal status
        if status == "clean":
            status = "warning"
        findings.append(message)

    def _fail(message: str) -> None:
        nonlocal status
        status = "failed"
        findings.append(message)

    if not str(packet.get("replay_packet_id", "")).strip():
        _fail("replay_packet_id missing")
    if not str(packet.get("action_id", "")).strip():
        _fail("action_id missing")
    if not str(packet.get("status", "")).strip():
        _fail("action status missing")
    review_required = bool(packet.get("review_required", False))
    review_reasons = list(packet.get("review_reasons", []) or [])
    if review_required and not review_reasons:
        _fail("review_required true without review reasons")
    if bool(packet.get("rollback_candidate", False)):
        if not str(packet.get("rollback_analysis_id", "") or packet.get("rollback_analysis_ref", "")).strip():
            _fail("rollback candidate missing rollback analysis id")
        if not rollback:
            _fail("rollback candidate missing rollback analysis payload")
    if not str(packet.get("checkpoint_ref", "")).strip():
        _warn("checkpoint_ref unavailable")
    if bool(packet.get("restore_performed", False)):
        _fail("restore_performed must remain false in rc85")
    if bool(packet.get("restore_allowed", False)):
        _warn("restore_allowed should remain false for rc85 mock proofs")
    action_type = str(packet.get("action_type", "")).strip()
    action_status = str(packet.get("status", "")).strip()
    if action_type and not action_type.startswith("noop.") and action_status in {"approved_for_mock_execution", "executed"}:
        _fail("forbidden action executed")
    for candidate_path in required_paths or []:
        if not Path(candidate_path).exists():
            _fail(f"evidence path missing: {Path(candidate_path).name}")
    merged_text = json.dumps(
        {
            "replay_packet": packet,
            "rollback_analysis": rollback,
            "review_item": review,
        },
        sort_keys=True,
    )
    for seed in fake_seeds or []:
        if seed and seed in merged_text:
            _fail("raw fake secret detected in evidence payload")
            break
    return EvidenceIntegrityResult(
        evidence_integrity_status=status,
        evidence_integrity_findings=findings,
        replay_packet_id=str(packet.get("replay_packet_id", "")).strip() or None,
        review_item_id=str(review.get("review_item_id", "")).strip() or None,
        rollback_analysis_id=str(rollback.get("rollback_analysis_id", "")).strip() or None,
        generated_at=_now_iso(),
    )


def write_evidence_integrity_summary(
    results: Iterable[EvidenceIntegrityResult | Mapping[str, Any]],
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    artifact_root = resolve_rc85_artifact_root(package_root, env=env)
    payloads = [dict(item.to_dict()) if hasattr(item, "to_dict") else dict(item) for item in results]
    clean_count = sum(
        1 for item in payloads if str(item.get("evidence_integrity_status", "")).strip() == "clean"
    )
    warning_count = sum(
        1 for item in payloads if str(item.get("evidence_integrity_status", "")).strip() == "warning"
    )
    failed_count = sum(
        1 for item in payloads if str(item.get("evidence_integrity_status", "")).strip() == "failed"
    )
    last_payload = payloads[-1] if payloads else {}
    summary = {
        "schema_name": "novali_rc85_evidence_integrity_summary_v1",
        "generated_at": _now_iso(),
        "result": "success" if failed_count == 0 else "failure",
        "entry_count": len(payloads),
        "clean_count": clean_count,
        "warning_count": warning_count,
        "failed_count": failed_count,
        "last_replay_packet_id": str(last_payload.get("replay_packet_id", "")).strip() or None,
        "last_review_item_id": str(last_payload.get("review_item_id", "")).strip() or None,
        "last_rollback_analysis_id": str(last_payload.get("rollback_analysis_id", "")).strip() or None,
        "findings": [finding for item in payloads for finding in list(item.get("evidence_integrity_findings", []) or [])][:20],
    }
    markdown = "\n".join(
        [
            "# rc85 Evidence Integrity Summary",
            "",
            f"- Result: {summary['result']}",
            f"- Entry count: {summary['entry_count']}",
            f"- Clean count: {summary['clean_count']}",
            f"- Warning count: {summary['warning_count']}",
            f"- Failed count: {summary['failed_count']}",
            f"- Last review item id: {summary['last_review_item_id'] or '<none>'}",
        ]
    )
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=EVIDENCE_INTEGRITY_SUMMARY_FILENAME,
        markdown_name=EVIDENCE_INTEGRITY_MARKDOWN,
        summary=summary,
        markdown=markdown,
    )
    return summary


def load_external_adapter_review_status(
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    artifact_root = resolve_rc85_artifact_root(package_root, env=env)
    review_items_root = resolve_review_items_root(package_root, env=env)
    rollback_root = resolve_rollback_analysis_root(package_root, env=env)
    review_summary = load_json_file(artifact_root / REVIEW_ITEM_LEDGER_SUMMARY_FILENAME)
    rollback_summary = load_json_file(artifact_root / ROLLBACK_ANALYSIS_SUMMARY_FILENAME)
    review_items = _load_json_objects(review_items_root)
    rollback_analyses = _load_json_objects(rollback_root)
    latest_review = max(
        review_items,
        key=lambda item: str(item.get("updated_at", "") or item.get("created_at", "") or ""),
        default={},
    )
    latest_rollback = max(
        rollback_analyses,
        key=lambda item: str(item.get("created_at", "") or ""),
        default={},
    )
    pending_count = sum(
        1 for item in review_items if str(item.get("review_status", "")).strip() == "pending_review"
    )
    escalated_count = sum(
        1 for item in review_items if str(item.get("review_status", "")).strip() == "escalated"
    )
    evidence_missing_count = sum(
        1 for item in review_items if str(item.get("review_status", "")).strip() == "evidence_missing"
    )
    blocked_count = sum(
        1 for item in review_items if str(item.get("review_status", "")).strip() == "blocked"
    )
    if review_summary:
        pending_count = int(review_summary.get("pending_count", pending_count) or pending_count)
        escalated_count = int(review_summary.get("escalated_count", escalated_count) or escalated_count)
        evidence_missing_count = int(
            review_summary.get("evidence_missing_count", evidence_missing_count)
            or evidence_missing_count
        )
    if blocked_count:
        status = "blocked"
    elif escalated_count:
        status = "escalated"
    elif pending_count or evidence_missing_count:
        status = "pending_review"
    else:
        status = "clear"
    summary = ReviewHoldStatusSummary(
        enabled=True,
        mode="mock_only",
        status=status,
        pending_count=pending_count + evidence_missing_count,
        escalated_count=escalated_count,
        evidence_missing_count=evidence_missing_count,
        last_review_item_id=str(latest_review.get("review_item_id", "")).strip() or None,
        last_replay_packet_id=(
            str(latest_review.get("replay_packet_id", "")).strip()
            or str(review_summary.get("last_replay_packet_id", "")).strip()
            or None
        ),
        last_rollback_analysis_id=(
            str(latest_review.get("rollback_analysis_id", "")).strip()
            or str(latest_rollback.get("rollback_analysis_id", "")).strip()
            or str(rollback_summary.get("last_rollback_analysis_id", "")).strip()
            or None
        ),
        review_items=[
            {
                "review_item_id": str(item.get("review_item_id", "")).strip(),
                "action_type": str(item.get("action_type", "")).strip(),
                "action_status": str(item.get("action_status", "")).strip(),
                "review_status": str(item.get("review_status", "")).strip(),
                "severity": str(item.get("severity", "")).strip(),
                "review_reasons": list(item.get("review_reasons", []) or []),
                "operator_action_required": str(item.get("operator_action_required", "")).strip(),
                "replay_packet_id": str(item.get("replay_packet_id", "")).strip() or None,
                "rollback_analysis_id": str(item.get("rollback_analysis_id", "")).strip() or None,
                "checkpoint_ref": str(item.get("checkpoint_ref", "")).strip() or None,
                "evidence_integrity_status": str(item.get("evidence_integrity_status", "")).strip() or "warning",
            }
            for item in sorted(
                review_items,
                key=lambda candidate: str(
                    candidate.get("updated_at", "") or candidate.get("created_at", "") or ""
                ),
                reverse=True,
            )[:8]
        ],
        advisory_copy=[
            "External adapter review items are evidence only.",
            "Controller authority and review gates remain unchanged.",
            "No real external-world mutation is allowed in rc85.",
        ],
    )
    payload = summary.to_dict()
    payload.update(
        {
            "last_operator_action_required": str(latest_review.get("operator_action_required", "")).strip() or None,
            "last_checkpoint_ref": (
                str(latest_review.get("checkpoint_ref", "")).strip()
                or str(latest_rollback.get("checkpoint_ref", "")).strip()
                or str(rollback_summary.get("last_checkpoint_ref", "")).strip()
                or None
            ),
            "rollback_possible": bool(latest_rollback.get("rollback_possible", False)),
            "rollback_candidate": bool(latest_rollback.get("rollback_candidate", False)),
            "checkpoint_available": bool(latest_rollback.get("checkpoint_available", False)),
            "restore_allowed": bool(latest_rollback.get("restore_allowed", False)),
            "restore_performed": bool(latest_rollback.get("restore_performed", False)),
            "ambiguity_level": (
                str(latest_rollback.get("ambiguity_level", "")).strip()
                or str(rollback_summary.get("last_ambiguity_level", "")).strip()
                or "none"
            ),
            "artifact_path": str(artifact_root / REVIEW_ITEM_LEDGER_SUMMARY_FILENAME),
            "review_items_root": str(review_items_root),
            "rollback_analysis_root": str(rollback_root),
        }
    )
    if review_summary and not payload["last_review_item_id"]:
        payload["last_review_item_id"] = (
            str(review_summary.get("last_review_item_id", "")).strip() or None
        )
    return payload


def _queue_item_from_review_item(review_item: Mapping[str, Any]) -> dict[str, Any]:
    review_item_id = str(review_item.get("review_item_id", "")).strip()
    action_type = str(review_item.get("action_type", "")).strip() or "external_adapter"
    action_status = str(review_item.get("action_status", "")).strip() or "review_required"
    review_status = str(review_item.get("review_status", "")).strip() or "pending_review"
    reasons = list(review_item.get("review_reasons", []) or [])
    reason_summary = ", ".join(reasons) if reasons else "External adapter review evidence is pending."
    return {
        "review_item_id": review_item_id,
        "title": f"External adapter review: {action_type}",
        "reason": reason_summary,
        "reason_summary": reason_summary,
        "reason_class": "external_adapter_review",
        "action_needed": str(review_item.get("operator_action_required", "")).strip(),
        "recommended_action": str(review_item.get("operator_action_required", "")).strip(),
        "recommended_action_id": "review_evidence_first_then_return",
        "severity": str(review_item.get("severity", "")).strip() or "warning",
        "blocks_continuation": review_status in {"pending_review", "evidence_missing", "escalated", "blocked"},
        "route": "/observability",
        "surface_hint": "/observability",
        "source": "external_adapter",
        "action_type": action_type,
        "action_status": action_status,
        "replay_packet_id": str(review_item.get("replay_packet_id", "")).strip() or None,
        "rollback_analysis_id": str(review_item.get("rollback_analysis_id", "")).strip() or None,
        "checkpoint_ref": str(review_item.get("checkpoint_ref", "")).strip() or None,
    }


def merge_external_adapter_review_into_snapshot(
    operator_state_payload: Mapping[str, Any],
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    merged = dict(operator_state_payload)
    review_status = load_external_adapter_review_status(package_root=package_root, env=env)
    merged["external_adapter_review"] = review_status
    review_items = list(review_status.get("review_items", []) or [])
    if not review_items:
        return merged

    intervention = dict(merged.get("intervention", {}))
    queue_items = [dict(item) for item in list(intervention.get("queue_items", []) or [])]
    existing_ids = {
        str(item.get("review_item_id", "")).strip() for item in queue_items if str(item.get("review_item_id", "")).strip()
    }
    added_items = []
    for review_item in review_items:
        queue_item = _queue_item_from_review_item(review_item)
        review_item_id = str(queue_item.get("review_item_id", "")).strip()
        if not review_item_id or review_item_id in existing_ids:
            continue
        existing_ids.add(review_item_id)
        added_items.append(queue_item)
    if added_items:
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
                "External adapter review evidence is pending through the existing Review Hold surface."
            )
        if not str(intervention.get("reason", "")).strip():
            intervention["reason"] = str(added_items[0].get("reason_summary", "")).strip()
        if not str(intervention.get("recommended_action", "")).strip():
            intervention["recommended_action"] = "Review evidence first"
        if not str(intervention.get("recommended_action_detail", "")).strip():
            intervention["recommended_action_detail"] = str(
                review_status.get("last_operator_action_required", "")
            ).strip()
        intervention["review_required_state"] = review_status.get("status", "pending_review")
        intervention["review_workspace_label"] = "External adapter review"
        if not str(intervention.get("primary_reason_class", "")).strip():
            intervention["primary_reason_class"] = "external_adapter_review"
        if not str(intervention.get("current_primary_review_item_id", "")).strip():
            intervention["current_primary_review_item_id"] = str(
                added_items[0].get("review_item_id", "")
            ).strip()
        if not str(intervention.get("current_primary_review_title", "")).strip():
            intervention["current_primary_review_title"] = str(added_items[0].get("title", "")).strip()
        if not str(intervention.get("next_state_after_review", "")).strip():
            intervention["next_state_after_review"] = (
                "Mock adapter evidence remains gated until the operator reviews the replay and rollback links."
            )
        merged["intervention"] = intervention

        stage_map = dict(merged.get("operator_state", {}))
        stage_map["review_required"] = True
        stage_map["intervention_required"] = True
        merged["operator_state"] = stage_map
    return merged
