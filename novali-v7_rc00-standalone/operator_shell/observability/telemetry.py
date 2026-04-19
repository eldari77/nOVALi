from __future__ import annotations

import contextlib
import inspect
import io
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.parse import urlsplit

from .config import (
    DEFAULT_SHUTDOWN_TIMEOUT_MS,
    NOVALI_BRANCH,
    NOVALI_PACKAGE_VERSION,
    ObservabilityConfig,
    load_observability_config,
)
from .redaction import REDACTED, redact_attributes, redact_value
from .status import (
    configure_observability_status,
    get_observability_shutdown_status,
    get_observability_status,
    mark_disabled,
    mark_export_failure,
    mark_export_success,
    update_dockerized_agent_probe,
    reset_observability_shutdown_status,
    update_portal_confirmation,
    update_trace_visibility_probe,
    update_observability_shutdown_status,
    mark_unavailable,
    update_live_collector_probe,
)

LOGGER = logging.getLogger("novali.observability")

_RUNTIME_LOCK = threading.RLock()
_RUNTIME: dict[str, Any] = {
    "config": None,
    "enabled": False,
    "tracer_provider": None,
    "meter_provider": None,
    "tracer": None,
    "meter": None,
    "counter_instruments": {},
    "histogram_instruments": {},
    "gauge_instruments": {},
    "gauge_values": {},
    "Observation": None,
    "shutdown_in_progress": False,
    "shutdown_complete": False,
}


class _NoopSpan:
    def add_event(self, name: str, attributes: Mapping[str, Any] | None = None) -> None:
        return

    def set_attribute(self, key: str, value: Any) -> None:
        return

    def record_exception(self, exception: BaseException) -> None:
        return


def _safe_log_event(name: str, attributes: Mapping[str, Any] | None = None) -> None:
    payload = {"event": name, "attributes": redact_attributes(attributes or {})}
    LOGGER.info("novali_otel %s", json.dumps(payload, sort_keys=True))


def _normalize_attributes(attributes: Mapping[str, Any] | None) -> dict[str, Any]:
    redacted = redact_attributes(attributes or {})
    if attributes and redacted != dict(attributes):
        _safe_log_event("novali.redaction.applied", {"attribute_keys": list(redacted.keys())})
    return redacted


def _load_otel_runtime() -> dict[str, Any]:
    from opentelemetry import metrics, trace
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.metrics import Observation
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExportResult, SpanExporter

    OTLPGrpcMetricExporter = None
    OTLPGrpcSpanExporter = None
    try:
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter as OTLPGrpcMetricExporter,
        )
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter as OTLPGrpcSpanExporter,
        )
    except Exception:  # pragma: no cover
        OTLPGrpcMetricExporter = None
        OTLPGrpcSpanExporter = None

    return {
        "metrics": metrics,
        "trace": trace,
        "Observation": Observation,
        "OTLPMetricExporter": OTLPMetricExporter,
        "OTLPSpanExporter": OTLPSpanExporter,
        "OTLPGrpcMetricExporter": OTLPGrpcMetricExporter,
        "OTLPGrpcSpanExporter": OTLPGrpcSpanExporter,
        "MeterProvider": MeterProvider,
        "PeriodicExportingMetricReader": PeriodicExportingMetricReader,
        "Resource": Resource,
        "TracerProvider": TracerProvider,
        "BatchSpanProcessor": BatchSpanProcessor,
        "SpanExportResult": SpanExportResult,
        "SpanExporter": SpanExporter,
    }


def _supported_kwargs(factory: Any, **kwargs: Any) -> dict[str, Any]:
    signature = inspect.signature(factory.__init__ if inspect.isclass(factory) else factory)
    return {key: value for key, value in kwargs.items() if key in signature.parameters}


def _trace_endpoint(base_endpoint: str) -> str:
    return f"{base_endpoint.rstrip('/')}/v1/traces"


def _metric_endpoint(base_endpoint: str) -> str:
    return f"{base_endpoint.rstrip('/')}/v1/metrics"


def _grpc_endpoint_is_insecure(endpoint: str) -> bool:
    try:
        parts = urlsplit(str(endpoint or "").strip())
    except ValueError:
        return False
    return str(parts.scheme or "").strip().lower() in {"", "http"}


def _runtime_attributes(extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    config = _RUNTIME.get("config")
    attrs = {
        "novali.branch": NOVALI_BRANCH,
        "novali.package.version": NOVALI_PACKAGE_VERSION,
        "novali.runtime.role": "operator_shell",
    }
    if config is not None:
        attrs["service.name"] = config.service_name
    if extra:
        attrs.update(dict(extra))
    return attrs


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _resolve_timeout_ms(
    timeout_ms: int | None,
    *,
    config: ObservabilityConfig | None = None,
    default: int = DEFAULT_SHUTDOWN_TIMEOUT_MS,
) -> int:
    candidate = timeout_ms
    if candidate is None and config is not None:
        candidate = getattr(config, "shutdown_timeout_ms", None)
    try:
        parsed = int(candidate or 0)
    except (TypeError, ValueError):
        parsed = 0
    return parsed if parsed > 0 else int(default)


def _truncate_summary(value: str | None, *, limit: int = 240) -> str | None:
    normalized = str(redact_value(value or "", key="error_summary") or "").strip()
    if not normalized:
        return None
    compact = " ".join(normalized.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _exception_summary(exc: BaseException) -> str | None:
    return _truncate_summary(f"{type(exc).__name__}: {exc}")


def _result_rank(result: str) -> int:
    return {
        "success": 0,
        "disabled": 0,
        "unavailable": 1,
        "timeout": 2,
        "degraded": 3,
        "failed": 4,
    }.get(str(result or "").strip(), 5)


def _max_result(*results: str) -> str:
    normalized = [str(item or "").strip() for item in results if str(item or "").strip()]
    if not normalized:
        return "unknown"
    return max(normalized, key=_result_rank)


def _captured_timeout_traceback(text: str) -> bool:
    lowered = str(text or "").lower()
    return (
        "traceback (most recent call last)" in lowered
        and "metricstimeouterror" in lowered
        and "timed out while executing callback" in lowered
    )


def _captured_timeout_warning(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(
        marker in lowered
        for marker in (
            "timed out while executing callback",
            "metric collection timed out.",
            "failed to export metrics batch due to timeout",
            "failed to export span batch due to timeout",
        )
    )


def _captured_expected_timeout(text: str) -> bool:
    return _captured_timeout_traceback(text) or _captured_timeout_warning(text)


def _is_expected_timeout_exception(exc: BaseException) -> bool:
    message = str(exc or "").strip().lower()
    return type(exc).__name__ in {"MetricsTimeoutError"} or (
        type(exc).__name__ in {"TimeoutError"}
        and "timed out while executing callback" in message
    )


def _runtime_snapshot() -> dict[str, Any]:
    with _RUNTIME_LOCK:
        return {
            "config": _RUNTIME.get("config"),
            "enabled": bool(_RUNTIME.get("enabled", False)),
            "tracer_provider": _RUNTIME.get("tracer_provider"),
            "meter_provider": _RUNTIME.get("meter_provider"),
            "shutdown_in_progress": bool(_RUNTIME.get("shutdown_in_progress", False)),
            "shutdown_complete": bool(_RUNTIME.get("shutdown_complete", False)),
        }


def _call_provider_method(
    provider: Any,
    method_name: str,
    *,
    timeout_ms: int,
) -> dict[str, Any]:
    if provider is None:
        return {"called": False, "success": True, "value": None}
    method = getattr(provider, method_name, None)
    if not callable(method):
        return {"called": False, "success": True, "value": None}
    kwargs = _supported_kwargs(
        method,
        timeout_millis=timeout_ms,
        timeout=timeout_ms / 1000.0,
    )
    value = method(**kwargs)
    success = True if value is None else bool(value)
    return {"called": True, "success": bool(success), "value": value}


def _capture_stderr(operation: Any) -> tuple[Any, str]:
    buffer = io.StringIO()
    with contextlib.redirect_stderr(buffer):
        result = operation()
    return result, buffer.getvalue()


def _emit_observability_shutdown_event(
    event_name: str,
    *,
    result: str,
    timeout_ms: int,
    error_type: str | None = None,
    error_summary: str | None = None,
    phase: str,
) -> None:
    attrs = {
        "result": result,
        "shutdown_phase": phase,
        "shutdown_timeout_ms": timeout_ms,
    }
    if error_type:
        attrs["shutdown_error_type"] = error_type
    if error_summary:
        attrs["shutdown_error_summary"] = error_summary
    _safe_log_event(event_name, attrs)


def _finalize_runtime_shutdown_state() -> None:
    with _RUNTIME_LOCK:
        _RUNTIME.update(
            {
                "enabled": False,
                "tracer_provider": None,
                "meter_provider": None,
                "tracer": None,
                "meter": None,
                "counter_instruments": {},
                "histogram_instruments": {},
                "gauge_instruments": {},
                "gauge_values": {},
                "Observation": None,
                "shutdown_in_progress": False,
                "shutdown_complete": True,
            }
        )


def initialize_observability(
    config: ObservabilityConfig | None = None,
) -> dict[str, Any]:
    with _RUNTIME_LOCK:
        config = config or load_observability_config()
        _RUNTIME["config"] = config
        _RUNTIME["shutdown_in_progress"] = False
        _RUNTIME["shutdown_complete"] = False
        reset_observability_shutdown_status(config.shutdown_timeout_ms)
        if not config.enabled:
            _RUNTIME["enabled"] = False
            mark_disabled(config)
            return get_observability_status()
        try:
            otel = _load_otel_runtime()
        except Exception as exc:  # pragma: no cover
            _RUNTIME["enabled"] = False
            mark_unavailable(config, error_type=type(exc).__name__)
            _safe_log_event(
                "novali.observability.export_degraded",
                {"reason": "otel_dependencies_missing", "error_type": type(exc).__name__},
            )
            return get_observability_status()

        SpanExporter = otel["SpanExporter"]
        SpanExportResult = otel["SpanExportResult"]

        class TrackingSpanExporter(SpanExporter):
            def __init__(self, inner: Any) -> None:
                super().__init__()
                self._inner = inner

            def export(self, spans: Any) -> Any:
                prior_status = get_observability_status()
                try:
                    result = self._inner.export(spans)
                except Exception as exc:  # pragma: no cover
                    mark_export_failure(type(exc).__name__)
                    record_counter(
                        "novali.observability.export.failure.count",
                        1,
                        {"novali.result": "failure"},
                    )
                    _safe_log_event(
                        "novali.observability.export_degraded",
                        {"pipeline": "traces", "error_type": type(exc).__name__},
                    )
                    return SpanExportResult.FAILURE
                if result == SpanExportResult.SUCCESS:
                    mark_export_success()
                    if prior_status.get("status") == "degraded" or prior_status.get(
                        "last_export_result"
                    ) == "failure":
                        _safe_log_event(
                            "novali.observability.export_recovered",
                            {"pipeline": "traces", "result": "success"},
                        )
                else:
                    mark_export_failure("trace_export_failure")
                    record_counter(
                        "novali.observability.export.failure.count",
                        1,
                        {"novali.result": "failure"},
                    )
                    _safe_log_event(
                        "novali.observability.export_degraded",
                        {"pipeline": "traces", "error_type": "trace_export_failure"},
                    )
                return result

            def shutdown(self) -> None:
                shutdown = getattr(self._inner, "shutdown", None)
                if callable(shutdown):
                    shutdown()

            def force_flush(self, timeout_millis: int = 30000) -> bool:
                flush = getattr(self._inner, "force_flush", None)
                if callable(flush):
                    return bool(flush(timeout_millis=timeout_millis))
                return True

        class TrackingMetricExporter:
            def __init__(self, inner: Any) -> None:
                self._inner = inner

            def __getattr__(self, name: str) -> Any:
                return getattr(self._inner, name)

            def export(self, metrics_data: Any, timeout_millis: float = 10_000, **kwargs: Any) -> Any:
                prior_status = get_observability_status()
                try:
                    result = self._inner.export(
                        metrics_data,
                        timeout_millis=timeout_millis,
                        **kwargs,
                    )
                except Exception as exc:  # pragma: no cover
                    mark_export_failure(type(exc).__name__)
                    record_counter(
                        "novali.observability.export.failure.count",
                        1,
                        {"novali.result": "failure"},
                    )
                    _safe_log_event(
                        "novali.observability.export_degraded",
                        {"pipeline": "metrics", "error_type": type(exc).__name__},
                    )
                    raise
                result_name = str(getattr(result, "name", result) or "").strip().upper()
                if result_name.endswith("SUCCESS") or result_name == "SUCCESS":
                    mark_export_success()
                    if prior_status.get("status") == "degraded" or prior_status.get(
                        "last_export_result"
                    ) == "failure":
                        _safe_log_event(
                            "novali.observability.export_recovered",
                            {"pipeline": "metrics", "result": "success"},
                        )
                else:
                    mark_export_failure("metric_export_failure")
                    record_counter(
                        "novali.observability.export.failure.count",
                        1,
                        {"novali.result": "failure"},
                    )
                    _safe_log_event(
                        "novali.observability.export_degraded",
                        {"pipeline": "metrics", "error_type": "metric_export_failure"},
                    )
                return result

        protocol = str(getattr(config, "otlp_protocol", "http") or "http").strip().lower()
        resource = otel["Resource"].create(dict(config.resource_attributes))
        if protocol == "grpc":
            grpc_span_exporter = otel.get("OTLPGrpcSpanExporter")
            grpc_metric_exporter = otel.get("OTLPGrpcMetricExporter")
            if grpc_span_exporter is None or grpc_metric_exporter is None:
                _RUNTIME["enabled"] = False
                mark_unavailable(config, error_type="grpc_exporter_missing")
                _safe_log_event(
                    "novali.observability.export_degraded",
                    {"reason": "grpc_exporter_missing", "otlp_protocol": "grpc"},
                )
                return get_observability_status()
            span_exporter_factory = grpc_span_exporter
            metric_exporter_factory = grpc_metric_exporter
            span_exporter_kwargs = _supported_kwargs(
                span_exporter_factory,
                endpoint=config.endpoint,
                timeout=config.export_timeout_ms / 1000.0,
                timeout_millis=config.export_timeout_ms,
                insecure=_grpc_endpoint_is_insecure(config.endpoint),
            )
            metric_exporter_kwargs = _supported_kwargs(
                metric_exporter_factory,
                endpoint=config.endpoint,
                timeout=config.export_timeout_ms / 1000.0,
                timeout_millis=config.export_timeout_ms,
                insecure=_grpc_endpoint_is_insecure(config.endpoint),
            )
        else:
            span_exporter_factory = otel["OTLPSpanExporter"]
            metric_exporter_factory = otel["OTLPMetricExporter"]
            span_exporter_kwargs = _supported_kwargs(
                span_exporter_factory,
                endpoint=_trace_endpoint(config.endpoint),
                timeout=config.export_timeout_ms / 1000.0,
                timeout_millis=config.export_timeout_ms,
            )
            metric_exporter_kwargs = _supported_kwargs(
                metric_exporter_factory,
                endpoint=_metric_endpoint(config.endpoint),
                timeout=config.export_timeout_ms / 1000.0,
                timeout_millis=config.export_timeout_ms,
            )

        span_exporter = TrackingSpanExporter(
            span_exporter_factory(
                **span_exporter_kwargs
            )
        )
        tracer_provider = otel["TracerProvider"](resource=resource)
        tracer_provider.add_span_processor(
            otel["BatchSpanProcessor"](span_exporter)
        )

        metric_exporter = TrackingMetricExporter(
            metric_exporter_factory(
                **metric_exporter_kwargs
            )
        )
        metric_reader = otel["PeriodicExportingMetricReader"](
            metric_exporter,
            export_interval_millis=max(1000, min(config.export_timeout_ms, 5000)),
        )
        meter_provider = otel["MeterProvider"](
            resource=resource,
            metric_readers=[metric_reader],
        )

        _RUNTIME.update(
            {
                "enabled": True,
                "tracer_provider": tracer_provider,
                "meter_provider": meter_provider,
                "tracer": tracer_provider.get_tracer(config.service_name),
                "meter": meter_provider.get_meter(config.service_name),
                "counter_instruments": {},
                "histogram_instruments": {},
                "gauge_instruments": {},
                "gauge_values": {},
                "Observation": otel["Observation"],
                "shutdown_in_progress": False,
                "shutdown_complete": False,
            }
        )
        configure_observability_status(config, mode="otlp", status="configured")
        return get_observability_status()


@contextlib.contextmanager
def trace_span(name: str, attributes: Mapping[str, Any] | None = None) -> Any:
    tracer = _RUNTIME.get("tracer")
    normalized = _normalize_attributes(_runtime_attributes(attributes))
    if not _RUNTIME.get("enabled") or tracer is None:
        yield _NoopSpan()
        return
    with tracer.start_as_current_span(name, attributes=normalized) as span:
        yield span


def _get_counter(name: str) -> Any:
    meter = _RUNTIME.get("meter")
    if meter is None:
        return None
    counters = _RUNTIME["counter_instruments"]
    if name not in counters:
        counters[name] = meter.create_counter(name)
    return counters[name]


def _get_histogram(name: str) -> Any:
    meter = _RUNTIME.get("meter")
    if meter is None:
        return None
    histograms = _RUNTIME["histogram_instruments"]
    if name not in histograms:
        histograms[name] = meter.create_histogram(name)
    return histograms[name]


def _ensure_gauge(name: str) -> None:
    meter = _RUNTIME.get("meter")
    Observation = _RUNTIME.get("Observation")
    if meter is None or Observation is None:
        return
    gauges = _RUNTIME["gauge_instruments"]
    if name in gauges:
        return

    def callback(_options: Any = None) -> list[Any]:
        if _RUNTIME.get("shutdown_in_progress"):
            return []
        stored = dict(_RUNTIME.get("gauge_values", {})).get(name)
        if not stored:
            return []
        return [Observation(stored["value"], stored["attributes"])]

    gauges[name] = meter.create_observable_gauge(name, callbacks=[callback])


def record_counter(
    name: str,
    value: int | float = 1,
    attributes: Mapping[str, Any] | None = None,
) -> None:
    counter = _get_counter(name)
    if counter is None:
        return
    counter.add(value, _normalize_attributes(_runtime_attributes(attributes)))


def record_histogram(
    name: str,
    value: int | float,
    attributes: Mapping[str, Any] | None = None,
) -> None:
    histogram = _get_histogram(name)
    if histogram is None:
        return
    histogram.record(value, _normalize_attributes(_runtime_attributes(attributes)))


def record_gauge_or_observable(
    name: str,
    value: int | float,
    attributes: Mapping[str, Any] | None = None,
) -> None:
    _ensure_gauge(name)
    with _RUNTIME_LOCK:
        _RUNTIME["gauge_values"][name] = {
            "value": value,
            "attributes": _normalize_attributes(_runtime_attributes(attributes)),
        }


def record_event(
    name: str,
    attributes: Mapping[str, Any] | None = None,
    severity: str = "info",
) -> None:
    event_attributes = _normalize_attributes(
        _runtime_attributes({"severity": severity, **dict(attributes or {})})
    )
    _safe_log_event(name, event_attributes)
    trace_api = None
    try:
        trace_api = _load_otel_runtime()["trace"]
    except Exception:
        trace_api = None
    if trace_api is None:
        return
    current_span = trace_api.get_current_span()
    if current_span is not None and getattr(current_span, "is_recording", lambda: False)():
        current_span.add_event(name, event_attributes)
        return
    with trace_span("novali.event", {"novali.event.name": name, "novali.result": "success"}) as span:
        span.add_event(name, event_attributes)


def flush_observability(
    timeout_ms: int | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    snapshot = _runtime_snapshot()
    config = snapshot.get("config")
    timeout_ms = _resolve_timeout_ms(
        timeout_ms,
        default=int(getattr(config, "export_timeout_ms", 4000) or 4000),
    )
    tracer_provider = snapshot.get("tracer_provider")
    meter_provider = snapshot.get("meter_provider")
    if tracer_provider is None and meter_provider is None:
        result = (
            "disabled"
            if config is None or not bool(getattr(config, "enabled", False))
            else "unavailable"
        )
        update_observability_shutdown_status(
            flush_result=result,
            timeout_ms=timeout_ms,
        )
        return {
            "ok": True,
            "skipped": True,
            "timeout_ms": timeout_ms,
            "traces_flushed": False,
            "metrics_flushed": False,
            "error_type": None,
            "error_summary_redacted": None,
            "result": result,
            "reason": str(reason or "").strip() or None,
            "traceback_suppressed_for_expected_timeout": False,
            "unexpected_exception_seen": False,
        }

    traces_flushed = True
    metrics_flushed = True
    error_type: str | None = None
    error_summary: str | None = None
    result = "success"
    traceback_suppressed = False
    unexpected_exception_seen = False
    captured_stderr = ""

    with trace_span(
        "novali.observability.export.flush",
        {"novali.result": "success"},
    ):
        try:
            def _operation() -> tuple[dict[str, Any], dict[str, Any]]:
                trace_result = _call_provider_method(
                    tracer_provider,
                    "force_flush",
                    timeout_ms=timeout_ms,
                )
                metric_result = _call_provider_method(
                    meter_provider,
                    "force_flush",
                    timeout_ms=timeout_ms,
                )
                return trace_result, metric_result

            (trace_result, metric_result), captured_stderr = _capture_stderr(_operation)
            traces_flushed = bool(trace_result.get("success", True))
            metrics_flushed = bool(metric_result.get("success", True))
            if _captured_expected_timeout(captured_stderr):
                result = "timeout"
                error_type = (
                    "MetricsTimeoutError"
                    if _captured_timeout_traceback(captured_stderr)
                    else "ExporterTimeoutWarning"
                )
                error_summary = (
                    "OpenTelemetry flush timed out while metrics callbacks or exporters were shutting down."
                )
                traceback_suppressed = _captured_timeout_traceback(captured_stderr)
            elif str(captured_stderr or "").strip():
                result = "degraded"
                error_type = "ExporterWarning"
                error_summary = _truncate_summary(captured_stderr)
            elif not traces_flushed or not metrics_flushed:
                result = "degraded"
                error_type = "force_flush_incomplete"
                error_summary = "One or more telemetry providers did not report a clean flush result."
        except Exception as exc:  # pragma: no cover
            traces_flushed = False
            metrics_flushed = False
            error_type = type(exc).__name__
            error_summary = _exception_summary(exc)
            if _is_expected_timeout_exception(exc):
                result = "timeout"
                traceback_suppressed = True
            else:
                result = "failed"
                unexpected_exception_seen = True

    if result == "success":
        mark_export_success()
    else:
        mark_export_failure(error_type or result)
        record_counter(
            "novali.observability.export.failure.count",
            1,
            {"novali.result": result},
        )
        _safe_log_event(
            "novali.observability.export_degraded",
            {"pipeline": "flush", "error_type": error_type or result, "result": result},
        )

    if result == "timeout":
        _emit_observability_shutdown_event(
            "novali.observability.shutdown.timeout",
            result=result,
            timeout_ms=timeout_ms,
            error_type=error_type,
            error_summary=error_summary,
            phase="flush",
        )
    elif result in {"degraded", "failed"}:
        _emit_observability_shutdown_event(
            "novali.observability.shutdown.failed",
            result=result,
            timeout_ms=timeout_ms,
            error_type=error_type,
            error_summary=error_summary,
            phase="flush",
        )

    update_observability_shutdown_status(
        flush_result=result,
        error_type=error_type,
        error_summary_redacted=error_summary,
        timeout_ms=timeout_ms,
        increment_timeout=result == "timeout",
        traceback_suppressed_for_expected_timeout=traceback_suppressed,
        unexpected_exception_seen=unexpected_exception_seen,
    )
    return {
        "ok": result in {"success", "disabled", "unavailable"},
        "skipped": False,
        "timeout_ms": timeout_ms,
        "traces_flushed": bool(traces_flushed),
        "metrics_flushed": bool(metrics_flushed),
        "error_type": error_type,
        "error_summary_redacted": error_summary,
        "result": result,
        "reason": str(reason or "").strip() or None,
        "traceback_suppressed_for_expected_timeout": traceback_suppressed,
        "unexpected_exception_seen": unexpected_exception_seen,
    }


def mark_live_probe_result(
    *,
    enabled: bool,
    result: str,
    probe_kind: str | None = None,
    probe_id: str | None = None,
    probe_time: str | None = None,
    endpoint_hint: str = "unset",
    collector_mode: str = "unknown",
    no_secrets_captured: bool = True,
) -> None:
    update_live_collector_probe(
        enabled=enabled,
        last_probe_result=result,
        last_probe_kind=probe_kind,
        last_probe_id=probe_id,
        last_probe_time=probe_time,
        endpoint_hint=endpoint_hint,
        collector_mode=collector_mode,
        no_secrets_captured=no_secrets_captured,
    )


def mark_trace_visibility_probe_result(
    *,
    enabled: bool,
    result: str,
    probe_id: str | None = None,
    probe_time: str | None = None,
    endpoint_hint: str = "unset",
    otlp_protocol: str = "unknown",
    service_name: str = "novali-operator-shell",
    service_name_lm_safe: bool = False,
    lm_mapping_attributes_complete: bool = False,
    lm_mapping_missing: list[str] | tuple[str, ...] | None = None,
    no_secrets_captured: bool = True,
) -> None:
    update_trace_visibility_probe(
        enabled=enabled,
        last_probe_result=result,
        last_probe_id=probe_id,
        last_probe_time=probe_time,
        endpoint_hint=endpoint_hint,
        otlp_protocol=otlp_protocol,
        service_name=service_name,
        service_name_lm_safe=service_name_lm_safe,
        lm_mapping_attributes_complete=lm_mapping_attributes_complete,
        lm_mapping_missing=lm_mapping_missing,
        no_secrets_captured=no_secrets_captured,
    )


def mark_portal_confirmation_result(
    *,
    confirmation_state: str,
    proof_id: str | None = None,
    service_name: str | None = None,
    recorded_at: str | None = None,
    protocol: str | None = None,
    endpoint_mode: str | None = None,
) -> None:
    update_portal_confirmation(
        confirmation_state=confirmation_state,
        proof_id=proof_id,
        service_name=service_name,
        recorded_at=recorded_at,
        protocol=protocol,
        endpoint_mode=endpoint_mode,
    )


def mark_dockerized_agent_probe_result(
    *,
    enabled: bool,
    result: str,
    probe_id: str | None = None,
    probe_time: str | None = None,
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
    update_dockerized_agent_probe(
        enabled=enabled,
        last_probe_result=result,
        last_probe_id=probe_id,
        last_probe_time=probe_time,
        endpoint_hint=endpoint_hint,
        endpoint_mode=endpoint_mode,
        network_mode=network_mode,
        otlp_protocol=otlp_protocol,
        service_name=service_name,
        service_name_lm_safe=service_name_lm_safe,
        lm_mapping_attributes_complete=lm_mapping_attributes_complete,
        lm_mapping_missing=lm_mapping_missing,
        container_runtime_proven=container_runtime_proven,
        container_hostname=container_hostname,
        no_secrets_captured=no_secrets_captured,
    )


def shutdown_observability(
    timeout_ms: int | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    snapshot = _runtime_snapshot()
    config = snapshot.get("config")
    timeout_ms = _resolve_timeout_ms(timeout_ms, config=config)
    tracer_provider = snapshot.get("tracer_provider")
    meter_provider = snapshot.get("meter_provider")
    prior_shutdown = get_observability_shutdown_status()
    if tracer_provider is None and meter_provider is None:
        result = (
            str(prior_shutdown.get("last_shutdown_result", "unknown") or "unknown")
            if snapshot.get("shutdown_complete")
            and str(prior_shutdown.get("last_shutdown_result", "unknown") or "unknown")
            != "unknown"
            else (
                "disabled"
                if config is None or not bool(getattr(config, "enabled", False))
                else "unavailable"
            )
        )
        update_observability_shutdown_status(
            shutdown_result=result,
            timeout_ms=timeout_ms,
            shutdown_time=_now_iso(),
        )
        _finalize_runtime_shutdown_state()
        return {
            "ok": result in {"success", "disabled", "unavailable"},
            "result": result,
            "timeout_ms": timeout_ms,
            "error_type": prior_shutdown.get("last_error_type"),
            "error_summary_redacted": prior_shutdown.get("last_error_summary_redacted"),
            "reason": str(reason or "").strip() or None,
            "traceback_suppressed_for_expected_timeout": bool(
                prior_shutdown.get(
                    "traceback_suppressed_for_expected_timeout", False
                )
            ),
            "unexpected_exception_seen": bool(
                prior_shutdown.get("unexpected_exception_seen", False)
            ),
            "already_shutdown": bool(snapshot.get("shutdown_complete", False)),
        }

    with _RUNTIME_LOCK:
        _RUNTIME["shutdown_in_progress"] = True
        _RUNTIME["gauge_values"] = {}

    flush_result = flush_observability(timeout_ms=timeout_ms, reason=reason or "shutdown")
    final_result = str(flush_result.get("result", "success") or "success")
    error_type = flush_result.get("error_type")
    error_summary = flush_result.get("error_summary_redacted")
    traceback_suppressed = bool(
        flush_result.get("traceback_suppressed_for_expected_timeout", False)
    )
    unexpected_exception_seen = bool(flush_result.get("unexpected_exception_seen", False))

    try:
        def _operation() -> tuple[dict[str, Any], dict[str, Any]]:
            metric_result = _call_provider_method(
                meter_provider,
                "shutdown",
                timeout_ms=timeout_ms,
            )
            trace_result = _call_provider_method(
                tracer_provider,
                "shutdown",
                timeout_ms=timeout_ms,
            )
            return trace_result, metric_result

        (trace_result, metric_result), captured_stderr = _capture_stderr(_operation)
        shutdown_result = "success"
        shutdown_error_type: str | None = None
        shutdown_error_summary: str | None = None
        if _captured_expected_timeout(captured_stderr):
            shutdown_result = "timeout"
            shutdown_error_type = (
                "MetricsTimeoutError"
                if _captured_timeout_traceback(captured_stderr)
                else "ExporterTimeoutWarning"
            )
            shutdown_error_summary = (
                "OpenTelemetry shutdown timed out while exporters or metrics callbacks were draining."
            )
            traceback_suppressed = traceback_suppressed or _captured_timeout_traceback(
                captured_stderr
            )
        elif str(captured_stderr or "").strip():
            shutdown_result = "degraded"
            shutdown_error_type = "ExporterWarning"
            shutdown_error_summary = _truncate_summary(captured_stderr)
        elif not bool(trace_result.get("success", True)) or not bool(
            metric_result.get("success", True)
        ):
            shutdown_result = "degraded"
            shutdown_error_type = "shutdown_incomplete"
            shutdown_error_summary = (
                "One or more telemetry providers did not report a clean shutdown result."
            )
        final_result = _max_result(final_result, shutdown_result)
        if _result_rank(shutdown_result) >= _result_rank(
            str(flush_result.get("result", "success") or "success")
        ):
            error_type = shutdown_error_type or error_type
            error_summary = shutdown_error_summary or error_summary
    except Exception as exc:  # pragma: no cover
        if _is_expected_timeout_exception(exc):
            final_result = _max_result(final_result, "timeout")
            error_type = type(exc).__name__
            error_summary = _exception_summary(exc)
            traceback_suppressed = True
        else:
            final_result = "failed"
            error_type = type(exc).__name__
            error_summary = _exception_summary(exc)
            unexpected_exception_seen = True
    finally:
        _finalize_runtime_shutdown_state()

    if final_result == "timeout":
        _emit_observability_shutdown_event(
            "novali.observability.shutdown.timeout",
            result=final_result,
            timeout_ms=timeout_ms,
            error_type=error_type,
            error_summary=error_summary,
            phase="shutdown",
        )
    elif final_result in {"degraded", "failed"}:
        _emit_observability_shutdown_event(
            "novali.observability.shutdown.failed",
            result=final_result,
            timeout_ms=timeout_ms,
            error_type=error_type,
            error_summary=error_summary,
            phase="shutdown",
        )
    else:
        _emit_observability_shutdown_event(
            "novali.observability.shutdown.completed",
            result=final_result,
            timeout_ms=timeout_ms,
            phase="shutdown",
        )

    update_observability_shutdown_status(
        shutdown_result=final_result,
        error_type=error_type,
        error_summary_redacted=error_summary,
        timeout_ms=timeout_ms,
        increment_timeout=final_result == "timeout" and str(
            flush_result.get("result", "")
        )
        != "timeout",
        traceback_suppressed_for_expected_timeout=traceback_suppressed,
        unexpected_exception_seen=unexpected_exception_seen,
        shutdown_time=_now_iso(),
    )
    return {
        "ok": final_result in {"success", "disabled", "unavailable"},
        "result": final_result,
        "timeout_ms": timeout_ms,
        "error_type": error_type,
        "error_summary_redacted": error_summary,
        "reason": str(reason or "").strip() or None,
        "traceback_suppressed_for_expected_timeout": traceback_suppressed,
        "unexpected_exception_seen": unexpected_exception_seen,
        "already_shutdown": False,
        "flush_result": flush_result,
    }
