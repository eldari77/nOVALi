from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .bounded_workspace_work import (
    GovernedExecutionFailure,
    build_governed_long_run_session_payload,
    load_checkpoint_inventory as load_governed_execution_checkpoint_inventory,
    load_controller_summary as load_governed_execution_controller_summary,
    load_session_summary as load_governed_execution_session_summary,
    run_governed_workspace_work_controller,
)
from .common import OPERATOR_SESSION_FILE_ENV, OperatorConstraintViolationError
from .policy import (
    EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING,
    GOVERNED_EXECUTION_MODE_MULTI_CYCLE,
    GOVERNED_EXECUTION_MODE_SINGLE_CYCLE,
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


def _pid_is_running(pid: int) -> bool:
    if int(pid or 0) <= 0:
        return False
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    return True


def _parse_iso_datetime(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _terminal_completion_state(value: str) -> bool:
    return str(value or "").strip() in {
        "completed",
        "budget_exhausted",
        "error",
        "operator_stop",
    }


def _lease_is_expired(value: str) -> bool:
    parsed = _parse_iso_datetime(value)
    if parsed is None:
        return False
    return parsed <= datetime.now(timezone.utc)


def _invocation_id(session_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{session_id or 'governed_execution'}::supervisor::{os.getpid()}::{stamp}"


def _lease_expiration(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=max(int(seconds or 0), 1))).isoformat()


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


def governed_execution_session_summary_for_workspace(workspace_root: str | Path | None) -> dict[str, Any]:
    return load_governed_execution_session_summary(workspace_root)


def governed_execution_controller_summary_for_workspace(workspace_root: str | Path | None) -> dict[str, Any]:
    return load_governed_execution_controller_summary(workspace_root)


def run_bounded_governed_execution(
    *,
    bootstrap_summary: dict[str, Any],
) -> dict[str, Any]:
    session = _load_runtime_session()
    runtime_constraints = dict(session.get("effective_runtime_constraints", {}))
    constraint_values = dict(runtime_constraints.get("constraints", {}))
    governed_execution_policy = dict(runtime_constraints.get("governed_execution", {}))
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
    prior_session_summary = load_governed_execution_session_summary(workspace_root)
    prior_long_run_session = dict(prior_session_summary.get("long_run_session", {}))
    checkpoint_inventory = load_governed_execution_checkpoint_inventory(workspace_root)

    runtime_event_log_path = Path(str(session.get("runtime_event_log_path", "")).strip())
    session_artifact_path = artifacts_root / "governed_execution_session_latest.json"
    session_archive_path = artifacts_root / f"{_session_token(str(session.get('session_id', '')))}.json"
    brief_path = plans_root / "governed_execution_brief.md"
    controller_mode = str(
        governed_execution_policy.get("mode", GOVERNED_EXECUTION_MODE_SINGLE_CYCLE)
    ).strip() or GOVERNED_EXECUTION_MODE_SINGLE_CYCLE
    max_cycles_per_invocation = int(
        governed_execution_policy.get(
            "max_cycles_per_invocation",
            2 if controller_mode == GOVERNED_EXECUTION_MODE_MULTI_CYCLE else 1,
        )
        or 1
    )
    max_total_cycles = int(
        governed_execution_policy.get(
            "max_total_cycles",
            3 if controller_mode == GOVERNED_EXECUTION_MODE_MULTI_CYCLE else max_cycles_per_invocation,
        )
        or max_cycles_per_invocation
    )
    max_wall_clock_seconds = int(
        governed_execution_policy.get("max_wall_clock_seconds", 900) or 900
    )
    max_restart_attempts = int(
        governed_execution_policy.get("max_restart_attempts", 3) or 3
    )
    supervisor_lease_seconds = int(
        governed_execution_policy.get("supervisor_lease_seconds", 120) or 120
    )
    max_tool_calls = int(governed_execution_policy.get("max_tool_calls", 0) or 0)
    max_trusted_source_calls = int(
        governed_execution_policy.get("max_trusted_source_calls", 0) or 0
    )
    latest_checkpoint = dict(checkpoint_inventory.get("latest_checkpoint", {}))
    session_id = str(
        prior_long_run_session.get("session_id", "") or session.get("session_id", "")
    )
    prior_active_process_id = int(prior_long_run_session.get("active_process_id", 0) or 0)
    prior_completion_state = str(prior_long_run_session.get("completion_state", "")).strip()
    prior_lifecycle_state = str(prior_long_run_session.get("lifecycle_state", "")).strip()
    prior_current_cycle = int(prior_long_run_session.get("current_cycle", 0) or 0)
    prior_checkpoint_count = int(prior_long_run_session.get("checkpoint_count", 0) or 0)
    prior_restart_attempt_count = int(
        prior_long_run_session.get("restart_attempt_count", 0) or 0
    )
    prior_active_invocation_id = str(
        prior_long_run_session.get("active_invocation_id", "")
    ).strip()
    prior_lease_owner_id = str(prior_long_run_session.get("lease_owner_id", "")).strip()
    prior_lease_acquired_at = str(
        prior_long_run_session.get("lease_acquired_at", "")
    ).strip()
    prior_lease_expires_at = str(
        prior_long_run_session.get("lease_expires_at", "")
    ).strip()
    prior_operator_pause_requested = bool(
        prior_long_run_session.get("operator_pause_requested", False)
    )
    prior_operator_stop_requested = bool(
        prior_long_run_session.get("operator_stop_requested", False)
    )
    prior_session_seeded = bool(
        prior_current_cycle > 0 or prior_lifecycle_state not in {"", "not_started"}
    )
    owner_alive = bool(prior_active_process_id and _pid_is_running(prior_active_process_id))
    lease_expired = _lease_is_expired(prior_lease_expires_at)
    resume_available = bool(
        prior_current_cycle > 0
        and not _terminal_completion_state(prior_completion_state)
        and str(latest_checkpoint.get("checkpoint_id", "")).strip()
        and Path(str(latest_checkpoint.get("checkpoint_path", ""))).exists()
    )
    stale_recovery_available = bool(
        prior_session_seeded
        and (
            prior_active_process_id > 0
            or prior_active_invocation_id
            or prior_lease_owner_id
        )
        and (not owner_alive or lease_expired)
    )
    resume_blocked_reason = ""
    if (
        prior_current_cycle > 0
        and not _terminal_completion_state(prior_completion_state)
        and not resume_available
    ):
        resume_blocked_reason = "checkpoint_invalid"
    planned_restart_attempt_count = prior_restart_attempt_count + (
        1 if (resume_available or stale_recovery_available) else 0
    )
    if (
        stale_recovery_available
        and max_restart_attempts > 0
        and planned_restart_attempt_count > max_restart_attempts
    ):
        resume_blocked_reason = "restart_budget_exhausted"
    duplicate_launch_reason = ""
    if (
        prior_session_seeded
        and owner_alive
        and not lease_expired
        and not prior_operator_pause_requested
        and not prior_operator_stop_requested
    ):
        owner_label = prior_lease_owner_id or prior_active_invocation_id or str(prior_active_process_id)
        duplicate_launch_reason = (
            f"active supervisor owner `{owner_label}` still holds this bounded long-run session lease"
        )

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
        "governed_execution_policy": {
            "mode": controller_mode,
            "max_cycles_per_invocation": max_cycles_per_invocation,
            "max_total_cycles": max_total_cycles,
            "max_wall_clock_seconds": max_wall_clock_seconds,
            "max_restart_attempts": max_restart_attempts,
            "supervisor_lease_seconds": supervisor_lease_seconds,
            "max_tool_calls": max_tool_calls,
            "max_trusted_source_calls": max_trusted_source_calls,
        },
        "allowed_write_roots": list(constraint_values.get("allowed_write_roots", [])),
        "protected_root_hints": list(workspace_policy.get("protected_root_hints", [])),
        "canonical_authority_file": str(
            dict(bootstrap_summary.get("artifact_paths", {})).get("governance_memory_authority", "")
        ),
        "reason": (
            "canonical bootstrap is complete and the bounded active workspace is attached; "
            "mutable-shell work may proceed only inside the approved workspace and generated/log roots"
        ),
        "work_cycle": {},
    }
    if duplicate_launch_reason:
        payload["status"] = "duplicate_long_run_launch_blocked"
        payload["reason"] = duplicate_launch_reason
        payload["long_run_session"] = build_governed_long_run_session_payload(
            prior_session=prior_long_run_session,
            session_id=session_id,
            directive_id=str(bootstrap_summary.get("directive_id", "")),
            workspace_id=workspace_id,
            workspace_root=_normalize_path(workspace_root),
            execution_profile=execution_profile,
            governed_execution_mode=controller_mode,
            lifecycle_state=prior_lifecycle_state or "running",
            current_cycle=prior_current_cycle,
            max_cycles=max_total_cycles,
            max_cycles_per_invocation=max_cycles_per_invocation,
            checkpoint_count=prior_checkpoint_count,
            max_wall_clock_seconds=max_wall_clock_seconds,
            max_tool_calls=max_tool_calls,
            max_trusted_source_calls=max_trusted_source_calls,
            max_restart_attempts=max_restart_attempts,
            restart_attempt_count=prior_restart_attempt_count,
            last_meaningful_event="duplicate_supervisor_launch_blocked",
            intervention_required=bool(prior_long_run_session.get("intervention_required", False)),
            halt_reason=str(prior_long_run_session.get("halt_reason", "")),
            completion_state=prior_completion_state or "in_progress",
            resume_from_checkpoint_id=str(
                prior_long_run_session.get("resume_from_checkpoint_id", "")
            ),
            latest_checkpoint_id=str(latest_checkpoint.get("checkpoint_id", "")),
            latest_checkpoint_path=str(latest_checkpoint.get("checkpoint_path", "")),
            latest_checkpoint_at=str(prior_long_run_session.get("last_checkpoint_at", "")),
            active_process_id=prior_active_process_id,
            recommended_next_action=(
                "Wait for the active bounded invocation to release its supervisor lease or recover it if it becomes stale."
            ),
            operator_summary=(
                "Duplicate long-run launch blocked because another active supervisor owner still holds the session lease."
            ),
            resume_available=resume_available,
            resume_blocked_reason="",
            watchdog_state="active",
            supervisor_enabled=True,
            active_invocation_id=prior_active_invocation_id,
            lease_owner_id=prior_lease_owner_id or prior_active_invocation_id,
            lease_acquired_at=prior_lease_acquired_at,
            lease_expires_at=prior_lease_expires_at,
            lease_state="active",
            stale_recovery_available=False,
            next_eligible_at="",
            last_heartbeat_at=str(prior_long_run_session.get("last_heartbeat_at", "")) or _now(),
            duplicate_launch_blocked=True,
            duplicate_launch_reason=duplicate_launch_reason,
            operator_pause_requested=prior_operator_pause_requested,
            operator_stop_requested=prior_operator_stop_requested,
        )
        session_artifact_path.write_text(_stable_json(payload), encoding="utf-8")
        session_archive_path.write_text(_stable_json(payload), encoding="utf-8")
        if str(runtime_event_log_path):
            _append_runtime_event(
                runtime_event_log_path,
                {
                    "event_type": "duplicate_supervisor_launch_blocked",
                    "timestamp": _now(),
                    "session_id": session_id,
                    "directive_id": str(bootstrap_summary.get("directive_id", "")),
                    "execution_profile": execution_profile,
                    "workspace_id": workspace_id,
                    "workspace_root": _normalize_path(workspace_root),
                    "reason": duplicate_launch_reason,
                },
            )
        raise OperatorConstraintViolationError(
            duplicate_launch_reason,
            constraint_id="active_long_run_session",
            enforcement_class="hard_enforced",
        )
    invocation_id = _invocation_id(session_id)
    launch_generated_at = _now()
    long_run_lifecycle_state = (
        "failed"
        if resume_blocked_reason
        else "paused_by_operator"
        if prior_operator_pause_requested and prior_session_seeded and not _terminal_completion_state(prior_completion_state)
        else "halted"
        if prior_operator_stop_requested and prior_session_seeded and not _terminal_completion_state(prior_completion_state)
        else "resuming"
        if resume_available or stale_recovery_available
        else "seeded"
    )
    long_run_halt_reason = (
        "resume_blocked"
        if resume_blocked_reason
        else "operator_pause"
        if long_run_lifecycle_state == "paused_by_operator"
        else "operator_stop"
        if long_run_lifecycle_state == "halted"
        else ""
    )
    long_run_completion_state = (
        "resume_blocked"
        if resume_blocked_reason
        else "operator_stop"
        if long_run_lifecycle_state == "halted"
        else "in_progress"
    )
    long_run_resume_available = bool(
        False if long_run_lifecycle_state == "halted" else resume_available
    )
    long_run_last_event = (
        "governed_execution_resume_requested"
        if resume_available
        else "stale_supervisor_recovery_requested"
        if stale_recovery_available
        else "operator_pause_honored"
        if long_run_lifecycle_state == "paused_by_operator"
        else "operator_stop_honored"
        if long_run_lifecycle_state == "halted"
        else "governed_execution_seeded"
    )
    long_run_operator_summary = (
        "Resume is blocked because the latest long-run checkpoint is missing, invalid, or the restart budget is exhausted."
        if resume_blocked_reason
        else "The bounded long-run session is paused by operator request."
        if long_run_lifecycle_state == "paused_by_operator"
        else "The bounded long-run session was halted by operator request."
        if long_run_lifecycle_state == "halted"
        else f"Recovering the bounded long-run session after stale supervisor ownership `{prior_lease_owner_id or prior_active_invocation_id or prior_active_process_id}` was detected."
        if stale_recovery_available
        else f"Resuming bounded long-run governed work from checkpoint `{str(latest_checkpoint.get('checkpoint_id', ''))}`."
        if resume_available
        else "Starting a new bounded long-run governed session."
    )
    long_run_recommended_next_action = (
        "Inspect the checkpoint inventory before retrying long-run continuation."
        if resume_blocked_reason
        else "Use operator resume when you want bounded continuation to continue from the latest checkpoint."
        if long_run_lifecycle_state == "paused_by_operator"
        else "Inspect the bounded output and decide whether to seed a new governed session."
        if long_run_lifecycle_state == "halted"
        else "Allow bounded continuation to recover from the stale lease and continue from the latest checkpoint."
        if stale_recovery_available
        else "Resume the existing bounded mission from the latest checkpoint."
        if resume_available
        else "Allow the bounded long-run session to enter the first checkpoint boundary."
    )
    long_run_watchdog_state = (
        "checkpoint_invalid"
        if resume_blocked_reason == "checkpoint_invalid"
        else "stale_blocked"
        if resume_blocked_reason == "restart_budget_exhausted"
        else "paused_by_operator"
        if long_run_lifecycle_state == "paused_by_operator"
        else "halted"
        if long_run_lifecycle_state == "halted"
        else "stale_recoverable"
        if stale_recovery_available
        else "resume_available"
        if resume_available
        else "healthy"
    )
    payload["long_run_session"] = build_governed_long_run_session_payload(
        prior_session=prior_long_run_session,
        session_id=session_id,
        directive_id=str(bootstrap_summary.get("directive_id", "")),
        workspace_id=workspace_id,
        workspace_root=_normalize_path(workspace_root),
        execution_profile=execution_profile,
        governed_execution_mode=controller_mode,
        lifecycle_state=long_run_lifecycle_state,
        current_cycle=prior_current_cycle,
        max_cycles=max_total_cycles,
        max_cycles_per_invocation=max_cycles_per_invocation,
        checkpoint_count=prior_checkpoint_count,
        max_wall_clock_seconds=max_wall_clock_seconds,
        max_tool_calls=max_tool_calls,
        max_trusted_source_calls=max_trusted_source_calls,
        max_restart_attempts=max_restart_attempts,
        restart_attempt_count=planned_restart_attempt_count,
        last_meaningful_event=long_run_last_event,
        intervention_required=False,
        halt_reason=long_run_halt_reason,
        completion_state=long_run_completion_state,
        resume_from_checkpoint_id=str(latest_checkpoint.get("checkpoint_id", "")) if resume_available else "",
        latest_checkpoint_id=str(latest_checkpoint.get("checkpoint_id", "")),
        latest_checkpoint_path=str(latest_checkpoint.get("checkpoint_path", "")),
        latest_checkpoint_at=str(latest_checkpoint.get("generated_at", "")),
        active_process_id=0 if long_run_lifecycle_state in {"paused_by_operator", "halted", "failed"} else os.getpid(),
        recommended_next_action=long_run_recommended_next_action,
        operator_summary=long_run_operator_summary,
        resume_available=long_run_resume_available,
        resume_blocked_reason=resume_blocked_reason,
        watchdog_state=long_run_watchdog_state,
        supervisor_enabled=True,
        active_invocation_id="" if long_run_lifecycle_state in {"paused_by_operator", "halted", "failed"} else invocation_id,
        lease_owner_id="" if long_run_lifecycle_state in {"paused_by_operator", "halted", "failed"} else invocation_id,
        lease_acquired_at="" if long_run_lifecycle_state in {"paused_by_operator", "halted", "failed"} else launch_generated_at,
        lease_expires_at="" if long_run_lifecycle_state in {"paused_by_operator", "halted", "failed"} else _lease_expiration(supervisor_lease_seconds),
        started_at_override=(
            launch_generated_at
            if long_run_lifecycle_state not in {"paused_by_operator", "halted", "failed"}
            else None
        ),
        lease_state=(
            "paused_by_operator"
            if long_run_lifecycle_state == "paused_by_operator"
            else "halted"
            if long_run_lifecycle_state == "halted"
            else "stale_blocked"
            if resume_blocked_reason
            else "active"
        ),
        stale_recovery_available=stale_recovery_available,
        next_eligible_at=launch_generated_at if long_run_lifecycle_state == "paused_by_operator" else "",
        last_heartbeat_at=launch_generated_at,
        duplicate_launch_blocked=False,
        duplicate_launch_reason="",
        operator_pause_requested=prior_operator_pause_requested,
        operator_stop_requested=prior_operator_stop_requested,
    )
    session_artifact_path.write_text(_stable_json(payload), encoding="utf-8")
    session_archive_path.write_text(_stable_json(payload), encoding="utf-8")
    if resume_blocked_reason:
        raise OperatorConstraintViolationError(
            "bounded long-run continuation is blocked because the latest checkpoint is missing or invalid",
            constraint_id="governed_long_run_checkpoint",
            enforcement_class="hard_enforced",
        )
    if long_run_lifecycle_state == "paused_by_operator":
        payload["status"] = "paused_by_operator"
        payload["reason"] = "bounded long-run continuation is paused by operator request"
        return {
            **payload,
            "session_artifact_path": str(session_artifact_path),
            "session_archive_path": str(session_archive_path),
            "brief_path": str(brief_path),
            "work_summary_path": str(artifacts_root / "bounded_work_summary_latest.json"),
            "controller_artifact_path": str(artifacts_root / "governed_execution_controller_latest.json"),
        }
    if long_run_lifecycle_state == "halted":
        payload["status"] = "halted_by_operator"
        payload["reason"] = "bounded long-run continuation was halted by operator request"
        return {
            **payload,
            "session_artifact_path": str(session_artifact_path),
            "session_archive_path": str(session_archive_path),
            "brief_path": str(brief_path),
            "work_summary_path": str(artifacts_root / "bounded_work_summary_latest.json"),
            "controller_artifact_path": str(artifacts_root / "governed_execution_controller_latest.json"),
        }

    brief_lines = [
        "# Governed Execution Brief",
        "",
        f"Directive ID: `{payload['directive_id']}`",
        f"Execution profile: `{payload['execution_profile']}`",
        f"Workspace: `{payload['workspace_id']} -> {payload['workspace_root']}`",
        f"Working directory: `{payload['working_directory']}`",
        f"Generated output root: `{payload['generated_output_root']}`",
        f"Runtime event log: `{payload['runtime_event_log_path']}`",
        f"Controller mode: `{controller_mode}`",
        f"Max cycles per invocation: `{max_cycles_per_invocation}`",
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

    work_summary_path = artifacts_root / "bounded_work_summary_latest.json"
    try:
        payload = run_governed_workspace_work_controller(
            bootstrap_summary=bootstrap_summary,
            session=session,
            payload=payload,
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
            controller_mode=controller_mode,
            max_cycles_per_invocation=max_cycles_per_invocation,
        )
    except GovernedExecutionFailure:
        raise
    except Exception as exc:
        failure_reason = f"bounded governed work failed before completion: {exc}"
        failure_summary = {
            "generated_at": _now(),
            "directive_id": str(payload.get("directive_id", "")),
            "workspace_id": workspace_id,
            "workspace_root": str(payload.get("workspace_root", "")),
            "status": "bounded_failure",
            "reason": failure_reason,
            "output_artifact_paths": [],
        }
        work_summary_path.write_text(_stable_json(failure_summary), encoding="utf-8")
        payload["generated_at"] = _now()
        payload["status"] = "bounded_failure"
        payload["reason"] = failure_reason
        payload["long_run_session"] = build_governed_long_run_session_payload(
            prior_session=dict(payload.get("long_run_session", {})),
            session_id=str(session.get("session_id", "")),
            directive_id=str(payload.get("directive_id", "")),
            workspace_id=workspace_id,
            workspace_root=str(payload.get("workspace_root", "")),
            execution_profile=execution_profile,
            governed_execution_mode=controller_mode,
            lifecycle_state="failed",
            current_cycle=int(
                dict(payload.get("long_run_session", {})).get("current_cycle", 0) or 0
            ),
            max_cycles=max_total_cycles,
            max_cycles_per_invocation=max_cycles_per_invocation,
            checkpoint_count=int(
                dict(payload.get("long_run_session", {})).get("checkpoint_count", 0) or 0
            ),
            max_wall_clock_seconds=max_wall_clock_seconds,
            max_tool_calls=max_tool_calls,
            max_trusted_source_calls=max_trusted_source_calls,
            max_restart_attempts=max_restart_attempts,
            restart_attempt_count=int(
                dict(payload.get("long_run_session", {})).get("restart_attempt_count", 0)
                or 0
            ),
            last_meaningful_event="bounded_work_failure",
            intervention_required=False,
            halt_reason="error",
            completion_state="error",
            resume_from_checkpoint_id=str(
                dict(payload.get("long_run_session", {})).get("resume_from_checkpoint_id", "")
            ),
            latest_checkpoint_id=str(
                dict(payload.get("long_run_session", {})).get("latest_checkpoint_id", "")
            ),
            latest_checkpoint_path=str(
                dict(payload.get("long_run_session", {})).get("latest_checkpoint_path", "")
            ),
            latest_checkpoint_at=str(
                dict(payload.get("long_run_session", {})).get("last_checkpoint_at", "")
            ),
            active_process_id=0,
            recommended_next_action="Inspect the bounded failure summary and latest checkpoint before retrying.",
            operator_summary="The bounded long-run session failed before reaching a safe stop boundary.",
            resume_available=False,
            resume_blocked_reason="",
            watchdog_state="failure",
        )
        payload["work_cycle"] = {
            "work_item_id": "bounded_failure",
            "summary_artifact_path": str(work_summary_path),
            "output_artifact_paths": [str(work_summary_path)],
        }
        session_text = _stable_json(payload)
        session_artifact_path.write_text(session_text, encoding="utf-8")
        session_archive_path.write_text(session_text, encoding="utf-8")
        brief_path.write_text(
            "\n".join(
                [
                    "# Governed Execution Brief",
                    "",
                    "Status: bounded_failure",
                    f"Reason: {failure_reason}",
                    f"Work summary: {work_summary_path}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        if str(runtime_event_log_path):
            _append_runtime_event(
                runtime_event_log_path,
                {
                    "event_type": "bounded_work_failure",
                    "timestamp": _now(),
                    "session_id": str(session.get("session_id", "")),
                    "directive_id": payload.get("directive_id", ""),
                    "execution_profile": execution_profile,
                    "workspace_id": workspace_id,
                    "workspace_root": payload.get("workspace_root", ""),
                    "reason": failure_reason,
                    "summary_artifact_path": str(work_summary_path),
                    "session_artifact_path": str(session_artifact_path),
                },
            )
        raise GovernedExecutionFailure(
            failure_reason,
            session_artifact_path=str(session_artifact_path),
            summary_artifact_path=str(work_summary_path),
        ) from exc

    return {
        **payload,
        "session_artifact_path": str(session_artifact_path),
        "session_archive_path": str(session_archive_path),
        "brief_path": str(brief_path),
        "work_summary_path": str(work_summary_path),
        "controller_artifact_path": str(artifacts_root / "governed_execution_controller_latest.json"),
    }
