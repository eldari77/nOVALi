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
    normalize_otlp_protocol,
    resolve_trace_visibility_endpoint,
    service_name_is_logicmonitor_safe,
)
from .rc83 import load_json_file

RC83_1_ARTIFACT_SUBPATH = Path("artifacts/operator_proof/rc83_1")
TRACE_VISIBILITY_SUMMARY_NAME = "trace_visibility_probe_summary.json"
PORTAL_CONFIRMATION_SUMMARY_NAME = "portal_confirmation_summary.json"


def _truthy(raw_value: str | bool | None) -> bool:
    return str(raw_value or "").strip().lower() in {"1", "true", "yes", "on"}


def resolve_rc83_1_artifact_root(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    env = env or os.environ
    configured = str(
        env.get("RC83_1_PROOF_ARTIFACT_ROOT") or env.get("RC83_PROOF_ARTIFACT_ROOT") or ""
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
        return (base_root / RC83_1_ARTIFACT_SUBPATH).resolve()
    return RC83_1_ARTIFACT_SUBPATH.resolve()


def load_trace_visibility_probe_status(
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = env or os.environ
    service_name = (
        str(env.get("OTEL_SERVICE_NAME") or "").strip() or DEFAULT_LOGICMONITOR_PROOF_SERVICE_NAME
    )
    protocol = normalize_otlp_protocol(
        env.get("RC83_1_OTLP_PROTOCOL") or env.get("OTEL_EXPORTER_OTLP_PROTOCOL")
    )
    endpoint = resolve_trace_visibility_endpoint(env, protocol=protocol)
    mapping_attributes = build_logicmonitor_mapping_attributes(
        service_name=service_name,
        env=env,
        allow_local_host_defaults=True,
    )
    mapping_missing = list(logicmonitor_mapping_missing(mapping_attributes))
    summary_path = resolve_rc83_1_artifact_root(package_root, env=env) / TRACE_VISIBILITY_SUMMARY_NAME
    payload = {
        "enabled": _truthy(env.get("RC83_1_TRACE_VISIBILITY_PROBE")),
        "last_probe_result": "not_recorded",
        "last_probe_id": None,
        "last_probe_time": None,
        "endpoint_hint": endpoint_hint_for(endpoint),
        "otlp_protocol": protocol or "unknown",
        "service_name": service_name,
        "service_name_lm_safe": service_name_is_logicmonitor_safe(service_name),
        "service_name_lm_safe_suggestion": logicmonitor_safe_service_name(service_name),
        "lm_mapping_attributes_complete": not mapping_missing,
        "lm_mapping_missing": mapping_missing,
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
            "otlp_protocol": str(summary.get("otlp_protocol", payload["otlp_protocol"]) or payload["otlp_protocol"]),
            "service_name": str(summary.get("service_name", payload["service_name"]) or payload["service_name"]),
            "service_name_lm_safe": bool(
                summary.get("service_name_lm_safe", payload["service_name_lm_safe"])
            ),
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
    summary_path = resolve_rc83_1_artifact_root(package_root, env=env) / PORTAL_CONFIRMATION_SUMMARY_NAME
    payload = {
        "confirmation_state": "not_recorded",
        "proof_id": None,
        "service_name": None,
        "recorded_at": None,
        "confirmation_source": None,
    }
    summary = load_json_file(summary_path)
    if not summary:
        payload["artifact_path"] = str(summary_path)
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
            "confirmation_source": str(summary.get("confirmation_source", "")).strip() or None,
            "artifact_path": str(summary_path),
        }
    )
    return payload


def merge_trace_visibility_status(
    observability_status: Mapping[str, Any],
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    merged = dict(observability_status)
    trace_visibility_probe = load_trace_visibility_probe_status(
        package_root=package_root,
        env=env,
    )
    portal_confirmation = load_portal_confirmation_status(
        package_root=package_root,
        env=env,
    )
    merged["trace_visibility_probe"] = trace_visibility_probe
    merged["last_visibility_probe_result"] = trace_visibility_probe.get("last_probe_result", "not_recorded")
    merged["last_visibility_probe_id"] = trace_visibility_probe.get("last_probe_id")
    merged["portal_confirmation"] = portal_confirmation
    merged["last_portal_confirmation"] = portal_confirmation.get("confirmation_state", "not_recorded")
    return merged
