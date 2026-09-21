from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from .config import collector_mode_for, endpoint_hint_for

RC83_ARTIFACT_SUBPATH = Path("artifacts/operator_proof/rc83")
LIVE_COLLECTOR_SUMMARY_NAME = "logicmonitor_live_collector_smoke_summary.json"


def _truthy(raw_value: str | bool | None) -> bool:
    return str(raw_value or "").strip().lower() in {"1", "true", "yes", "on"}


def resolve_rc83_artifact_root(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    env = env or os.environ
    configured = str(env.get("RC83_PROOF_ARTIFACT_ROOT") or "").strip()
    base_root = Path(package_root).resolve() if package_root is not None else None
    if configured:
        configured_path = Path(configured)
        if configured_path.is_absolute():
            return configured_path.resolve()
        if base_root is not None:
            return (base_root / configured_path).resolve()
        return configured_path.resolve()
    if base_root is not None:
        return (base_root / RC83_ARTIFACT_SUBPATH).resolve()
    return RC83_ARTIFACT_SUBPATH.resolve()


def load_json_file(path: str | Path) -> dict[str, Any]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def write_summary_artifacts(
    *,
    artifact_root: str | Path,
    json_name: str,
    markdown_name: str,
    summary: Mapping[str, Any],
    markdown: str,
) -> tuple[Path, Path]:
    target_root = Path(artifact_root)
    target_root.mkdir(parents=True, exist_ok=True)
    json_path = target_root / json_name
    markdown_path = target_root / markdown_name
    json_path.write_text(
        json.dumps(dict(summary), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(str(markdown).rstrip() + "\n", encoding="utf-8")
    return json_path, markdown_path


def scan_forbidden_strings(
    payloads: Sequence[str | bytes],
    forbidden_strings: Sequence[str],
) -> list[str]:
    normalized_payloads = [
        payload.decode("utf-8", errors="ignore") if isinstance(payload, bytes) else str(payload)
        for payload in payloads
    ]
    hits: list[str] = []
    for forbidden in forbidden_strings:
        if any(forbidden and forbidden in payload for payload in normalized_payloads):
            hits.append(forbidden)
    return sorted(set(hits))


def signal_signature(payload: Mapping[str, Any]) -> str:
    normalized = json.dumps(dict(payload), sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_runtime_signal_snapshot(
    observability_snapshot: Mapping[str, Any] | None,
) -> dict[str, Any]:
    snapshot = dict(observability_snapshot or {})
    review_queue = dict(snapshot.get("operator_review_queue", {}))
    queue_items = list(review_queue.get("queue_items", []) or [])
    blocking_review_count = int(
        snapshot.get("operator_blocking_review_count", review_queue.get("blocking_review_count", 0))
        or 0
    )
    pending_review_count = int(
        snapshot.get("operator_pending_review_count", review_queue.get("pending_review_count", len(queue_items)))
        or 0
    )
    total_queue_items = max(int(review_queue.get("total_review_item_count", 0) or 0), len(queue_items), pending_review_count)
    deferred_items = list(snapshot.get("deferred_items", []) or [])
    total_deferred_items = len(deferred_items)
    if total_deferred_items >= 3 or (total_deferred_items > 0 and blocking_review_count > 0):
        pressure_band = "high"
    elif total_deferred_items > 0:
        pressure_band = "rising"
    else:
        pressure_band = "low"
    review_status = str(snapshot.get("review_status", "")).strip()
    if not review_status:
        review_status = "intervention_required" if pending_review_count > 0 else "clear"
    return {
        "queue_items": total_queue_items,
        "pending_review_count": pending_review_count,
        "blocking_review_count": blocking_review_count,
        "deferred_items": total_deferred_items,
        "pressure_band": pressure_band,
        "review_status": review_status,
        "deferred_pressure_supported": True,
        "deferred_pressure_detail": (
            "Shell-level deferred pressure proxy is derived from current deferred backlog count only."
        ),
    }


def build_deferred_response_outcome(
    current_signal: Mapping[str, Any] | None,
    previous_signal: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if not current_signal or not previous_signal:
        return None
    current = dict(current_signal)
    previous = dict(previous_signal)
    ranking = {"low": 0, "rising": 1, "high": 2}
    current_band = str(current.get("pressure_band", "low"))
    previous_band = str(previous.get("pressure_band", "low"))
    current_deferred = int(current.get("deferred_items", 0) or 0)
    previous_deferred = int(previous.get("deferred_items", 0) or 0)
    outcome_key = "stable"
    detail = "Shell-level deferred pressure proxy is unchanged."
    if current_deferred < previous_deferred or ranking.get(current_band, 0) < ranking.get(previous_band, 0):
        outcome_key = "improved"
        detail = (
            f"Shell-level deferred pressure proxy improved from {previous_deferred} deferred item(s) "
            f"to {current_deferred}."
        )
    elif current_deferred > previous_deferred or ranking.get(current_band, 0) > ranking.get(previous_band, 0):
        outcome_key = "worsened"
        detail = (
            f"Shell-level deferred pressure proxy worsened from {previous_deferred} deferred item(s) "
            f"to {current_deferred}."
        )
    return {
        "key": outcome_key,
        "label": {
            "improved": "Deferred pressure improved",
            "worsened": "Deferred pressure worsened",
            "stable": "Deferred pressure stable",
        }.get(outcome_key, "Deferred pressure stable"),
        "detail": detail,
    }


def load_live_probe_status(
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = env or os.environ
    selected_endpoint = str(
        env.get("RC83_LMOTEL_ENDPOINT") or env.get("OTEL_EXPORTER_OTLP_ENDPOINT") or ""
    ).strip()
    summary_path = resolve_rc83_artifact_root(package_root, env=env) / LIVE_COLLECTOR_SUMMARY_NAME
    selected_result = "unknown" if _truthy(env.get("RC83_LIVE_COLLECTOR_PROOF")) else "skipped"
    payload = {
        "enabled": _truthy(env.get("RC83_LIVE_COLLECTOR_PROOF")),
        "last_probe_result": selected_result,
        "last_probe_kind": None,
        "last_probe_id": None,
        "last_probe_time": None,
        "endpoint_hint": endpoint_hint_for(selected_endpoint),
        "collector_mode": collector_mode_for(selected_endpoint),
        "no_secrets_captured": True,
    }
    summary = load_json_file(summary_path)
    if not summary:
        return payload
    summary_endpoint = str(summary.get("selected_endpoint") or selected_endpoint).strip()
    payload.update(
        {
            "enabled": bool(summary.get("opt_in_enabled", payload["enabled"])),
            "last_probe_result": str(summary.get("result", payload["last_probe_result"]) or payload["last_probe_result"]),
            "last_probe_kind": str(summary.get("proof_kind", "")).strip() or None,
            "last_probe_id": str(summary.get("proof_id", "")).strip() or None,
            "last_probe_time": str(summary.get("generated_at", "")).strip() or None,
            "endpoint_hint": endpoint_hint_for(summary_endpoint),
            "collector_mode": str(summary.get("collector_mode_status", "")).strip()
            or collector_mode_for(summary_endpoint),
            "no_secrets_captured": bool(summary.get("no_secrets_captured", True)),
            "artifact_path": str(summary_path),
        }
    )
    return payload


def merge_live_probe_status(
    observability_status: Mapping[str, Any],
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    merged = dict(observability_status)
    merged["live_collector_probe"] = load_live_probe_status(
        package_root=package_root,
        env=env,
    )
    return merged


def build_alert_candidates(
    observability_status: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None = None,
) -> list[dict[str, str]]:
    status = dict(observability_status or {})
    signals = dict(runtime_signals or {})
    live_probe = dict(status.get("live_collector_probe", {}))
    shutdown_state = dict(status.get("observability_shutdown", {}))
    candidates: list[dict[str, str]] = []

    if str(status.get("status", "")).strip() in {"degraded", "unavailable"} or str(
        status.get("last_export_result", "")
    ).strip() == "failure":
        candidates.append(
            {
                "alert_key": "telemetry_export_failure",
                "label": "Telemetry export degraded",
                "severity": "warning",
                "detail": "Exporter degradation is visible, but controller behavior remains unchanged.",
                "state": "implemented",
            }
        )

    shutdown_result = str(
        shutdown_state.get("last_shutdown_result", "unknown") or "unknown"
    ).strip()
    timeout_count = int(shutdown_state.get("last_timeout_count", 0) or 0)
    if shutdown_result == "timeout":
        candidates.append(
            {
                "alert_key": "telemetry_shutdown_timeout",
                "label": "Telemetry shutdown timed out",
                "severity": "high" if timeout_count > 1 else "warning",
                "detail": "The latest observability shutdown path recorded a bounded timeout; controller authority is unchanged.",
                "state": "implemented",
            }
        )
    elif shutdown_result == "unavailable":
        candidates.append(
            {
                "alert_key": "telemetry_export_unavailable",
                "label": "Telemetry exporter unavailable",
                "severity": "warning",
                "detail": "The observability exporter path is unavailable, but NOVALI remains in a safe evidence-only posture.",
                "state": "implemented",
            }
        )
    elif bool(shutdown_state.get("unexpected_exception_seen", False)):
        candidates.append(
            {
                "alert_key": "telemetry_unexpected_shutdown_exception",
                "label": "Telemetry shutdown hit an unexpected exception",
                "severity": "high",
                "detail": "The latest observability shutdown path captured an unexpected exception and preserved bounded degraded evidence.",
                "state": "implemented",
            }
        )

    if str(live_probe.get("last_probe_result", "")).strip() == "failure":
        candidates.append(
            {
                "alert_key": "collector_down",
                "label": "Live collector proof failed",
                "severity": "warning",
                "detail": "The latest live collector proof did not flush cleanly to the configured collector path.",
                "state": "implemented",
            }
        )

    if str(status.get("last_visibility_probe_result", "")).strip() == "failure":
        candidates.append(
            {
                "alert_key": "no_telemetry_seen",
                "label": "Trace visibility probe failed",
                "severity": "warning",
                "detail": "The latest trace-visibility proof did not reach a clean app-to-collector exporting state.",
                "state": "implemented",
            }
        )

    if str(status.get("dockerized_agent_probe_result", "")).strip() == "failure":
        candidates.append(
            {
                "alert_key": "no_telemetry_seen",
                "label": "Dockerized agent trace probe failed",
                "severity": "warning",
                "detail": "The latest Dockerized NOVALI runtime proof did not reach a clean app-to-collector exporting state.",
                "state": "implemented",
            }
        )

    if live_probe.get("no_secrets_captured") is False or dict(
        status.get("dockerized_agent_probe", {})
    ).get("no_secrets_captured") is False:
        candidates.append(
            {
                "alert_key": "redaction_failure",
                "label": "Redaction proof failed",
                "severity": "critical",
                "detail": "A proof artifact indicates redaction failed, so export evidence should not be trusted.",
                "state": "implemented",
            }
        )

    if str(signals.get("pressure_band", "")).strip() == "high":
        candidates.append(
            {
                "alert_key": "deferred_pressure_high",
                "label": "Deferred pressure high",
                "severity": "warning",
                "detail": "Shell-level deferred backlog is elevated and should stay review-visible.",
                "state": "implemented",
            }
        )
    elif str(dict(signals.get("response_outcome", {})).get("key", "")).strip() == "worsened":
        candidates.append(
            {
                "alert_key": "deferred_pressure_worsening",
                "label": "Deferred pressure worsening",
                "severity": "warning",
                "detail": "The shell-level deferred pressure proxy worsened since the last manager check sample.",
                "state": "implemented",
            }
        )

    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for candidate in candidates:
        alert_key = str(candidate.get("alert_key", "")).strip()
        if not alert_key or alert_key in seen:
            continue
        seen.add(alert_key)
        deduped.append(candidate)
    return deduped
