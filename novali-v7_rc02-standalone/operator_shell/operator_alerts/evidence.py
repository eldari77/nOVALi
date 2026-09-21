from __future__ import annotations

import json
import os
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from operator_shell.observability.rc83 import load_json_file, write_summary_artifacts
from operator_shell.observability.redaction import REDACTED, redact_value

from .schemas import OperatorAlertEvidenceBundle

RC88_ARTIFACT_SUBPATH = Path("artifacts/operator_proof/rc88")
EVIDENCE_BUNDLES_DIRNAME = "evidence_bundles"
EVIDENCE_BUNDLE_SUMMARY_FILENAME = "evidence_bundle_summary.json"
EVIDENCE_BUNDLE_SUMMARY_MARKDOWN = "evidence_bundle_summary.md"
REFERENCE_HINT_KEYS = {
    "replay_packet_refs",
    "review_ticket_refs",
    "rollback_analysis_refs",
    "mutation_refusal_refs",
    "source_immutability_refs",
    "lane_attribution_refs",
    "telemetry_refs",
    "package_validation_refs",
    "status_endpoint_snapshot_ref",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _redact_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): redact_value(value, key=str(key)) for key, value in payload.items()}


def resolve_rc88_artifact_root(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    env = env or os.environ
    configured = str(
        env.get("RC88_1_PROOF_ARTIFACT_ROOT") or env.get("RC88_PROOF_ARTIFACT_ROOT") or ""
    ).strip()
    base_root = Path(package_root).resolve() if package_root is not None else None
    if configured:
        configured_path = Path(configured)
        if configured_path.is_absolute():
            return configured_path.resolve()
        if base_root is not None:
            return (base_root / configured_path).resolve()
        return configured_path.resolve()
    if base_root is not None:
        return (base_root / RC88_ARTIFACT_SUBPATH).resolve()
    return RC88_ARTIFACT_SUBPATH.resolve()


def resolve_evidence_bundles_root(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    return resolve_rc88_artifact_root(package_root, env=env) / EVIDENCE_BUNDLES_DIRNAME


def _collect_strings(value: Any) -> list[tuple[str | None, str]]:
    collected: list[tuple[str | None, str]] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            collected.extend(_collect_strings_with_key(item, str(key)))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            collected.extend(_collect_strings(item))
    elif isinstance(value, str):
        collected.append((None, value))
    return collected


def _collect_strings_with_key(value: Any, key: str) -> list[tuple[str | None, str]]:
    collected: list[tuple[str | None, str]] = []
    if isinstance(value, Mapping):
        for inner_key, item in value.items():
            collected.extend(_collect_strings_with_key(item, str(inner_key)))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            if isinstance(item, Mapping):
                collected.extend(_collect_strings(item))
            elif isinstance(item, str):
                collected.append((key, item))
    elif isinstance(value, str):
        collected.append((key, value))
    return collected


def _contains_secret_like_content(payload: Mapping[str, Any]) -> bool:
    for key, value in _collect_strings(payload):
        redacted = redact_value(value, key=key)
        if redacted == REDACTED and value != REDACTED:
            normalized_key = str(key or "").strip()
            lowered_value = str(value or "").strip().lower()
            if normalized_key in REFERENCE_HINT_KEYS and not any(
                marker in lowered_value
                for marker in (
                    "bearer ",
                    "authorization=",
                    "api_key",
                    "access_key",
                    "cookie=",
                    "otlp_headers",
                    "otel_exporter_otlp_headers",
                    "token",
                )
            ):
                continue
            return True
    return False


def _normalize_refs(refs: Iterable[str] | None) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for ref in refs or []:
        value = str(ref or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _ref_exists(ref: str, *, package_root: Path) -> bool:
    candidate = str(ref or "").strip()
    if not candidate:
        return False
    if candidate.startswith("/shell/") or candidate.startswith("shell/"):
        return True
    if candidate.startswith("status:") or candidate.startswith("lm:"):
        return True
    path = Path(candidate)
    if path.is_absolute():
        return path.exists()
    rc88_artifact_root = resolve_rc88_artifact_root(package_root)
    for resolved in (
        (package_root / path).resolve(),
        (rc88_artifact_root / path).resolve(),
    ):
        if resolved.exists():
            return True
    return False


def evaluate_bundle_integrity(
    *,
    package_root: str | Path | None,
    replay_packet_refs: Iterable[str] | None = None,
    review_ticket_refs: Iterable[str] | None = None,
    rollback_analysis_refs: Iterable[str] | None = None,
    mutation_refusal_refs: Iterable[str] | None = None,
    source_immutability_refs: Iterable[str] | None = None,
    lane_attribution_refs: Iterable[str] | None = None,
    telemetry_refs: Iterable[str] | None = None,
    status_endpoint_snapshot_ref: str | None = None,
    package_validation_refs: Iterable[str] | None = None,
) -> tuple[str, list[str], str]:
    package_root_path = Path(package_root).resolve() if package_root is not None else Path.cwd().resolve()
    refs_by_kind = {
        "replay_packet_refs": _normalize_refs(replay_packet_refs),
        "review_ticket_refs": _normalize_refs(review_ticket_refs),
        "rollback_analysis_refs": _normalize_refs(rollback_analysis_refs),
        "mutation_refusal_refs": _normalize_refs(mutation_refusal_refs),
        "source_immutability_refs": _normalize_refs(source_immutability_refs),
        "lane_attribution_refs": _normalize_refs(lane_attribution_refs),
        "telemetry_refs": _normalize_refs(telemetry_refs),
        "package_validation_refs": _normalize_refs(package_validation_refs),
    }
    findings: list[str] = []
    for kind, refs in refs_by_kind.items():
        for ref in refs:
            if not _ref_exists(ref, package_root=package_root_path):
                findings.append(f"{kind} missing: {ref}")
    if status_endpoint_snapshot_ref and not _ref_exists(status_endpoint_snapshot_ref, package_root=package_root_path):
        findings.append(f"status endpoint snapshot missing: {status_endpoint_snapshot_ref}")
    payload = {
        **refs_by_kind,
        "status_endpoint_snapshot_ref": status_endpoint_snapshot_ref,
    }
    redaction_status = "failed" if _contains_secret_like_content(payload) else "clean"
    if redaction_status == "failed":
        findings.append("secret-like content detected in evidence references")
    if findings and any("missing" in finding for finding in findings):
        status = "failed"
    elif findings:
        status = "warning"
    else:
        status = "clean"
    return status, findings, redaction_status


def build_evidence_bundle(
    *,
    alert_id: str,
    source: str,
    source_case: str,
    replay_packet_refs: Iterable[str] | None = None,
    review_ticket_refs: Iterable[str] | None = None,
    rollback_analysis_refs: Iterable[str] | None = None,
    mutation_refusal_refs: Iterable[str] | None = None,
    source_immutability_refs: Iterable[str] | None = None,
    lane_attribution_refs: Iterable[str] | None = None,
    telemetry_refs: Iterable[str] | None = None,
    status_endpoint_snapshot_ref: str | None = None,
    package_validation_refs: Iterable[str] | None = None,
    package_root: str | Path | None = None,
) -> OperatorAlertEvidenceBundle:
    integrity_status, findings, redaction_status = evaluate_bundle_integrity(
        package_root=package_root,
        replay_packet_refs=replay_packet_refs,
        review_ticket_refs=review_ticket_refs,
        rollback_analysis_refs=rollback_analysis_refs,
        mutation_refusal_refs=mutation_refusal_refs,
        source_immutability_refs=source_immutability_refs,
        lane_attribution_refs=lane_attribution_refs,
        telemetry_refs=telemetry_refs,
        status_endpoint_snapshot_ref=status_endpoint_snapshot_ref,
        package_validation_refs=package_validation_refs,
    )
    digest_source = "|".join(
        [
            alert_id,
            source,
            source_case,
            ",".join(_normalize_refs(replay_packet_refs)),
            ",".join(_normalize_refs(review_ticket_refs)),
            ",".join(_normalize_refs(rollback_analysis_refs)),
        ]
    )
    evidence_bundle_id = f"alert-evidence-{hashlib.sha1(digest_source.encode('utf-8')).hexdigest()[:12]}"
    return OperatorAlertEvidenceBundle(
        evidence_bundle_id=evidence_bundle_id,
        alert_id=alert_id,
        source=source,
        source_case=source_case,
        replay_packet_refs=_normalize_refs(replay_packet_refs),
        review_ticket_refs=_normalize_refs(review_ticket_refs),
        rollback_analysis_refs=_normalize_refs(rollback_analysis_refs),
        mutation_refusal_refs=_normalize_refs(mutation_refusal_refs),
        source_immutability_refs=_normalize_refs(source_immutability_refs),
        lane_attribution_refs=_normalize_refs(lane_attribution_refs),
        telemetry_refs=_normalize_refs(telemetry_refs),
        status_endpoint_snapshot_ref=str(status_endpoint_snapshot_ref or "").strip() or None,
        package_validation_refs=_normalize_refs(package_validation_refs),
        evidence_integrity_status=integrity_status,
        evidence_integrity_findings=findings,
        redaction_status=redaction_status,
        created_at=_now_iso(),
    )


def write_evidence_bundle(
    bundle: OperatorAlertEvidenceBundle,
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    root = resolve_evidence_bundles_root(package_root, env=env)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{bundle.evidence_bundle_id}.json"
    path.write_text(
        json.dumps(_redact_payload(bundle.to_dict()), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
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


def summarize_evidence_bundles(
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    artifact_root = resolve_rc88_artifact_root(package_root, env=env)
    bundles_root = resolve_evidence_bundles_root(package_root, env=env)
    bundles = _load_json_objects(bundles_root)
    latest = max(bundles, key=lambda item: str(item.get("created_at", "")), default={})
    failed_count = sum(
        1 for item in bundles if str(item.get("evidence_integrity_status", "")).strip() == "failed"
    )
    warning_count = sum(
        1 for item in bundles if str(item.get("evidence_integrity_status", "")).strip() == "warning"
    )
    summary = {
        "schema_name": "novali_rc88_evidence_bundle_summary_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "evidence_bundle_count": len(bundles),
        "failed_count": failed_count,
        "warning_count": warning_count,
        "latest_evidence_bundle_id": str(latest.get("evidence_bundle_id", "")).strip() or None,
        "latest_alert_id": str(latest.get("alert_id", "")).strip() or None,
        "bundles_root": str(bundles_root),
    }
    markdown = "\n".join(
        [
            "# rc88 Evidence Bundle Summary",
            "",
            f"- Evidence bundle count: {summary['evidence_bundle_count']}",
            f"- Failed count: {summary['failed_count']}",
            f"- Warning count: {summary['warning_count']}",
            f"- Latest evidence bundle id: {summary['latest_evidence_bundle_id'] or '<none>'}",
        ]
    )
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=EVIDENCE_BUNDLE_SUMMARY_FILENAME,
        markdown_name=EVIDENCE_BUNDLE_SUMMARY_MARKDOWN,
        summary=summary,
        markdown=markdown,
    )
    return summary
