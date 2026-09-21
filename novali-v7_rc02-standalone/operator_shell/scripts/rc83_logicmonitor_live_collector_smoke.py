from __future__ import annotations

import json
import os
import random
import string
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operator_shell.observability import (
    flush_observability,
    get_observability_status,
    initialize_observability,
    load_observability_config,
    mark_live_probe_result,
    record_counter,
    record_event,
    redact_attributes,
    shutdown_observability,
    trace_span,
)
from operator_shell.observability.config import (
    DEFAULT_LOGICMONITOR_PROOF_SERVICE_NAME,
    NOVALI_TELEMETRY_SCHEMA_VERSION,
    collector_mode_for,
    endpoint_hint_for,
    resolve_live_collector_endpoint,
)
from operator_shell.observability.rc83 import (
    resolve_rc83_artifact_root,
    scan_forbidden_strings,
    write_summary_artifacts,
)

PROOF_KIND = "live_collector_intake"
COLLECTOR_MODE = "docker_live"


def _truthy(raw_value: str | bool | None) -> bool:
    return str(raw_value or "").strip().lower() in {"1", "true", "yes", "on"}


def _now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()


def _fake_seed(suffix: str) -> str:
    return f"FAKE_{suffix}_RC83_SHOULD_NOT_EXPORT"


FAKE_SECRET_SEEDS = {
    "authorization": f"Bearer {_fake_seed('SECRET_TOKEN')}",
    "novali.secret": _fake_seed("NOVALI_SECRET"),
    "api_key": _fake_seed("API_KEY"),
    "cookie": _fake_seed("COOKIE"),
}


def _build_proof_id(now: datetime | None = None) -> str:
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    short_random = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(6))
    return instant.strftime(f"rc83-logicmonitor-live-%Y%m%d-%H%M%S-{short_random}")


def _safe_endpoint(endpoint: str) -> str:
    normalized = str(endpoint or "").strip()
    if not normalized:
        return ""
    try:
        parts = urlsplit(normalized)
    except ValueError:
        return ""
    if parts.username or parts.password or parts.query or parts.fragment:
        return ""
    return normalized


def _markdown_summary(summary: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# rc83 Live Collector Smoke Summary",
            "",
            f"- Result: {summary.get('result', '<unknown>')}",
            f"- Proof ID: {summary.get('proof_id', '<none>')}",
            f"- Proof kind: {summary.get('proof_kind', '<none>')}",
            f"- Collector mode: {summary.get('collector_mode', '<none>')}",
            f"- Collector mode status: {summary.get('collector_mode_status', '<none>')}",
            f"- Endpoint hint: {summary.get('endpoint_hint', '<none>')}",
            f"- Service name: {summary.get('service_name', '<none>')}",
            f"- Exporter status after flush: {summary.get('status_after_flush', {}).get('status', '<none>')}",
            f"- Redaction proof passed: {summary.get('redaction_proof_passed', False)}",
            f"- No secrets captured: {summary.get('no_secrets_captured', False)}",
            f"- Summary: {summary.get('summary', '')}",
        ]
    )


def run_live_collector_smoke(
    *,
    env: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    env = env or os.environ
    artifact_root = resolve_rc83_artifact_root(ROOT, env=env)
    selected_endpoint = resolve_live_collector_endpoint(env)
    service_name = (
        str(env.get("OTEL_SERVICE_NAME") or "").strip() or DEFAULT_LOGICMONITOR_PROOF_SERVICE_NAME
    )
    proof_id = _build_proof_id(now)
    generated_at = _now_iso(now)
    proof_attributes = {
        "rc83.proof_id": proof_id,
        "rc83.run_id": proof_id,
        "rc83.collector_mode": COLLECTOR_MODE,
        "rc83.proof_kind": PROOF_KIND,
        "novali.telemetry.schema_version": NOVALI_TELEMETRY_SCHEMA_VERSION,
        **FAKE_SECRET_SEEDS,
    }
    safe_endpoint = _safe_endpoint(selected_endpoint)
    endpoint_hint = endpoint_hint_for(selected_endpoint)
    collector_mode_status = collector_mode_for(selected_endpoint)

    if not _truthy(env.get("RC83_LIVE_COLLECTOR_PROOF")):
        summary = {
            "schema_name": "novali_rc83_logicmonitor_live_collector_smoke_summary_v1",
            "generated_at": generated_at,
            "result": "skipped",
            "summary": "Live collector proof skipped because RC83_LIVE_COLLECTOR_PROOF=true was not set.",
            "opt_in_enabled": False,
            "proof_id": proof_id,
            "proof_kind": PROOF_KIND,
            "collector_mode": COLLECTOR_MODE,
            "collector_mode_status": collector_mode_status,
            "selected_endpoint": safe_endpoint,
            "endpoint_hint": endpoint_hint,
            "service_name": service_name,
            "redaction_proof_passed": True,
            "no_secrets_captured": True,
        }
        markdown = _markdown_summary(summary)
        write_summary_artifacts(
            artifact_root=artifact_root,
            json_name="logicmonitor_live_collector_smoke_summary.json",
            markdown_name="logicmonitor_live_collector_smoke_summary.md",
            summary=summary,
            markdown=markdown,
        )
        mark_live_probe_result(
            enabled=False,
            result="skipped",
            probe_kind=PROOF_KIND,
            probe_id=proof_id,
            probe_time=generated_at,
            endpoint_hint=endpoint_hint,
            collector_mode=collector_mode_status,
        )
        return summary

    local_env = dict(env)
    local_env["NOVALI_OTEL_ENABLED"] = "true"
    local_env["OTEL_EXPORTER_OTLP_ENDPOINT"] = selected_endpoint
    local_env["OTEL_SERVICE_NAME"] = service_name
    local_env.setdefault("NOVALI_OTEL_REDACTION_MODE", "strict")
    local_env.setdefault("NOVALI_OBSERVABILITY_STATUS_DETAIL", "compact")

    redacted_attributes = redact_attributes(proof_attributes)
    local_redaction_payload = json.dumps(redacted_attributes, sort_keys=True)
    redaction_hits = scan_forbidden_strings([local_redaction_payload], list(FAKE_SECRET_SEEDS.values()))
    redaction_proof_passed = not redaction_hits
    initial_status: dict[str, Any] = {}
    flush_result: dict[str, Any] = {}
    status_after_flush: dict[str, Any] = {}
    final_result = "failure"
    summary = {}

    try:
        config = load_observability_config(env=local_env)
        initial_status = initialize_observability(config)
        mark_live_probe_result(
            enabled=True,
            result="unknown",
            probe_kind=PROOF_KIND,
            probe_id=proof_id,
            probe_time=generated_at,
            endpoint_hint=endpoint_hint,
            collector_mode=collector_mode_status,
        )
        with trace_span(
            "novali.observability.live_collector.probe",
            {
                "novali.result": "success",
                "novali.probe_kind": PROOF_KIND,
                "novali.collector_mode": collector_mode_status,
            },
        ) as span:
            span.add_event("novali.rc83.live_collector.proof", redacted_attributes)
            record_event("novali.rc83.live_collector.proof", redacted_attributes)
        flush_result = flush_observability(config.export_timeout_ms)
        status_after_flush = get_observability_status()
        final_result = (
            "success"
            if redaction_proof_passed
            and flush_result.get("ok", False)
            and str(status_after_flush.get("status", "")).strip() == "exporting"
            else "failure"
        )
        record_counter(
            "novali.observability.live_probe.count",
            1,
            {
                "novali.result": final_result,
                "novali.probe_kind": PROOF_KIND,
                "novali.collector_mode": collector_mode_status,
            },
        )
        flush_result = flush_observability(config.export_timeout_ms)
        status_after_flush = get_observability_status()
        mark_live_probe_result(
            enabled=True,
            result=final_result,
            probe_kind=PROOF_KIND,
            probe_id=proof_id,
            probe_time=generated_at,
            endpoint_hint=endpoint_hint,
            collector_mode=collector_mode_status,
            no_secrets_captured=redaction_proof_passed,
        )
        status_after_flush = get_observability_status()
        summary = {
            "schema_name": "novali_rc83_logicmonitor_live_collector_smoke_summary_v1",
            "generated_at": generated_at,
            "result": final_result,
            "summary": (
                "Live collector proof flushed through the configured OTLP collector path."
                if final_result == "success"
                else "Live collector proof did not reach a clean exporting state; portal ingestion is not claimed."
            ),
            "opt_in_enabled": True,
            "proof_id": proof_id,
            "run_id": proof_id,
            "proof_kind": PROOF_KIND,
            "collector_mode": COLLECTOR_MODE,
            "collector_mode_status": collector_mode_status,
            "selected_endpoint": safe_endpoint,
            "endpoint_hint": endpoint_hint,
            "service_name": service_name,
            "initial_status": initial_status,
            "status_after_flush": status_after_flush,
            "flush_result": flush_result,
            "redaction_proof_passed": redaction_proof_passed,
            "redaction_hits": redaction_hits,
            "no_secrets_captured": redaction_proof_passed,
            "exporter_crashed": bool(flush_result.get("error_type")),
        }
    finally:
        shutdown_observability()

    markdown = _markdown_summary(summary)
    secret_hits = scan_forbidden_strings(
        [json.dumps(summary, sort_keys=True), markdown, local_redaction_payload],
        list(FAKE_SECRET_SEEDS.values()),
    )
    if secret_hits:
        summary["result"] = "failure"
        summary["summary"] = "Live collector proof failed because forbidden fake-secret seed text appeared in local proof material."
        summary["no_secrets_captured"] = False
        summary["secret_hits"] = secret_hits
        markdown = _markdown_summary(summary)
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name="logicmonitor_live_collector_smoke_summary.json",
        markdown_name="logicmonitor_live_collector_smoke_summary.md",
        summary=summary,
        markdown=markdown,
    )
    return summary


def main() -> int:
    try:
        summary = run_live_collector_smoke()
    except Exception as exc:  # pragma: no cover
        artifact_root = resolve_rc83_artifact_root(ROOT)
        failure_summary = {
            "schema_name": "novali_rc83_logicmonitor_live_collector_smoke_summary_v1",
            "generated_at": _now_iso(),
            "result": "failure",
            "summary": "Live collector smoke script failed before completion.",
            "error_type": type(exc).__name__,
        }
        write_summary_artifacts(
            artifact_root=artifact_root,
            json_name="logicmonitor_live_collector_smoke_summary.json",
            markdown_name="logicmonitor_live_collector_smoke_summary.md",
            summary=failure_summary,
            markdown=_markdown_summary(failure_summary),
        )
        raise
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if str(summary.get("result", "")).strip() in {"success", "skipped"} else 1


if __name__ == "__main__":
    sys.exit(main())
