from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .directive_scaffold import (
    build_active_line_bootstrap_context,
    build_standalone_directive_payload,
)
from .observability import record_counter, record_event, record_histogram, trace_span
from .observability.enrichment import llm_metric_attributes, llm_span_attributes
from .observability.redaction import REDACTED, redact_value


LLM_CONTEXT_SCHEMA_NAME = "NovaliLLMContextBundle"
LLM_CONTEXT_SCHEMA_VERSION = "novali_llm_context_bundle_v1"
LLM_CHAT_RECORD_SCHEMA_NAME = "NovaliLLMChatRecord"
LLM_CHAT_RECORD_SCHEMA_VERSION = "novali_llm_chat_record_v1"
LLM_HISTORY_SCHEMA_NAME = "NovaliLLMChatHistory"
LLM_HISTORY_SCHEMA_VERSION = "novali_llm_chat_history_v1"
LLM_STATUS_SCHEMA_NAME = "NovaliLocalLLMStatus"
LLM_STATUS_SCHEMA_VERSION = "novali_local_llm_status_v1"
LLM_PENDING_DIRECTIVE_SCHEMA_NAME = "NovaliLLMPendingDirectivePromotion"
LLM_PENDING_DIRECTIVE_SCHEMA_VERSION = "novali_llm_pending_directive_promotion_v1"
LLM_PENDING_DIRECTIVE_LIST_SCHEMA_NAME = "NovaliLLMPendingDirectiveList"
LLM_PENDING_DIRECTIVE_LIST_SCHEMA_VERSION = "novali_llm_pending_directive_list_v1"

DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "llama3.1"
LOCAL_LLM_PROVIDER = "ollama"
SUPPORTED_LLM_MODES = ("explain_state", "draft_directive", "draft_plan")
MAX_PROMPT_CHARS = 4000
MAX_ASSISTANT_CHARS = 12000
MAX_CONTEXT_JSON_CHARS = 16000
MAX_PENDING_DIRECTIVE_TEXT_CHARS = 8000
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 20.0
SAFE_RECORD_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_dump(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)


def _compact_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash_payload(payload: Any, *, length: int = 16) -> str:
    return hashlib.sha256(_compact_json(payload).encode("utf-8")).hexdigest()[:length]


def _coerce_float(value: str | None, default: float) -> float:
    try:
        parsed = float(value or "")
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def configured_ollama_base_url() -> str:
    return str(os.environ.get("NOVALI_LOCAL_LLM_BASE_URL") or DEFAULT_OLLAMA_BASE_URL).rstrip("/")


def configured_ollama_model() -> str:
    return str(os.environ.get("NOVALI_LOCAL_LLM_MODEL") or DEFAULT_OLLAMA_MODEL).strip() or DEFAULT_OLLAMA_MODEL


def configured_ollama_timeout_seconds() -> float:
    return _coerce_float(
        os.environ.get("NOVALI_LOCAL_LLM_TIMEOUT_SECONDS"),
        DEFAULT_OLLAMA_TIMEOUT_SECONDS,
    )


def llm_chat_root(operator_root: str | Path) -> Path:
    return Path(operator_root) / "llm_chat"


def llm_pending_directive_root(operator_root: str | Path) -> Path:
    return Path(operator_root) / "llm_pending_directives"


def _configured_model_available(configured_model: str, available_models: list[str]) -> bool:
    wanted = str(configured_model or "").strip()
    if not wanted:
        return False
    wanted_base = wanted.split(":", 1)[0]
    for model_name in available_models:
        candidate = str(model_name or "").strip()
        if candidate == wanted:
            return True
        if ":" not in wanted and candidate.split(":", 1)[0] == wanted_base:
            return True
    return False


def _redact_payload(payload: Any) -> Any:
    return redact_value(payload)


def _redact_chat_record_for_display(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    record = dict(payload or {})
    for key, limit in (
        ("prompt_summary_redacted", 1200),
        ("assistant_response_redacted", MAX_ASSISTANT_CHARS),
        ("error_summary_redacted", 1200),
    ):
        if key in record:
            record[key] = _truncate_text(redact_value(record.get(key)), limit)
    notes = record.get("refusal_or_limitation_notes", [])
    if isinstance(notes, list):
        record["refusal_or_limitation_notes"] = [
            _truncate_text(redact_value(item), 600) for item in notes
        ]
    return record


def _redact_pending_evidence_for_display(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    record = dict(payload or {})
    for key, limit in (
        ("prompt_summary_redacted", 1200),
        ("assistant_response_summary_redacted", 2400),
        ("operator_note_redacted", 1200),
    ):
        if key in record:
            record[key] = _truncate_text(redact_value(record.get(key)), limit)
    return record


def _redaction_status(original: Any, redacted: Any) -> str:
    return "redacted" if _compact_json(original) != _compact_json(redacted) else "clean"


def _truncate_text(value: Any, limit: int) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...[truncated {len(text) - limit} chars]"


def _safe_record_id(value: str) -> str:
    record_id = str(value or "").strip()
    if not record_id or not SAFE_RECORD_ID_RE.fullmatch(record_id):
        return ""
    return record_id


def _slug(value: str, *, fallback: str) -> str:
    token = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()).strip("._-")
    return token or fallback


def _compact_mapping(source: Mapping[str, Any] | None, keys: tuple[str, ...]) -> dict[str, Any]:
    payload = dict(source or {})
    return {key: payload.get(key) for key in keys if key in payload}


def _compact_artifacts(artifacts: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(artifacts or {})
    allowed_keys = (
        "workspace_id",
        "workspace_root",
        "workspace_root_hint",
        "session_artifact_path",
        "runtime_event_log_path",
        "artifact_index_path",
        "bounded_work_summary_path",
        "implementation_bundle_summary_path",
        "trusted_planning_evidence_path",
        "successor_capability_gap_path",
    )
    compacted: dict[str, Any] = {}
    for key in allowed_keys:
        value = payload.get(key)
        if value not in (None, "", [], {}):
            compacted[key] = str(value)
    return compacted


def build_llm_context_bundle(
    *,
    operator_state: Mapping[str, Any] | None = None,
    bootstrap_status: Mapping[str, Any] | None = None,
    governed_status: Mapping[str, Any] | None = None,
    directive_summary: Mapping[str, Any] | None = None,
    intervention_state: Mapping[str, Any] | None = None,
    long_run_state: Mapping[str, Any] | None = None,
    workspace_artifacts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the compact, redacted state surface allowed to leave the backend."""

    shell_state = dict(operator_state or {})
    bootstrap = dict(bootstrap_status or {})
    governed = dict(governed_status or {})
    directive = dict(directive_summary or {})
    intervention = dict(intervention_state or {})
    long_run_payload = dict(long_run_state or {})
    long_run = dict(long_run_payload.get("long_run", {}))
    operator_guidance = dict(long_run_payload.get("operator_guidance", {}))

    raw_bundle = {
        "schema_name": LLM_CONTEXT_SCHEMA_NAME,
        "schema_version": LLM_CONTEXT_SCHEMA_VERSION,
        "generated_at": _now(),
        "authority_boundary": (
            "Explain and draft only. This context cannot authorize launch, review "
            "approval, continuation, pause, resume, stop, directive mutation, or file writes."
        ),
        "operator_state": _compact_mapping(
            dict(shell_state.get("operator_state", {})),
            (
                "state",
                "status",
                "run_status",
                "review_required",
                "intervention_required",
                "directive_ready",
                "runtime_ready",
                "operator_next_action",
                "operator_next_action_detail",
            ),
        ),
        "session": _compact_mapping(
            dict(shell_state.get("session", {})),
            (
                "session_id",
                "session_handle",
                "workspace_id",
                "workflow_stage",
                "run_status",
                "latest_checkpoint_id",
            ),
        ),
        "launch_readiness": {
            "bootstrap": _compact_mapping(
                bootstrap,
                (
                    "mode",
                    "can_launch",
                    "selected_launch",
                    "workflow_lane",
                    "expected_execution_profile",
                    "operator_next_action",
                    "operator_next_action_detail",
                    "blocking_reasons",
                    "warnings",
                ),
            ),
            "governed": _compact_mapping(
                governed,
                (
                    "mode",
                    "can_launch",
                    "selected_launch",
                    "workflow_lane",
                    "expected_execution_profile",
                    "operator_next_action",
                    "operator_next_action_detail",
                    "blocking_reasons",
                    "warnings",
                    "review_required",
                ),
            ),
        },
        "directive": {
            "path_hint": str(directive.get("path", "") or directive.get("directive_path", "")),
            "directive_id": str(directive.get("directive_id", "") or directive.get("id", "")),
            "summary": _truncate_text(directive.get("summary", ""), 1500),
            "loaded": bool(directive.get("path") or directive.get("directive_path") or directive.get("summary")),
            "raw_directive_body_excluded": True,
        },
        "intervention": {
            "intervention_required": bool(intervention.get("intervention_required", False)),
            "review_required": bool(intervention.get("review_required", False)),
            "intervention": _compact_mapping(
                dict(intervention.get("intervention", {})),
                (
                    "required",
                    "reason",
                    "summary",
                    "operator_next_action",
                    "operator_next_action_detail",
                    "blocking_reasons",
                ),
            ),
            "attention_signal": intervention.get("attention_signal", {}),
            "attention_inbox": _compact_mapping(
                dict(intervention.get("attention_inbox", {})),
                (
                    "label",
                    "blocking_count",
                    "informational_count",
                    "total_count",
                    "empty_state_label",
                    "empty_state_detail",
                ),
            ),
            "operator_alerts": _compact_mapping(
                dict(intervention.get("operator_alerts", {})),
                (
                    "status",
                    "state",
                    "active_count",
                    "blocking_count",
                    "summary",
                    "headline",
                    "label",
                ),
            ),
        },
        "long_run": {
            "state": _compact_mapping(
                long_run,
                (
                    "lifecycle_state",
                    "lease_state",
                    "checkpoint_count",
                    "current_cycle",
                    "max_cycles",
                    "resume_available",
                    "operator_pause_requested",
                    "operator_stop_requested",
                    "operator_summary",
                    "recommended_next_action",
                    "stale_recovery_available",
                ),
            ),
            "guidance": _compact_mapping(
                operator_guidance,
                (
                    "primary_label",
                    "primary_detail",
                    "current_blocker_label",
                    "current_blocker",
                    "recommended_next_action_label",
                    "recommended_next_action_detail",
                ),
            ),
        },
        "workspace_artifacts": _compact_artifacts(
            workspace_artifacts or shell_state.get("artifacts", {})
        ),
        "excluded_payloads": [
            "raw secrets",
            "raw directive bodies",
            "credential files",
            "full trusted-source responses",
            "full runtime logs",
            "broad workspace file contents",
        ],
    }
    redacted = _redact_payload(raw_bundle)
    if not isinstance(redacted, dict):
        redacted = {"schema_name": LLM_CONTEXT_SCHEMA_NAME, "redaction_error": True}
    redacted["context_bundle_id"] = f"llmctx-{_hash_payload(redacted)}"
    redacted["redaction_status"] = _redaction_status(raw_bundle, redacted)
    return redacted


def build_llm_status_payload(
    *,
    base_url: str | None = None,
    model: str | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    provider_base_url = (base_url or configured_ollama_base_url()).rstrip("/")
    configured_model = model or configured_ollama_model()
    timeout = timeout_seconds if timeout_seconds is not None else min(configured_ollama_timeout_seconds(), 2.0)
    started = time.perf_counter()
    status = "unavailable"
    error_type = ""
    error_summary = ""
    available_models: list[str] = []
    try:
        request = urllib.request.Request(
            f"{provider_base_url}/api/tags",
            method="GET",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
        payload = json.loads(raw or "{}")
        available_models = [
            str(item.get("name", "")).strip()
            for item in list(payload.get("models", []) or [])
            if str(item.get("name", "")).strip()
        ]
        status = "available"
    except (TimeoutError, socket.timeout):
        status = "timeout"
        error_type = "timeout"
        error_summary = "Timed out while checking local Ollama provider."
    except (urllib.error.URLError, ConnectionError, OSError) as exc:
        status = "unavailable"
        error_type = type(exc).__name__
        error_summary = str(exc)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        status = "malformed_response"
        error_type = type(exc).__name__
        error_summary = "Local Ollama status response was not valid JSON."
    latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
    model_available = _configured_model_available(configured_model, available_models)
    chat_available = status == "available" and model_available
    return {
        "schema_name": LLM_STATUS_SCHEMA_NAME,
        "schema_version": LLM_STATUS_SCHEMA_VERSION,
        "generated_at": _now(),
        "provider": LOCAL_LLM_PROVIDER,
        "provider_base_url": provider_base_url,
        "model": configured_model,
        "status": status,
        "available": status == "available",
        "chat_available": chat_available,
        "configured_model_available": model_available,
        "available_models": available_models[:25],
        "last_health_result": {
            "status": status,
            "latency_ms": latency_ms,
            "last_error_type": error_type,
            "last_error_summary_redacted": redact_value(error_summary),
        },
        "capability_boundary": "explain_and_draft_only",
    }


def _system_prompt(mode: str) -> str:
    mode_instruction = {
        "explain_state": "Explain current state, blockers, and safe operator next steps.",
        "draft_directive": "Draft directive wording only. Do not present it as approved or active.",
        "draft_plan": "Draft a safe next-step plan only. Do not claim execution authority.",
    }.get(mode, "Explain or draft within the supplied boundary.")
    return (
        "You are Novali's local operator assistant. You receive only curated, redacted "
        "backend context. You may explain state, identify blockers, and draft operator "
        "text. You must not claim you launched, approved, continued, paused, resumed, "
        "stopped, wrote files, changed directives, bypassed review, or mutated Novali "
        f"state. Current mode: {mode}. {mode_instruction}"
    )


def _record_chat(
    *,
    operator_root: str | Path,
    message: str,
    mode: str,
    context_bundle: Mapping[str, Any] | None,
    assistant_text: str,
    provider: str,
    model: str,
    status: str,
    latency_ms: float,
    refusal_or_limitation_notes: list[str],
    error_type: str = "",
    error_summary: str = "",
) -> dict[str, Any]:
    context_id = str(dict(context_bundle or {}).get("context_bundle_id", ""))
    created_at = _now()
    original_record = {
        "schema_name": LLM_CHAT_RECORD_SCHEMA_NAME,
        "schema_version": LLM_CHAT_RECORD_SCHEMA_VERSION,
        "record_id": "",
        "created_at": created_at,
        "mode": mode,
        "provider": provider,
        "model": model,
        "status": status,
        "context_bundle_id": context_id,
        "prompt_summary_redacted": _truncate_text(message, 1200),
        "assistant_response_redacted": _truncate_text(assistant_text, MAX_ASSISTANT_CHARS),
        "latency_ms": latency_ms,
        "error_type": error_type,
        "error_summary_redacted": error_summary,
        "refusal_or_limitation_notes": refusal_or_limitation_notes,
        "redaction_notes": [
            "Record contains redacted prompt and assistant summaries only.",
            "Raw directive bodies, secrets, credential files, and full logs are not stored.",
        ],
    }
    redacted = _redact_payload(original_record)
    if not isinstance(redacted, dict):
        redacted = {"schema_name": LLM_CHAT_RECORD_SCHEMA_NAME, "created_at": created_at}
    redacted["redaction_status"] = _redaction_status(original_record, redacted)
    record_id = f"chat-{created_at.replace(':', '').replace('.', '')}-{_hash_payload(redacted, length=10)}"
    redacted["record_id"] = record_id
    root = llm_chat_root(operator_root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{record_id}.json"
    path.write_text(_json_dump(redacted) + "\n", encoding="utf-8")
    redacted["record_path_hint"] = str(path)
    return redacted


def validate_llm_chat_request(*, message: str, mode: str) -> dict[str, Any] | None:
    clean_message = str(message or "").strip()
    clean_mode = str(mode or "").strip()
    if not clean_message:
        return {
            "ok": False,
            "status": "rejected",
            "message": "Message is required.",
            "details": ["Empty prompts are rejected before any local LLM call."],
        }
    if clean_mode not in SUPPORTED_LLM_MODES:
        return {
            "ok": False,
            "status": "rejected",
            "message": "Unknown LLM mode.",
            "details": [f"Supported modes: {', '.join(SUPPORTED_LLM_MODES)}"],
        }
    if len(clean_message) > MAX_PROMPT_CHARS:
        return {
            "ok": False,
            "status": "rejected",
            "message": "Prompt is too large.",
            "details": [f"Maximum prompt length is {MAX_PROMPT_CHARS} characters."],
        }
    return None


def _llm_span_base(
    *,
    provider: str,
    model: str,
    mode: str,
    context_bundle_id: str = "",
) -> dict[str, Any]:
    return {
        "provider": provider,
        "model": model,
        "mode": str(mode or "").strip() or "unknown",
        "context_bundle_id": str(context_bundle_id or "").strip(),
    }


def _record_llm_chat_result(
    span: Any,
    *,
    span_base: Mapping[str, Any],
    status: str,
    latency_ms: float,
) -> None:
    status_value = str(status or "unknown").strip() or "unknown"
    span_attrs = llm_span_attributes(status=status_value, **dict(span_base))
    metric_attrs = llm_metric_attributes(
        provider=str(span_base.get("provider", "") or "unknown"),
        model=str(span_base.get("model", "") or "unknown"),
        mode=str(span_base.get("mode", "") or "unknown"),
        status=status_value,
    )
    for key, value in span_attrs.items():
        span.set_attribute(key, value)
    record_counter("novali.llm.chat.count", 1, metric_attrs)
    record_histogram(
        "novali.llm.chat.duration_ms",
        float(latency_ms),
        metric_attrs,
    )
    record_event("novali.llm.chat.result", span_attrs)


def record_llm_chat_rejection(
    *,
    mode: str,
    model: str | None = None,
    context_bundle_id: str = "",
) -> None:
    configured_model = model or configured_ollama_model()
    span_base = _llm_span_base(
        provider=f"local_{LOCAL_LLM_PROVIDER}",
        model=configured_model,
        mode=mode,
        context_bundle_id=context_bundle_id,
    )
    with trace_span(
        "novali.llm.chat",
        llm_span_attributes(status="started", **span_base),
    ) as span:
        _record_llm_chat_result(
            span,
            span_base=span_base,
            status="rejected",
            latency_ms=0.0,
        )


def chat_with_ollama(
    *,
    operator_root: str | Path,
    message: str,
    mode: str,
    context_bundle: Mapping[str, Any],
    base_url: str | None = None,
    model: str | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    clean_message = str(message or "").strip()
    clean_mode = str(mode or "").strip()
    provider_base_url = (base_url or configured_ollama_base_url()).rstrip("/")
    configured_model = model or configured_ollama_model()
    context_id = str(dict(context_bundle or {}).get("context_bundle_id", "") or "")
    span_base = _llm_span_base(
        provider=f"local_{LOCAL_LLM_PROVIDER}",
        model=configured_model,
        mode=clean_mode or "unknown",
        context_bundle_id=context_id,
    )

    with trace_span(
        "novali.llm.chat",
        llm_span_attributes(status="started", **span_base),
    ) as span:
        rejection = validate_llm_chat_request(message=clean_message, mode=clean_mode)
        if rejection is not None:
            _record_llm_chat_result(
                span,
                span_base=span_base,
                status="rejected",
                latency_ms=0.0,
            )
            return rejection

        redacted_context = _redact_payload(dict(context_bundle or {}))
        context_json = _truncate_text(_json_dump(redacted_context), MAX_CONTEXT_JSON_CHARS)
        user_prompt = (
            f"Mode: {clean_mode}\n"
            f"Operator message:\n{redact_value(clean_message)}\n\n"
            f"Curated Novali context JSON:\n{context_json}"
        )
        request_payload = {
            "model": configured_model,
            "stream": False,
            "messages": [
                {"role": "system", "content": _system_prompt(clean_mode)},
                {"role": "user", "content": user_prompt},
            ],
            "options": {"temperature": 0.2, "num_predict": 512},
        }
        started = time.perf_counter()
        status = "error"
        assistant_text = ""
        error_type = ""
        error_summary = ""
        limitation_notes = [
            "Local LLM output is explain-and-draft evidence only.",
            "The response did not execute or mutate Novali state.",
        ]
        try:
            request = urllib.request.Request(
                f"{provider_base_url}/api/chat",
                data=json.dumps(request_payload).encode("utf-8"),
                method="POST",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(
                request,
                timeout=timeout_seconds
                if timeout_seconds is not None
                else configured_ollama_timeout_seconds(),
            ) as response:
                raw = response.read().decode("utf-8")
            payload = json.loads(raw or "{}")
            assistant_text = str(
                dict(payload.get("message", {})).get("content", "") or ""
            ).strip()
            if not assistant_text:
                status = "malformed_response"
                error_type = "malformed_response"
                error_summary = "Local Ollama response did not contain message.content."
            else:
                status = "completed"
                assistant_text = _truncate_text(
                    redact_value(assistant_text),
                    MAX_ASSISTANT_CHARS,
                )
        except (TimeoutError, socket.timeout):
            status = "timeout"
            error_type = "timeout"
            error_summary = "Timed out while waiting for local Ollama chat response."
            assistant_text = "Local Ollama did not respond before the timeout."
        except (urllib.error.URLError, ConnectionError, OSError) as exc:
            status = "unavailable"
            error_type = type(exc).__name__
            error_summary = str(exc)
            assistant_text = "Local Ollama is unavailable. Start Ollama and try again."
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            status = "malformed_response"
            error_type = type(exc).__name__
            error_summary = "Local Ollama returned a malformed response."
            assistant_text = "Local Ollama returned a malformed response."
        latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
        _record_llm_chat_result(
            span,
            span_base=span_base,
            status=status,
            latency_ms=latency_ms,
        )
        record = _record_chat(
            operator_root=operator_root,
            message=clean_message,
            mode=clean_mode,
            context_bundle=redacted_context if isinstance(redacted_context, Mapping) else {},
            assistant_text=assistant_text,
            provider=LOCAL_LLM_PROVIDER,
            model=configured_model,
            status=status,
            latency_ms=latency_ms,
            refusal_or_limitation_notes=limitation_notes,
            error_type=error_type,
            error_summary=str(redact_value(error_summary) or ""),
        )
        return {
            "ok": status == "completed",
            "status": status,
            "message": "LLM response generated." if status == "completed" else assistant_text,
            "assistant_text": assistant_text,
            "provider": LOCAL_LLM_PROVIDER,
            "model": configured_model,
            "latency_ms": latency_ms,
            "context_bundle_id": str(record.get("context_bundle_id", "")),
            "record_id": str(record.get("record_id", "")),
            "record_path_hint": str(record.get("record_path_hint", "")),
            "redaction_status": str(record.get("redaction_status", "")),
            "refusal_or_limitation_notes": limitation_notes,
            "error_type": error_type,
            "error_summary_redacted": str(redact_value(error_summary) or ""),
        }


def load_llm_chat_record(operator_root: str | Path, record_id: str) -> dict[str, Any]:
    payload = _load_llm_chat_record_raw(operator_root, record_id)
    if not payload:
        return {}
    redacted = _redact_chat_record_for_display(payload)
    redacted["record_path_hint"] = str(llm_chat_root(operator_root) / f"{_safe_record_id(record_id)}.json")
    return redacted


def _load_llm_chat_record_raw(operator_root: str | Path, record_id: str) -> dict[str, Any]:
    clean_record_id = _safe_record_id(record_id)
    if not clean_record_id:
        return {}
    path = llm_chat_root(operator_root) / f"{clean_record_id}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    payload["record_path_hint"] = str(path)
    return payload


def _pending_directive_candidate_id(*, record_id: str, draft_text: str, created_at: str) -> str:
    digest = hashlib.sha256(f"{record_id}\n{draft_text}\n{created_at}".encode("utf-8")).hexdigest()[:12]
    timestamp_token = re.sub(r"[^0-9A-Za-z]+", "", created_at)[:16] or "pending"
    return f"llm_draft_{timestamp_token}_{digest}"


def promote_llm_draft_to_pending_directive(
    *,
    operator_root: str | Path,
    package_root: str | Path,
    directive_root: str | Path,
    record_id: str,
    operator_note: str = "",
) -> dict[str, Any]:
    """Convert a stored draft-directive chat record into a review-gated directive candidate."""

    record = _load_llm_chat_record_raw(operator_root, record_id)
    if not record:
        return {
            "ok": False,
            "status": "rejected",
            "message": "Stored LLM draft record was not found.",
            "details": ["Promotion requires a persisted redacted draft_directive chat record."],
        }
    if str(record.get("mode", "")).strip() != "draft_directive":
        return {
            "ok": False,
            "status": "rejected",
            "message": "Only draft_directive LLM records can be promoted.",
            "details": [f"Record mode was {record.get('mode', '<missing>')}."],
        }
    if str(record.get("status", "")).strip() != "completed":
        return {
            "ok": False,
            "status": "rejected",
            "message": "Only completed LLM draft records can be promoted.",
            "details": [f"Record status was {record.get('status', '<missing>')}."],
        }

    draft_text = str(record.get("assistant_response_redacted", "") or "").strip()
    if not draft_text:
        return {
            "ok": False,
            "status": "rejected",
            "message": "The stored draft record has no assistant response to promote.",
            "details": ["Ask Novali for a directive draft again, then promote the completed record."],
        }
    draft_text = _truncate_text(str(redact_value(draft_text) or ""), MAX_PENDING_DIRECTIVE_TEXT_CHARS)
    created_at = _now()
    candidate_id = _pending_directive_candidate_id(
        record_id=str(record.get("record_id", "")),
        draft_text=draft_text,
        created_at=created_at,
    )
    directive_id = _slug(candidate_id, fallback="llm_draft_pending_directive")
    prompt_summary = _truncate_text(record.get("prompt_summary_redacted", ""), 1200)
    clarified_summary = _truncate_text(
        (
            "Pending LLM-generated directive draft created for operator review only. "
            "Source prompt summary: "
            f"{prompt_summary or '<not recorded>'}"
        ),
        1500,
    )
    directive_payload = build_standalone_directive_payload(
        package_root=package_root,
        directive_id=directive_id,
        directive_text=draft_text,
        clarified_intent_summary=clarified_summary,
        bootstrap_context=build_active_line_bootstrap_context(package_root),
        trusted_sources=[
            "local_repo:novali-v7",
            "local_artifacts:novali-v7/data",
            "local_logs:logs",
            "trusted_benchmark_pack_v1",
        ],
        success_criteria=[
            "operator reviews the promoted draft before selecting it as the active directive",
            "bootstrap readiness validates the formal wrapper before any launch",
            "governed execution remains blocked unless existing readiness and review gates pass",
        ],
        human_approval_points=[
            "operator explicitly selects this pending directive candidate",
            "operator starts bootstrap or governed execution through existing shell controls",
            "any branch-state, policy, resource, or protected-surface change remains review-gated",
        ],
        stop_conditions=[
            "operator rejects or abandons the pending draft",
            "directive validation fails",
            "bootstrap or governed readiness reports blocking review/intervention state",
        ],
    )
    directive_payload["llm_draft_promotion"] = {
        "schema_name": LLM_PENDING_DIRECTIVE_SCHEMA_NAME,
        "schema_version": LLM_PENDING_DIRECTIVE_SCHEMA_VERSION,
        "promotion_state": "pending_operator_approval",
        "created_at": created_at,
        "source_record_id": str(record.get("record_id", "")),
        "source_context_bundle_id": str(record.get("context_bundle_id", "")),
        "source_provider": str(record.get("provider", "")),
        "source_model": str(record.get("model", "")),
        "prompt_summary_redacted": prompt_summary,
        "operator_note_redacted": _truncate_text(redact_value(operator_note), 1200),
        "capability_boundary": (
            "This candidate was created from redacted LLM draft evidence. It is not selected, "
            "approved, launched, or active until the operator uses the existing directive and "
            "launch controls."
        ),
    }

    pending_dir = Path(directive_root) / "pending_llm"
    pending_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = pending_dir / f"{directive_id}.json"
    candidate_path.write_text(_json_dump(directive_payload) + "\n", encoding="utf-8")

    evidence = {
        "schema_name": LLM_PENDING_DIRECTIVE_SCHEMA_NAME,
        "schema_version": LLM_PENDING_DIRECTIVE_SCHEMA_VERSION,
        "promotion_id": f"promotion-{candidate_id}",
        "created_at": created_at,
        "status": "pending_operator_approval",
        "candidate_id": candidate_id,
        "candidate_directive_id": directive_id,
        "candidate_path_hint": str(candidate_path),
        "source_record_id": str(record.get("record_id", "")),
        "source_context_bundle_id": str(record.get("context_bundle_id", "")),
        "source_record_path_hint": str(record.get("record_path_hint", "")),
        "prompt_summary_redacted": prompt_summary,
        "assistant_response_summary_redacted": _truncate_text(draft_text, 2400),
        "provider": str(record.get("provider", "")),
        "model": str(record.get("model", "")),
        "operator_note_redacted": _truncate_text(redact_value(operator_note), 1200),
        "redaction_notes": [
            "Promoted directive candidate contains redacted LLM draft text only.",
            "Promotion does not select, approve, launch, or mutate active directive state.",
        ],
        "required_operator_approval": [
            "review the candidate directive JSON",
            "select it through the existing Load Directive control if acceptable",
            "start bootstrap/governed execution only through existing readiness-gated controls",
        ],
    }
    evidence = _redact_pending_evidence_for_display(evidence)
    evidence["redaction_status"] = _redaction_status(
        {"draft_text": draft_text, "operator_note": operator_note},
        {"draft_text": evidence.get("assistant_response_summary_redacted", ""), "operator_note": evidence.get("operator_note_redacted", "")},
    )
    root = llm_pending_directive_root(operator_root)
    root.mkdir(parents=True, exist_ok=True)
    evidence_path = root / f"{evidence.get('promotion_id', 'promotion')}.json"
    evidence_path.write_text(_json_dump(evidence) + "\n", encoding="utf-8")
    evidence["evidence_path_hint"] = str(evidence_path)

    return {
        "ok": True,
        "status": "pending_operator_approval",
        "message": "LLM draft promoted to a pending directive candidate.",
        "candidate_id": candidate_id,
        "candidate_directive_id": directive_id,
        "candidate_path": str(candidate_path),
        "evidence_path": str(evidence_path),
        "source_record_id": str(record.get("record_id", "")),
        "redaction_status": str(evidence.get("redaction_status", "")),
        "approval_required": True,
        "launch_performed": False,
        "active_directive_mutated": False,
        "next_operator_action": "Review the candidate, then select it with the existing Load Directive control if acceptable.",
    }


def load_pending_directive_promotions(operator_root: str | Path, *, limit: int = 25) -> dict[str, Any]:
    root = llm_pending_directive_root(operator_root)
    records: list[dict[str, Any]] = []
    if root.is_dir():
        files = sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        for path in files[: max(1, limit)]:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                payload = _redact_pending_evidence_for_display(payload)
                payload["evidence_path_hint"] = str(path)
                records.append(payload)
    return {
        "schema_name": LLM_PENDING_DIRECTIVE_LIST_SCHEMA_NAME,
        "schema_version": LLM_PENDING_DIRECTIVE_LIST_SCHEMA_VERSION,
        "generated_at": _now(),
        "promotion_root_hint": str(root),
        "records": records,
    }


def load_llm_history(operator_root: str | Path, *, limit: int = 25) -> dict[str, Any]:
    root = llm_chat_root(operator_root)
    records: list[dict[str, Any]] = []
    if root.is_dir():
        files = sorted(root.glob("chat-*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        for path in files[: max(1, limit)]:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                payload = _redact_chat_record_for_display(payload)
                payload["record_path_hint"] = str(path)
                records.append(payload)
    return {
        "schema_name": LLM_HISTORY_SCHEMA_NAME,
        "schema_version": LLM_HISTORY_SCHEMA_VERSION,
        "generated_at": _now(),
        "history_root_hint": str(root),
        "records": records,
    }


__all__ = [
    "DEFAULT_OLLAMA_BASE_URL",
    "DEFAULT_OLLAMA_MODEL",
    "LLM_CHAT_RECORD_SCHEMA_NAME",
    "LLM_CONTEXT_SCHEMA_NAME",
    "MAX_PROMPT_CHARS",
    "SUPPORTED_LLM_MODES",
    "build_llm_context_bundle",
    "build_llm_status_payload",
    "chat_with_ollama",
    "configured_ollama_model",
    "load_llm_chat_record",
    "load_llm_history",
    "load_pending_directive_promotions",
    "llm_chat_root",
    "llm_pending_directive_root",
    "promote_llm_draft_to_pending_directive",
    "record_llm_chat_rejection",
    "validate_llm_chat_request",
]
