from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from .config import (
    DEFAULT_LOGICMONITOR_PROOF_SERVICE_NAME,
    build_logicmonitor_mapping_attributes,
    endpoint_hint_for,
    logicmonitor_mapping_missing,
    logicmonitor_safe_service_name,
    service_name_is_logicmonitor_safe,
)
from .rc83 import load_json_file

RC83_2_ARTIFACT_SUBPATH = Path("artifacts/operator_proof/rc83_2")
DOCKERIZED_AGENT_TRACE_SUMMARY_NAME = "dockerized_agent_trace_probe_summary.json"
DOCKER_NETWORK_PREFLIGHT_SUMMARY_NAME = "docker_network_preflight_summary.json"
PORTAL_CONFIRMATION_SUMMARY_NAME = "portal_confirmation_summary.json"
PACKAGED_PORTAL_CONFIRMATION_SNAPSHOT_NAME = "rc83_2_portal_confirmation_snapshot.json"

SUPPORTED_DOCKERIZED_ENDPOINT_MODES = {
    "same_network",
    "host_gateway",
    "host_published",
    "custom",
}
SUPPORTED_DOCKERIZED_PROTOCOL_SELECTIONS = {"grpc", "http", "both"}
DEFAULT_DOCKERIZED_ENDPOINT_MODE = "same_network"
DEFAULT_DOCKERIZED_PROTOCOL_SELECTION = "both"
DEFAULT_DOCKERIZED_NETWORK = "novali-observability"


def _truthy(raw_value: str | bool | None) -> bool:
    return str(raw_value or "").strip().lower() in {"1", "true", "yes", "on"}


def normalize_dockerized_endpoint_mode(
    raw_value: str | None,
    *,
    default: str = DEFAULT_DOCKERIZED_ENDPOINT_MODE,
) -> str:
    normalized = str(raw_value or "").strip().lower()
    if normalized in SUPPORTED_DOCKERIZED_ENDPOINT_MODES:
        return normalized
    return default


def normalize_dockerized_protocol_selection(
    raw_value: str | None,
    *,
    default: str = DEFAULT_DOCKERIZED_PROTOCOL_SELECTION,
) -> str:
    normalized = str(raw_value or "").strip().lower()
    if normalized in SUPPORTED_DOCKERIZED_PROTOCOL_SELECTIONS:
        return normalized
    return default


def dockerized_protocol_attempts(selection: str | None) -> list[str]:
    normalized = normalize_dockerized_protocol_selection(selection)
    if normalized == "grpc":
        return ["grpc"]
    if normalized == "http":
        return ["http"]
    return ["grpc", "http"]


def resolve_rc83_2_artifact_root(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    env = env or os.environ
    configured = str(env.get("RC83_2_PROOF_ARTIFACT_ROOT") or "").strip()
    base_root = Path(package_root).resolve() if package_root is not None else None
    if configured:
        configured_path = Path(configured)
        if configured_path.is_absolute():
            return configured_path.resolve()
        if base_root is not None:
            return (base_root / configured_path).resolve()
        return configured_path.resolve()
    if base_root is not None:
        return (base_root / RC83_2_ARTIFACT_SUBPATH).resolve()
    return RC83_2_ARTIFACT_SUBPATH.resolve()


def resolve_dockerized_probe_endpoint(
    *,
    env: Mapping[str, str] | None = None,
    protocol: str,
    endpoint_mode: str | None = None,
) -> str:
    env = env or os.environ
    normalized_mode = normalize_dockerized_endpoint_mode(
        endpoint_mode or env.get("RC83_2_ENDPOINT_MODE")
    )
    port = "4317" if str(protocol or "").strip().lower() == "grpc" else "4318"
    if normalized_mode == "custom":
        return str(env.get("RC83_2_LMOTEL_ENDPOINT") or "").strip()
    if normalized_mode == "same_network":
        collector_name = str(
            env.get("RC83_2_LMOTEL_CONTAINER_NAME") or env.get("RC83_LMOTEL_CONTAINER_NAME") or ""
        ).strip()
        return f"http://{collector_name}:{port}" if collector_name else ""
    return f"http://host.docker.internal:{port}"


def build_dockerized_mapping_attributes(
    *,
    service_name: str,
    env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    env = dict(env or os.environ)
    allow_default_resource_type = bool(
        str(env.get("NOVALI_LM_HOST_NAME") or "").strip()
        and str(env.get("NOVALI_LM_IP") or "").strip()
        and not str(env.get("NOVALI_LM_RESOURCE_TYPE") or "").strip()
    )
    return build_logicmonitor_mapping_attributes(
        service_name=service_name,
        env=env,
        allow_local_host_defaults=allow_default_resource_type,
    )


def dockerized_mapping_status(
    *,
    service_name: str,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    attributes = build_dockerized_mapping_attributes(service_name=service_name, env=env)
    missing = list(logicmonitor_mapping_missing(attributes))
    return {
        "attributes": attributes,
        "complete": not missing,
        "missing": missing,
    }


def load_dockerized_agent_probe_status(
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = env or os.environ
    service_name = (
        str(env.get("OTEL_SERVICE_NAME") or "").strip() or DEFAULT_LOGICMONITOR_PROOF_SERVICE_NAME
    )
    endpoint_mode = normalize_dockerized_endpoint_mode(env.get("RC83_2_ENDPOINT_MODE"))
    protocol_attempts = dockerized_protocol_attempts(env.get("RC83_2_OTLP_PROTOCOL"))
    selected_protocol = protocol_attempts[0] if protocol_attempts else "unknown"
    endpoint = resolve_dockerized_probe_endpoint(
        env=env,
        protocol=selected_protocol,
        endpoint_mode=endpoint_mode,
    )
    mapping = dockerized_mapping_status(service_name=service_name, env=env)
    summary_path = (
        resolve_rc83_2_artifact_root(package_root, env=env) / DOCKERIZED_AGENT_TRACE_SUMMARY_NAME
    )
    payload = {
        "enabled": _truthy(env.get("RC83_2_DOCKERIZED_TRACE_PROOF")),
        "last_probe_result": "not_recorded",
        "last_probe_id": None,
        "last_probe_time": None,
        "endpoint_hint": endpoint_hint_for(endpoint),
        "endpoint_mode": endpoint_mode,
        "network_mode": endpoint_mode,
        "otlp_protocol": selected_protocol,
        "service_name": service_name,
        "service_name_lm_safe": service_name_is_logicmonitor_safe(service_name),
        "service_name_lm_safe_suggestion": logicmonitor_safe_service_name(service_name),
        "lm_mapping_attributes_complete": bool(mapping["complete"]),
        "lm_mapping_missing": list(mapping["missing"]),
        "container_runtime_proven": False,
        "container_hostname": None,
        "no_secrets_captured": True,
    }
    summary = load_json_file(summary_path)
    if not summary:
        return payload
    payload.update(
        {
            "enabled": bool(summary.get("opt_in_enabled", payload["enabled"])),
            "last_probe_result": str(summary.get("result", payload["last_probe_result"]) or payload["last_probe_result"]),
            "last_probe_id": str(summary.get("proof_id", "")).strip() or None,
            "last_probe_time": str(summary.get("generated_at", "")).strip() or None,
            "endpoint_hint": str(summary.get("endpoint_hint", payload["endpoint_hint"]) or payload["endpoint_hint"]),
            "endpoint_mode": str(summary.get("endpoint_mode", payload["endpoint_mode"]) or payload["endpoint_mode"]),
            "network_mode": str(summary.get("docker_network_mode", payload["network_mode"]) or payload["network_mode"]),
            "otlp_protocol": str(summary.get("otlp_protocol", payload["otlp_protocol"]) or payload["otlp_protocol"]),
            "service_name": str(summary.get("service_name", payload["service_name"]) or payload["service_name"]),
            "service_name_lm_safe": bool(summary.get("service_name_lm_safe", payload["service_name_lm_safe"])),
            "service_name_lm_safe_suggestion": logicmonitor_safe_service_name(
                str(summary.get("service_name", payload["service_name"]) or payload["service_name"])
            ),
            "lm_mapping_attributes_complete": bool(
                summary.get(
                    "lm_mapping_attributes_complete",
                    payload["lm_mapping_attributes_complete"],
                )
            ),
            "lm_mapping_missing": list(
                summary.get("lm_mapping_missing", payload["lm_mapping_missing"]) or []
            ),
            "container_runtime_proven": bool(
                summary.get("container_runtime_proven", payload["container_runtime_proven"])
            ),
            "container_hostname": str(summary.get("container_hostname", "")).strip() or None,
            "no_secrets_captured": bool(summary.get("no_secrets_captured", True)),
            "artifact_path": str(summary_path),
        }
    )
    return payload


def load_portal_confirmation_status(
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    summary_path = resolve_rc83_2_artifact_root(package_root, env=env) / PORTAL_CONFIRMATION_SUMMARY_NAME
    package_base = Path(package_root).resolve() if package_root is not None else None
    packaged_snapshot_path = (
        (package_base / "observability" / "logicmonitor" / PACKAGED_PORTAL_CONFIRMATION_SNAPSHOT_NAME)
        if package_base is not None
        else Path("observability") / "logicmonitor" / PACKAGED_PORTAL_CONFIRMATION_SNAPSHOT_NAME
    )
    payload = {
        "confirmation_state": "not_recorded",
        "proof_id": None,
        "service_name": None,
        "recorded_at": None,
        "protocol": None,
        "endpoint_mode": None,
        "confirmation_source": None,
    }
    summary = load_json_file(summary_path)
    if not summary:
        summary = load_json_file(packaged_snapshot_path)
    if not summary:
        payload["artifact_path"] = str(summary_path)
        payload["snapshot_path"] = str(packaged_snapshot_path)
        return payload
    payload.update(
        {
            "confirmation_state": str(
                summary.get("confirmation_state", payload["confirmation_state"])
                or payload["confirmation_state"]
            ),
            "proof_id": str(summary.get("proof_id", "")).strip() or None,
            "service_name": str(summary.get("service_name", "")).strip() or None,
            "recorded_at": str(summary.get("generated_at", "")).strip() or None,
            "protocol": str(summary.get("protocol", "")).strip() or None,
            "endpoint_mode": str(summary.get("endpoint_mode", "")).strip() or None,
            "confirmation_source": str(summary.get("confirmation_source", "")).strip() or None,
            "artifact_path": str(summary_path),
            "snapshot_path": str(packaged_snapshot_path),
        }
    )
    return payload


def merge_dockerized_trace_status(
    observability_status: Mapping[str, Any],
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    merged = dict(observability_status)
    dockerized_agent_probe = load_dockerized_agent_probe_status(
        package_root=package_root,
        env=env,
    )
    portal_confirmation = load_portal_confirmation_status(
        package_root=package_root,
        env=env,
    )
    merged["dockerized_agent_probe"] = dockerized_agent_probe
    merged["dockerized_agent_probe_result"] = dockerized_agent_probe.get(
        "last_probe_result",
        "not_recorded",
    )
    merged["dockerized_agent_probe_id"] = dockerized_agent_probe.get("last_probe_id")
    merged["dockerized_agent_runtime_proven"] = bool(
        dockerized_agent_probe.get("container_runtime_proven", False)
    )
    merged["dockerized_endpoint_mode"] = str(
        dockerized_agent_probe.get("endpoint_mode", "unknown")
    )
    merged["dockerized_network_mode"] = str(
        dockerized_agent_probe.get("network_mode", "unknown")
    )
    merged["dockerized_protocol"] = str(
        dockerized_agent_probe.get("otlp_protocol", "unknown")
    )
    merged["dockerized_mapping_complete"] = bool(
        dockerized_agent_probe.get("lm_mapping_attributes_complete", False)
    )
    portal_artifact_found = False
    artifact_path = str(portal_confirmation.get("artifact_path", "")).strip()
    if artifact_path:
        portal_artifact_found = Path(artifact_path).exists()
    if portal_artifact_found or str(
        portal_confirmation.get("confirmation_state", "not_recorded")
    ).strip() != "not_recorded":
        merged["portal_confirmation"] = portal_confirmation
        merged["last_portal_confirmation"] = portal_confirmation.get(
            "confirmation_state",
            "not_recorded",
        )
    return merged
