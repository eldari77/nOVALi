from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Mapping

from .telemetry import (
    record_counter,
    record_event,
    record_gauge_or_observable,
    record_histogram,
    trace_span,
)

ACTIVE_LONG_RUN_STATES = {"active", "checkpointed", "resuming", "running"}


def _text(value: Any, fallback: str = "") -> str:
    normalized = str(value or "").strip()
    return normalized or fallback


def _int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return fallback


def _float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return fallback


def _bool(value: Any) -> bool:
    return bool(value)


def short_ref(value: Any, *, prefix: str = "", length: int = 12) -> str:
    normalized = _text(value)
    if not normalized:
        return ""
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[: max(6, int(length or 12))]
    clean_prefix = _text(prefix)
    return f"{clean_prefix}-{digest}" if clean_prefix else digest


def _parse_datetime(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _checkpoint_age_seconds(long_run: Mapping[str, Any]) -> float | None:
    checkpoint_at = (
        _parse_datetime(long_run.get("latest_checkpoint_at"))
        or _parse_datetime(long_run.get("last_checkpoint_at"))
        or _parse_datetime(long_run.get("last_heartbeat_at"))
    )
    if checkpoint_at is None:
        return None
    age = datetime.now(timezone.utc) - checkpoint_at
    return max(0.0, round(age.total_seconds(), 3))


def _state_family(
    long_run: Mapping[str, Any],
    operator_guidance: Mapping[str, Any] | None,
) -> str:
    guidance = dict(operator_guidance or {})
    family = _text(guidance.get("state_family"))
    if family:
        return family
    if _bool(long_run.get("stale_recovery_available")):
        return "stale_recovery"
    lifecycle_state = _text(long_run.get("lifecycle_state"), "unknown")
    if lifecycle_state in ACTIVE_LONG_RUN_STATES:
        return "running"
    if lifecycle_state in {"not_started", "paused_by_operator", "halted", "failed"}:
        return lifecycle_state
    return "other"


def _review_status(
    long_run: Mapping[str, Any],
    operator_guidance: Mapping[str, Any] | None,
) -> str:
    guidance = dict(operator_guidance or {})
    review_status = _text(guidance.get("review_status"))
    if review_status:
        return review_status
    if _bool(long_run.get("intervention_required")):
        return "intervention_required"
    return "clear"


def long_run_metric_attributes(
    long_run: Mapping[str, Any],
    operator_guidance: Mapping[str, Any] | None = None,
    *,
    result: str = "success",
) -> dict[str, Any]:
    return {
        "novali.result": _text(result, "success"),
        "novali.lifecycle_state": _text(long_run.get("lifecycle_state"), "unknown"),
        "novali.lease_state": _text(long_run.get("lease_state"), "unknown"),
        "novali.watchdog_state": _text(long_run.get("watchdog_state"), "unknown"),
        "novali.state_family": _state_family(long_run, operator_guidance),
        "novali.review_status": _review_status(long_run, operator_guidance),
    }


def long_run_span_attributes(
    long_run: Mapping[str, Any],
    operator_guidance: Mapping[str, Any] | None = None,
    *,
    result: str = "success",
) -> dict[str, Any]:
    checkpoint_id = (
        _text(long_run.get("latest_checkpoint_id"))
        or _text(long_run.get("resume_from_checkpoint_id"))
        or _text(dict(long_run.get("latest_checkpoint", {}) or {}).get("checkpoint_id"))
    )
    attrs = long_run_metric_attributes(long_run, operator_guidance, result=result)
    attrs.update(
        {
            "novali.session_ref": short_ref(long_run.get("session_id"), prefix="session"),
            "novali.workspace_ref": short_ref(long_run.get("workspace_id"), prefix="workspace"),
            "novali.checkpoint_ref": short_ref(checkpoint_id, prefix="checkpoint"),
            "novali.checkpoint_count": _int(long_run.get("checkpoint_count")),
            "novali.current_cycle": _int(long_run.get("current_cycle")),
            "novali.active_process_present": _int(long_run.get("active_process_id")) > 0,
            "novali.stale_recovery_available": _bool(
                long_run.get("stale_recovery_available")
            ),
        }
    )
    return {key: value for key, value in attrs.items() if value not in {"", None}}


def record_long_run_timeline(
    *,
    long_run: Mapping[str, Any],
    operator_guidance: Mapping[str, Any] | None = None,
    previous_stale_recovery_available: bool = False,
) -> dict[str, Any]:
    payload = dict(long_run or {})
    guidance = dict(operator_guidance or {})
    metric_attrs = long_run_metric_attributes(payload, guidance)
    span_attrs = long_run_span_attributes(payload, guidance)
    stale_available = _bool(payload.get("stale_recovery_available"))
    active = (
        _text(payload.get("lifecycle_state")) in ACTIVE_LONG_RUN_STATES
        or _state_family(payload, guidance) == "running"
    ) and not stale_available
    checkpoint_age_seconds = _checkpoint_age_seconds(payload)

    with trace_span("novali.long_run.state", span_attrs):
        with trace_span("novali.progress.heartbeat", span_attrs):
            record_counter("novali.progress.heartbeat.count", 1, metric_attrs)
            record_event("novali.progress.heartbeat", span_attrs)

        record_gauge_or_observable(
            "novali.long_run.active",
            1 if active else 0,
            metric_attrs,
        )
        record_gauge_or_observable(
            "novali.stale_recovery.available",
            1 if stale_available else 0,
            metric_attrs,
        )
        record_gauge_or_observable(
            "novali.checkpoint.count",
            _int(payload.get("checkpoint_count")),
            metric_attrs,
        )
        if checkpoint_age_seconds is not None:
            record_gauge_or_observable(
                "novali.checkpoint.age_seconds",
                checkpoint_age_seconds,
                metric_attrs,
            )

        if stale_available:
            record_counter("novali.stale_recovery.available.count", 1, metric_attrs)
            record_event(
                "novali.stale_recovery.available",
                span_attrs,
                severity="warning",
            )
        elif previous_stale_recovery_available:
            record_counter("novali.stale_recovery.cleared.count", 1, metric_attrs)
            record_event("novali.stale_recovery.cleared", span_attrs)

    return {
        "active": active,
        "stale_recovery_available": stale_available,
        "checkpoint_age_seconds": checkpoint_age_seconds,
        "state_family": _state_family(payload, guidance),
    }


def llm_span_attributes(
    *,
    provider: str,
    model: str,
    mode: str,
    status: str,
    context_bundle_id: str = "",
    retry_count: int = 0,
) -> dict[str, Any]:
    return {
        "novali.result": _text(status, "unknown"),
        "novali.llm.provider": _text(provider, "unknown"),
        "novali.llm.model": _text(model, "unknown"),
        "novali.llm.mode": _text(mode, "unknown"),
        "novali.llm.context_ref": short_ref(context_bundle_id, prefix="llmctx"),
        "novali.retry_count": _int(retry_count),
    }


def llm_metric_attributes(
    *,
    provider: str,
    model: str,
    mode: str,
    status: str,
) -> dict[str, Any]:
    return {
        "novali.result": _text(status, "unknown"),
        "novali.llm.provider": _text(provider, "unknown"),
        "novali.llm.model": _text(model, "unknown"),
        "novali.llm.mode": _text(mode, "unknown"),
    }


def record_tool_execution(
    *,
    tool_name: str,
    result: str,
    duration_ms: float | None = None,
    category: str = "operator_shell",
) -> None:
    attrs = {
        "novali.result": _text(result, "unknown"),
        "novali.tool.name": _text(tool_name, "unknown"),
        "novali.tool.category": _text(category, "operator_shell"),
    }
    with trace_span("novali.tool.execution", attrs):
        record_counter("novali.tool.execution.count", 1, attrs)
        if duration_ms is not None:
            record_histogram("novali.tool.execution.duration_ms", float(duration_ms), attrs)
        record_event("novali.tool.execution", attrs)


def _safe_label(value: Any, *, fallback: str = "unknown", limit: int = 80) -> str:
    normalized = _text(value, fallback).lower()
    allowed = []
    for char in normalized:
        if char.isalnum() or char == "_":
            allowed.append(char)
        elif char in {" ", "-", "/", ".", ":"}:
            allowed.append("_")
    label = "_".join("".join(allowed).split("_"))
    if not label:
        label = fallback
    return label[: max(12, int(limit or 80))]


def _progress_band(value: Any) -> str:
    progress = _float(value)
    if progress <= 0:
        return "none"
    if progress < 0.34:
        return "low"
    if progress < 0.67:
        return "medium"
    if progress < 1:
        return "high"
    return "complete"


def _score_band(value: Any) -> str:
    score = _float(value)
    if score <= 0:
        return "none"
    if score < 0.4:
        return "low"
    if score < 0.7:
        return "medium"
    return "high"


def _weak_area_label(weak_areas: Any) -> str:
    if isinstance(weak_areas, str):
        items = [weak_areas]
    else:
        items = list(weak_areas or [])
    lowered = " ".join(str(item or "").lower() for item in items)
    if "missing promotion packet" in lowered:
        return "missing_promotion_packet"
    if "repeated signal signature" in lowered:
        return "repeated_signal_signature"
    if "artifact churn" in lowered:
        return "artifact_churn"
    if "directive" in lowered:
        return "directive_progress"
    if "capability" in lowered:
        return "capability_growth"
    if not lowered.strip():
        return "none"
    return "other"


def _skip_reason_label(reason: Any) -> str:
    lowered = _text(reason).lower()
    if "not enabled" in lowered or "not allowed" in lowered:
        return "not_enabled"
    if "already executed" in lowered:
        return "already_executed"
    if "board" in lowered or "approve" in lowered:
        return "board_not_approved"
    if "budget" in lowered:
        return "budget_boundary"
    if "readiness" in lowered or "launchable" in lowered:
        return "governed_readiness_blocked"
    if "emergency" in lowered or "not active" in lowered:
        return "inactive_or_emergency_stop"
    if "disabled" in lowered:
        return "policy_disabled"
    if "malformed" in lowered:
        return "malformed_policy"
    if "wall_clock" in lowered or "stop_after" in lowered:
        return "wall_clock_stop"
    if "no operation" in lowered or "no operation_id" in lowered:
        return "missing_operation_id"
    if "failure limit" in lowered:
        return "failure_limit"
    return "unknown" if not lowered else "other"


def _operation_metric_attributes(
    *,
    operation: Mapping[str, Any] | None = None,
    action: str = "",
    result: str = "",
    skip_reason: str = "",
) -> dict[str, Any]:
    payload = dict(operation or {})
    attrs = {
        "novali.action": _safe_label(action or payload.get("action"), fallback="unknown"),
        "novali.result": _safe_label(result, fallback="unknown"),
    }
    if skip_reason:
        attrs["novali.skip_reason"] = _skip_reason_label(skip_reason)
    target = _safe_label(payload.get("target"), fallback="")
    if target:
        attrs["novali.target"] = target
    return {key: value for key, value in attrs.items() if value not in {"", None}}


def autonomy_operation_span_attributes(
    operation: Mapping[str, Any] | None,
    *,
    result: str,
    skip_reason: str = "",
    decision: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(operation or {})
    decision_payload = dict(decision or {})
    attrs = _operation_metric_attributes(
        operation=payload,
        result=result,
        skip_reason=skip_reason,
    )
    attrs.update(
        {
            "novali.operation_ref": short_ref(payload.get("operation_id"), prefix="op"),
            "novali.decision_ref": short_ref(decision_payload.get("decision_id"), prefix="board"),
            "novali.goal_ref": short_ref(payload.get("goal_id"), prefix="goal"),
            "novali.capability_ref": short_ref(
                payload.get("capability_gap_id") or payload.get("capability_kind"),
                prefix="cap",
            ),
        }
    )
    return {key: value for key, value in attrs.items() if value not in {"", None}}


def _record_autonomy_operation(
    *,
    span_name: str,
    counter_name: str,
    operation: Mapping[str, Any] | None,
    result: str,
    skip_reason: str = "",
    decision: Mapping[str, Any] | None = None,
    duration_ms: float | None = None,
) -> dict[str, Any]:
    metric_attrs = _operation_metric_attributes(
        operation=operation,
        result=result,
        skip_reason=skip_reason,
    )
    span_attrs = autonomy_operation_span_attributes(
        operation,
        result=result,
        skip_reason=skip_reason,
        decision=decision,
    )
    with trace_span(span_name, span_attrs):
        record_counter(counter_name, 1, metric_attrs)
        if duration_ms is not None:
            record_histogram(
                "novali.autonomy.operation.duration_ms",
                float(duration_ms),
                metric_attrs,
            )
        record_event(span_name, span_attrs)
    return span_attrs


def record_autonomy_operation_proposed(
    operation: Mapping[str, Any] | None,
    *,
    decision: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return _record_autonomy_operation(
        span_name="novali.autonomy.operation.proposed",
        counter_name="novali.autonomy.operation.proposed.count",
        operation=operation,
        decision=decision,
        result="proposed",
    )


def record_autonomy_operation_executed(
    operation: Mapping[str, Any] | None,
    *,
    result: str = "executed",
    decision: Mapping[str, Any] | None = None,
    duration_ms: float | None = None,
) -> dict[str, Any]:
    return _record_autonomy_operation(
        span_name="novali.autonomy.operation.executed",
        counter_name="novali.autonomy.operation.executed.count",
        operation=operation,
        decision=decision,
        result=result,
        duration_ms=duration_ms,
    )


def record_autonomy_operation_skipped(
    operation: Mapping[str, Any] | None = None,
    *,
    action: str = "",
    skip_reason: str,
) -> dict[str, Any]:
    return _record_autonomy_operation(
        span_name="novali.autonomy.operation.skipped",
        counter_name="novali.autonomy.operation.skipped.count",
        operation=operation or {"action": action},
        result="skipped",
        skip_reason=skip_reason,
    )


def record_autonomy_operation_auto_approval(
    *,
    operation: Mapping[str, Any] | None = None,
    tier: str,
    result: str,
    reason: str = "",
) -> dict[str, Any]:
    payload = dict(operation or {})
    attrs = autonomy_operation_span_attributes(
        payload,
        result=result,
        skip_reason=reason if result not in {"approved", "executed"} else "",
    )
    attrs["novali.autonomy_tier"] = _safe_label(tier, fallback="unknown")
    attrs["novali.approval_result"] = _safe_label(result, fallback="unknown")
    metric_attrs = {
        key: value
        for key, value in attrs.items()
        if key
        in {
            "novali.result",
            "novali.action",
            "novali.skip_reason",
            "novali.autonomy_tier",
            "novali.approval_result",
        }
    }
    with trace_span("novali.autonomy.operation.auto_approval", attrs):
        record_counter("novali.autonomy.operation.auto_approval.count", 1, metric_attrs)
        record_event("novali.autonomy.operation.auto_approval", attrs)
    return attrs


def record_high_impact_validation(
    validation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload = dict(validation or {})
    operation = {
        "operation_id": payload.get("operation_id", ""),
        "action": payload.get("action", ""),
    }
    result = _safe_label(payload.get("result", ""), fallback="unknown")
    blocker = ""
    blockers = list(payload.get("blockers", []) or [])
    if blockers:
        blocker = _safe_label(blockers[0], fallback="blocked")
    attrs = autonomy_operation_span_attributes(
        operation,
        result=result,
        skip_reason=blocker if result != "approved" else "",
    )
    attrs.update(
        {
            "novali.autonomy_tier": "high_impact",
            "novali.validation_result": result,
            "novali.validation_check_count": _int(payload.get("check_count", 0)),
            "novali.blocker": blocker,
        }
    )
    metric_attrs = {
        key: value
        for key, value in attrs.items()
        if key
        in {
            "novali.result",
            "novali.action",
            "novali.skip_reason",
            "novali.autonomy_tier",
            "novali.validation_result",
            "novali.blocker",
        }
    }
    with trace_span("novali.autonomy.high_impact.validation", attrs):
        record_counter("novali.autonomy.high_impact.validation.count", 1, metric_attrs)
        record_event("novali.autonomy.high_impact.validation", attrs)
    return attrs


def record_continuous_autonomy_handoff(
    *,
    operation: Mapping[str, Any] | None = None,
    result: str,
    checkpoint_count: int = 0,
    handoff_state: str = "",
) -> dict[str, Any]:
    payload = dict(operation or {})
    attrs = autonomy_operation_span_attributes(payload, result=result)
    attrs.update(
        {
            "novali.handoff_state": _safe_label(handoff_state, fallback="unknown"),
            "novali.checkpoint_count": _int(checkpoint_count),
        }
    )
    metric_attrs = {
        key: value
        for key, value in attrs.items()
        if key
        in {
            "novali.result",
            "novali.action",
            "novali.handoff_state",
        }
    }
    with trace_span("novali.continuous_autonomy.handoff", attrs):
        record_counter("novali.continuous_autonomy.handoff.count", 1, metric_attrs)
        record_gauge_or_observable(
            "novali.checkpoint.count",
            _int(checkpoint_count),
            metric_attrs,
        )
        record_event("novali.continuous_autonomy.handoff", attrs)
    return attrs


def meaningful_work_span_attributes(evaluation: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(evaluation or {})
    score = _float(payload.get("total_score"))
    directive_progress = _float(payload.get("directive_progress"))
    attrs = {
        "novali.result": "success",
        "novali.action": _safe_label(payload.get("action"), fallback="unknown"),
        "novali.meaningful_delta": _bool(payload.get("meaningful_delta")),
        "novali.meaningful_score_band": _score_band(score),
        "novali.directive_progress_band": _progress_band(directive_progress),
        "novali.weak_area": _weak_area_label(payload.get("weak_areas")),
        "novali.meaningful_work_ref": short_ref(payload.get("meaningful_work_id"), prefix="meaningful"),
        "novali.operation_ref": short_ref(payload.get("operation_id"), prefix="op"),
    }
    deliverable_kind = _safe_label(payload.get("directive_track_deliverable_kind"), fallback="")
    if deliverable_kind:
        attrs["novali.deliverable_kind"] = deliverable_kind
    directive_focus = _safe_label(
        payload.get("directive_track_delta_focus_id"),
        fallback="",
    )
    if directive_focus:
        attrs["novali.directive_focus"] = directive_focus
    directive_layer = _safe_label(
        payload.get("directive_track_delta_layer_id"),
        fallback="",
    )
    if directive_layer:
        attrs["novali.directive_layer"] = directive_layer
    focus_rotation_state = _safe_label(
        payload.get("directive_track_focus_rotation_state"),
        fallback="",
    )
    if focus_rotation_state:
        attrs["novali.focus_rotation_state"] = focus_rotation_state
    layer_rotation_state = _safe_label(
        payload.get("directive_track_layer_rotation_state"),
        fallback="",
    )
    if layer_rotation_state:
        attrs["novali.layer_rotation_state"] = layer_rotation_state
    delta_materiality = (
        "material"
        if bool(payload.get("directive_track_delta_materially_new", False))
        else "repeated"
        if payload.get("directive_track_artifact_ref")
        else ""
    )
    if delta_materiality:
        attrs["novali.directive.delta_materiality"] = delta_materiality
    rejection_reason = _safe_label(
        payload.get("directive_track_delta_rejection_reason"),
        fallback="",
    )
    if rejection_reason:
        attrs["novali.delta_rejection_reason"] = rejection_reason
    dossier_materiality = (
        "material"
        if bool(payload.get("directive_dossier_materially_new", False))
        else "repeated"
        if payload.get("latest_directive_dossier_ref")
        or payload.get("directive_dossier_artifact_ref")
        else ""
    )
    if dossier_materiality:
        attrs["novali.directive.dossier.materiality"] = dossier_materiality
    source_coverage = _safe_label(
        payload.get("directive_source_coverage_state"),
        fallback="",
    )
    if source_coverage:
        attrs["novali.directive.source_coverage"] = source_coverage
    librarian_decision = _safe_label(
        payload.get("librarian_gap_reuse_decision"),
        fallback="",
    )
    if librarian_decision:
        attrs["novali.librarian_gap_reuse_decision"] = librarian_decision
    trusted_validation = _safe_label(
        payload.get("trusted_source_retrieval_validation_state"),
        fallback="",
    )
    if trusted_validation:
        attrs["novali.trusted_source.validation_state"] = trusted_validation
    memory_band = _safe_label(payload.get("memory_pressure_band"), fallback="")
    if memory_band:
        attrs["novali.memory_pressure_band"] = memory_band
    return {key: value for key, value in attrs.items() if value not in {"", None}}


def record_meaningful_work_evaluation(evaluation: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(evaluation or {})
    attrs = meaningful_work_span_attributes(payload)
    metric_attrs = {
        key: value
        for key, value in attrs.items()
        if key
        in {
            "novali.result",
            "novali.action",
            "novali.meaningful_delta",
            "novali.meaningful_score_band",
            "novali.directive_progress_band",
            "novali.weak_area",
            "novali.memory_pressure_band",
            "novali.deliverable_kind",
            "novali.directive_focus",
            "novali.directive_layer",
            "novali.focus_rotation_state",
            "novali.layer_rotation_state",
            "novali.directive.delta_materiality",
            "novali.directive.dossier.materiality",
            "novali.directive.source_coverage",
            "novali.librarian_gap_reuse_decision",
            "novali.trusted_source.validation_state",
            "novali.delta_rejection_reason",
        }
    }
    score = _float(payload.get("total_score"))
    directive_progress = _float(payload.get("directive_progress"))
    with trace_span("novali.meaningful_work.evaluation", attrs):
        record_counter("novali.meaningful_work.evaluation.count", 1, metric_attrs)
        record_gauge_or_observable("novali.meaningful_work.score", score, metric_attrs)
        record_gauge_or_observable("novali.directive.progress", directive_progress, metric_attrs)
        record_event("novali.meaningful_work.evaluation", attrs)
    return attrs


def record_directive_dossier_updated(dossier: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(dossier or {})
    materiality = (
        "material"
        if bool(payload.get("directive_dossier_materially_new", False))
        else "repeated"
    )
    attrs = {
        "novali.result": _safe_label(payload.get("result"), fallback="updated"),
        "novali.deliverable_kind": _safe_label(
            payload.get("selected_deliverable_kind")
            or payload.get("deliverable_kind"),
            fallback="unknown",
        ),
        "novali.directive.dossier.materiality": materiality,
        "novali.directive.source_coverage": _safe_label(
            payload.get("directive_source_coverage_state"),
            fallback="unknown",
        ),
        "novali.librarian_gap_reuse_decision": _safe_label(
            payload.get("librarian_gap_reuse_decision"),
            fallback="unknown",
        ),
        "novali.trusted_source.validation_state": _safe_label(
            payload.get("trusted_source_retrieval_validation_state"),
            fallback="unknown",
        ),
    }
    rejection = _safe_label(
        payload.get("directive_dossier_rejection_reason"),
        fallback="",
    )
    if rejection:
        attrs["novali.delta_rejection_reason"] = rejection
    attrs = {key: value for key, value in attrs.items() if value not in {"", None}}
    metric_attrs = {
        key: value
        for key, value in attrs.items()
        if key
        in {
            "novali.result",
            "novali.deliverable_kind",
            "novali.directive.dossier.materiality",
            "novali.directive.source_coverage",
            "novali.librarian_gap_reuse_decision",
            "novali.trusted_source.validation_state",
            "novali.delta_rejection_reason",
        }
    }
    with trace_span("novali.directive.dossier.updated", attrs):
        record_counter("novali.directive.dossier.updated.count", 1, metric_attrs)
        record_event("novali.directive.dossier.updated", attrs)
    return attrs


def record_autonomy_churn_breaker(churn: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(churn or {})
    attrs = {
        "novali.result": _safe_label(payload.get("result"), fallback="classified"),
        "novali.action": _safe_label(
            payload.get("recommended_breaker_action"),
            fallback="none",
        ),
        "novali.churn_state": _safe_label(payload.get("churn_state"), fallback="clear"),
        "novali.churn_repeat_count": int(payload.get("churn_repeat_count", 0) or 0),
        "novali.directive_depth": _safe_label(
            payload.get("directive_track_depth_target"),
            fallback="none",
        ),
    }
    suppressed = _safe_label(payload.get("suppressed_action"), fallback="")
    if suppressed:
        attrs["novali.suppressed_action"] = suppressed
    signature_ref = short_ref(payload.get("churn_signature_ref"), prefix="churn")
    if signature_ref:
        attrs["novali.churn_signature_ref"] = signature_ref
    attrs = {key: value for key, value in attrs.items() if value not in {"", None}}
    with trace_span("novali.autonomy.churn_breaker", attrs):
        record_counter(
            "novali.autonomy.churn_breaker.count",
            1,
            {
                key: value
                for key, value in attrs.items()
                if key
                in {
                    "novali.result",
                    "novali.action",
                    "novali.churn_state",
                    "novali.directive_depth",
                    "novali.suppressed_action",
                }
            },
        )
        record_event("novali.autonomy.churn_breaker", attrs)
    return attrs


def promotion_packet_state_span_attributes(
    promotion: Mapping[str, Any] | None = None,
    operation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    promotion_payload = dict(promotion or {})
    operation_payload = dict(operation or {})
    packet_present = bool(
        promotion_payload.get("promotion_packet") or operation_payload.get("promotion_packet")
    )
    state = "present" if packet_present else "missing"
    if _bool(promotion_payload.get("auto_adopt_eligible")):
        state = "eligible"
    attrs = {
        "novali.result": _safe_label(promotion_payload.get("decision"), fallback=state),
        "novali.action": _safe_label(operation_payload.get("action"), fallback="unknown"),
        "novali.promotion_packet_state": state,
        "novali.operation_ref": short_ref(
            operation_payload.get("operation_id") or promotion_payload.get("operation_id"),
            prefix="op",
        ),
        "novali.promotion_ref": short_ref(
            promotion_payload.get("promotion_decision_id")
            or promotion_payload.get("promotion_result_id"),
            prefix="promotion",
        ),
        "novali.weak_area": _weak_area_label(promotion_payload.get("weak_areas")),
    }
    return {key: value for key, value in attrs.items() if value not in {"", None}}


def record_promotion_packet_state(
    promotion: Mapping[str, Any] | None = None,
    *,
    operation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    attrs = promotion_packet_state_span_attributes(promotion, operation)
    metric_attrs = {
        key: value
        for key, value in attrs.items()
        if key
        in {
            "novali.result",
            "novali.action",
            "novali.promotion_packet_state",
            "novali.weak_area",
        }
    }
    with trace_span("novali.promotion_packet.state", attrs):
        record_counter("novali.promotion_packet.state.count", 1, metric_attrs)
        record_event("novali.promotion_packet.state", attrs)
    return attrs


def record_continuous_autonomy_heartbeat(
    *,
    status: Mapping[str, Any],
    checkpoint_count: int = 0,
) -> dict[str, Any]:
    payload = dict(status or {})
    operation = dict(payload.get("latest_operation_proposal", {}) or {})
    growth = dict(payload.get("autonomous_growth", {}) or {})
    executor = dict(payload.get("overnight_auto_executor", {}) or {})
    action = _text(operation.get("action"), "unknown")
    result = _text(executor.get("state") or payload.get("runtime_state"), "unknown")
    skip_reason = _skip_reason_label(executor.get("reason")) if result == "skipped" else ""
    directive_progress = _float(growth.get("directive_progress"))
    attrs = {
        "novali.result": _safe_label(result, fallback="unknown"),
        "novali.action": _safe_label(action, fallback="unknown"),
        "novali.operation_ref": short_ref(operation.get("operation_id"), prefix="op"),
        "novali.checkpoint_count": _int(checkpoint_count),
        "novali.meaningful_delta": _bool(growth.get("meaningful_delta")),
        "novali.meaningful_score_band": _score_band(growth.get("meaningful_work_score")),
        "novali.directive_progress_band": _progress_band(directive_progress),
        "novali.weak_area": _weak_area_label(growth.get("weak_areas")),
        "novali.memory_pressure_band": _safe_label(
            growth.get("memory_pressure_band") or growth.get("memory_pressure", {}).get("band"),
            fallback="unknown",
        ),
    }
    if skip_reason:
        attrs["novali.skip_reason"] = skip_reason
    attrs = {key: value for key, value in attrs.items() if value not in {"", None}}
    metric_attrs = {
        key: value
        for key, value in attrs.items()
        if key
        in {
            "novali.result",
            "novali.action",
            "novali.meaningful_delta",
            "novali.meaningful_score_band",
            "novali.directive_progress_band",
            "novali.weak_area",
            "novali.memory_pressure_band",
            "novali.skip_reason",
        }
    }
    with trace_span("novali.continuous_autonomy.heartbeat", attrs):
        record_counter("novali.continuous_autonomy.heartbeat.count", 1, metric_attrs)
        record_gauge_or_observable(
            "novali.autonomy.active",
            1 if _bool(payload.get("active")) else 0,
            metric_attrs,
        )
        record_gauge_or_observable(
            "novali.directive.progress",
            directive_progress,
            metric_attrs,
        )
        record_gauge_or_observable(
            "novali.checkpoint.count",
            _int(checkpoint_count),
            metric_attrs,
        )
        record_event("novali.continuous_autonomy.heartbeat", attrs)
    return attrs


def trusted_source_triage_span_attributes(digest: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(digest or {})
    attrs = {
        "novali.result": _safe_label(payload.get("status"), fallback="unknown"),
        "novali.digest_source": _safe_label(payload.get("digest_source"), fallback="unknown"),
        "novali.trusted_source.failure_class": _safe_label(
            payload.get("trusted_source_failure_class"),
            fallback="none",
        ),
        "novali.trusted_source.parse_outcome": _safe_label(
            payload.get("trusted_source_parse_outcome"),
            fallback="unknown",
        ),
        "novali.trusted_source.usable": _bool(payload.get("digest_usable_for_learning")),
        "novali.triage_ref": short_ref(
            payload.get("trusted_source_triage_digest_id"),
            prefix="triage",
        ),
        "novali.operation_ref": short_ref(payload.get("operation_id"), prefix="op"),
        "novali.citation_count": _int(payload.get("citation_count")),
        "novali.action_suggestion_count": len(
            list(payload.get("action_suggestions", []) or [])
        ),
        "novali.provider": _safe_label(payload.get("provider_id"), fallback="unknown"),
        "novali.model_class": _safe_label(payload.get("provider_model"), fallback="unknown"),
    }
    return {key: value for key, value in attrs.items() if value not in {"", None}}


def record_trusted_source_triage(digest: Mapping[str, Any]) -> dict[str, Any]:
    attrs = trusted_source_triage_span_attributes(digest)
    metric_attrs = {
        key: value
        for key, value in attrs.items()
        if key
        in {
            "novali.result",
            "novali.digest_source",
            "novali.trusted_source.failure_class",
            "novali.trusted_source.parse_outcome",
            "novali.trusted_source.usable",
        }
    }
    with trace_span("novali.trusted_source.triage", attrs):
        record_counter("novali.trusted_source.triage.count", 1, metric_attrs)
        record_gauge_or_observable(
            "novali.trusted_source.triage.citation_count",
            _int(dict(digest or {}).get("citation_count")),
            metric_attrs,
        )
        record_gauge_or_observable(
            "novali.trusted_source.triage.action_suggestion_count",
            len(list(dict(digest or {}).get("action_suggestions", []) or [])),
            metric_attrs,
        )
        record_event("novali.trusted_source.triage", attrs)
    return attrs


def memory_maintenance_span_attributes(status: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(status or {})
    attrs = {
        "novali.result": _safe_label(payload.get("status"), fallback="success"),
        "novali.memory_pressure_band": _safe_label(
            payload.get("pressure_band"),
            fallback="unknown",
        ),
        "novali.partial_archive_cleanup_state": _safe_label(
            payload.get("partial_archive_cleanup_state"),
            fallback="unknown",
        ),
        "novali.compaction_progress_class": _safe_label(
            payload.get("latest_compaction_progress_class"),
            fallback="unknown",
        ),
        "novali.restart_recommended": _bool(
            payload.get("restart_recommended")
            or payload.get("restart_recommended_after_compaction")
            or payload.get("restart_recommended_after_archive_stall")
        ),
        "novali.archive_ref": short_ref(
            payload.get("memory_archive_id")
            or payload.get("latest_archive_id")
            or payload.get("latest_abandoned_partial_archive", {}).get("memory_archive_id"),
            prefix="archive",
        ),
    }
    return {key: value for key, value in attrs.items() if value not in {"", None}}


def record_memory_maintenance(status: Mapping[str, Any]) -> dict[str, Any]:
    attrs = memory_maintenance_span_attributes(status)
    metric_attrs = {
        key: value
        for key, value in attrs.items()
        if key
        in {
            "novali.result",
            "novali.memory_pressure_band",
            "novali.partial_archive_cleanup_state",
            "novali.compaction_progress_class",
            "novali.restart_recommended",
        }
    }
    with trace_span("novali.memory.maintenance", attrs):
        record_counter("novali.memory.maintenance.count", 1, metric_attrs)
        record_event("novali.memory.maintenance", attrs)
    return attrs


def oom_guard_span_attributes(status: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(status or {})
    attrs = {
        "novali.result": _safe_label(payload.get("result"), fallback="success"),
        "novali.oom_guard_state": _safe_label(
            payload.get("oom_guard_state"),
            fallback="unknown",
        ),
        "novali.oom_guard_action": _safe_label(
            payload.get("oom_guard_action"),
            fallback="none",
        ),
        "novali.memory_pressure_band": _safe_label(
            payload.get("pressure_band"),
            fallback="unknown",
        ),
        "novali.lifecycle_state": _safe_label(
            payload.get("lifecycle_state"),
            fallback="unknown",
        ),
        "novali.memory_recovery_ref": short_ref(
            payload.get("memory_recovery_request_id")
            or payload.get("last_recycle_request_id"),
            prefix="memory-recovery",
        ),
        "novali.checkpoint_ref": short_ref(
            payload.get("checkpoint_id") or payload.get("latest_checkpoint_id"),
            prefix="checkpoint",
        ),
    }
    return {key: value for key, value in attrs.items() if value not in {"", None}}


def record_oom_guard(status: Mapping[str, Any]) -> dict[str, Any]:
    attrs = oom_guard_span_attributes(status)
    metric_attrs = {
        key: value
        for key, value in attrs.items()
        if key
        in {
            "novali.result",
            "novali.oom_guard_state",
            "novali.oom_guard_action",
            "novali.memory_pressure_band",
            "novali.lifecycle_state",
        }
    }
    with trace_span("novali.memory.oom_guard", attrs):
        record_counter("novali.memory.oom_guard.count", 1, metric_attrs)
        record_event("novali.memory.oom_guard", attrs)
    return attrs


def record_service_recycle_requested(status: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(status or {})
    attrs = oom_guard_span_attributes(
        {
            **payload,
            "result": payload.get("result", "requested"),
            "oom_guard_action": payload.get("oom_guard_action", "request_service_recycle"),
        }
    )
    attrs["novali.recycle_reason"] = _safe_label(
        payload.get("recycle_reason") or payload.get("oom_guard_reason"),
        fallback="memory_pressure",
    )
    metric_attrs = {
        key: value
        for key, value in attrs.items()
        if key
        in {
            "novali.result",
            "novali.oom_guard_state",
            "novali.oom_guard_action",
            "novali.memory_pressure_band",
            "novali.lifecycle_state",
            "novali.recycle_reason",
        }
    }
    with trace_span("novali.service.recycle_requested", attrs):
        record_counter("novali.service.recycle_requested.count", 1, metric_attrs)
        record_event("novali.service.recycle_requested", attrs)
    return attrs


def memory_smoothing_span_attributes(status: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(status or {})
    attrs = {
        "novali.result": _safe_label(payload.get("result"), fallback="success"),
        "novali.memory_smoothing_state": _safe_label(
            payload.get("memory_smoothing_state"),
            fallback="unknown",
        ),
        "novali.memory_smoothing_action": _safe_label(
            payload.get("latest_smoothing_action"),
            fallback="none",
        ),
        "novali.memory_spill_profile": _safe_label(
            payload.get("memory_spill_profile"),
            fallback="balanced",
        ),
        "novali.memory_spill_action": _safe_label(
            payload.get("latest_spill_action"),
            fallback="none",
        ),
        "novali.memory_pressure_band": _safe_label(
            payload.get("pressure_band"),
            fallback="unknown",
        ),
        "novali.checkpoint_ref": short_ref(
            payload.get("checkpoint_id") or payload.get("latest_checkpoint_id"),
            prefix="checkpoint",
        ),
    }
    return {key: value for key, value in attrs.items() if value not in {"", None}}


def record_memory_smoothing(status: Mapping[str, Any]) -> dict[str, Any]:
    attrs = memory_smoothing_span_attributes(status)
    metric_attrs = {
        key: value
        for key, value in attrs.items()
        if key
        in {
            "novali.result",
            "novali.memory_smoothing_state",
            "novali.memory_smoothing_action",
            "novali.memory_spill_profile",
            "novali.memory_spill_action",
            "novali.memory_pressure_band",
        }
    }
    with trace_span("novali.memory.smoothing", attrs):
        record_counter("novali.memory.smoothing.count", 1, metric_attrs)
        record_event("novali.memory.smoothing", attrs)
    return attrs


def record_memory_disk_spill(status: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(status or {})
    attrs = {
        **memory_smoothing_span_attributes(payload),
        "novali.spill_kind": _safe_label(payload.get("spill_kind"), fallback="unknown"),
    }
    metric_attrs = {
        key: value
        for key, value in attrs.items()
        if key
        in {
            "novali.result",
            "novali.memory_smoothing_state",
            "novali.memory_pressure_band",
            "novali.memory_spill_profile",
            "novali.memory_spill_action",
            "novali.spill_kind",
        }
    }
    with trace_span("novali.memory.disk_spill", attrs):
        record_counter("novali.memory.disk_spill.count", 1, metric_attrs)
        record_histogram(
            "novali.memory.disk_spill.bytes",
            float(payload.get("disk_spill_bytes", 0) or 0),
            metric_attrs,
        )
        record_event("novali.memory.disk_spill", attrs)
    return attrs


def _byte_count_band(value: Any) -> str:
    count = max(0, _int(value, 0))
    if count == 0:
        return "zero"
    if count < 1024 * 1024:
        return "under_1mb"
    if count < 16 * 1024 * 1024:
        return "one_to_sixteen_mb"
    if count < 128 * 1024 * 1024:
        return "sixteen_to_128mb"
    return "over_128mb"


def _result_count_band(value: Any) -> str:
    count = max(0, _int(value, 0))
    if count == 0:
        return "zero"
    if count <= 5:
        return "one_to_five"
    if count <= 25:
        return "six_to_twenty_five"
    return "over_twenty_five"


def record_runtime_log_segment_moved(status: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(status or {})
    attrs = {
        "novali.result": _safe_label(payload.get("result"), fallback="unknown"),
        "novali.source_kind": "runtime_log_segment",
        "novali.session_ref": short_ref(payload.get("session_ref"), prefix="session"),
        "novali.segment_ref": short_ref(payload.get("segment_ref"), prefix="logseg"),
        "novali.byte_count_band": _byte_count_band(payload.get("byte_count")),
        "novali.storage_state": _safe_label(payload.get("storage_state"), fallback="moved_to_spill"),
    }
    metric_attrs = {
        key: value
        for key, value in attrs.items()
        if key
        in {
            "novali.result",
            "novali.source_kind",
            "novali.byte_count_band",
            "novali.storage_state",
        }
    }
    with trace_span("novali.runtime_log.segment_moved", attrs):
        record_counter("novali.runtime_log.segment_moved.count", 1, metric_attrs)
        record_histogram(
            "novali.runtime_log.segment_moved.bytes",
            float(payload.get("byte_count", 0) or 0),
            metric_attrs,
        )
        record_event("novali.runtime_log.segment_moved", attrs)
    return attrs


def record_workspace_artifact_cold_moved(status: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(status or {})
    attrs = {
        "novali.result": _safe_label(payload.get("result"), fallback="unknown"),
        "novali.source_kind": "cold_workspace_artifact",
        "novali.workspace_ref": short_ref(payload.get("workspace_ref"), prefix="workspace"),
        "novali.artifact_ref": short_ref(payload.get("artifact_ref"), prefix="artifact"),
        "novali.byte_count_band": _byte_count_band(payload.get("byte_count")),
        "novali.storage_state": _safe_label(payload.get("storage_state"), fallback="moved_to_spill"),
    }
    metric_attrs = {
        key: value
        for key, value in attrs.items()
        if key
        in {
            "novali.result",
            "novali.source_kind",
            "novali.byte_count_band",
            "novali.storage_state",
        }
    }
    with trace_span("novali.workspace_artifact.cold_moved", attrs):
        record_counter("novali.workspace_artifact.cold_moved.count", 1, metric_attrs)
        record_histogram(
            "novali.workspace_artifact.cold_moved.bytes",
            float(payload.get("byte_count", 0) or 0),
            metric_attrs,
        )
        record_event("novali.workspace_artifact.cold_moved", attrs)
    return attrs


def record_data_at_rest_lookup(status: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(status or {})
    attrs = {
        "novali.result": _safe_label(payload.get("result"), fallback="success"),
        "novali.lookup_kind": _safe_label(payload.get("kind"), fallback="all"),
        "novali.result_count_band": _result_count_band(payload.get("result_count")),
    }
    metric_attrs = dict(attrs)
    with trace_span("novali.data_at_rest.lookup", attrs):
        record_counter("novali.data_at_rest.lookup.count", 1, metric_attrs)
        record_gauge_or_observable(
            "novali.data_at_rest.lookup.result_count",
            _int(payload.get("result_count"), 0),
            metric_attrs,
        )
        record_event("novali.data_at_rest.lookup", attrs)
    return attrs


def record_spill_sweeper_pass(status: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(status or {})
    attrs = {
        "novali.result": _safe_label(payload.get("result"), fallback="unknown"),
        "novali.spill_sweeper_state": _safe_label(
            payload.get("spill_sweeper_state"),
            fallback="unknown",
        ),
        "novali.spill_activity_state": _safe_label(
            payload.get("spill_activity_state"),
            fallback="unknown",
        ),
        "novali.runtime_log_segment_count_band": _result_count_band(
            payload.get("runtime_log_segment_move_count")
        ),
        "novali.cold_artifact_count_band": _result_count_band(
            payload.get("cold_artifact_move_count")
        ),
        "novali.byte_count_band": _byte_count_band(
            payload.get("spill_budget_used_bytes") or payload.get("moved_bytes")
        ),
    }
    metric_attrs = dict(attrs)
    with trace_span("novali.spill.sweeper.pass", attrs):
        record_counter("novali.spill.sweeper.pass.count", 1, metric_attrs)
        record_histogram(
            "novali.spill.sweeper.pass.bytes",
            float(payload.get("spill_budget_used_bytes", 0) or payload.get("moved_bytes", 0) or 0),
            metric_attrs,
        )
        record_event("novali.spill.sweeper.pass", attrs)
    return attrs


def record_memory_trim(status: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(status or {})
    attrs = {
        **memory_smoothing_span_attributes(payload),
        "novali.trim_result": _safe_label(
            payload.get("last_trim_result") or payload.get("result"),
            fallback="unknown",
        ),
    }
    metric_attrs = {
        key: value
        for key, value in attrs.items()
        if key
        in {
            "novali.result",
            "novali.memory_smoothing_state",
            "novali.memory_pressure_band",
            "novali.trim_result",
        }
    }
    with trace_span("novali.memory.trim", attrs):
        record_counter("novali.memory.trim.count", 1, metric_attrs)
        record_gauge_or_observable(
            "novali.memory.cache_eviction.count",
            _int(payload.get("cache_eviction_count")),
            metric_attrs,
        )
        record_event("novali.memory.trim", attrs)
    return attrs


def _librarian_count_band(value: int) -> str:
    count = max(0, int(value or 0))
    if count == 0:
        return "zero"
    if count <= 5:
        return "one_to_five"
    if count <= 25:
        return "six_to_twenty_five"
    if count <= 100:
        return "twenty_six_to_hundred"
    return "over_hundred"


def _librarian_attrs(payload: Mapping[str, Any], *, fallback_result: str) -> dict[str, Any]:
    data = dict(payload or {})
    attrs = {
        "novali.pack_ref": short_ref(data.get("pack_id"), prefix="pack"),
        "novali.pack_kind": _safe_label(data.get("pack_kind"), fallback="unknown"),
        "novali.quality_state": _safe_label(data.get("quality_state"), fallback="unknown"),
        "novali.reuse_state": _safe_label(data.get("reuse_state"), fallback="unknown"),
        "novali.source_kind": _safe_label(data.get("source_kind"), fallback="unknown"),
        "novali.validation_result": _safe_label(
            data.get("validation_result") or data.get("stage_result") or data.get("result"),
            fallback=fallback_result,
        ),
        "novali.rejection_reason": _safe_label(
            data.get("rejection_reason") or data.get("latest_librarian_blocker"),
            fallback="none",
        ),
        "novali.result": _safe_label(data.get("result"), fallback=fallback_result),
    }
    return {key: value for key, value in attrs.items() if value not in {"", None}}


def record_librarian_pack_discovered(pack: Mapping[str, Any]) -> dict[str, Any]:
    attrs = _librarian_attrs(pack, fallback_result="discovered")
    metric_attrs = {
        key: value
        for key, value in attrs.items()
        if key
        in {
            "novali.pack_kind",
            "novali.source_kind",
            "novali.validation_result",
            "novali.result",
        }
    }
    with trace_span("novali.librarian.pack.discovered", attrs):
        record_counter("novali.librarian.pack.discovered.count", 1, metric_attrs)
        record_event("novali.librarian.pack.discovered", attrs)
    return attrs


def record_librarian_pack_staged(pack: Mapping[str, Any]) -> dict[str, Any]:
    attrs = _librarian_attrs(pack, fallback_result="staged")
    metric_attrs = {
        key: value
        for key, value in attrs.items()
        if key
        in {
            "novali.pack_kind",
            "novali.quality_state",
            "novali.reuse_state",
            "novali.source_kind",
            "novali.validation_result",
            "novali.result",
        }
    }
    with trace_span("novali.librarian.pack.staged", attrs):
        record_counter("novali.librarian.pack.staged.count", 1, metric_attrs)
        record_event("novali.librarian.pack.staged", attrs)
    return attrs


def record_librarian_pack_reused(pack: Mapping[str, Any]) -> dict[str, Any]:
    attrs = _librarian_attrs(pack, fallback_result="reused")
    metric_attrs = {
        key: value
        for key, value in attrs.items()
        if key in {"novali.pack_kind", "novali.reuse_state", "novali.result"}
    }
    with trace_span("novali.librarian.pack.reused", attrs):
        record_counter("novali.librarian.pack.reused.count", 1, metric_attrs)
        record_event("novali.librarian.pack.reused", attrs)
    return attrs


def record_librarian_pack_rejected(pack: Mapping[str, Any]) -> dict[str, Any]:
    attrs = _librarian_attrs(pack, fallback_result="rejected")
    metric_attrs = {
        key: value
        for key, value in attrs.items()
        if key
        in {
            "novali.pack_kind",
            "novali.source_kind",
            "novali.validation_result",
            "novali.rejection_reason",
            "novali.result",
        }
    }
    with trace_span("novali.librarian.pack.rejected", attrs):
        record_counter("novali.librarian.pack.rejected.count", 1, metric_attrs)
        record_event("novali.librarian.pack.rejected", attrs)
    return attrs


def record_librarian_catalog_refresh(status: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(status or {})
    attrs = {
        "novali.result": _safe_label(payload.get("result"), fallback="completed"),
        "novali.pack_count_band": _librarian_count_band(_int(payload.get("pack_count"), 0)),
        "novali.reusable_count_band": _librarian_count_band(
            _int(payload.get("reusable_count"), 0)
        ),
    }
    metric_attrs = dict(attrs)
    with trace_span("novali.librarian.catalog.refresh", attrs):
        record_counter("novali.librarian.catalog.refresh.count", 1, metric_attrs)
        record_gauge_or_observable(
            "novali.librarian.pack.count",
            _int(payload.get("pack_count"), 0),
            metric_attrs,
        )
        record_gauge_or_observable(
            "novali.librarian.reusable.count",
            _int(payload.get("reusable_count"), 0),
            metric_attrs,
        )
        record_event("novali.librarian.catalog.refresh", attrs)
    return attrs
