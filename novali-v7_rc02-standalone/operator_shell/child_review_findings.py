"""Independent finding scopes; legacy ambiguity blocks both artifact and method."""
from __future__ import annotations
from typing import Any

SCOPES = ('artifact', 'method', 'both')


def validate(finding: Any) -> None:
    required = {'path', 'code', 'finding', 'verification'}
    if (not isinstance(finding, dict) or not required <= set(finding)
            or set(finding) - required - {'scope'}
            or any(not isinstance(v, str) or not 1 <= len(v) <= 800 for v in finding.values())
            or not finding['path'].startswith('/') or finding.get('scope', 'both') not in SCOPES):
        raise ValueError('typed_scoped_review_finding_required')


def scope(finding: dict[str, Any]) -> str:
    validate({k:v for k,v in finding.items() if k in {'path','code','finding','verification','scope'}})
    return finding.get('scope', 'both')
