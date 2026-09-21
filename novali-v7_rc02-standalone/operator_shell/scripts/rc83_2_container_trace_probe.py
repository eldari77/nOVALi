from __future__ import annotations

import json
import os
import random
import socket
import string
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operator_shell.observability import (
    flush_observability,
    get_observability_status,
    initialize_observability,
    load_observability_config,
    mark_dockerized_agent_probe_result,
    record_counter,
    record_event,
    redact_attributes,
    shutdown_observability,
    trace_span,
)
from operator_shell.observability.config import (
    DEFAULT_LOGICMONITOR_PROOF_SERVICE_NAME,
    NOVALI_TELEMETRY_SCHEMA_VERSION,
    endpoint_hint_for,
    logicmonitor_safe_service_name,
    service_name_is_logicmonitor_safe,
)
from operator_shell.observability.rc83 import scan_forbidden_strings, write_summary_artifacts
from operator_shell.observability.rc83_2 import (
    resolve_dockerized_probe_endpoint,
    resolve_rc83_2_artifact_root,
    build_dockerized_mapping_attributes,
    dockerized_mapping_status,
    normalize_dockerized_endpoint_mode,
)

PROOF_KIND = "dockerized_agent_trace_proof"


def _now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()


def _build_proof_id(now: datetime | None = None) -> str:
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    short_random = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(6))
    return instant.strftime(f"rc83-2-dockerized-trace-%Y%m%d-%H%M%S-{short_random}")


def _fake_seed(suffix: str) -> str:
    return f"FAKE_{suffix}_RC83_2_SHOULD_NOT_EXPORT"


FAKE_SECRET_SEEDS = {
    "authorization": f"Bearer {_fake_seed('SECRET_TOKEN')}",
    "novali.secret": _fake_seed("NOVALI_SECRET"),
    "api_key": _fake_seed("API_KEY"),
    "cookie": _fake_seed("COOKIE"),
    "OTEL_EXPORTER_OTLP_HEADERS": f"authorization=Bearer {_fake_seed('OTEL_HEADER')}",
}


def _sanitize_protocol(raw_value: str | None) -> str:
    normalized = str(raw_value or "").strip().lower()
    return normalized if normalized in {"grpc", "http"} else "grpc"


def _markdown_summary(summary: Mapping[str, Any]) -> str:
    diagnostics = dict(summary.get("diagnostics", {}))
    return "\n".join(
        [
            "# rc83.2 Dockerized Agent Trace Probe Summary",
            "",
            f"- Result: {summary.get('result', '<unknown>')}",
            f"- Proof ID: {summary.get('proof_id', '<none>')}",
            f"- Image: {summary.get('novali_image', '<none>')}",
            f"- Container name: {summary.get('novali_container_name', '<none>')}",
            f"- Collector container: {summary.get('collector_container_name', '<none>')}",
            f"- Endpoint mode: {summary.get('endpoint_mode', '<none>')}",
            f"- Endpoint hint: {summary.get('endpoint_hint', '<none>')}",
            f"- Protocol: {summary.get('otlp_protocol', '<none>')}",
            f"- Service name: {summary.get('service_name', '<none>')}",
            f"- Mapping complete: {summary.get('lm_mapping_attributes_complete', False)}",
            f"- Mapping missing: {', '.join(summary.get('lm_mapping_missing', [])) or '<none>'}",
            f"- Docker network: {summary.get('docker_network_used', '<none>')}",
            f"- Container runtime proven: {summary.get('container_runtime_proven', False)}",
            f"- App-to-collector result: {summary.get('app_to_collector_result', '<unknown>')}",
            f"- Exporter crashed: {summary.get('exporter_crashed', False)}",
            f"- Redaction proof passed: {summary.get('redaction_proof_passed', False)}",
            f"- Portal visibility: {summary.get('portal_visibility', 'not_recorded')}",
            f"- Runtime enablement: {diagnostics.get('runtime_enablement', '<unknown>')}",
            f"- Network topology: {diagnostics.get('network_topology', '<unknown>')}",
            f"- No secrets captured: {summary.get('no_secrets_captured', False)}",
            f"- Summary: {summary.get('summary', '')}",
        ]
    )


def _diagnostics_payload(
    *,
    initial_status: Mapping[str, Any],
    flush_result: Mapping[str, Any],
    status_after_flush: Mapping[str, Any],
    endpoint_mode: str,
    service_name_lm_safe: bool,
    lm_mapping_attributes_complete: bool,
) -> dict[str, str]:
    runtime_enablement = (
        "success"
        if bool(initial_status.get("enabled")) and str(initial_status.get("status", "")).strip()
        not in {"disabled", "unavailable"}
        else "failure"
    )
    app_to_collector_export = (
        "success"
        if bool(flush_result.get("ok")) and str(status_after_flush.get("status", "")).strip() == "exporting"
        else "failure"
    )
    return {
        "runtime_enablement": runtime_enablement,
        "network_topology": endpoint_mode,
        "app_to_collector_export": app_to_collector_export,
        "resource_identity_mapping": (
            "success" if service_name_lm_safe and lm_mapping_attributes_complete else "warning"
        ),
        "collector_to_logicmonitor_forwarding": "not_verified",
        "portal_visibility": "operator_confirmation_required",
    }


def run_container_trace_probe(
    *,
    env: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    env = dict(env or os.environ)
    artifact_root = resolve_rc83_2_artifact_root(ROOT, env=env)
    generated_at = _now_iso(now)
    proof_id = _build_proof_id(now)
    protocol = _sanitize_protocol(
        env.get("OTEL_EXPORTER_OTLP_PROTOCOL") or env.get("RC83_2_OTLP_PROTOCOL")
    )
    endpoint_mode = normalize_dockerized_endpoint_mode(env.get("RC83_2_ENDPOINT_MODE"))
    service_name = (
        str(env.get("OTEL_SERVICE_NAME") or "").strip() or DEFAULT_LOGICMONITOR_PROOF_SERVICE_NAME
    )
    local_env = dict(env)
    if (
        str(local_env.get("NOVALI_LM_HOST_NAME") or "").strip()
        and str(local_env.get("NOVALI_LM_IP") or "").strip()
        and not str(local_env.get("NOVALI_LM_RESOURCE_TYPE") or "").strip()
    ):
        local_env["NOVALI_LM_RESOURCE_TYPE"] = "host"
    selected_endpoint = resolve_dockerized_probe_endpoint(
        env=local_env,
        protocol=protocol,
        endpoint_mode=endpoint_mode,
    )
    endpoint_hint = endpoint_hint_for(selected_endpoint)
    mapping = dockerized_mapping_status(service_name=service_name, env=local_env)
    mapping_attributes = build_dockerized_mapping_attributes(
        service_name=service_name,
        env=local_env,
    )
    service_name_lm_safe = service_name_is_logicmonitor_safe(service_name)
    proof_attributes = {
        "rc83_2.proof_id": proof_id,
        "rc83_2.run_id": proof_id,
        "rc83_2.proof_kind": PROOF_KIND,
        "rc83_2.collector_mode": endpoint_mode,
        "novali.telemetry.schema_version": NOVALI_TELEMETRY_SCHEMA_VERSION,
        **mapping_attributes,
        **FAKE_SECRET_SEEDS,
    }
    redacted_attributes = redact_attributes(proof_attributes)
    redaction_hits = scan_forbidden_strings(
        [json.dumps(redacted_attributes, sort_keys=True)],
        list(FAKE_SECRET_SEEDS.values()),
    )
    redaction_proof_passed = not redaction_hits

    summary: dict[str, Any] = {
        "schema_name": "novali_rc83_2_dockerized_agent_trace_probe_summary_v1",
        "generated_at": generated_at,
        "opt_in_enabled": True,
        "proof_id": proof_id,
        "proof_kind": PROOF_KIND,
        "novali_image": str(local_env.get("RC83_2_NOVALI_IMAGE") or "").strip() or None,
        "novali_container_name": str(local_env.get("RC83_2_NOVALI_CONTAINER_NAME") or "").strip()
        or None,
        "collector_container_name": str(local_env.get("RC83_2_LMOTEL_CONTAINER_NAME") or "").strip()
        or None,
        "endpoint_mode": endpoint_mode,
        "endpoint_hint": endpoint_hint,
        "otlp_protocol": protocol,
        "service_name": service_name,
        "service_name_lm_safe": service_name_lm_safe,
        "service_name_lm_safe_suggestion": logicmonitor_safe_service_name(service_name),
        "lm_mapping_attributes_complete": bool(mapping["complete"]),
        "lm_mapping_missing": list(mapping["missing"]),
        "docker_network_used": str(local_env.get("RC83_2_DOCKER_NETWORK") or "").strip() or None,
        "docker_network_mode": endpoint_mode,
        "container_runtime_proven": True,
        "container_hostname": socket.gethostname(),
        "exporter_crashed": False,
        "redaction_proof_passed": redaction_proof_passed,
        "portal_visibility": "not_confirmed",
        "no_secrets_captured": redaction_proof_passed,
        "result": "failure",
    }

    if not selected_endpoint:
        summary.update(
            {
                "summary": "Containerized probe could not resolve a collector endpoint for the selected Docker endpoint mode.",
                "app_to_collector_result": "failure",
                "diagnostics": {
                    "runtime_enablement": "not_run",
                    "network_topology": endpoint_mode,
                    "app_to_collector_export": "failure",
                    "resource_identity_mapping": (
                        "success"
                        if service_name_lm_safe and bool(mapping["complete"])
                        else "warning"
                    ),
                    "collector_to_logicmonitor_forwarding": "not_verified",
                    "portal_visibility": "operator_confirmation_required",
                },
            }
        )
        write_summary_artifacts(
            artifact_root=artifact_root,
            json_name="dockerized_agent_trace_probe_summary.json",
            markdown_name="dockerized_agent_trace_probe_summary.md",
            summary=summary,
            markdown=_markdown_summary(summary),
        )
        mark_dockerized_agent_probe_result(
            enabled=True,
            result="failure",
            probe_id=proof_id,
            probe_time=generated_at,
            endpoint_hint=endpoint_hint,
            endpoint_mode=endpoint_mode,
            network_mode=endpoint_mode,
            otlp_protocol=protocol,
            service_name=service_name,
            service_name_lm_safe=service_name_lm_safe,
            lm_mapping_attributes_complete=bool(mapping["complete"]),
            lm_mapping_missing=list(mapping["missing"]),
            container_runtime_proven=True,
            container_hostname=summary["container_hostname"],
            no_secrets_captured=bool(summary["no_secrets_captured"]),
        )
        return summary

    local_env["NOVALI_OTEL_ENABLED"] = "true"
    local_env["OTEL_EXPORTER_OTLP_ENDPOINT"] = selected_endpoint
    local_env["OTEL_EXPORTER_OTLP_PROTOCOL"] = protocol
    local_env["OTEL_SERVICE_NAME"] = service_name
    local_env.setdefault("NOVALI_OTEL_REDACTION_MODE", "strict")
    local_env.setdefault("NOVALI_OBSERVABILITY_STATUS_DETAIL", "compact")

    initial_status: dict[str, Any] = {}
    flush_result: dict[str, Any] = {}
    status_after_flush: dict[str, Any] = {}

    try:
        config = load_observability_config(env=local_env)
        initial_status = initialize_observability(config)
        mark_dockerized_agent_probe_result(
            enabled=True,
            result="unknown",
            probe_id=proof_id,
            probe_time=generated_at,
            endpoint_hint=endpoint_hint,
            endpoint_mode=endpoint_mode,
            network_mode=endpoint_mode,
            otlp_protocol=protocol,
            service_name=config.service_name,
            service_name_lm_safe=config.service_name_lm_safe,
            lm_mapping_attributes_complete=config.lm_mapping_attributes_complete,
            lm_mapping_missing=list(config.lm_mapping_missing),
            container_runtime_proven=True,
            container_hostname=socket.gethostname(),
        )

        @contextmanager
        def _probe_span() -> Any:
            with trace_span("novali.observability.dockerized_agent.probe", redacted_attributes) as span:
                yield span

        with _probe_span() as span:
            span.add_event(
                "novali.observability.dockerized_agent.probe",
                redact_attributes(
                    {
                        "rc83_2.proof_id": proof_id,
                        "novali.collector_mode": endpoint_mode,
                        "novali.probe_kind": PROOF_KIND,
                    }
                ),
            )
            record_counter(
                "novali.observability.live_probe.count",
                1,
                {
                    "novali.branch": "novali-v6",
                    "novali.package.version": "rc83_2",
                    "novali.runtime.role": "operator_shell",
                    "novali.probe_kind": PROOF_KIND,
                    "novali.collector_mode": endpoint_mode,
                    "novali.result": "attempted",
                },
            )
            record_event(
                "novali.observability.dockerized_agent.probe.summary",
                {
                    "proof_id": proof_id,
                    "endpoint_mode": endpoint_mode,
                    "otlp_protocol": protocol,
                    "service_name_lm_safe": service_name_lm_safe,
                    "lm_mapping_attributes_complete": bool(mapping["complete"]),
                },
            )

        flush_result = flush_observability()
        status_after_flush = get_observability_status()
        diagnostics = _diagnostics_payload(
            initial_status=initial_status,
            flush_result=flush_result,
            status_after_flush=status_after_flush,
            endpoint_mode=endpoint_mode,
            service_name_lm_safe=bool(config.service_name_lm_safe),
            lm_mapping_attributes_complete=bool(config.lm_mapping_attributes_complete),
        )
        app_to_collector_result = diagnostics.get("app_to_collector_export", "failure")
        result = "success" if app_to_collector_result == "success" and redaction_proof_passed else "failure"
        summary.update(
            {
                "result": result,
                "summary": (
                    "Dockerized NOVALI runtime reached a clean app-to-collector export path."
                    if result == "success"
                    else "Dockerized NOVALI runtime did not reach a clean app-to-collector export path."
                ),
                "app_to_collector_result": app_to_collector_result,
                "diagnostics": diagnostics,
                "flush_result": flush_result,
                "status_after_flush": status_after_flush,
                "no_secrets_captured": redaction_proof_passed,
            }
        )
    except Exception as exc:  # pragma: no cover - exercised in live proof path
        status_after_flush = get_observability_status()
        summary.update(
            {
                "result": "failure",
                "summary": "Dockerized NOVALI runtime probe raised an exporter or runtime exception.",
                "app_to_collector_result": "failure",
                "exporter_crashed": True,
                "diagnostics": {
                    "runtime_enablement": "failure",
                    "network_topology": endpoint_mode,
                    "app_to_collector_export": "failure",
                    "resource_identity_mapping": (
                        "success"
                        if service_name_lm_safe and bool(mapping["complete"])
                        else "warning"
                    ),
                    "collector_to_logicmonitor_forwarding": "not_verified",
                    "portal_visibility": "operator_confirmation_required",
                },
                "status_after_flush": status_after_flush,
                "exception_type": type(exc).__name__,
                "no_secrets_captured": redaction_proof_passed,
            }
        )
    finally:
        shutdown_observability()

    summary_text = json.dumps(summary, sort_keys=True, default=str)
    forbidden_hits = scan_forbidden_strings([summary_text], list(FAKE_SECRET_SEEDS.values()))
    if forbidden_hits:
        summary.update(
            {
                "result": "failure",
                "summary": "Dockerized probe failed because forbidden fake-secret seed text appeared in proof material.",
                "forbidden_hits": forbidden_hits,
                "no_secrets_captured": False,
            }
        )
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name="dockerized_agent_trace_probe_summary.json",
        markdown_name="dockerized_agent_trace_probe_summary.md",
        summary=summary,
        markdown=_markdown_summary(summary),
    )
    mark_dockerized_agent_probe_result(
        enabled=True,
        result=str(summary.get("result", "failure")),
        probe_id=proof_id,
        probe_time=generated_at,
        endpoint_hint=endpoint_hint,
        endpoint_mode=endpoint_mode,
        network_mode=endpoint_mode,
        otlp_protocol=protocol,
        service_name=service_name,
        service_name_lm_safe=service_name_lm_safe,
        lm_mapping_attributes_complete=bool(mapping["complete"]),
        lm_mapping_missing=list(mapping["missing"]),
        container_runtime_proven=True,
        container_hostname=summary.get("container_hostname"),
        no_secrets_captured=bool(summary.get("no_secrets_captured", False)),
    )
    return summary


def main() -> int:
    summary = run_container_trace_probe()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if str(summary.get("result", "")).strip() == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
