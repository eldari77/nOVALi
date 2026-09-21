from __future__ import annotations

import re
from typing import Any, Mapping

REDACTED = "[REDACTED]"

SENSITIVE_KEY_FRAGMENTS = (
    "authorization",
    "bearer",
    "token",
    "api_key",
    "apikey",
    "access_id",
    "access_key",
    "secret",
    "password",
    "credential",
    "cookie",
    "set-cookie",
    "session_secret",
    "provider_key",
    "trusted_source_credential",
    "novali.secret",
    "http.request.header.authorization",
    "request.header.authorization",
    "otel_exporter_otlp_headers",
    "logicmonitor_access_id",
    "logicmonitor_access_key",
    "lm_access_id",
    "lm_access_key",
)

BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[a-z0-9_\-\.=+/]+\b")
TOKENISH_PATTERN = re.compile(r"(?i)\b(sk|rk|pk|ak|lm)[-_][a-z0-9]{12,}\b")
LONG_SECRETISH_PATTERN = re.compile(r"^[A-Za-z0-9_\-=/+.]{28,}$")
FAKE_SECRET_PATTERN = re.compile(r"FAKE_[A-Z0-9_]+_SHOULD_NOT_EXPORT")
COOKIEISH_PATTERN = re.compile(r"(?i)\b[a-z0-9_\-]+\s*=\s*[a-z0-9_\-./+=]{10,}")
AUTH_HEADER_PATTERN = re.compile(r"(?i)\b[a-z0-9_\-]+\s*=\s*[a-z0-9_\-./+=]{16,}(?:;\s*[a-z0-9_\-]+\s*=\s*[a-z0-9_\-./+=]{8,})*")


def _is_sensitive_key(key: str) -> bool:
    lowered = str(key or "").strip().lower()
    return any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS)


def _is_sensitive_string(value: str) -> bool:
    normalized = str(value or "").strip()
    lowered = normalized.lower()
    if not normalized:
        return False
    if BEARER_PATTERN.search(normalized):
        return True
    if TOKENISH_PATTERN.search(normalized):
        return True
    if FAKE_SECRET_PATTERN.search(normalized):
        return True
    if "authorization:" in lowered or "cookie:" in lowered:
        return True
    if COOKIEISH_PATTERN.search(normalized):
        return True
    if AUTH_HEADER_PATTERN.search(normalized):
        return True
    return bool(LONG_SECRETISH_PATTERN.match(normalized) and any(ch.isdigit() for ch in normalized))


def redact_value(value: Any, *, key: str | None = None) -> Any:
    if key is not None and _is_sensitive_key(key):
        return REDACTED
    if isinstance(value, Mapping):
        return {
            str(inner_key): redact_value(inner_value, key=str(inner_key))
            for inner_key, inner_value in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [redact_value(item, key=key) for item in value]
    if isinstance(value, bytes):
        return REDACTED
    if isinstance(value, str) and _is_sensitive_string(value):
        return REDACTED
    return value


def redact_attributes(attributes: Mapping[str, Any] | None) -> dict[str, Any]:
    if not attributes:
        return {}
    return {
        str(key): redact_value(value, key=str(key))
        for key, value in attributes.items()
    }
