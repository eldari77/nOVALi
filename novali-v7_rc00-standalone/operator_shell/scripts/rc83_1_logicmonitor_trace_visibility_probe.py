from __future__ import annotations

import importlib.util
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
    mark_trace_visibility_probe_result,
    record_counter,
    record_event,
    redact_attributes,
    shutdown_observability,
    trace_span,
)
from operator_shell.observability.config import (
    DEFAULT_LOGICMONITOR_PROOF_SERVICE_NAME,
    NOVALI_TELEMETRY_SCHEMA_VERSION,
    build_logicmonitor_mapping_attributes,
    endpoint_hint_for,
    logicmonitor_mapping_missing,
    logicmonitor_safe_service_name,
    normalize_otlp_protocol,
    resolve_trace_visibility_endpoint,
    service_name_is_logicmonitor_safe,
)
from operator_shell.observability.rc83 import scan_forbidden_strings, write_summary_artifacts
from operator_shell.observability.rc83_1 import resolve_rc83_1_artifact_root

PROOF_KIND = "trace_visibility_alignment"


def _truthy(raw_value: str | bool | None) -> bool:
    return str(raw_value or "").strip().lower() in {"1", "true", "yes", "on"}


def _now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()


def _fake_seed(suffix: str) -> str:
    return f"FAKE_{suffix}_RC83_1_SHOULD_NOT_EXPORT"


FAKE_SECRET_SEEDS = {
    "authorization": f"Bearer {_fake_seed('SECRET_TOKEN')}",
    "novali.secret": _fake_seed("NOVALI_SECRET"),
    "api_key": _fake_seed("API_KEY"),
    "cookie": _fake_seed("COOKIE"),
}


def _build_proof_id(now: datetime | None = None) -> str:
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    short_random = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(6))
    return instant.strftime(f"rc83-1-trace-visibility-%Y%m%d-%H%M%S-{short_random}")


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


def _grpc_exporters_available() -> bool:
    required = (
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter",
        "opentelemetry.exporter.otlp.proto.grpc.metric_exporter",
    )
    return all(importlib.util.find_spec(name) is not None for name in required)


def _diagnostics_payload(
    *,
    initial_status: Mapping[str, Any],
    flush_result: Mapping[str, Any],
    status_after_flush: Mapping[str, Any],
    service_name_lm_safe: bool,
    lm_mapping_attributes_complete: bool,
    protocol: str,
    dependency_available: bool,
) -> dict[str, str]:
    runtime_enablement = (
        "success"
        if bool(initial_status.get("enabled")) and str(initial_status.get("status", "")).strip() not in {"disabled", "unavailable"}
        else "failure"
    )
    app_to_collector_export = (
        "success"
        if bool(flush_result.get("ok")) and str(status_after_flush.get("status", "")).strip() == "exporting"
        else "failure"
    )
    protocol_alignment = "success"
    if protocol == "grpc" and not dependency_available:
        protocol_alignment = "dependency_missing"
    elif app_to_collector_export == "failure":
        protocol_alignment = "suspected_mismatch"
    resource_identity = "success" if service_name_lm_safe and lm_mapping_attributes_complete else "warning"
    return {
        "runtime_enablement": runtime_enablement,
        "app_to_collector_export": app_to_collector_export,
        "protocol_alignment": protocol_alignment,
        "resource_identity_mapping": resource_identity,
        "collector_to_logicmonitor_forwarding": "not_verified",
        "portal_visibility": "operator_confirmation_required",
    }


def _markdown_summary(summary: Mapping[str, Any]) -> str:
    diagnostics = dict(summary.get("diagnostics", {}))
    lines = [
        "# rc83.1 Trace Visibility Probe Summary",
        "",
        f"- Result: {summary.get('result', '<unknown>')}",
        f"- Proof ID: {summary.get('proof_id', '<none>')}",
        f"- Protocol: {summary.get('otlp_protocol', '<unknown>')}",
        f"- Service name: {summary.get('service_name', '<none>')}",
        f"- Service name LogicMonitor-safe: {summary.get('service_name_lm_safe', False)}",
        f"- Mapping complete: {summary.get('lm_mapping_attributes_complete', False)}",
        f"- Mapping missing: {', '.join(summary.get('lm_mapping_missing', [])) or '<none>'}",
        f"- Endpoint hint: {summary.get('endpoint_hint', '<none>')}",
        f"- Exporter status after flush: {summary.get('status_after_flush', {}).get('status', '<none>')}",
        f"- Portal confirmation: {summary.get('portal_visibility', 'not_recorded')}",
        f"- Runtime enablement: {diagnostics.get('runtime_enablement', '<unknown>')}",
        f"- App-to-collector export: {diagnostics.get('app_to_collector_export', '<unknown>')}",
        f"- Protocol alignment: {diagnostics.get('protocol_alignment', '<unknown>')}",
        f"- Resource identity mapping: {diagnostics.get('resource_identity_mapping', '<unknown>')}",
        f"- No secrets captured: {summary.get('no_secrets_captured', False)}",
        f"- Summary: {summary.get('summary', '')}",
    ]
    return "\n".join(lines)


def run_trace_visibility_probe(
    *,
    env: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    env = env or os.environ
    artifact_root = resolve_rc83_1_artifact_root(ROOT, env=env)
    protocol = normalize_otlp_protocol(
        env.get("RC83_1_OTLP_PROTOCOL") or env.get("OTEL_EXPORTER_OTLP_PROTOCOL")
    )
    selected_endpoint = resolve_trace_visibility_endpoint(env, protocol=protocol)
    service_name = (
        str(env.get("OTEL_SERVICE_NAME") or "").strip() or DEFAULT_LOGICMONITOR_PROOF_SERVICE_NAME
    )
    proof_id = _build_proof_id(now)
    generated_at = _now_iso(now)
    endpoint_hint = endpoint_hint_for(selected_endpoint)
    service_name_lm_safe = service_name_is_logicmonitor_safe(service_name)
    mapping_attributes = build_logicmonitor_mapping_attributes(
        service_name=service_name,
        env=env,
        allow_local_host_defaults=True,
    )
    lm_mapping_missing = list(logicmonitor_mapping_missing(mapping_attributes))
    lm_mapping_complete = not lm_mapping_missing
    safe_endpoint = _safe_endpoint(selected_endpoint)
    grpc_available = _grpc_exporters_available()
    proof_attributes = {
        "rc83_1.proof_id": proof_id,
        "rc83_1.run_id": proof_id,
        "rc83_1.proof_kind": PROOF_KIND,
        "rc83_1.otlp_protocol": protocol,
        "novali.telemetry.schema_version": NOVALI_TELEMETRY_SCHEMA_VERSION,
        **mapping_attributes,
        **FAKE_SECRET_SEEDS,
    }

    if not _truthy(env.get("RC83_1_TRACE_VISIBILITY_PROBE")):
        summary = {
            "schema_name": "novali_rc83_1_trace_visibility_probe_summary_v1",
            "generated_at": generated_at,
            "result": "skipped",
            "summary": "Trace visibility probe skipped because RC83_1_TRACE_VISIBILITY_PROBE=true was not set.",
            "opt_in_enabled": False,
            "proof_id": proof_id,
            "proof_kind": PROOF_KIND,
            "otlp_protocol": protocol,
            "selected_endpoint": safe_endpoint,
            "endpoint_hint": endpoint_hint,
            "service_name": service_name,
            "service_name_lm_safe": service_name_lm_safe,
            "service_name_lm_safe_suggestion": logicmonitor_safe_service_name(service_name),
            "lm_mapping_attributes_complete": lm_mapping_complete,
            "lm_mapping_missing": lm_mapping_missing,
            "portal_visibility": "not_recorded",
            "redaction_proof_passed": True,
            "no_secrets_captured": True,
        }
        write_summary_artifacts(
            artifact_root=artifact_root,
            json_name="trace_visibility_probe_summary.json",
            markdown_name="trace_visibility_probe_summary.md",
            summary=summary,
            markdown=_markdown_summary(summary),
        )
        mark_trace_visibility_probe_result(
            enabled=False,
            result="not_recorded",
            probe_id=proof_id,
            probe_time=generated_at,
            endpoint_hint=endpoint_hint,
            otlp_protocol=protocol,
            service_name=service_name,
            service_name_lm_safe=service_name_lm_safe,
            lm_mapping_attributes_complete=lm_mapping_complete,
            lm_mapping_missing=lm_mapping_missing,
        )
        return summary

    if protocol == "grpc" and not grpc_available:
        summary = {
            "schema_name": "novali_rc83_1_trace_visibility_probe_summary_v1",
            "generated_at": generated_at,
            "result": "skipped",
            "summary": "Trace visibility probe skipped because the OTLP gRPC exporter dependency is unavailable.",
            "opt_in_enabled": True,
            "proof_id": proof_id,
            "proof_kind": PROOF_KIND,
            "otlp_protocol": protocol,
            "selected_endpoint": safe_endpoint,
            "endpoint_hint": endpoint_hint,
            "service_name": service_name,
            "service_name_lm_safe": service_name_lm_safe,
            "service_name_lm_safe_suggestion": logicmonitor_safe_service_name(service_name),
            "lm_mapping_attributes_complete": lm_mapping_complete,
            "lm_mapping_missing": lm_mapping_missing,
            "portal_visibility": "not_recorded",
            "redaction_proof_passed": True,
            "no_secrets_captured": True,
            "dependency_available": False,
        }
        write_summary_artifacts(
            artifact_root=artifact_root,
            json_name="trace_visibility_probe_summary.json",
            markdown_name="trace_visibility_probe_summary.md",
            summary=summary,
            markdown=_markdown_summary(summary),
        )
        mark_trace_visibility_probe_result(
            enabled=True,
            result="skipped",
            probe_id=proof_id,
            probe_time=generated_at,
            endpoint_hint=endpoint_hint,
            otlp_protocol=protocol,
            service_name=service_name,
            service_name_lm_safe=service_name_lm_safe,
            lm_mapping_attributes_complete=lm_mapping_complete,
            lm_mapping_missing=lm_mapping_missing,
        )
        return summary

    local_env = dict(env)
    local_env["NOVALI_OTEL_ENABLED"] = "true"
    local_env["OTEL_EXPORTER_OTLP_ENDPOINT"] = selected_endpoint
    local_env["OTEL_EXPORTER_OTLP_PROTOCOL"] = protocol
    local_env["OTEL_SERVICE_NAME"] = service_name
    local_env.setdefault("NOVALI_OTEL_REDACTION_MODE", "strict")
    local_env.setdefault("NOVALI_OBSERVABILITY_STATUS_DETAIL", "compact")
    if not str(local_env.get("NOVALI_LM_RESOURCE_TYPE") or "").strip():
        local_env["NOVALI_LM_RESOURCE_TYPE"] = "host"

    redacted_attributes = redact_attributes(proof_attributes)
    local_redaction_payload = json.dumps(redacted_attributes, sort_keys=True)
    redaction_hits = scan_forbidden_strings([local_redaction_payload], list(FAKE_SECRET_SEEDS.values()))
    redaction_proof_passed = not redaction_hits
    initial_status: dict[str, Any] = {}
    flush_result: dict[str, Any] = {}
    status_after_flush: dict[str, Any] = {}
    diagnostics: dict[str, str] = {}
    final_result = "failure"
    summary: dict[str, Any] = {}

    try:
        config = load_observability_config(env=local_env)
        initial_status = initialize_observability(config)
        if str(initial_status.get("status", "")).strip() == "unavailable" and str(
            initial_status.get("last_error_type", "")
        ).strip() == "grpc_exporter_missing":
            final_result = "skipped"
            status_after_flush = dict(initial_status)
            diagnostics = _diagnostics_payload(
                initial_status=initial_status,
                flush_result={},
                status_after_flush=status_after_flush,
                service_name_lm_safe=bool(config.service_name_lm_safe),
                lm_mapping_attributes_complete=bool(config.lm_mapping_attributes_complete),
                protocol=protocol,
                dependency_available=False,
            )
        else:
            mark_trace_visibility_probe_result(
                enabled=True,
                result="unknown",
                probe_id=proof_id,
                probe_time=generated_at,
                endpoint_hint=endpoint_hint,
                otlp_protocol=protocol,
                service_name=config.service_name,
                service_name_lm_safe=config.service_name_lm_safe,
                lm_mapping_attributes_complete=config.lm_mapping_attributes_complete,
                lm_mapping_missing=config.lm_mapping_missing,
                no_secrets_captured=redaction_proof_passed,
            )
            with trace_span(
                "novali.observability.trace_visibility.probe",
                {
                    "novali.result": "success",
                    "novali.probe_kind": PROOF_KIND,
                    "novali.otlp_protocol": protocol,
                },
            ) as span:
                span.add_event("novali.rc83_1.trace_visibility.proof", redacted_attributes)
                record_event("novali.rc83_1.trace_visibility.proof", redacted_attributes)
            flush_result = flush_observability(config.export_timeout_ms)
            status_after_flush = get_observability_status()
            diagnostics = _diagnostics_payload(
                initial_status=initial_status,
                flush_result=flush_result,
                status_after_flush=status_after_flush,
                service_name_lm_safe=bool(config.service_name_lm_safe),
                lm_mapping_attributes_complete=bool(config.lm_mapping_attributes_complete),
                protocol=protocol,
                dependency_available=grpc_available,
            )
            final_result = (
                "success"
                if redaction_proof_passed
                and diagnostics.get("app_to_collector_export") == "success"
                else "failure"
            )
            record_counter(
                "novali.observability.live_probe.count",
                1,
                {
                    "novali.result": final_result,
                    "novali.probe_kind": PROOF_KIND,
                },
            )
            flush_result = flush_observability(config.export_timeout_ms)
            status_after_flush = get_observability_status()
            mark_trace_visibility_probe_result(
                enabled=True,
                result=final_result,
                probe_id=proof_id,
                probe_time=generated_at,
                endpoint_hint=endpoint_hint,
                otlp_protocol=protocol,
                service_name=config.service_name,
                service_name_lm_safe=config.service_name_lm_safe,
                lm_mapping_attributes_complete=config.lm_mapping_attributes_complete,
                lm_mapping_missing=config.lm_mapping_missing,
                no_secrets_captured=redaction_proof_passed,
            )
            status_after_flush = get_observability_status()

        summary = {
            "schema_name": "novali_rc83_1_trace_visibility_probe_summary_v1",
            "generated_at": generated_at,
            "result": final_result,
            "summary": (
                "Trace visibility probe flushed through the configured app-to-collector OTLP path."
                if final_result == "success"
                else (
                    "Trace visibility probe was skipped because the selected gRPC exporter dependency is unavailable."
                    if final_result == "skipped"
                    else "Trace visibility probe did not reach a clean exporting state; portal ingestion is not claimed."
                )
            ),
            "opt_in_enabled": True,
            "proof_id": proof_id,
            "run_id": proof_id,
            "proof_kind": PROOF_KIND,
            "otlp_protocol": protocol,
            "selected_endpoint": safe_endpoint,
            "endpoint_hint": endpoint_hint,
            "service_name": service_name,
            "service_name_lm_safe": service_name_lm_safe,
            "service_name_lm_safe_suggestion": logicmonitor_safe_service_name(service_name),
            "lm_mapping_attributes_complete": lm_mapping_complete,
            "lm_mapping_missing": lm_mapping_missing,
            "initial_status": initial_status,
            "status_after_flush": status_after_flush,
            "flush_result": flush_result,
            "redaction_proof_passed": redaction_proof_passed,
            "redaction_hits": redaction_hits,
            "dependency_available": grpc_available if protocol == "grpc" else True,
            "diagnostics": diagnostics,
            "portal_visibility": "not_confirmed",
            "no_secrets_captured": redaction_proof_passed,
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
        summary["summary"] = (
            "Trace visibility probe failed because forbidden fake-secret seed text appeared in local proof material."
        )
        summary["no_secrets_captured"] = False
        summary["secret_hits"] = secret_hits
        markdown = _markdown_summary(summary)
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name="trace_visibility_probe_summary.json",
        markdown_name="trace_visibility_probe_summary.md",
        summary=summary,
        markdown=markdown,
    )
    return summary


def main() -> int:
    try:
        summary = run_trace_visibility_probe()
    except Exception as exc:  # pragma: no cover
        artifact_root = resolve_rc83_1_artifact_root(ROOT)
        failure_summary = {
            "schema_name": "novali_rc83_1_trace_visibility_probe_summary_v1",
            "generated_at": _now_iso(),
            "result": "failure",
            "summary": "Trace visibility probe failed before completion.",
            "error_type": type(exc).__name__,
        }
        write_summary_artifacts(
            artifact_root=artifact_root,
            json_name="trace_visibility_probe_summary.json",
            markdown_name="trace_visibility_probe_summary.md",
            summary=failure_summary,
            markdown=_markdown_summary(failure_summary),
        )
        raise
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if str(summary.get("result", "")).strip() in {"success", "skipped"} else 1


if __name__ == "__main__":
    sys.exit(main())
