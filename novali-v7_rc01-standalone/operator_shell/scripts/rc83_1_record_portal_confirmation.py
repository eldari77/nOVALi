from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operator_shell.observability import mark_portal_confirmation_result
from operator_shell.observability.config import (
    DEFAULT_LOGICMONITOR_PROOF_SERVICE_NAME,
    logicmonitor_safe_service_name,
    service_name_is_logicmonitor_safe,
)
from operator_shell.observability.rc83 import write_summary_artifacts
from operator_shell.observability.rc83_1 import resolve_rc83_1_artifact_root
from operator_shell.observability.rc83_2 import resolve_rc83_2_artifact_root
from operator_shell.observability.redaction import redact_value


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _confirmed_state(raw_value: str | bool | None) -> str:
    normalized = str(raw_value or "").strip().lower()
    if normalized in {"1", "true", "yes", "y", "confirmed"}:
        return "confirmed"
    if normalized in {"0", "false", "no", "n", "not_confirmed"}:
        return "not_confirmed"
    return "not_confirmed"


def _artifact_context(env: dict[str, str]) -> tuple[str, Path]:
    milestone = str(env.get("RC83_PORTAL_CONFIRMATION_MILESTONE") or "").strip().lower()
    if not milestone:
        if str(env.get("RC83_2_PROOF_ARTIFACT_ROOT") or "").strip() or str(
            env.get("RC83_2_PROOF_ID") or ""
        ).strip():
            milestone = "rc83_2"
        else:
            milestone = "rc83_1"
    if milestone == "rc83_2":
        return milestone, resolve_rc83_2_artifact_root(ROOT, env=env)
    return "rc83_1", resolve_rc83_1_artifact_root(ROOT, env=env)


def _markdown_summary(summary: dict[str, object]) -> str:
    milestone = str(summary.get("milestone", "rc83_1"))
    return "\n".join(
        [
            f"# {milestone.replace('_', '.')} Portal Confirmation Summary",
            "",
            f"- Confirmation state: {summary.get('confirmation_state', 'not_recorded')}",
            f"- Confirmation source: {summary.get('confirmation_source', '<none>')}",
            f"- Proof ID: {summary.get('proof_id', '<none>')}",
            f"- Service name: {summary.get('service_name', '<none>')}",
            f"- Protocol: {summary.get('protocol', '<none>')}",
            f"- Endpoint mode: {summary.get('endpoint_mode', '<none>')}",
            f"- Service name LogicMonitor-safe: {summary.get('service_name_lm_safe', False)}",
            f"- Summary: {summary.get('summary', '')}",
            f"- Notes: {summary.get('notes', '')}",
        ]
    )


def record_portal_confirmation(
    *,
    proof_id: str,
    service_name: str,
    confirmed: str | bool | None,
    notes: str = "",
    protocol: str = "",
    endpoint_mode: str = "",
    confirmation_source: str = "",
    env: dict[str, str] | None = None,
) -> dict[str, object]:
    env = dict(env or os.environ)
    milestone, artifact_root = _artifact_context(env)
    confirmation_state = _confirmed_state(confirmed)
    safe_service_name = str(service_name or "").strip() or DEFAULT_LOGICMONITOR_PROOF_SERVICE_NAME
    safe_notes = str(redact_value(notes or "") or "").strip()
    safe_protocol = str(redact_value(protocol or "") or "").strip()
    safe_endpoint_mode = str(redact_value(endpoint_mode or "") or "").strip()
    safe_confirmation_source = str(
        redact_value(confirmation_source or env.get("RC83_PORTAL_CONFIRMATION_SOURCE") or "human operator")
        or ""
    ).strip() or "human operator"
    generated_at = _now_iso()
    summary: dict[str, object] = {
        "schema_name": "novali_portal_confirmation_summary_v2",
        "generated_at": generated_at,
        "milestone": milestone,
        "result": "success",
        "confirmation_state": confirmation_state,
        "confirmation_source": safe_confirmation_source,
        "proof_id": str(proof_id or "").strip() or None,
        "service_name": safe_service_name,
        "protocol": safe_protocol or None,
        "endpoint_mode": safe_endpoint_mode or None,
        "service_name_lm_safe": service_name_is_logicmonitor_safe(safe_service_name),
        "service_name_lm_safe_suggestion": logicmonitor_safe_service_name(safe_service_name),
        "notes": safe_notes,
        "summary": (
            "Operator confirmed the proof is visible in the LogicMonitor portal."
            if confirmation_state == "confirmed"
            else "Operator has not confirmed proof visibility in the LogicMonitor portal."
        ),
        "no_credentials_stored": True,
        "no_api_calls_made": True,
    }
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name="portal_confirmation_summary.json",
        markdown_name="portal_confirmation_summary.md",
        summary=summary,
        markdown=_markdown_summary(summary),
    )
    mark_portal_confirmation_result(
        confirmation_state=confirmation_state,
        proof_id=str(summary.get("proof_id") or ""),
        service_name=safe_service_name,
        recorded_at=generated_at,
        protocol=safe_protocol or None,
        endpoint_mode=safe_endpoint_mode or None,
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--proof-id",
        default=os.environ.get("RC83_2_PROOF_ID") or os.environ.get("RC83_1_PROOF_ID", ""),
    )
    parser.add_argument(
        "--service-name",
        default=os.environ.get("OTEL_SERVICE_NAME") or DEFAULT_LOGICMONITOR_PROOF_SERVICE_NAME,
    )
    parser.add_argument(
        "--confirmed",
        default=os.environ.get("RC83_2_PORTAL_CONFIRMED")
        or os.environ.get("RC83_1_PORTAL_CONFIRMED", "no"),
    )
    parser.add_argument(
        "--notes",
        default=os.environ.get("RC83_2_PORTAL_NOTES") or os.environ.get("RC83_1_PORTAL_NOTES", ""),
    )
    parser.add_argument(
        "--protocol",
        default=os.environ.get("RC83_2_OTLP_PROTOCOL") or os.environ.get("RC83_1_OTLP_PROTOCOL", ""),
    )
    parser.add_argument(
        "--endpoint-mode",
        default=os.environ.get("RC83_2_ENDPOINT_MODE", ""),
    )
    parser.add_argument(
        "--confirmation-source",
        default=os.environ.get("RC83_PORTAL_CONFIRMATION_SOURCE", "human operator"),
    )
    args = parser.parse_args()
    summary = record_portal_confirmation(
        proof_id=args.proof_id,
        service_name=args.service_name,
        confirmed=args.confirmed,
        notes=args.notes,
        protocol=args.protocol,
        endpoint_mode=args.endpoint_mode,
        confirmation_source=args.confirmation_source,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
