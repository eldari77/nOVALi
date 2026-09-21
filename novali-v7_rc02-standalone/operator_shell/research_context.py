"""Filter secrets at the planner boundary without destroying authorized evidence.

This is deliberately separate from telemetry export policy. Inputs have already
passed the research source/record allowlists; this module grants no new access.
"""
from __future__ import annotations

import os
import json
import re
from typing import Any, Mapping

from .observability.redaction import BEARER_PATTERN, FAKE_SECRET_PATTERN, REDACTED, TOKENISH_PATTERN

EVIDENCE_DELIVERY_VERSION = "planner_evidence_v1"


def decode_theory_response(answer: str) -> tuple[dict, str]:
    """Recover only a missing outer brace, never an argument, value or rationale."""
    def unique_fields(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise ValueError("duplicate_model_response_field")
            result[key] = value
        return result
    try:
        return json.loads(answer, object_pairs_hook=unique_fields), ""
    except json.JSONDecodeError as error:
        stripped = answer.rstrip()
        if error.pos != len(stripped) or not stripped.startswith("{") or not stripped.endswith("}"):
            raise
        try:
            candidate = json.loads(stripped + "}", object_pairs_hook=unique_fields)
        except (json.JSONDecodeError, ValueError):
            raise error
        if (not isinstance(candidate, dict) or not {"command", "arguments"}.issubset(candidate)
                or set(candidate) - {"command", "arguments", "why"} or not isinstance(candidate["arguments"], dict)):
            raise error
        return candidate, "closed_missing_outer_object_brace"
_SECRET_KEY = re.compile(
    r"(?:^|[_.-])(?:authorization|bearer|api_?key|access_key|access_id|password|passwd|"
    r"secret(?:_seed)?|credential(?:s)?|cookie|set_cookie|private_key|provider_key|"
    r"access_token|refresh_token|session_token|client_secret)(?:$|[_.-])", re.I
)
_ASSIGNMENT = re.compile(
    r'''(?ix)(\b(?:api_?key|password|passwd|secret|access_token|refresh_token|client_secret)\b\s*["']?\s*[:=]\s*)
        (?P<value>"[^"\r\n]*"|'[^'\r\n]*'|[^\s,;\r\n}]+)'''
)
_HEADER = re.compile(r"(?im)(\b(?:authorization|proxy-authorization|cookie|set-cookie)\s*:\s*)[^\r\n]+")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S)
_URL_CREDENTIAL = re.compile(r"(https?://)[^\s/@:]+:[^\s/@]+@", re.I)


def _sensitive_key(key: str) -> bool:
    return key.lower() == "token" or bool(_SECRET_KEY.search(key))


def sanitize_planner_context(value: Any) -> Any:
    # Only known configured credential values are matched by value. Long strings
    # alone are not evidence of a secret: record IDs and SHA256 hashes are long.
    known = sorted({v for k, v in os.environ.items() if _sensitive_key(k) and len(v) >= 8}, key=len, reverse=True)

    def mask_string(text: str) -> str:
        for secret in known:
            text = text.replace(secret, REDACTED)
        for pattern in (_PRIVATE_KEY, BEARER_PATTERN, TOKENISH_PATTERN, FAKE_SECRET_PATTERN, _JWT):
            text = pattern.sub(REDACTED, text)
        text = _ASSIGNMENT.sub(lambda m: m.group(1) + REDACTED, text)
        text = _HEADER.sub(lambda m: m.group(1) + REDACTED, text)
        return _URL_CREDENTIAL.sub(lambda m: m.group(1) + REDACTED + "@", text)

    def visit(item: Any, key: str = "") -> Any:
        if _sensitive_key(key):
            return REDACTED
        if isinstance(item, Mapping):
            return {mask_string(str(k)): visit(v, str(k)) for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [visit(v) for v in item]
        if isinstance(item, bytes):
            return REDACTED
        return mask_string(item) if isinstance(item, str) else item

    return visit(value)
