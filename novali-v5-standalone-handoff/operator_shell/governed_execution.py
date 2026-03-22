from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import OPERATOR_SESSION_FILE_ENV, OperatorConstraintViolationError
from .policy import (
    EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING,
    load_effective_operator_session_from_file,
    validate_effective_operator_session,
)


GOVERNED_EXECUTION_SESSION_SCHEMA_NAME = "GovernedExecutionSession"
GOVERNED_EXECUTION_SESSION_SCHEMA_VERSION = "governed_execution_session_v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_path(value: Any) -> str:
    if value in {None, ""}:
        return ""
    try:
        return str(Path(str(value)).resolve())
    except OSError:
        return str(value)


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def _session_token(session_id: str) -> str:
    return str(session_id or "governed_execution").replace(":", "_")


def _append_runtime_event(log_path: Path, payload: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _load_runtime_session() -> dict[str, Any]:
    session_path = str(os.environ.get(OPERATOR_SESSION_FILE_ENV, "")).strip()
    if not session_path:
        raise OperatorConstraintViolationError(
            "governed execution requires a frozen operator session file in canonical operator mode",
            constraint_id="operator_session_file",
            enforcement_class="hard_enforced",
        )

    session = load_effective_operator_session_from_file(session_path)
    session_errors = validate_effective_operator_session(
        session,
        operator_root=session.get("operator_policy_root", ""),
        package_root=session.get("package_root", ""),
    )
    if session_errors:
        raise OperatorConstraintViolationError(
            "governed execution requires a valid frozen operator session",
            constraint_id="effective_operator_session",
            enforcement_class="hard_enforced",
        )
    return session


def run_bounded_governed_execution(
    *,
    bootstrap_summary: dict[str, Any],
) -> dict[str, Any]:
    session = _load_runtime_session()
    runtime_constraints = dict(session.get("effective_runtime_constraints", {}))
    constraint_values = dict(runtime_constraints.get("constraints", {}))
    workspace_policy = dict(
        session.get("workspace_policy", runtime_constraints.get("workspace_policy", {}))
    )

    execution_profile = str(
        session.get("execution_profile", runtime_constraints.get("execution_profile", ""))
    ).strip()
    if execution_profile != EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING:
        raise OperatorConstraintViolationError(
            "governed execution requires the bounded_active_workspace_coding execution profile",
            constraint_id="governed_execution_profile",
            enforcement_class="hard_enforced",
        )

    workspace_id = str(workspace_policy.get("workspace_id", "")).strip()
    workspace_root_text = str(workspace_policy.get("workspace_root", "")).strip()
    if not workspace_id or not workspace_root_text:
        raise OperatorConstraintViolationError(
            "governed execution requires an active workspace id and root",
            constraint_id="active_workspace_root",
            enforcement_class="hard_enforced",
        )

    workspace_root = Path(workspace_root_text)
    workspace_root.mkdir(parents=True, exist_ok=True)
    artifacts_root = workspace_root / "artifacts"
    plans_root = workspace_root / "plans"
    artifacts_root.mkdir(parents=True, exist_ok=True)
    plans_root.mkdir(parents=True, exist_ok=True)

    runtime_event_log_path = Path(str(session.get("runtime_event_log_path", "")).strip())
    session_artifact_path = artifacts_root / "governed_execution_session_latest.json"
    session_archive_path = artifacts_root / f"{_session_token(str(session.get('session_id', '')))}.json"
    brief_path = plans_root / "governed_execution_brief.md"

    payload = {
        "schema_name": GOVERNED_EXECUTION_SESSION_SCHEMA_NAME,
        "schema_version": GOVERNED_EXECUTION_SESSION_SCHEMA_VERSION,
        "generated_at": _now(),
        "status": "ready_for_bounded_mutable_shell_work",
        "session_id": str(session.get("session_id", "")),
        "launch_kind": str(session.get("launch_kind", "")),
        "directive_id": str(bootstrap_summary.get("directive_id", "")),
        "state_root": str(bootstrap_summary.get("state_root", "")),
        "execution_profile": execution_profile,
        "workspace_id": workspace_id,
        "workspace_root": _normalize_path(workspace_root),
        "working_directory": str(workspace_policy.get("working_directory", "")),
        "generated_output_root": str(workspace_policy.get("generated_output_root", "")),
        "log_root": str(workspace_policy.get("log_root", "")),
        "runtime_event_log_path": str(runtime_event_log_path),
        "allowed_write_roots": list(constraint_values.get("allowed_write_roots", [])),
        "protected_root_hints": list(workspace_policy.get("protected_root_hints", [])),
        "canonical_authority_file": str(
            dict(bootstrap_summary.get("artifact_paths", {})).get("governance_memory_authority", "")
        ),
        "reason": (
            "canonical bootstrap is complete and the bounded active workspace is attached; "
            "mutable-shell work may proceed only inside the approved workspace and generated/log roots"
        ),
    }
    session_artifact_path.write_text(_stable_json(payload), encoding="utf-8")
    session_archive_path.write_text(_stable_json(payload), encoding="utf-8")

    brief_lines = [
        "# Governed Execution Brief",
        "",
        f"Directive ID: `{payload['directive_id']}`",
        f"Execution profile: `{payload['execution_profile']}`",
        f"Workspace: `{payload['workspace_id']} -> {payload['workspace_root']}`",
        f"Working directory: `{payload['working_directory']}`",
        f"Generated output root: `{payload['generated_output_root']}`",
        f"Runtime event log: `{payload['runtime_event_log_path']}`",
        "",
        "Writable roots:",
        *[f"- `{item}`" for item in payload["allowed_write_roots"]],
        "",
        "Protected root hints:",
        *[f"- `{item}`" for item in payload["protected_root_hints"]],
        "",
        "Status: ready for bounded mutable-shell work.",
    ]
    brief_path.write_text("\n".join(brief_lines) + "\n", encoding="utf-8")

    if str(runtime_event_log_path):
        _append_runtime_event(
            runtime_event_log_path,
            {
                "event_type": "governed_execution_entered",
                "timestamp": _now(),
                "session_id": str(session.get("session_id", "")),
                "directive_id": payload["directive_id"],
                "execution_profile": execution_profile,
                "workspace_id": workspace_id,
                "workspace_root": payload["workspace_root"],
                "session_artifact_path": str(session_artifact_path),
                "brief_path": str(brief_path),
            },
        )

    return {
        **payload,
        "session_artifact_path": str(session_artifact_path),
        "session_archive_path": str(session_archive_path),
        "brief_path": str(brief_path),
    }
