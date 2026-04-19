from __future__ import annotations

import threading
from typing import Any

from .config import DEFAULT_SHUTDOWN_TIMEOUT_MS, ObservabilityConfig, endpoint_hint_for


def _default_shutdown_state(timeout_ms: int = DEFAULT_SHUTDOWN_TIMEOUT_MS) -> dict[str, Any]:
    return {
        "last_flush_result": "unknown",
        "last_shutdown_result": "unknown",
        "last_timeout_count": 0,
        "last_error_type": None,
        "last_error_summary_redacted": None,
        "last_shutdown_time": None,
        "timeout_ms": int(timeout_ms or DEFAULT_SHUTDOWN_TIMEOUT_MS),
        "traceback_suppressed_for_expected_timeout": False,
        "unexpected_exception_seen": False,
    }

_LOCK = threading.RLock()
_STATE: dict[str, Any] = {
    "enabled": False,
    "mode": "disabled",
    "status": "disabled",
    "endpoint_configured": False,
    "endpoint_hint": "unset",
    "service_name": "novali-operator-shell",
    "service_name_lm_safe": False,
    "service_name_lm_warning": None,
    "resource_summary": {},
    "last_export_result": "not_attempted",
    "last_error_type": None,
    "redaction_mode": "strict",
    "env_state": "valid",
    "active_otlp_protocol": "unknown",
    "lm_mapping_attributes_complete": False,
    "lm_mapping_missing": ["host.name", "ip", "resource.type"],
    "export_failure_count": 0,
    "live_collector_probe": {
        "enabled": False,
        "last_probe_result": "unknown",
        "last_probe_kind": None,
        "last_probe_id": None,
        "last_probe_time": None,
        "endpoint_hint": "unset",
        "collector_mode": "unknown",
        "no_secrets_captured": True,
    },
    "trace_visibility_probe": {
        "enabled": False,
        "last_probe_result": "not_recorded",
        "last_probe_id": None,
        "last_probe_time": None,
        "endpoint_hint": "unset",
        "otlp_protocol": "unknown",
        "service_name": "novali-operator-shell",
        "service_name_lm_safe": False,
        "lm_mapping_attributes_complete": False,
        "lm_mapping_missing": ["host.name", "ip", "resource.type"],
        "no_secrets_captured": True,
    },
    "dockerized_agent_probe": {
        "enabled": False,
        "last_probe_result": "not_recorded",
        "last_probe_id": None,
        "last_probe_time": None,
        "endpoint_hint": "unset",
        "endpoint_mode": "unknown",
        "network_mode": "unknown",
        "otlp_protocol": "unknown",
        "service_name": "novali-operator-shell",
        "service_name_lm_safe": False,
        "lm_mapping_attributes_complete": False,
        "lm_mapping_missing": ["host.name", "ip", "resource.type"],
        "container_runtime_proven": False,
        "container_hostname": None,
        "no_secrets_captured": True,
    },
    "last_visibility_probe_result": "not_recorded",
    "last_visibility_probe_id": None,
    "dockerized_agent_probe_result": "not_recorded",
    "dockerized_agent_probe_id": None,
    "dockerized_agent_runtime_proven": False,
    "dockerized_endpoint_mode": "unknown",
    "dockerized_network_mode": "unknown",
    "dockerized_protocol": "unknown",
    "dockerized_mapping_complete": False,
    "last_portal_confirmation": "not_recorded",
    "portal_confirmation": {
        "confirmation_state": "not_recorded",
        "proof_id": None,
        "service_name": None,
        "recorded_at": None,
        "protocol": None,
        "endpoint_mode": None,
    },
    "observability_shutdown": _default_shutdown_state(),
}


def _resource_summary(config: ObservabilityConfig) -> dict[str, str]:
    keys = (
        "service.namespace",
        "service.name",
        "service.version",
        "deployment.environment.name",
        "resource.type",
        "host.name",
        "ip",
        "resource.group",
    )
    return {
        key: str(config.resource_attributes.get(key, ""))
        for key in keys
        if config.resource_attributes.get(key)
    }


def configure_observability_status(
    config: ObservabilityConfig,
    *,
    mode: str,
    status: str,
    last_export_result: str = "not_attempted",
    last_error_type: str | None = None,
) -> None:
    with _LOCK:
        previous_shutdown = dict(_STATE.get("observability_shutdown", {}))
        shutdown_state = _default_shutdown_state(
            int(getattr(config, "shutdown_timeout_ms", DEFAULT_SHUTDOWN_TIMEOUT_MS))
        )
        shutdown_state.update(
            {
                "last_flush_result": str(
                    previous_shutdown.get("last_flush_result", "unknown") or "unknown"
                ),
                "last_shutdown_result": str(
                    previous_shutdown.get("last_shutdown_result", "unknown") or "unknown"
                ),
                "last_timeout_count": int(
                    previous_shutdown.get("last_timeout_count", 0) or 0
                ),
                "last_error_type": previous_shutdown.get("last_error_type"),
                "last_error_summary_redacted": previous_shutdown.get(
                    "last_error_summary_redacted"
                ),
                "last_shutdown_time": previous_shutdown.get("last_shutdown_time"),
                "traceback_suppressed_for_expected_timeout": bool(
                    previous_shutdown.get(
                        "traceback_suppressed_for_expected_timeout", False
                    )
                ),
                "unexpected_exception_seen": bool(
                    previous_shutdown.get("unexpected_exception_seen", False)
                ),
            }
        )
        _STATE.update(
            {
                "enabled": bool(config.enabled),
                "mode": mode,
                "status": status,
                "endpoint_configured": bool(config.endpoint),
                "endpoint_hint": endpoint_hint_for(config.endpoint),
                "service_name": config.service_name,
                "service_name_lm_safe": bool(config.service_name_lm_safe),
                "service_name_lm_warning": config.service_name_lm_warning,
                "resource_summary": _resource_summary(config),
                "last_export_result": last_export_result,
                "last_error_type": last_error_type,
                "redaction_mode": config.redaction_mode,
                "env_state": config.env_state,
                "active_otlp_protocol": str(config.otlp_protocol or "unknown"),
                "lm_mapping_attributes_complete": bool(config.lm_mapping_attributes_complete),
                "lm_mapping_missing": list(config.lm_mapping_missing),
                "observability_shutdown": shutdown_state,
            }
        )


def mark_export_success() -> None:
    with _LOCK:
        _STATE["status"] = "exporting"
        _STATE["last_export_result"] = "success"
        _STATE["last_error_type"] = None


def mark_export_failure(error_type: str | None = None) -> None:
    with _LOCK:
        _STATE["status"] = "degraded"
        _STATE["last_export_result"] = "failure"
        _STATE["last_error_type"] = str(error_type or "export_failure")
        _STATE["export_failure_count"] = int(_STATE.get("export_failure_count", 0) or 0) + 1


def mark_disabled(config: ObservabilityConfig) -> None:
    configure_observability_status(config, mode="disabled", status="disabled")


def mark_unavailable(config: ObservabilityConfig, *, error_type: str | None = None) -> None:
    configure_observability_status(
        config,
        mode="noop",
        status="unavailable",
        last_error_type=error_type,
    )


def reset_observability_shutdown_status(timeout_ms: int | None = None) -> None:
    with _LOCK:
        _STATE["observability_shutdown"] = _default_shutdown_state(
            int(timeout_ms or _STATE.get("observability_shutdown", {}).get("timeout_ms", 0) or DEFAULT_SHUTDOWN_TIMEOUT_MS)
        )


def update_observability_shutdown_status(
    *,
    flush_result: str | None = None,
    shutdown_result: str | None = None,
    error_type: str | None = None,
    error_summary_redacted: str | None = None,
    timeout_ms: int | None = None,
    increment_timeout: bool = False,
    traceback_suppressed_for_expected_timeout: bool | None = None,
    unexpected_exception_seen: bool | None = None,
    shutdown_time: str | None = None,
) -> None:
    with _LOCK:
        state = dict(_STATE.get("observability_shutdown", _default_shutdown_state()))
        if flush_result is not None:
            state["last_flush_result"] = str(flush_result or "unknown")
        if shutdown_result is not None:
            state["last_shutdown_result"] = str(shutdown_result or "unknown")
        if error_type is not None:
            state["last_error_type"] = str(error_type or "").strip() or None
        elif shutdown_result in {"success", "disabled", "unavailable"} and flush_result in {
            None,
            "success",
            "disabled",
            "unavailable",
        }:
            state["last_error_type"] = None
        if error_summary_redacted is not None:
            state["last_error_summary_redacted"] = (
                str(error_summary_redacted or "").strip() or None
            )
        elif shutdown_result in {"success", "disabled", "unavailable"} and flush_result in {
            None,
            "success",
            "disabled",
            "unavailable",
        }:
            state["last_error_summary_redacted"] = None
        if timeout_ms is not None:
            state["timeout_ms"] = int(timeout_ms or DEFAULT_SHUTDOWN_TIMEOUT_MS)
        if increment_timeout:
            state["last_timeout_count"] = int(state.get("last_timeout_count", 0) or 0) + 1
        if traceback_suppressed_for_expected_timeout is not None:
            state["traceback_suppressed_for_expected_timeout"] = bool(
                traceback_suppressed_for_expected_timeout
            )
        if unexpected_exception_seen is not None:
            state["unexpected_exception_seen"] = bool(unexpected_exception_seen)
        if shutdown_time is not None:
            state["last_shutdown_time"] = str(shutdown_time or "").strip() or None
        _STATE["observability_shutdown"] = state


def update_live_collector_probe(
    *,
    enabled: bool,
    last_probe_result: str,
    last_probe_kind: str | None = None,
    last_probe_id: str | None = None,
    last_probe_time: str | None = None,
    endpoint_hint: str = "unset",
    collector_mode: str = "unknown",
    no_secrets_captured: bool = True,
) -> None:
    with _LOCK:
        _STATE["live_collector_probe"] = {
            "enabled": bool(enabled),
            "last_probe_result": str(last_probe_result or "unknown"),
            "last_probe_kind": str(last_probe_kind or "") or None,
            "last_probe_id": str(last_probe_id or "") or None,
            "last_probe_time": str(last_probe_time or "") or None,
            "endpoint_hint": str(endpoint_hint or "unset"),
            "collector_mode": str(collector_mode or "unknown"),
            "no_secrets_captured": bool(no_secrets_captured),
        }


def update_trace_visibility_probe(
    *,
    enabled: bool,
    last_probe_result: str,
    last_probe_id: str | None = None,
    last_probe_time: str | None = None,
    endpoint_hint: str = "unset",
    otlp_protocol: str = "unknown",
    service_name: str = "novali-operator-shell",
    service_name_lm_safe: bool = False,
    lm_mapping_attributes_complete: bool = False,
    lm_mapping_missing: list[str] | tuple[str, ...] | None = None,
    no_secrets_captured: bool = True,
) -> None:
    with _LOCK:
        payload = {
            "enabled": bool(enabled),
            "last_probe_result": str(last_probe_result or "not_recorded"),
            "last_probe_id": str(last_probe_id or "") or None,
            "last_probe_time": str(last_probe_time or "") or None,
            "endpoint_hint": str(endpoint_hint or "unset"),
            "otlp_protocol": str(otlp_protocol or "unknown"),
            "service_name": str(service_name or "novali-operator-shell"),
            "service_name_lm_safe": bool(service_name_lm_safe),
            "lm_mapping_attributes_complete": bool(lm_mapping_attributes_complete),
            "lm_mapping_missing": list(lm_mapping_missing or []),
            "no_secrets_captured": bool(no_secrets_captured),
        }
        _STATE["trace_visibility_probe"] = payload
        _STATE["last_visibility_probe_result"] = payload["last_probe_result"]
        _STATE["last_visibility_probe_id"] = payload["last_probe_id"]


def update_dockerized_agent_probe(
    *,
    enabled: bool,
    last_probe_result: str,
    last_probe_id: str | None = None,
    last_probe_time: str | None = None,
    endpoint_hint: str = "unset",
    endpoint_mode: str = "unknown",
    network_mode: str = "unknown",
    otlp_protocol: str = "unknown",
    service_name: str = "novali-operator-shell",
    service_name_lm_safe: bool = False,
    lm_mapping_attributes_complete: bool = False,
    lm_mapping_missing: list[str] | tuple[str, ...] | None = None,
    container_runtime_proven: bool = False,
    container_hostname: str | None = None,
    no_secrets_captured: bool = True,
) -> None:
    with _LOCK:
        payload = {
            "enabled": bool(enabled),
            "last_probe_result": str(last_probe_result or "not_recorded"),
            "last_probe_id": str(last_probe_id or "") or None,
            "last_probe_time": str(last_probe_time or "") or None,
            "endpoint_hint": str(endpoint_hint or "unset"),
            "endpoint_mode": str(endpoint_mode or "unknown"),
            "network_mode": str(network_mode or "unknown"),
            "otlp_protocol": str(otlp_protocol or "unknown"),
            "service_name": str(service_name or "novali-operator-shell"),
            "service_name_lm_safe": bool(service_name_lm_safe),
            "lm_mapping_attributes_complete": bool(lm_mapping_attributes_complete),
            "lm_mapping_missing": list(lm_mapping_missing or []),
            "container_runtime_proven": bool(container_runtime_proven),
            "container_hostname": str(container_hostname or "") or None,
            "no_secrets_captured": bool(no_secrets_captured),
        }
        _STATE["dockerized_agent_probe"] = payload
        _STATE["dockerized_agent_probe_result"] = payload["last_probe_result"]
        _STATE["dockerized_agent_probe_id"] = payload["last_probe_id"]
        _STATE["dockerized_agent_runtime_proven"] = payload["container_runtime_proven"]
        _STATE["dockerized_endpoint_mode"] = payload["endpoint_mode"]
        _STATE["dockerized_network_mode"] = payload["network_mode"]
        _STATE["dockerized_protocol"] = payload["otlp_protocol"]
        _STATE["dockerized_mapping_complete"] = payload["lm_mapping_attributes_complete"]


def update_portal_confirmation(
    *,
    confirmation_state: str,
    proof_id: str | None = None,
    service_name: str | None = None,
    recorded_at: str | None = None,
    protocol: str | None = None,
    endpoint_mode: str | None = None,
) -> None:
    with _LOCK:
        payload = {
            "confirmation_state": str(confirmation_state or "not_recorded"),
            "proof_id": str(proof_id or "") or None,
            "service_name": str(service_name or "") or None,
            "recorded_at": str(recorded_at or "") or None,
            "protocol": str(protocol or "") or None,
            "endpoint_mode": str(endpoint_mode or "") or None,
        }
        _STATE["portal_confirmation"] = payload
        _STATE["last_portal_confirmation"] = payload["confirmation_state"]


def get_observability_status() -> dict[str, Any]:
    with _LOCK:
        shutdown_state = dict(
            _STATE.get("observability_shutdown", _default_shutdown_state())
        )
        return {
            "enabled": bool(_STATE.get("enabled", False)),
            "mode": str(_STATE.get("mode", "disabled")),
            "status": str(_STATE.get("status", "disabled")),
            "endpoint_configured": bool(_STATE.get("endpoint_configured", False)),
            "endpoint_hint": str(_STATE.get("endpoint_hint", "unset")),
            "service_name": str(_STATE.get("service_name", "novali-operator-shell")),
            "service_name_lm_safe": bool(_STATE.get("service_name_lm_safe", False)),
            "service_name_lm_warning": _STATE.get("service_name_lm_warning"),
            "resource_summary": dict(_STATE.get("resource_summary", {})),
            "last_export_result": str(_STATE.get("last_export_result", "not_attempted")),
            "last_error_type": _STATE.get("last_error_type"),
            "redaction_mode": str(_STATE.get("redaction_mode", "strict")),
            "env_state": str(_STATE.get("env_state", "valid")),
            "active_otlp_protocol": str(_STATE.get("active_otlp_protocol", "unknown")),
            "lm_mapping_attributes_complete": bool(
                _STATE.get("lm_mapping_attributes_complete", False)
            ),
            "lm_mapping_missing": list(_STATE.get("lm_mapping_missing", [])),
            "export_failure_count": int(_STATE.get("export_failure_count", 0) or 0),
            "live_collector_probe": dict(_STATE.get("live_collector_probe", {})),
            "trace_visibility_probe": dict(_STATE.get("trace_visibility_probe", {})),
            "last_visibility_probe_result": str(
                _STATE.get("last_visibility_probe_result", "not_recorded")
            ),
            "last_visibility_probe_id": _STATE.get("last_visibility_probe_id"),
            "dockerized_agent_probe": dict(_STATE.get("dockerized_agent_probe", {})),
            "dockerized_agent_probe_result": str(
                _STATE.get("dockerized_agent_probe_result", "not_recorded")
            ),
            "dockerized_agent_probe_id": _STATE.get("dockerized_agent_probe_id"),
            "dockerized_agent_runtime_proven": bool(
                _STATE.get("dockerized_agent_runtime_proven", False)
            ),
            "dockerized_endpoint_mode": str(
                _STATE.get("dockerized_endpoint_mode", "unknown")
            ),
            "dockerized_network_mode": str(
                _STATE.get("dockerized_network_mode", "unknown")
            ),
            "dockerized_protocol": str(_STATE.get("dockerized_protocol", "unknown")),
            "dockerized_mapping_complete": bool(
                _STATE.get("dockerized_mapping_complete", False)
            ),
            "last_portal_confirmation": str(
                _STATE.get("last_portal_confirmation", "not_recorded")
            ),
            "portal_confirmation": dict(_STATE.get("portal_confirmation", {})),
            "observability_shutdown": shutdown_state,
            "last_otel_shutdown_result": str(
                shutdown_state.get("last_shutdown_result", "unknown") or "unknown"
            ),
            "last_otel_shutdown_timeout_count": int(
                shutdown_state.get("last_timeout_count", 0) or 0
            ),
            "last_otel_shutdown_error_type": shutdown_state.get("last_error_type"),
            "expected_timeout_traceback_suppressed": bool(
                shutdown_state.get(
                    "traceback_suppressed_for_expected_timeout", False
                )
            ),
        }


def get_observability_shutdown_status() -> dict[str, Any]:
    with _LOCK:
        return dict(_STATE.get("observability_shutdown", _default_shutdown_state()))
