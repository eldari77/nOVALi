from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .gui_presenter import (
    summarize_constraint_rows,
    summarize_latest_launch_attempt,
    summarize_trusted_source_rows,
)
from .launcher import build_operator_dashboard_snapshot


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dump(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def build_manual_acceptance_evidence(
    *,
    package_root: str | Path,
    operator_root: str | Path,
    state_root: str | Path,
    directive_file: str | Path | None = None,
) -> dict[str, Any]:
    dashboard = build_operator_dashboard_snapshot(
        package_root=package_root,
        operator_root=operator_root,
        state_root=state_root,
    )
    launch_context = dict(dashboard.get("launch_context", {}))
    last_launch_event = dict(launch_context.get("last_launch_event", {}))
    constraint_summary = summarize_constraint_rows(dashboard)
    trusted_source_summary = summarize_trusted_source_rows(dashboard)
    latest_attempt_summary = summarize_latest_launch_attempt(launch_context)
    return {
        "schema_name": "NovaliManualAcceptanceEvidence",
        "schema_version": "novali_manual_acceptance_evidence_v1",
        "generated_at": _now(),
        "non_authoritative_evidence_only": True,
        "canonical_operator_launch": "python -m novali_v5.web_operator",
        "equivalent_convenience_launch": "python -m novali_v5",
        "transitional_desktop_launch": "python -m novali_v5.operator_shell",
        "directive_file_selected": str(directive_file or ""),
        "operator_root": str(Path(operator_root)),
        "state_root": str(Path(state_root)),
        "canonical_posture": dict(dashboard.get("canonical_posture", {})),
        "artifact_presence": dict(dashboard.get("artifact_presence", {})),
        "launch_context": launch_context,
        "last_launch_event": last_launch_event,
        "latest_attempt_summary": latest_attempt_summary,
        "trusted_source_summary": {
            "ready_sources": list(trusted_source_summary.get("ready_sources", [])),
            "attention_required_sources": list(trusted_source_summary.get("attention_required_sources", [])),
            "disabled_sources": list(trusted_source_summary.get("disabled_sources", [])),
            "rows": list(trusted_source_summary.get("rows", [])),
        },
        "runtime_constraint_summary": {
            "valid": bool(constraint_summary.get("valid", False)),
            "errors": list(constraint_summary.get("errors", [])),
            "hard_enforced_count": int(constraint_summary.get("hard_enforced_count", 0)),
            "watchdog_enforced_count": int(constraint_summary.get("watchdog_enforced_count", 0)),
            "unsupported_count": int(constraint_summary.get("unsupported_count", 0)),
            "rows": list(constraint_summary.get("rows", [])),
        },
        "key_artifact_paths": dict(dashboard.get("operator_paths", {})),
    }


def render_manual_acceptance_markdown(evidence: dict[str, Any]) -> str:
    posture = dict(evidence.get("canonical_posture", {}))
    artifact_presence = dict(evidence.get("artifact_presence", {}))
    launch_context = dict(evidence.get("launch_context", {}))
    last_launch_event = dict(evidence.get("last_launch_event", {}))
    last_launch_plan = dict(launch_context.get("last_launch_plan", {}))
    latest_attempt_summary = dict(evidence.get("latest_attempt_summary", {}))
    runtime_summary = dict(evidence.get("runtime_constraint_summary", {}))
    trusted_summary = dict(evidence.get("trusted_source_summary", {}))
    key_paths = dict(evidence.get("key_artifact_paths", {}))
    lines = [
        "# NOVALI Manual Acceptance Evidence",
        "",
        f"- Generated at: `{evidence.get('generated_at', '')}`",
        f"- Preferred browser launch: `{evidence.get('canonical_operator_launch', '')}`",
        f"- Convenience launch: `{evidence.get('equivalent_convenience_launch', '')}`",
        f"- Transitional desktop launch: `{evidence.get('transitional_desktop_launch', '')}`",
        f"- Directive selected: `{evidence.get('directive_file_selected', '') or '<resume>'}`",
        f"- State root: `{evidence.get('state_root', '')}`",
        f"- Operator root: `{evidence.get('operator_root', '')}`",
        f"- Evidence only: `{evidence.get('non_authoritative_evidence_only', False)}`",
        "",
        "## Canonical Posture",
        "",
        f"- Active branch: `{posture.get('active_branch', '') or '<missing>'}`",
        f"- Branch state: `{posture.get('current_branch_state', '') or '<missing>'}`",
        f"- Operating stance: `{posture.get('current_operating_stance', '') or '<missing>'}`",
        f"- Held baseline: `{posture.get('held_baseline_template', '') or '<missing>'}`",
        f"- Routing status: `{posture.get('routing_status', '') or '<missing>'}`",
        "",
        "## Latest Attempt",
        "",
        f"- Outcome: `{latest_attempt_summary.get('headline', '') or '<none>'}`",
        f"- Latest event type: `{last_launch_event.get('event_type', '') or '<none>'}`",
        f"- Latest event timestamp: `{last_launch_event.get('timestamp', '') or '<none>'}`",
    ]
    latest_attempt_details = list(latest_attempt_summary.get("details", []))
    if latest_attempt_details:
        lines.extend(["", "Latest attempt details:"])
        lines.extend(f"- {item}" for item in latest_attempt_details)
    lines.extend(
        [
            "",
            "## Launch Context",
            "",
            f"- Current launch mode: `{launch_context.get('current_launch_mode', '') or '<none recorded>'}`",
            f"- Frozen session valid: `{launch_context.get('effective_operator_session_valid', False)}`",
            f"- Frozen session id: `{dict(launch_context.get('effective_operator_session', {})).get('session_id', '') or '<missing>'}`",
        ]
    )
    effective_session = dict(launch_context.get("effective_operator_session", {}))
    if effective_session.get("launch_kind"):
        lines.append(f"- Launch kind: `{effective_session.get('launch_kind', '')}`")
    if effective_session.get("execution_profile"):
        lines.append(f"- Execution profile: `{effective_session.get('execution_profile', '')}`")
    if effective_session.get("workspace_root"):
        lines.append(
            "- Active workspace: "
            f"`{effective_session.get('workspace_id', '')} -> {effective_session.get('workspace_root', '')}`"
        )
    if last_launch_event.get("failure_reason"):
        lines.append(f"- Latest recorded failure/refusal reason: `{last_launch_event.get('failure_reason', '')}`")
    if last_launch_plan:
        last_launch_plan_summary = dict(last_launch_plan.get("summary", {}))
        lines.append(f"- Latest launch-plan backend: `{last_launch_plan.get('backend_kind', '') or '<none>'}`")
        if str(last_launch_plan.get("execution_profile", "")).strip():
            lines.append(f"- Latest launch-plan execution profile: `{last_launch_plan.get('execution_profile', '')}`")
        if str(last_launch_plan.get("workspace_root", "")).strip():
            lines.append(
                "- Latest launch-plan active workspace: "
                f"`{last_launch_plan.get('workspace_id', '')} -> {last_launch_plan.get('workspace_root', '')}`"
            )
        if str(last_launch_plan_summary.get("image", "")).strip():
            lines.append(f"- Latest launch-plan image: `{last_launch_plan_summary.get('image', '')}`")
    lines.extend(
        [
            "",
            "## Canonical Artifact Presence",
            "",
            f"- directive_state: `{artifact_presence.get('directive_state_present', False)}`",
            f"- bucket_state: `{artifact_presence.get('bucket_state_present', False)}`",
            f"- branch_registry: `{artifact_presence.get('branch_registry_present', False)}`",
            f"- governance_memory_authority: `{artifact_presence.get('governance_memory_authority_present', False)}`",
            f"- self_structure_state: `{artifact_presence.get('self_structure_state_present', False)}`",
            f"- canonical_state_available: `{artifact_presence.get('canonical_state_available', False)}`",
            "",
            "## Runtime Constraints",
            "",
            f"- Valid: `{runtime_summary.get('valid', False)}`",
            f"- Hard enforced: `{runtime_summary.get('hard_enforced_count', 0)}`",
            f"- Watchdog enforced: `{runtime_summary.get('watchdog_enforced_count', 0)}`",
            f"- Unsupported: `{runtime_summary.get('unsupported_count', 0)}`",
        ]
    )
    errors = list(runtime_summary.get("errors", []))
    if errors:
        lines.extend(["", "Constraint errors:"])
        lines.extend(f"- {item}" for item in errors)
    lines.extend(["", "Constraint rows:"])
    for row in list(runtime_summary.get("rows", [])):
        lines.append(
            f"- `{row.get('constraint_id', '')}` = `{row.get('requested_display', '')}` "
            f"[{row.get('enforcement_label', '')}]"
        )
    lines.extend(
        [
            "",
            "## Trusted Sources",
            "",
            f"- Ready: `{len(list(trusted_summary.get('ready_sources', [])))}`",
            f"- Attention required: `{len(list(trusted_summary.get('attention_required_sources', [])))}`",
            f"- Disabled: `{len(list(trusted_summary.get('disabled_sources', [])))}`",
            "",
            "Trusted-source rows:",
        ]
    )
    trusted_rows = list(trusted_summary.get("rows", []))
    if trusted_rows:
        for row in trusted_rows:
            lines.append(
                f"- `{row.get('source_id', '')}`: "
                f"{row.get('enabled_label', '')}, "
                f"{row.get('source_kind', '')}, "
                f"{row.get('availability_class', '')}, "
                f"secret={row.get('secret_source_label', '')}"
            )
            if row.get("availability_reason"):
                lines.append(f"  reason: {row.get('availability_reason', '')}")
    else:
        lines.append("- No trusted-source rows were available from the persisted operator snapshot.")
    lines.extend(["", "## Key Artifact Paths", ""])
    for key, value in key_paths.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Operator Notes",
            "",
            "- Desktop environment / OS build:",
            "- Actions performed:",
            "- Refusals observed:",
            "- Resume behavior observed:",
            "- Follow-up issues:",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def write_manual_acceptance_report(
    *,
    output_path: str | Path,
    evidence: dict[str, Any],
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_manual_acceptance_markdown(evidence), encoding="utf-8")
    return path


def write_manual_acceptance_report_json(
    *,
    output_path: str | Path,
    evidence: dict[str, Any],
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_dump(evidence), encoding="utf-8")
    return path
