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
LOCAL_CODING_ASSIST_QWEN_SCHEMA_NAME = "NovaliLocalCodingAssistQwenResult"
LOCAL_CODING_ASSIST_QWEN_SCHEMA_VERSION = "novali_local_coding_assist_qwen_result_v1"

DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "qwen3.6:35b-a3b"
DEFAULT_OLLAMA_NUM_CTX = 16384
LOCAL_LLM_PROVIDER = "ollama"
LOCAL_LLM_PROVIDER_ROLE = "local_coding_assist"
LOCAL_LLM_CAPABILITY_BOUNDARY = "explain_draft_and_local_coding_evidence_only"
SUPPORTED_LLM_MODES = ("explain_state", "draft_directive", "draft_plan")
MAX_PROMPT_CHARS = 4000
MAX_ASSISTANT_CHARS = 12000
MAX_CONTEXT_JSON_CHARS = 16000
MAX_PENDING_DIRECTIVE_TEXT_CHARS = 8000
MAX_CODING_ASSIST_CONTEXT_FILES = 8
MAX_CODING_ASSIST_FILE_CHARS = 6000
MAX_CODING_ASSIST_TOTAL_CHARS = 30000
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 600.0
DEFAULT_OLLAMA_TEMPERATURE = 0.2
DEFAULT_DRAFT_DIRECTIVE_TEMPERATURE = 0.1
DEFAULT_DRAFT_DIRECTIVE_TOP_P = 0.9
DEFAULT_DRAFT_DIRECTIVE_REPEAT_PENALTY = 1.1
DEFAULT_DRAFT_DIRECTIVE_NUM_PREDICT = 1024
MAX_MALFORMED_REPAIR_ATTEMPTS = 3
DRAFT_DIRECTIVE_REQUIRED_HEADINGS = (
    "DIRECTIVE:",
    "Mission:",
    "Objectives:",
    "Deliverables:",
    "Success Criteria:",
    "Stop Conditions:",
)
SAFE_RECORD_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
UNSAFE_CODING_ASSIST_PATH_PARTS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    "operator_state",
    "runtime_data",
    "runtime",
    "logs",
    "dist",
    "build",
    ".pytest_cache",
}
SECRETISH_CODING_ASSIST_PATH_TOKENS = (
    "secret",
    "credential",
    "credentials",
    "token",
    "apikey",
    "api_key",
    "password",
)


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


def configured_ollama_num_ctx() -> int:
    try:
        parsed = int(str(os.environ.get("NOVALI_LOCAL_LLM_NUM_CTX") or "").strip())
    except (TypeError, ValueError):
        parsed = 0
    return parsed if parsed > 0 else DEFAULT_OLLAMA_NUM_CTX


def configured_ollama_timeout_seconds() -> float:
    return _coerce_float(
        os.environ.get("NOVALI_LOCAL_LLM_TIMEOUT_SECONDS"),
        DEFAULT_OLLAMA_TIMEOUT_SECONDS,
    )


def llm_chat_root(operator_root: str | Path) -> Path:
    return Path(operator_root) / "llm_chat"


def llm_pending_directive_root(operator_root: str | Path) -> Path:
    return Path(operator_root) / "llm_pending_directives"


def local_coding_assist_qwen_root(operator_root: str | Path) -> Path:
    return Path(operator_root) / "autonomy"


def _ollama_model_family(model: str) -> str:
    clean = str(model or "").strip().lower()
    if clean.startswith("qwen3.6"):
        return "qwen3.6"
    if ":" in clean:
        return clean.split(":", 1)[0]
    return clean


def _draft_directive_format_contract() -> str:
    return (
        "Draft directive acceptance contract:\n"
        "Return only the directive draft.\n"
        "Do not return JSON.\n"
        "Do not wrap the response in labels such as [DRAFT DIRECTIVE PAYLOAD].\n"
        "Build the directive skeleton first.\n"
        "Keep the complete draft under 900 words.\n"
        "Use concise bounded bullets.\n"
        "Use these exact required headings in this order:\n"
        f"{DRAFT_DIRECTIVE_REQUIRED_HEADINGS[0]} <short directive title>\n\n"
        "Mission:\n"
        "<one concise mission paragraph>\n\n"
        "Objectives:\n"
        "1. <objective>\n\n"
        "Deliverables:\n"
        "1. <deliverable>\n\n"
        "Success Criteria:\n"
        "1. <criterion>\n\n"
        "Stop Conditions:\n"
        "- <condition>\n\n"
        "The draft will be rejected if any required heading is missing."
    )


def _directive_draft_completeness(draft_text: str) -> dict[str, Any]:
    draft = str(draft_text or "").strip()
    lower = draft.lower()
    checks = (
        (
            "missing_directive_title",
            bool(re.search(r"directive\s*:", draft, re.IGNORECASE))
            or bool(re.search(r"^#?\s*directive\b", draft, re.IGNORECASE)),
        ),
        ("missing_mission", "mission" in lower),
        ("missing_objectives", "objectives" in lower),
        ("missing_deliverables", "deliverables" in lower),
        ("missing_success_criteria", "success criteria" in lower),
        ("missing_stop_conditions", "stop conditions" in lower),
    )
    reasons = [reason for reason, passed in checks if not passed]
    trailing_fragments = (
        "document assumptions",
        "major scope expansion,",
        "and",
        "or",
    )
    trimmed = draft.lower()
    if any(trimmed.endswith(fragment) for fragment in trailing_fragments):
        reasons.append("appears_truncated")
    return {
        "complete": not reasons,
        "reasons": reasons,
    }


def _first_present_mapping_value(payload: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _format_directive_section_value(value: Any, *, bullets: bool = False) -> str:
    if isinstance(value, list):
        lines: list[str] = []
        for index, item in enumerate(value, start=1):
            text = _format_directive_section_value(item)
            if not text:
                continue
            prefix = "-" if bullets else f"{index}."
            lines.append(f"{prefix} {text}")
        return "\n".join(lines).strip()
    if isinstance(value, Mapping):
        return _compact_json(value)
    return str(value or "").strip()


def _extract_json_mapping_from_directive_response(draft_text: str) -> dict[str, Any]:
    text = str(draft_text or "").strip()
    if not text:
        return {}
    candidates = [text]
    first = text.find("{")
    last = text.rfind("}")
    if 0 <= first < last:
        candidates.append(text[first : last + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if isinstance(parsed, Mapping):
            return dict(parsed)
    return {}


def _render_json_directive_payload(payload: Mapping[str, Any]) -> str:
    title = _first_present_mapping_value(
        payload,
        ("directive_title", "title", "name", "directive_id"),
    )
    mission = _first_present_mapping_value(payload, ("mission", "objective"))
    objectives = _first_present_mapping_value(payload, ("objectives", "goals"))
    deliverables = _first_present_mapping_value(
        payload,
        ("deliverables", "expected_deliverables", "outputs", "expected_outputs"),
    )
    success_criteria = _first_present_mapping_value(
        payload,
        ("success_criteria", "acceptance_criteria", "acceptance_thresholds"),
    )
    stop_conditions = _first_present_mapping_value(
        payload,
        ("stop_conditions", "safety_stop_conditions", "kill_conditions"),
    )
    required_values = (
        title,
        mission,
        objectives,
        deliverables,
        success_criteria,
        stop_conditions,
    )
    if any(value in (None, "", [], {}) for value in required_values):
        return ""
    return "\n\n".join(
        (
            f"DIRECTIVE: {_format_directive_section_value(title)}",
            f"Mission:\n{_format_directive_section_value(mission)}",
            f"Objectives:\n{_format_directive_section_value(objectives)}",
            f"Deliverables:\n{_format_directive_section_value(deliverables)}",
            f"Success Criteria:\n{_format_directive_section_value(success_criteria)}",
            f"Stop Conditions:\n{_format_directive_section_value(stop_conditions, bullets=True)}",
        )
    ).strip()


def _prepare_directive_draft_response(assistant_text: str) -> tuple[str, dict[str, Any]]:
    draft_text = str(assistant_text or "").strip()
    draft_format = "plain_text"
    normalized_from_json = False
    json_payload = _extract_json_mapping_from_directive_response(draft_text)
    if json_payload:
        rendered = _render_json_directive_payload(json_payload)
        if rendered:
            draft_text = rendered
            draft_format = "normalized_json"
            normalized_from_json = True
        else:
            draft_format = "json_unusable"
    completeness = _directive_draft_completeness(draft_text)
    missing_sections = list(completeness.get("reasons", []) or [])
    metadata = {
        "directive_draft_complete": bool(completeness.get("complete", False)),
        "directive_draft_missing_sections": missing_sections,
        "directive_draft_format": draft_format,
        "directive_draft_normalized_from_json": normalized_from_json,
        "format_warning": ""
        if bool(completeness.get("complete", False))
        else "directive_draft_missing_required_sections",
    }
    return draft_text, metadata


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
    model_family = _ollama_model_family(configured_model)
    return {
        "schema_name": LLM_STATUS_SCHEMA_NAME,
        "schema_version": LLM_STATUS_SCHEMA_VERSION,
        "generated_at": _now(),
        "provider": LOCAL_LLM_PROVIDER,
        "provider_role": LOCAL_LLM_PROVIDER_ROLE,
        "provider_base_url": provider_base_url,
        "model": configured_model,
        "model_family": model_family,
        "context_window_tokens": configured_ollama_num_ctx(),
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
        "capability_boundary": LOCAL_LLM_CAPABILITY_BOUNDARY,
    }


def _system_prompt(mode: str) -> str:
    mode_instruction = {
        "explain_state": "Explain current state, blockers, and safe operator next steps.",
        "draft_directive": "Draft directive wording only. Do not present it as approved or active.",
        "draft_plan": "Draft a safe next-step plan only. Do not claim execution authority.",
    }.get(mode, "Explain or draft within the supplied boundary.")
    prompt = (
        "You are Novali's local operator assistant. You receive only curated, redacted "
        "backend context. You may explain state, identify blockers, and draft operator "
        "text. You must not claim you launched, approved, continued, paused, resumed, "
        "stopped, wrote files, changed directives, bypassed review, or mutated Novali "
        f"state. Current mode: {mode}. {mode_instruction}"
    )
    if str(mode or "").strip() == "draft_directive":
        prompt = f"{prompt}\n\n{_draft_directive_format_contract()}"
    return prompt


def _num_predict_for_mode(mode: str) -> int:
    clean_mode = str(mode or "").strip()
    if clean_mode == "draft_directive":
        return DEFAULT_DRAFT_DIRECTIVE_NUM_PREDICT
    if clean_mode == "draft_plan":
        return 2048
    if clean_mode == "local_coding_assist":
        return 4096
    return 768


def _ollama_options_for_mode(mode: str) -> dict[str, Any]:
    clean_mode = str(mode or "").strip()
    options: dict[str, Any] = {
        "temperature": DEFAULT_OLLAMA_TEMPERATURE,
        "num_predict": _num_predict_for_mode(clean_mode),
        "num_ctx": configured_ollama_num_ctx(),
    }
    if clean_mode == "draft_directive":
        options.update(
            {
                "temperature": DEFAULT_DRAFT_DIRECTIVE_TEMPERATURE,
                "top_p": DEFAULT_DRAFT_DIRECTIVE_TOP_P,
                "repeat_penalty": DEFAULT_DRAFT_DIRECTIVE_REPEAT_PENALTY,
            }
        )
    return options


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
    directive_draft_metadata: Mapping[str, Any] | None = None,
    created_at: str | None = None,
    record_id: str | None = None,
    started_at: str | None = None,
    finalized_at: str | None = None,
    llm_request_state: str = "finalized",
    request_options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    context_id = str(dict(context_bundle or {}).get("context_bundle_id", ""))
    created_at = created_at or _now()
    original_record = {
        "schema_name": LLM_CHAT_RECORD_SCHEMA_NAME,
        "schema_version": LLM_CHAT_RECORD_SCHEMA_VERSION,
        "record_id": "",
        "created_at": created_at,
        "started_at": started_at or created_at,
        "finalized_at": finalized_at or "",
        "llm_request_state": llm_request_state,
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
        "llm_request_options": dict(request_options or {}),
        "redaction_notes": [
            "Record contains redacted prompt and assistant summaries only.",
            "Raw directive bodies, secrets, credential files, and full logs are not stored.",
        ],
    }
    if directive_draft_metadata:
        original_record.update(dict(directive_draft_metadata))
    redacted = _redact_payload(original_record)
    if not isinstance(redacted, dict):
        redacted = {"schema_name": LLM_CHAT_RECORD_SCHEMA_NAME, "created_at": created_at}
    redacted["redaction_status"] = _redaction_status(original_record, redacted)
    record_id = record_id or f"chat-{created_at.replace(':', '').replace('.', '')}-{_hash_payload(redacted, length=10)}"
    redacted["record_id"] = record_id
    root = llm_chat_root(operator_root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{record_id}.json"
    path.write_text(_json_dump(redacted) + "\n", encoding="utf-8")
    redacted["record_path_hint"] = str(path)
    return redacted


def _ollama_response_shape(payload: Mapping[str, Any]) -> dict[str, Any]:
    message = payload.get("message")
    return {
        "top_level_keys": sorted(str(key) for key in payload.keys()),
        "message_keys": sorted(str(key) for key in message.keys()) if isinstance(message, Mapping) else [],
        "message_type": type(message).__name__ if message is not None else "missing",
    }


def _strip_thinking_blocks(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL)
    return text.strip()


def _llm_attempt_progress(
    *,
    attempt_index: int,
    max_repair_attempts: int,
    phase: str,
    latest_repair_feedback: str = "",
) -> dict[str, Any]:
    total_attempts = max_repair_attempts + 1
    clean_phase = str(phase or "").strip() or "attempt"
    if clean_phase in {"completed", "failed"}:
        percent = 100
    else:
        percent = min(95, max(5, int(round(((attempt_index - 1) / max(1, total_attempts)) * 80 + 10))))
    return {
        "current_attempt_index": attempt_index,
        "max_repair_attempts": max_repair_attempts,
        "malformed_retry_count": max(0, attempt_index - 1),
        "llm_progress_phase": clean_phase,
        "llm_progress_percent": percent,
        "latest_repair_feedback": latest_repair_feedback,
    }


def _malformed_repair_feedback(reason: str) -> str:
    clean = str(reason or "").strip() or "malformed_response"
    if clean == "empty_message_content":
        return (
            "previous attempt returned empty message.content; return the final answer in "
            "message.content only; do not place the answer in thinking."
        )
    if clean == "thinking_only_content":
        return (
            "previous attempt placed only thinking text in the answer; return only the final "
            "operator-facing answer in message.content."
        )
    if clean == "malformed_json":
        return "previous attempt returned malformed JSON; return a valid Ollama chat message with message.content."
    return f"previous attempt failed with {clean}; return the final answer in message.content only."


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
            "/no_think\n"
            f"Mode: {clean_mode}\n"
            f"Operator message:\n{redact_value(clean_message)}\n\n"
            f"Curated Novali context JSON:\n{context_json}"
        )
        if clean_mode == "draft_directive":
            user_prompt = f"{_draft_directive_format_contract()}\n\n{user_prompt}"
        request_payload = {
            "model": configured_model,
            "stream": False,
            "messages": [
                {"role": "system", "content": _system_prompt(clean_mode)},
                {"role": "user", "content": user_prompt},
            ],
            "options": _ollama_options_for_mode(clean_mode),
            "think": False,
        }
        request_options = dict(request_payload.get("options", {}))
        started_at = _now()
        max_repair_attempts = MAX_MALFORMED_REPAIR_ATTEMPTS
        attempt_records: list[dict[str, Any]] = []
        progress_metadata = _llm_attempt_progress(
            attempt_index=1,
            max_repair_attempts=max_repair_attempts,
            phase="starting",
        )
        started_record = _record_chat(
            operator_root=operator_root,
            message=clean_message,
            mode=clean_mode,
            context_bundle=redacted_context if isinstance(redacted_context, Mapping) else {},
            assistant_text="",
            provider=LOCAL_LLM_PROVIDER,
            model=configured_model,
            status="in_progress",
            latency_ms=0.0,
            refusal_or_limitation_notes=[
                "Local LLM request has started; final output is not available yet.",
                "The response did not execute or mutate Novali state.",
            ],
            created_at=started_at,
            started_at=started_at,
            llm_request_state="in_progress",
            request_options=request_options,
            directive_draft_metadata={
                **progress_metadata,
                "llm_attempts": attempt_records,
            },
        )
        started = time.perf_counter()
        deadline_started = time.monotonic()
        overall_timeout = (
            float(timeout_seconds)
            if timeout_seconds is not None
            else float(configured_ollama_timeout_seconds())
        )
        status = "error"
        assistant_text = ""
        error_type = ""
        error_summary = ""
        directive_draft_metadata: dict[str, Any] = {}
        limitation_notes = [
            "Local LLM output is explain-and-draft evidence only.",
            "The response did not execute or mutate Novali state.",
        ]
        latest_repair_feedback = ""
        latest_malformed_shape: dict[str, Any] = {}
        for attempt_index in range(1, max_repair_attempts + 2):
            progress_phase = "attempt" if attempt_index == 1 else "repair_attempt"
            progress_metadata = _llm_attempt_progress(
                attempt_index=attempt_index,
                max_repair_attempts=max_repair_attempts,
                phase=progress_phase,
                latest_repair_feedback=latest_repair_feedback,
            )
            _record_chat(
                operator_root=operator_root,
                message=clean_message,
                mode=clean_mode,
                context_bundle=redacted_context if isinstance(redacted_context, Mapping) else {},
                assistant_text="",
                provider=LOCAL_LLM_PROVIDER,
                model=configured_model,
                status="in_progress",
                latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
                refusal_or_limitation_notes=limitation_notes,
                created_at=str(started_record.get("created_at", started_at)),
                record_id=str(started_record.get("record_id", "")),
                started_at=str(started_record.get("started_at", started_at)),
                llm_request_state="in_progress",
                request_options=request_options,
                directive_draft_metadata={
                    **progress_metadata,
                    "llm_attempts": attempt_records,
                },
            )
            remaining_timeout = max(0.001, overall_timeout - (time.monotonic() - deadline_started))
            attempt_payload = dict(request_payload)
            attempt_messages = list(request_payload["messages"])
            if latest_repair_feedback:
                attempt_messages.append(
                    {
                        "role": "user",
                        "content": (
                            "/no_think\n"
                            "Repair feedback for the previous malformed response:\n"
                            f"{latest_repair_feedback}\n\n"
                            "Return only the final operator-facing answer in message.content."
                        ),
                    }
                )
            attempt_payload["messages"] = attempt_messages
            try:
                request = urllib.request.Request(
                    f"{provider_base_url}/api/chat",
                    data=json.dumps(attempt_payload).encode("utf-8"),
                    method="POST",
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                )
                with urllib.request.urlopen(request, timeout=remaining_timeout) as response:
                    raw = response.read().decode("utf-8")
                payload = json.loads(raw or "{}")
                if not isinstance(payload, Mapping):
                    raise TypeError("Ollama response was not an object.")
                message_payload = payload.get("message")
                if not isinstance(message_payload, Mapping):
                    message_payload = {}
                raw_content = str(message_payload.get("content", "") or "")
                assistant_text = _strip_thinking_blocks(raw_content)
                latest_malformed_shape = _ollama_response_shape(payload)
                if not assistant_text:
                    malformed_reason = "empty_message_content" if not raw_content.strip() else "thinking_only_content"
                    latest_repair_feedback = _malformed_repair_feedback(malformed_reason)
                    attempt_records.append(
                        {
                            "attempt_index": attempt_index,
                            "status": "malformed_response",
                            "malformed_reason": malformed_reason,
                            "response_shape": latest_malformed_shape,
                            "content_present": bool(raw_content.strip()),
                            "thinking_present": bool(str(message_payload.get("thinking", "") or "").strip()),
                        }
                    )
                    status = "malformed_response"
                    error_type = "malformed_response"
                    error_summary = "Local Ollama response did not contain message.content."
                    if attempt_index <= max_repair_attempts:
                        continue
                    assistant_text = ""
                    break
                status = "completed"
                assistant_text = _truncate_text(
                    redact_value(assistant_text),
                    MAX_ASSISTANT_CHARS,
                )
                if clean_mode == "draft_directive":
                    assistant_text, directive_draft_metadata = _prepare_directive_draft_response(
                        assistant_text
                    )
                    assistant_text = _truncate_text(assistant_text, MAX_ASSISTANT_CHARS)
                attempt_records.append(
                    {
                        "attempt_index": attempt_index,
                        "status": "completed",
                        "response_shape": latest_malformed_shape,
                        "content_present": True,
                        "thinking_present": bool(str(message_payload.get("thinking", "") or "").strip()),
                    }
                )
                error_type = ""
                error_summary = ""
                break
            except (TimeoutError, socket.timeout):
                status = "timeout"
                error_type = "timeout"
                error_summary = "Timed out while waiting for local Ollama chat response."
                assistant_text = "Local Ollama did not respond before the timeout."
                attempt_records.append({"attempt_index": attempt_index, "status": "timeout"})
                break
            except (urllib.error.URLError, ConnectionError, OSError) as exc:
                status = "unavailable"
                error_type = type(exc).__name__
                error_summary = str(exc)
                assistant_text = "Local Ollama is unavailable. Start Ollama and try again."
                attempt_records.append({"attempt_index": attempt_index, "status": "unavailable"})
                break
            except json.JSONDecodeError:
                status = "malformed_response"
                error_type = "JSONDecodeError"
                error_summary = "Local Ollama returned a malformed response."
                latest_repair_feedback = _malformed_repair_feedback("malformed_json")
                attempt_records.append(
                    {
                        "attempt_index": attempt_index,
                        "status": "malformed_response",
                        "malformed_reason": "malformed_json",
                        "response_shape": {"top_level_keys": [], "message_keys": [], "message_type": "unparsed"},
                    }
                )
                if attempt_index <= max_repair_attempts:
                    continue
                assistant_text = "Local Ollama returned a malformed response."
                break
            except (TypeError, ValueError) as exc:
                status = "malformed_response"
                error_type = type(exc).__name__
                error_summary = "Local Ollama returned a malformed response."
                latest_repair_feedback = _malformed_repair_feedback(type(exc).__name__)
                attempt_records.append(
                    {
                        "attempt_index": attempt_index,
                        "status": "malformed_response",
                        "malformed_reason": type(exc).__name__,
                        "response_shape": {"top_level_keys": [], "message_keys": [], "message_type": "invalid"},
                    }
                )
                if attempt_index <= max_repair_attempts:
                    continue
                assistant_text = "Local Ollama returned a malformed response."
                break
        latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
        final_phase = "completed" if status == "completed" else "failed"
        progress_metadata = _llm_attempt_progress(
            attempt_index=max(1, len(attempt_records)),
            max_repair_attempts=max_repair_attempts,
            phase=final_phase,
            latest_repair_feedback=latest_repair_feedback,
        )
        directive_draft_metadata.update(
            {
                **progress_metadata,
                "llm_attempts": attempt_records,
            }
        )
        if latest_malformed_shape and status == "malformed_response":
            directive_draft_metadata["ollama_response_shape"] = latest_malformed_shape
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
            directive_draft_metadata=directive_draft_metadata,
            created_at=str(started_record.get("created_at", started_at)),
            record_id=str(started_record.get("record_id", "")),
            started_at=str(started_record.get("started_at", started_at)),
            finalized_at=_now(),
            llm_request_state="finalized",
            request_options=request_options,
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
            **directive_draft_metadata,
        }


def _coding_assist_rejection_reason(path_value: str) -> str:
    clean = str(path_value or "").strip().replace("\\", "/")
    if not clean:
        return "empty_path"
    path = Path(clean)
    if path.is_absolute() or re.match(r"^[A-Za-z]:/", clean):
        return "absolute_paths_are_rejected"
    parts = [part for part in clean.split("/") if part]
    if any(part == ".." for part in parts):
        return "path_traversal_is_rejected"
    lowered_parts = [part.lower() for part in parts]
    if any(part in UNSAFE_CODING_ASSIST_PATH_PARTS for part in lowered_parts):
        return "runtime_or_vcs_paths_are_rejected"
    if any(part == ".env" or part.startswith(".env.") for part in lowered_parts):
        return "env_files_are_rejected"
    lowered_path = "/".join(lowered_parts)
    if any(token in lowered_path for token in SECRETISH_CODING_ASSIST_PATH_TOKENS):
        return "credential_like_paths_are_rejected"
    return ""


def _safe_package_relative_path(package_root: Path, path_value: str) -> tuple[Path | None, str]:
    reason = _coding_assist_rejection_reason(path_value)
    if reason:
        return None, reason
    candidate = package_root / str(path_value).strip().replace("\\", "/")
    try:
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(package_root.resolve(strict=False))
    except (OSError, ValueError):
        return None, "path_outside_package_root"
    return resolved, ""


def _collect_coding_assist_snippets(
    *,
    package_root: Path,
    context_paths: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    snippets: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    total_chars = 0
    seen_paths: set[str] = set()
    for raw_path in context_paths:
        if len(snippets) >= MAX_CODING_ASSIST_CONTEXT_FILES:
            rejected.append({"path": str(raw_path), "reason": "max_file_count_reached"})
            continue
        safe_path, reason = _safe_package_relative_path(package_root, str(raw_path))
        if reason or safe_path is None:
            rejected.append({"path": str(raw_path), "reason": reason or "unsafe_path"})
            continue
        try:
            relative_path = safe_path.relative_to(package_root.resolve(strict=False)).as_posix()
        except (OSError, ValueError):
            rejected.append({"path": str(raw_path), "reason": "path_outside_package_root"})
            continue
        if relative_path in seen_paths:
            continue
        seen_paths.add(relative_path)
        try:
            content = safe_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            rejected.append({"path": relative_path, "reason": "unreadable_or_missing"})
            continue
        remaining = MAX_CODING_ASSIST_TOTAL_CHARS - total_chars
        if remaining <= 0:
            rejected.append({"path": relative_path, "reason": "max_total_chars_reached"})
            continue
        limit = min(MAX_CODING_ASSIST_FILE_CHARS, remaining)
        snippet = _truncate_text(redact_value(content), limit)
        total_chars += len(snippet)
        snippets.append(
            {
                "path": relative_path,
                "char_count": len(snippet),
                "truncated": len(str(content)) > limit,
                "content_redacted": snippet,
            }
        )
    return snippets, rejected


def _normalize_coding_assist_list(value: Any, *, limit: int = 12) -> list[str]:
    if isinstance(value, list):
        return [_truncate_text(redact_value(item), 1600) for item in value[:limit]]
    if value in (None, ""):
        return []
    return [_truncate_text(redact_value(value), 1600)]


def _parse_coding_assist_json(text: str) -> dict[str, Any]:
    clean = str(text or "").strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\s*```$", "", clean)
    payload = json.loads(clean or "{}")
    if not isinstance(payload, dict):
        raise ValueError("coding assist response must be a JSON object")
    return {
        "summary": _truncate_text(redact_value(payload.get("summary", "")), 2400),
        "implementation_steps": _normalize_coding_assist_list(payload.get("implementation_steps")),
        "patch_suggestions": _normalize_coding_assist_list(payload.get("patch_suggestions")),
        "test_plan": _normalize_coding_assist_list(payload.get("test_plan")),
        "risk_notes": _normalize_coding_assist_list(payload.get("risk_notes")),
        "external_research_needed": bool(payload.get("external_research_needed", False)),
    }


def _persist_local_coding_assist_qwen_result(
    *,
    operator_root: str | Path,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    root = local_coding_assist_qwen_root(operator_root)
    ledger_root = root / "ledgers"
    root.mkdir(parents=True, exist_ok=True)
    ledger_root.mkdir(parents=True, exist_ok=True)
    redacted = _redact_payload(dict(evidence))
    if not isinstance(redacted, dict):
        redacted = {"schema_name": LOCAL_CODING_ASSIST_QWEN_SCHEMA_NAME, "status": "completed_with_warnings"}
    redacted["redaction_status"] = _redaction_status(evidence, redacted)
    if not str(redacted.get("result_id", "") or "").strip():
        redacted["result_id"] = f"qwenassist-{_hash_payload(redacted, length=12)}"
    latest_path = root / "local_coding_assist_qwen_latest.json"
    ledger_path = ledger_root / "local_coding_assist_qwen_results.jsonl"
    latest_path.write_text(_json_dump(redacted) + "\n", encoding="utf-8")
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(_compact_json(redacted) + "\n")
    redacted["evidence_path_hint"] = str(latest_path)
    redacted["ledger_path_hint"] = str(ledger_path)
    return redacted


def run_local_coding_assist_qwen(
    *,
    operator_root: str | Path,
    package_root: str | Path,
    objective: str,
    context_bundle: Mapping[str, Any] | None = None,
    context_paths: list[str] | None = None,
    operation_id: str = "",
    base_url: str | None = None,
    model: str | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    provider_base_url = (base_url or configured_ollama_base_url()).rstrip("/")
    configured_model = model or configured_ollama_model()
    package_path = Path(package_root)
    clean_objective = _truncate_text(redact_value(objective), 2000)
    snippets, rejected_paths = _collect_coding_assist_snippets(
        package_root=package_path,
        context_paths=[str(item) for item in list(context_paths or [])],
    )
    warnings: list[str] = []
    if not snippets:
        warnings.append("empty_local_context")
    redacted_context = _redact_payload(dict(context_bundle or {}))
    context_json = _truncate_text(_json_dump(redacted_context), MAX_CONTEXT_JSON_CHARS)
    snippets_json = _truncate_text(_json_dump(snippets), MAX_CODING_ASSIST_TOTAL_CHARS + 2000)
    user_prompt = (
        "Objective:\n"
        f"{clean_objective}\n\n"
        "Curated Novali context JSON:\n"
        f"{context_json}\n\n"
        "Safe package-relative file snippets JSON:\n"
        f"{snippets_json}\n\n"
        "Return only JSON with keys: summary, implementation_steps, "
        "patch_suggestions, test_plan, risk_notes, external_research_needed."
    )
    request_payload = {
        "model": configured_model,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are Novali's local Qwen coding advisor. Use only the supplied "
                    "redacted local context and file snippets. Produce reviewable evidence "
                    "only; do not claim authority to edit files, run commands, launch governed "
                    "execution, approve directives, or replace external trusted-source research. "
                    "Return strict JSON and no markdown."
                ),
            },
            {"role": "user", "content": user_prompt},
        ],
        "options": _ollama_options_for_mode("local_coding_assist"),
    }
    started = time.perf_counter()
    parsed: dict[str, Any] = {
        "summary": "",
        "implementation_steps": [],
        "patch_suggestions": [],
        "test_plan": [],
        "risk_notes": [],
        "external_research_needed": False,
    }
    ok = False
    warning_type = ""
    error_type = ""
    error_summary = ""
    try:
        request = urllib.request.Request(
            f"{provider_base_url}/api/chat",
            data=json.dumps(request_payload).encode("utf-8"),
            method="POST",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(
            request,
            timeout=timeout_seconds
            if timeout_seconds is not None
            else configured_ollama_timeout_seconds(),
        ) as response:
            raw = response.read().decode("utf-8")
        payload = json.loads(raw or "{}")
        assistant_text = str(dict(payload.get("message", {}) or {}).get("content", "") or "").strip()
        if not assistant_text:
            raise ValueError("Local Qwen response did not contain message.content")
        parsed = _parse_coding_assist_json(assistant_text)
        ok = True
    except (TimeoutError, socket.timeout):
        warning_type = "timeout"
        error_type = "timeout"
        error_summary = "Timed out while waiting for local Qwen coding assist response."
    except (urllib.error.URLError, ConnectionError, OSError) as exc:
        warning_type = "unavailable"
        error_type = type(exc).__name__
        error_summary = str(exc)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        warning_type = "malformed_response"
        error_type = type(exc).__name__
        error_summary = "Local Qwen coding assist response was not valid JSON."
    status = "completed" if ok and snippets else "completed_with_warnings"
    if warning_type and warning_type not in warnings:
        warnings.append(warning_type)
    if ok and not snippets and "empty_local_context" not in warnings:
        warnings.append("empty_local_context")
    latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
    evidence = {
        "schema_name": LOCAL_CODING_ASSIST_QWEN_SCHEMA_NAME,
        "schema_version": LOCAL_CODING_ASSIST_QWEN_SCHEMA_VERSION,
        "created_at": _now(),
        "result_id": "",
        "operation_id": str(operation_id or ""),
        "provider": LOCAL_LLM_PROVIDER,
        "provider_role": LOCAL_LLM_PROVIDER_ROLE,
        "provider_base_url": provider_base_url,
        "model": configured_model,
        "model_family": _ollama_model_family(configured_model),
        "context_window_tokens": configured_ollama_num_ctx(),
        "capability_boundary": LOCAL_LLM_CAPABILITY_BOUNDARY,
        "authority_boundary": (
            "Local Qwen coding assist produces redacted review evidence only. "
            "It does not edit protected roots, run commands, launch governed execution, "
            "approve directives, or replace external trusted-source research."
        ),
        "protected_root_write_allowed": False,
        "ok": ok,
        "status": status,
        "warning_type": warning_type,
        "warnings": warnings,
        "error_type": error_type,
        "error_summary_redacted": str(redact_value(error_summary) or ""),
        "objective_redacted": clean_objective,
        "context_bundle_id": str(dict(redacted_context if isinstance(redacted_context, Mapping) else {}).get("context_bundle_id", "")),
        "snippet_refs": [
            {
                "path": str(item.get("path", "")),
                "char_count": int(item.get("char_count", 0) or 0),
                "truncated": bool(item.get("truncated", False)),
            }
            for item in snippets
        ],
        "rejected_context_paths": rejected_paths,
        "summary": parsed["summary"],
        "implementation_steps": parsed["implementation_steps"],
        "patch_suggestions": parsed["patch_suggestions"],
        "test_plan": parsed["test_plan"],
        "risk_notes": parsed["risk_notes"],
        "external_research_needed": bool(parsed["external_research_needed"]),
        "latency_ms": latency_ms,
    }
    evidence["result_id"] = f"qwenassist-{_hash_payload(evidence, length=12)}"
    persisted = _persist_local_coding_assist_qwen_result(
        operator_root=operator_root,
        evidence=evidence,
    )
    return {
        "ok": bool(persisted.get("ok", False)),
        "status": str(persisted.get("status", status)),
        "message": (
            "Local Qwen coding assist evidence generated."
            if bool(persisted.get("ok", False))
            else "Local Qwen coding assist completed with warnings."
        ),
        "result_id": str(persisted.get("result_id", "")),
        "provider": LOCAL_LLM_PROVIDER,
        "model": configured_model,
        "model_family": _ollama_model_family(configured_model),
        "context_window_tokens": configured_ollama_num_ctx(),
        "warning_type": str(persisted.get("warning_type", "")),
        "warnings": list(persisted.get("warnings", []) or []),
        "error_type": str(persisted.get("error_type", "")),
        "error_summary_redacted": str(persisted.get("error_summary_redacted", "")),
        "summary": str(persisted.get("summary", "")),
        "implementation_steps": list(persisted.get("implementation_steps", []) or []),
        "patch_suggestions": list(persisted.get("patch_suggestions", []) or []),
        "test_plan": list(persisted.get("test_plan", []) or []),
        "risk_notes": list(persisted.get("risk_notes", []) or []),
        "external_research_needed": bool(persisted.get("external_research_needed", False)),
        "snippet_refs": list(persisted.get("snippet_refs", []) or []),
        "rejected_context_paths": list(persisted.get("rejected_context_paths", []) or []),
        "evidence_path_hint": str(persisted.get("evidence_path_hint", "")),
        "ledger_path_hint": str(persisted.get("ledger_path_hint", "")),
        "protected_root_write_allowed": False,
        "exit_code": 0 if str(persisted.get("status", "")) == "completed" else 1,
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
    completeness = _directive_draft_completeness(draft_text)
    if not bool(completeness.get("complete", False)):
        missing_sections = [str(item) for item in list(completeness.get("reasons", []) or [])]
        return {
            "ok": False,
            "status": "rejected",
            "message": "The stored draft record is missing required Novali directive sections.",
            "details": [
                "Promotion requires: DIRECTIVE:, Mission:, Objectives:, "
                "Deliverables:, Success Criteria:, and Stop Conditions:.",
                f"Missing or invalid sections: {', '.join(missing_sections) or '<unknown>'}.",
            ],
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
    "configured_ollama_num_ctx",
    "local_coding_assist_qwen_root",
    "load_llm_chat_record",
    "load_llm_history",
    "load_pending_directive_promotions",
    "llm_chat_root",
    "llm_pending_directive_root",
    "promote_llm_draft_to_pending_directive",
    "record_llm_chat_rejection",
    "run_local_coding_assist_qwen",
    "validate_llm_chat_request",
]
