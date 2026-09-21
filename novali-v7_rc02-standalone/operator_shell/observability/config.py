from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlsplit

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"", "0", "false", "no", "off"}
SUPPORTED_REDACTION_MODES = {"strict", "standard"}
SUPPORTED_STATUS_DETAIL = {"compact", "verbose"}
SUPPORTED_OTLP_PROTOCOLS = {"http", "grpc"}

DEFAULT_HTTP_OTLP_ENDPOINT = "http://localhost:4318"
DEFAULT_GRPC_OTLP_ENDPOINT = "http://localhost:4317"
DEFAULT_OTLP_ENDPOINT = DEFAULT_HTTP_OTLP_ENDPOINT
DEFAULT_SERVICE_NAME = "novali-operator-shell"
DEFAULT_LOGICMONITOR_PROOF_SERVICE_NAME = "novalioperatorshell"
DEFAULT_EXPORT_TIMEOUT_MS = 4000
DEFAULT_SHUTDOWN_TIMEOUT_MS = 3000
DEFAULT_REDACTION_MODE = "strict"
DEFAULT_STATUS_DETAIL = "compact"
DEFAULT_OTLP_PROTOCOL = "http"

NOVALI_BRANCH = "novali-v7"
NOVALI_PACKAGE_VERSION = "v7rc00"
NOVALI_SERVICE_VERSION = "novali-v7_rc00"
NOVALI_TELEMETRY_SCHEMA_VERSION = "v7rc00.v1"

LOGICMONITOR_SAFE_SERVICE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9]+$")


@dataclass(frozen=True)
class ObservabilityConfig:
    enabled: bool
    endpoint: str
    service_name: str
    resource_attributes: dict[str, str]
    redaction_mode: str
    export_timeout_ms: int
    shutdown_timeout_ms: int
    status_detail: str
    env_state: str
    otlp_protocol: str
    service_name_lm_safe: bool
    service_name_lm_warning: str | None
    lm_mapping_attributes_complete: bool
    lm_mapping_missing: tuple[str, ...]
    live_collector_proof_enabled: bool
    live_collector_endpoint: str
    live_collector_container_name: str
    docker_preflight_enabled: bool
    trace_visibility_probe_enabled: bool
    proof_artifact_root: str


def _parse_bool(raw_value: str | None) -> tuple[bool, str]:
    normalized = str(raw_value or "").strip().lower()
    if normalized in TRUE_VALUES:
        return True, "valid"
    if normalized in FALSE_VALUES:
        return False, "valid"
    return False, "invalid"


def _safe_int(raw_value: str | None, default: int) -> int:
    try:
        parsed = int(str(raw_value or "").strip())
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def normalize_otlp_protocol(raw_value: str | None, default: str = DEFAULT_OTLP_PROTOCOL) -> str:
    normalized = str(raw_value or "").strip().lower()
    if not normalized:
        return default
    if normalized in SUPPORTED_OTLP_PROTOCOLS:
        return normalized
    return default


def default_otlp_endpoint_for(protocol: str) -> str:
    return DEFAULT_GRPC_OTLP_ENDPOINT if normalize_otlp_protocol(protocol) == "grpc" else DEFAULT_HTTP_OTLP_ENDPOINT


def _normalize_base_endpoint(endpoint: str, *, protocol: str = DEFAULT_OTLP_PROTOCOL) -> str:
    normalized_protocol = normalize_otlp_protocol(protocol)
    normalized = str(endpoint or "").strip() or default_otlp_endpoint_for(normalized_protocol)
    if normalized_protocol == "http":
        for suffix in ("/v1/traces", "/v1/metrics", "/v1/logs"):
            if normalized.endswith(suffix):
                return normalized[: -len(suffix)]
    return normalized.rstrip("/")


def parse_resource_attributes(raw_value: str | None) -> dict[str, str]:
    if not raw_value:
        return {}
    parsed: dict[str, str] = {}
    for segment in str(raw_value).split(","):
        piece = segment.strip()
        if not piece or "=" not in piece:
            continue
        key, value = piece.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and value:
            parsed[key] = value
    return parsed


def service_name_is_logicmonitor_safe(service_name: str) -> bool:
    normalized = str(service_name or "").strip()
    return bool(normalized and LOGICMONITOR_SAFE_SERVICE_NAME_PATTERN.fullmatch(normalized))


def logicmonitor_safe_service_name(service_name: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9]+", "", str(service_name or "").strip())
    return sanitized or DEFAULT_LOGICMONITOR_PROOF_SERVICE_NAME


def logicmonitor_service_name_warning(service_name: str) -> str | None:
    if service_name_is_logicmonitor_safe(service_name):
        return None
    return (
        "Service name contains characters that may be unsafe for LogicMonitor trace display; "
        f"use {DEFAULT_LOGICMONITOR_PROOF_SERVICE_NAME} for proof alignment."
    )


def build_logicmonitor_mapping_attributes(
    *,
    service_name: str,
    env: Mapping[str, str] | None = None,
    allow_local_host_defaults: bool = False,
) -> dict[str, str]:
    env = env or os.environ
    host_name = str(env.get("NOVALI_LM_HOST_NAME") or "").strip()
    ip_value = str(env.get("NOVALI_LM_IP") or "").strip()
    resource_type = str(env.get("NOVALI_LM_RESOURCE_TYPE") or "").strip()
    resource_group = str(env.get("NOVALI_LM_RESOURCE_GROUP") or "").strip()
    if allow_local_host_defaults and not resource_type:
        resource_type = "host"
    attributes = {
        "service.namespace": "novali",
        "service.name": service_name,
    }
    if host_name:
        attributes["host.name"] = host_name
    if ip_value:
        attributes["ip"] = ip_value
    if resource_type:
        attributes["resource.type"] = resource_type
    if resource_group:
        attributes["resource.group"] = resource_group
    return attributes


def logicmonitor_mapping_missing(
    resource_attributes: Mapping[str, str] | None,
) -> tuple[str, ...]:
    payload = dict(resource_attributes or {})
    required_keys = ("host.name", "ip", "resource.type")
    return tuple(key for key in required_keys if not str(payload.get(key, "")).strip())


def build_default_resource_attributes(
    *,
    service_name: str,
    env: Mapping[str, str] | None = None,
    allow_local_host_defaults: bool = False,
) -> dict[str, str]:
    env = env or os.environ
    deployment_environment = (
        str(env.get("NOVALI_DEPLOYMENT_ENVIRONMENT") or "").strip() or "local"
    )
    attributes = {
        "service.namespace": "novali",
        "service.name": service_name,
        "service.version": NOVALI_SERVICE_VERSION,
        "deployment.environment.name": deployment_environment,
        "novali.branch": NOVALI_BRANCH,
        "novali.package.version": NOVALI_PACKAGE_VERSION,
        "novali.runtime.role": "operator_shell",
        "novali.telemetry.schema_version": NOVALI_TELEMETRY_SCHEMA_VERSION,
    }
    attributes.update(
        build_logicmonitor_mapping_attributes(
            service_name=service_name,
            env=env,
            allow_local_host_defaults=allow_local_host_defaults,
        )
    )
    return attributes


def endpoint_hint_for(endpoint: str) -> str:
    normalized = str(endpoint or "").strip()
    if not normalized:
        return "unset"
    try:
        parts = urlsplit(normalized)
    except ValueError:
        return "custom"
    hostname = str(parts.hostname or "").strip().lower()
    if hostname in {"", "localhost", "127.0.0.1"}:
        return "localhost"
    if hostname == "host.docker.internal":
        return "host.docker.internal"
    if hostname and "." not in hostname and hostname != "localhost":
        return "docker_network_alias"
    return "custom"


def collector_mode_for(endpoint: str) -> str:
    endpoint_hint = endpoint_hint_for(endpoint)
    if endpoint_hint == "docker_network_alias":
        return "docker"
    if endpoint_hint in {"localhost", "host.docker.internal"}:
        return "same_host"
    if endpoint_hint == "custom":
        return "custom"
    return "unknown"


def resolve_runtime_otlp_endpoint(
    env: Mapping[str, str] | None = None,
    *,
    protocol: str | None = None,
) -> str:
    env = env or os.environ
    selected_protocol = normalize_otlp_protocol(
        protocol or env.get("OTEL_EXPORTER_OTLP_PROTOCOL") or env.get("RC83_1_OTLP_PROTOCOL")
    )
    raw_endpoint = str(
        env.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        or env.get("RC83_1_LMOTEL_ENDPOINT")
        or env.get("LMOTEL_ENDPOINT")
        or default_otlp_endpoint_for(selected_protocol)
    ).strip()
    return _normalize_base_endpoint(raw_endpoint, protocol=selected_protocol)


def resolve_trace_visibility_endpoint(
    env: Mapping[str, str] | None = None,
    *,
    protocol: str | None = None,
) -> str:
    env = env or os.environ
    selected_protocol = normalize_otlp_protocol(
        protocol or env.get("RC83_1_OTLP_PROTOCOL") or env.get("OTEL_EXPORTER_OTLP_PROTOCOL")
    )
    raw_endpoint = str(
        env.get("RC83_1_LMOTEL_ENDPOINT")
        or env.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        or env.get("LMOTEL_ENDPOINT")
        or default_otlp_endpoint_for(selected_protocol)
    ).strip()
    return _normalize_base_endpoint(raw_endpoint, protocol=selected_protocol)


def resolve_live_collector_endpoint(env: Mapping[str, str] | None = None) -> str:
    env = env or os.environ
    raw_endpoint = str(
        env.get("RC83_LMOTEL_ENDPOINT")
        or env.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        or env.get("RC83_1_LMOTEL_ENDPOINT")
        or env.get("LMOTEL_ENDPOINT")
        or DEFAULT_HTTP_OTLP_ENDPOINT
    ).strip()
    return _normalize_base_endpoint(raw_endpoint, protocol="http")


def load_observability_config(
    env: Mapping[str, str] | None = None,
) -> ObservabilityConfig:
    env = env or os.environ
    enabled, env_state = _parse_bool(env.get("NOVALI_OTEL_ENABLED"))
    service_name = (
        str(env.get("OTEL_SERVICE_NAME") or "").strip() or DEFAULT_SERVICE_NAME
    )
    otlp_protocol = normalize_otlp_protocol(
        env.get("OTEL_EXPORTER_OTLP_PROTOCOL") or env.get("RC83_1_OTLP_PROTOCOL")
    )
    endpoint = resolve_runtime_otlp_endpoint(env, protocol=otlp_protocol)
    redaction_mode = str(
        env.get("NOVALI_OTEL_REDACTION_MODE") or DEFAULT_REDACTION_MODE
    ).strip().lower()
    if redaction_mode not in SUPPORTED_REDACTION_MODES:
        redaction_mode = DEFAULT_REDACTION_MODE
    status_detail = str(
        env.get("NOVALI_OBSERVABILITY_STATUS_DETAIL") or DEFAULT_STATUS_DETAIL
    ).strip().lower()
    if status_detail not in SUPPORTED_STATUS_DETAIL:
        status_detail = DEFAULT_STATUS_DETAIL
    resource_attributes = build_default_resource_attributes(
        service_name=service_name,
        env=env,
    )
    resource_attributes.update(parse_resource_attributes(env.get("OTEL_RESOURCE_ATTRIBUTES")))
    resource_attributes.update(
        build_logicmonitor_mapping_attributes(
            service_name=service_name,
            env=env,
        )
    )
    live_collector_proof_enabled, _ = _parse_bool(env.get("RC83_LIVE_COLLECTOR_PROOF"))
    docker_preflight_enabled, _ = _parse_bool(env.get("RC83_DOCKER_PREFLIGHT"))
    trace_visibility_probe_enabled, _ = _parse_bool(env.get("RC83_1_TRACE_VISIBILITY_PROBE"))
    lm_mapping_missing = logicmonitor_mapping_missing(resource_attributes)
    return ObservabilityConfig(
        enabled=enabled,
        endpoint=endpoint,
        service_name=service_name,
        resource_attributes=resource_attributes,
        redaction_mode=redaction_mode,
        export_timeout_ms=_safe_int(
            env.get("NOVALI_OTEL_EXPORT_TIMEOUT_MS"),
            DEFAULT_EXPORT_TIMEOUT_MS,
        ),
        shutdown_timeout_ms=_safe_int(
            env.get("NOVALI_OTEL_SHUTDOWN_TIMEOUT_MS"),
            DEFAULT_SHUTDOWN_TIMEOUT_MS,
        ),
        status_detail=status_detail,
        env_state=env_state,
        otlp_protocol=otlp_protocol,
        service_name_lm_safe=service_name_is_logicmonitor_safe(service_name),
        service_name_lm_warning=logicmonitor_service_name_warning(service_name),
        lm_mapping_attributes_complete=not lm_mapping_missing,
        lm_mapping_missing=lm_mapping_missing,
        live_collector_proof_enabled=live_collector_proof_enabled,
        live_collector_endpoint=resolve_live_collector_endpoint(env),
        live_collector_container_name=str(env.get("RC83_LMOTEL_CONTAINER_NAME") or "").strip(),
        docker_preflight_enabled=docker_preflight_enabled,
        trace_visibility_probe_enabled=trace_visibility_probe_enabled,
        proof_artifact_root=str(
            env.get("RC88_1_PROOF_ARTIFACT_ROOT")
            or env.get("RC88_PROOF_ARTIFACT_ROOT")
            or env.get("RC87_PROOF_ARTIFACT_ROOT")
            or env.get("RC85_PROOF_ARTIFACT_ROOT")
            or env.get("RC84_PROOF_ARTIFACT_ROOT")
            or env.get("RC83_2_PROOF_ARTIFACT_ROOT")
            or env.get("RC83_1_PROOF_ARTIFACT_ROOT")
            or env.get("RC83_PROOF_ARTIFACT_ROOT")
            or "artifacts/operator_proof/v7rc00"
        ).strip(),
    )
