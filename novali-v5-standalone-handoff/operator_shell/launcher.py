from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .common import (
    OPERATOR_CONTEXT_ENV,
    OPERATOR_POLICY_ROOT_ENV,
    OPERATOR_ROLE_RUNTIME,
    OPERATOR_RUNTIME_LOCK_ENV,
    OPERATOR_SESSION_FILE_ENV,
    STARTUP_MODE_CANONICAL_OPERATOR,
    STARTUP_MODE_ENV,
)
from .envelope import (
    BACKEND_LOCAL_DOCKER,
    build_container_runtime_session_view,
    build_operator_runtime_launch_plan,
    operator_runtime_launch_plan_dir,
    operator_runtime_launch_plan_latest_path,
)
from .policy import (
    default_operator_root,
    freeze_effective_operator_session,
    load_effective_operator_session_from_file,
    read_operator_status_snapshot,
    record_operator_launch_event,
)


class OperatorLaunchRefusedError(RuntimeError):
    def __init__(self, message: str, *, errors: list[str] | None = None) -> None:
        self.errors = list(errors or [])
        super().__init__(message)


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _normalize_path(value: Any) -> str:
    if value in {None, ""}:
        return ""
    try:
        return str(Path(str(value)).resolve())
    except OSError:
        return str(value)


def _short_failure_reason(
    stdout_text: str,
    stderr_text: str,
    watchdog_reason: str,
    *,
    exit_code: int,
) -> str:
    if watchdog_reason:
        return str(watchdog_reason)
    if int(exit_code) == 0:
        return ""
    for stream in (stderr_text, stdout_text):
        for line in str(stream).splitlines():
            piece = line.strip()
            if piece:
                return piece[:300]
    return ""


def _build_main_args(
    *,
    directive_file: str | Path | None,
    clarification_file: str | Path | None,
    state_root: str | Path | None,
    launch_action: str,
    extra_args: list[str] | None = None,
) -> list[str]:
    args: list[str] = []
    if directive_file:
        args.extend(["--directive-file", str(directive_file)])
    if clarification_file:
        args.extend(["--clarification-file", str(clarification_file)])
    if state_root:
        args.extend(["--state-root", str(state_root)])
    if launch_action == "bootstrap_only":
        args.append("--bootstrap-only")
    elif launch_action == "governed_execution":
        args.append("--governed-execution")
    elif launch_action == "proposal_analytics":
        args.append("--proposal-analytics")
    elif launch_action == "proposal_recommend":
        args.append("--proposal-recommend")
    elif launch_action == "benchmark_only":
        args.append("--benchmark-only")
    args.extend(list(extra_args or []))
    return args


def _read_process_memory_mb_windows(pid: int) -> float | None:
    if not sys.platform.startswith("win"):
        return None

    class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]

    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_READ = 0x0010
    kernel32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi
    handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, int(pid))
    if not handle:
        return None
    counters = PROCESS_MEMORY_COUNTERS_EX()
    counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
    success = psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
    kernel32.CloseHandle(handle)
    if not success:
        return None
    return float(counters.WorkingSetSize) / (1024.0 * 1024.0)


def prepare_effective_operator_session(
    *,
    package_root: str | Path | None = None,
    operator_root: str | Path | None = None,
    directive_file: str | Path | None = None,
    clarification_file: str | Path | None = None,
    state_root: str | Path | None = None,
    entry_script: str | Path | None = None,
    runtime_args: list[str] | None = None,
    launch_kind: str = "bootstrap_only",
) -> dict[str, Any]:
    root = default_operator_root() if operator_root is None else Path(operator_root)
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    session, errors = freeze_effective_operator_session(
        root=root,
        package_root=package_root_path,
        directive_file=directive_file,
        clarification_file=clarification_file,
        state_root=state_root,
        entry_script=entry_script,
        runtime_args=runtime_args,
        launch_kind=launch_kind,
    )
    if errors:
        record_operator_launch_event(
            {
                "event_type": "launch_refused_preflight",
                "timestamp": _now(),
                "startup_mode": STARTUP_MODE_CANONICAL_OPERATOR,
                "launch_kind": str(launch_kind),
                "directive_file": _normalize_path(directive_file),
                "state_root": _normalize_path(state_root),
                "entry_script": _normalize_path(entry_script),
                "errors": list(errors),
            },
            root=root,
        )
        raise OperatorLaunchRefusedError(
            "operator policy is missing or invalid for launch",
            errors=errors,
        )
    return session


def _record_launch_refused_preflight(
    *,
    root: Path,
    launch_kind: str,
    directive_file: str | Path | None,
    state_root: str | Path | None,
    entry_script: str | Path | None,
    errors: list[str],
    backend_kind: str = "",
) -> None:
    record_operator_launch_event(
        {
            "event_type": "launch_refused_preflight",
            "timestamp": _now(),
            "startup_mode": STARTUP_MODE_CANONICAL_OPERATOR,
            "launch_kind": str(launch_kind),
            "directive_file": _normalize_path(directive_file),
            "state_root": _normalize_path(state_root),
            "entry_script": _normalize_path(entry_script),
            "backend_kind": str(backend_kind),
            "errors": list(errors),
        },
        root=root,
    )


def _build_local_guarded_env(
    *,
    operator_root_path: Path,
) -> dict[str, str]:
    env = os.environ.copy()
    env[OPERATOR_CONTEXT_ENV] = OPERATOR_ROLE_RUNTIME
    env[OPERATOR_SESSION_FILE_ENV] = str(operator_root_path / "effective_operator_session_latest.json")
    env[OPERATOR_POLICY_ROOT_ENV] = str(operator_root_path)
    env[OPERATOR_RUNTIME_LOCK_ENV] = "1"
    env[STARTUP_MODE_ENV] = STARTUP_MODE_CANONICAL_OPERATOR
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _write_launch_plan_artifacts(
    *,
    root: Path,
    session_id: str,
    plan: dict[str, Any],
) -> tuple[str, str]:
    latest_path = operator_runtime_launch_plan_latest_path(root)
    archive_dir = operator_runtime_launch_plan_dir(root)
    archive_path = archive_dir / f"{str(session_id or 'runtime_session').replace(':', '_')}.json"
    payload = json.loads(json.dumps(plan))
    payload["recorded_at"] = _now()
    latest_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    archive_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return str(latest_path), str(archive_path)


def _run_process_with_watchdog(
    *,
    process: subprocess.Popen[str],
    constraints: dict[str, Any],
    backend_kind: str,
    docker_cleanup_command: list[str] | None,
    poll_interval_seconds: float,
) -> tuple[str, str, str, str, str, float]:
    deadline = None
    if constraints.get("session_time_limit_seconds") is not None:
        deadline = time.time() + float(constraints["session_time_limit_seconds"])
    memory_limit_mb = constraints.get("max_memory_mb")
    watchdog_reason = ""
    watchdog_constraint_id = ""
    watchdog_enforcement_class = ""
    max_observed_memory_mb = 0.0

    while True:
        exit_code = process.poll()
        if exit_code is not None:
            break
        if deadline is not None and time.time() >= deadline:
            watchdog_reason = "session time budget exceeded"
            watchdog_constraint_id = "session_time_limit_seconds"
            watchdog_enforcement_class = "watchdog_enforced"
            process.kill()
            if docker_cleanup_command:
                subprocess.run(docker_cleanup_command, capture_output=True, text=True, encoding="utf-8", check=False)
            break
        if (
            backend_kind != BACKEND_LOCAL_DOCKER
            and memory_limit_mb is not None
            and sys.platform.startswith("win")
        ):
            current_memory = _read_process_memory_mb_windows(int(process.pid))
            if current_memory is not None:
                max_observed_memory_mb = max(max_observed_memory_mb, float(current_memory))
                if float(current_memory) > float(memory_limit_mb):
                    watchdog_reason = "working-set memory limit exceeded"
                    watchdog_constraint_id = "max_memory_mb"
                    watchdog_enforcement_class = "watchdog_enforced"
                    process.kill()
                    break
        time.sleep(max(0.05, float(poll_interval_seconds)))

    stdout_text, stderr_text = process.communicate()
    if (
        backend_kind != BACKEND_LOCAL_DOCKER
        and sys.platform.startswith("win")
        and memory_limit_mb is not None
    ):
        current_memory = _read_process_memory_mb_windows(int(process.pid))
        if current_memory is not None:
            max_observed_memory_mb = max(max_observed_memory_mb, float(current_memory))
    return (
        str(watchdog_reason),
        str(watchdog_constraint_id),
        str(watchdog_enforcement_class),
        stdout_text,
        stderr_text,
        max_observed_memory_mb,
    )


def launch_python_entrypoint(
    *,
    entry_script: str | Path,
    args: list[str] | None = None,
    package_root: str | Path | None = None,
    operator_root: str | Path | None = None,
    directive_file: str | Path | None = None,
    clarification_file: str | Path | None = None,
    state_root: str | Path | None = None,
    launch_kind: str = "bootstrap_only",
    wait: bool = True,
    poll_interval_seconds: float = 0.2,
) -> dict[str, Any]:
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    operator_root_path = default_operator_root() if operator_root is None else Path(operator_root)
    entry_script_path = Path(entry_script).resolve()
    runtime_args = [str(item) for item in list(args or [])]

    session = prepare_effective_operator_session(
        package_root=package_root_path,
        operator_root=operator_root_path,
        directive_file=directive_file,
        clarification_file=clarification_file,
        state_root=state_root,
        entry_script=entry_script_path,
        runtime_args=runtime_args,
        launch_kind=launch_kind,
    )
    plan, plan_errors = build_operator_runtime_launch_plan(
        session=session,
        package_root=package_root_path,
        operator_root=operator_root_path,
        entry_script=entry_script_path,
        runtime_args=runtime_args,
        directive_file=directive_file,
        clarification_file=clarification_file,
        state_root=state_root,
    )
    if plan_errors:
        backend_kind = str(dict(session.get("effective_runtime_envelope", {})).get("backend_kind", ""))
        _record_launch_refused_preflight(
            root=operator_root_path,
            launch_kind=launch_kind,
            directive_file=directive_file,
            state_root=state_root,
            entry_script=entry_script_path,
            errors=plan_errors,
            backend_kind=backend_kind,
        )
        raise OperatorLaunchRefusedError(
            "operator runtime envelope could not produce a valid backend launch plan",
            errors=plan_errors,
        )
    launch_plan_path, launch_plan_archive_path = _write_launch_plan_artifacts(
        root=operator_root_path,
        session_id=str(session.get("session_id", "")),
        plan=plan,
    )

    constraints = dict(dict(session.get("effective_runtime_constraints", {})).get("constraints", {}))
    workspace_policy = dict(dict(session.get("effective_runtime_constraints", {})).get("workspace_policy", {}))
    execution_profile = str(dict(session.get("effective_runtime_constraints", {})).get("execution_profile", "")).strip()
    backend_kind = str(plan.get("backend_kind", ""))
    working_directory = Path(
        str(plan.get("host_working_directory", constraints.get("working_directory", package_root_path)))
    ).resolve()
    command = list(plan.get("command", [])) if backend_kind != BACKEND_LOCAL_DOCKER else list(plan.get("docker_command", []))
    env = (
        _build_local_guarded_env(operator_root_path=operator_root_path)
        if backend_kind != BACKEND_LOCAL_DOCKER
        else os.environ.copy()
    )

    runtime_session_runtime_view_path = ""
    if backend_kind == BACKEND_LOCAL_DOCKER:
        runtime_session_runtime_view_path = str(plan.get("runtime_session_host_path", ""))
        runtime_session_payload = build_container_runtime_session_view(session=session, launch_plan=plan)
        runtime_session_path = Path(runtime_session_runtime_view_path)
        runtime_session_path.parent.mkdir(parents=True, exist_ok=True)
        runtime_session_path.write_text(
            json.dumps(runtime_session_payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    launch_started_at = _now()
    record_operator_launch_event(
        {
            "event_type": "launch_started",
            "timestamp": launch_started_at,
            "session_id": str(session.get("session_id", "")),
            "launch_kind": str(launch_kind),
            "startup_mode": STARTUP_MODE_CANONICAL_OPERATOR,
            "entry_script": str(entry_script_path),
            "runtime_args": runtime_args,
            "directive_file": _normalize_path(directive_file),
            "state_root": _normalize_path(state_root),
            "working_directory": str(working_directory),
            "backend_kind": backend_kind,
            "execution_profile": execution_profile,
            "workspace_id": str(workspace_policy.get("workspace_id", "")),
            "workspace_root": str(workspace_policy.get("workspace_root", "")),
            "launch_plan_summary": dict(plan.get("summary", {})),
            "launch_plan_path": launch_plan_path,
            "launch_plan_archive_path": launch_plan_archive_path,
            "runtime_session_runtime_view_path": runtime_session_runtime_view_path,
            "effective_operator_session_path": str(operator_root_path / "effective_operator_session_latest.json"),
        },
        root=operator_root_path,
    )

    process = subprocess.Popen(
        command,
        cwd=str(working_directory),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if not wait:
        return {
            "status": "launched",
            "pid": int(process.pid),
            "session": session,
            "command": command,
            "backend_kind": backend_kind,
            "launch_plan": plan,
            "launch_plan_path": launch_plan_path,
            "launch_plan_archive_path": launch_plan_archive_path,
        }

    docker_cleanup_command = None
    if backend_kind == BACKEND_LOCAL_DOCKER:
        docker_cleanup_command = [str(command[0]), "rm", "-f", str(plan.get("container_name", ""))]
    (
        watchdog_reason,
        watchdog_constraint_id,
        watchdog_enforcement_class,
        stdout_text,
        stderr_text,
        max_observed_memory_mb,
    ) = _run_process_with_watchdog(
        process=process,
        constraints=constraints,
        backend_kind=backend_kind,
        docker_cleanup_command=docker_cleanup_command,
        poll_interval_seconds=poll_interval_seconds,
    )

    status = "completed"
    if watchdog_reason:
        status = "terminated_by_watchdog"

    result = {
        "status": status,
        "startup_mode": STARTUP_MODE_CANONICAL_OPERATOR,
        "exit_code": int(process.returncode),
        "failure_reason": _short_failure_reason(
            stdout_text,
            stderr_text,
            watchdog_reason,
            exit_code=int(process.returncode),
        ),
        "stdout": stdout_text,
        "stderr": stderr_text,
        "command": command,
        "session": load_effective_operator_session_from_file(operator_root_path / "effective_operator_session_latest.json"),
        "backend_kind": backend_kind,
        "launch_plan": plan,
        "launch_plan_path": launch_plan_path,
        "launch_plan_archive_path": launch_plan_archive_path,
        "watchdog_reason": watchdog_reason,
        "watchdog_constraint_id": watchdog_constraint_id,
        "watchdog_enforcement_class": watchdog_enforcement_class,
        "max_observed_memory_mb": max_observed_memory_mb,
        "working_directory": str(working_directory),
        "operator_root": str(operator_root_path),
    }
    record_operator_launch_event(
        {
            "event_type": "launch_completed",
            "timestamp": _now(),
            "session_id": str(session.get("session_id", "")),
            "launch_kind": str(launch_kind),
            "startup_mode": STARTUP_MODE_CANONICAL_OPERATOR,
            "status": str(status),
            "exit_code": int(process.returncode),
            "watchdog_reason": watchdog_reason,
            "watchdog_constraint_id": watchdog_constraint_id,
            "watchdog_enforcement_class": watchdog_enforcement_class,
            "max_observed_memory_mb": max_observed_memory_mb,
            "backend_kind": backend_kind,
            "execution_profile": execution_profile,
            "workspace_id": str(workspace_policy.get("workspace_id", "")),
            "workspace_root": str(workspace_policy.get("workspace_root", "")),
            "launch_plan_summary": dict(plan.get("summary", {})),
            "launch_plan_path": launch_plan_path,
            "launch_plan_archive_path": launch_plan_archive_path,
            "failure_reason": _short_failure_reason(
                stdout_text,
                stderr_text,
                watchdog_reason,
                exit_code=int(process.returncode),
            ),
        },
        root=operator_root_path,
    )
    return result


def launch_novali_main(
    *,
    package_root: str | Path | None = None,
    operator_root: str | Path | None = None,
    directive_file: str | Path | None = None,
    clarification_file: str | Path | None = None,
    state_root: str | Path | None = None,
    launch_action: str = "bootstrap_only",
    extra_args: list[str] | None = None,
    wait: bool = True,
) -> dict[str, Any]:
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    main_path = package_root_path / "main.py"
    args = _build_main_args(
        directive_file=directive_file,
        clarification_file=clarification_file,
        state_root=state_root,
        launch_action=launch_action,
        extra_args=extra_args,
    )
    return launch_python_entrypoint(
        entry_script=main_path,
        args=args,
        package_root=package_root_path,
        operator_root=operator_root,
        directive_file=directive_file,
        clarification_file=clarification_file,
        state_root=state_root,
        launch_kind=launch_action,
        wait=wait,
    )


def build_operator_dashboard_snapshot(
    *,
    package_root: str | Path | None = None,
    operator_root: str | Path | None = None,
    state_root: str | Path | None = None,
) -> dict[str, Any]:
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    operator_root_path = default_operator_root() if operator_root is None else Path(operator_root)
    state_root_path = Path(state_root) if state_root is not None else package_root_path / "data"
    directive_state_path = state_root_path / "directive_state_latest.json"
    bucket_state_path = state_root_path / "bucket_state_latest.json"
    branch_registry_path = state_root_path / "branch_registry_latest.json"
    governance_memory_authority_path = state_root_path / "governance_memory_authority_latest.json"
    self_structure_state_path = state_root_path / "self_structure_state_latest.json"

    def _load(path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}

    authority = _load(governance_memory_authority_path)
    directive_state = _load(directive_state_path)
    self_structure = _load(self_structure_state_path)
    policy_snapshot = read_operator_status_snapshot(root=operator_root_path, package_root=package_root_path)

    authority_summary = dict(authority.get("authority_file_summary", {}))
    current_state_summary = dict(self_structure.get("current_state_summary", {}))
    trusted_source_summary = dict(policy_snapshot.get("trusted_source_summary", {}))
    constraint_enforcement = dict(policy_snapshot.get("runtime_constraint_enforcement", {}))
    runtime_envelope = {
        "valid": bool(policy_snapshot.get("runtime_envelope_spec_valid", False)),
        "errors": list(policy_snapshot.get("runtime_envelope_spec_errors", [])),
        "spec": dict(policy_snapshot.get("runtime_envelope_spec", {})),
        "effective": dict(policy_snapshot.get("effective_runtime_envelope", {})),
        "backend_probe": dict(policy_snapshot.get("runtime_backend_probe", {})),
    }
    last_launch_event = dict(policy_snapshot.get("last_launch_event", {}))
    last_launch_plan = dict(policy_snapshot.get("last_launch_plan", {}))
    effective_session = dict(policy_snapshot.get("effective_operator_session", {}))
    effective_runtime_constraints = dict(effective_session.get("effective_runtime_constraints", {}))
    effective_workspace_policy = dict(effective_runtime_constraints.get("workspace_policy", {}))
    launch_mode = str(last_launch_event.get("startup_mode", ""))
    if not launch_mode and effective_session:
        launch_mode = "canonical_operator"

    return {
        "artifact_presence": {
            "directive_state_present": directive_state_path.exists(),
            "bucket_state_present": bucket_state_path.exists(),
            "branch_registry_present": branch_registry_path.exists(),
            "governance_memory_authority_present": governance_memory_authority_path.exists(),
            "self_structure_state_present": self_structure_state_path.exists(),
            "canonical_state_available": all(
                path.exists()
                for path in (
                    directive_state_path,
                    bucket_state_path,
                    branch_registry_path,
                    governance_memory_authority_path,
                    self_structure_state_path,
                )
            ),
        },
        "canonical_posture": {
            "active_branch": str(authority_summary.get("active_branch", "")),
            "current_branch_state": str(authority_summary.get("current_branch_state", "")),
            "current_operating_stance": str(authority_summary.get("current_operating_stance", "")),
            "held_baseline_template": str(authority_summary.get("held_baseline_template", "")),
            "routing_status": str(authority_summary.get("routing_status", "")),
            "initialization_state": str(directive_state.get("initialization_state", "")),
            "active_directive_id": str(current_state_summary.get("active_directive_id", "")),
        },
        "launch_context": {
            "canonical_human_launcher": "python -m novali_v5.web_operator",
            "equivalent_convenience_launcher": "python -m novali_v5",
            "transitional_desktop_launcher": "python -m novali_v5.operator_shell",
            "current_launch_mode": launch_mode,
            "last_launch_event": last_launch_event,
            "last_launch_plan": {
                "backend_kind": str(last_launch_plan.get("backend_kind", "")),
                "summary": dict(last_launch_plan.get("summary", {})),
                "execution_profile": str(last_launch_plan.get("execution_profile", "")),
                "workspace_id": str(last_launch_plan.get("workspace_id", "")),
                "workspace_root": str(last_launch_plan.get("workspace_root", "")),
            },
            "effective_operator_session_valid": bool(policy_snapshot.get("effective_operator_session_valid", False)),
            "effective_operator_session_errors": list(policy_snapshot.get("effective_operator_session_errors", [])),
            "effective_operator_session": {
                "session_id": str(effective_session.get("session_id", "")),
                "launch_kind": str(effective_session.get("launch_kind", "")),
                "execution_profile": str(
                    effective_session.get(
                        "execution_profile",
                        effective_runtime_constraints.get("execution_profile", ""),
                    )
                ),
                "workspace_id": str(
                    dict(effective_session.get("workspace_policy", {})).get(
                        "workspace_id",
                        effective_workspace_policy.get("workspace_id", ""),
                    )
                ),
                "workspace_root": str(
                    dict(effective_session.get("workspace_policy", {})).get(
                        "workspace_root",
                        effective_workspace_policy.get("workspace_root", ""),
                    )
                ),
                "directive_file": str(effective_session.get("directive_file", "")),
                "state_root": str(effective_session.get("state_root", "")),
                "runtime_event_log_path": str(effective_session.get("runtime_event_log_path", "")),
                "entry_script": str(effective_session.get("entry_script", "")),
            },
        },
        "trusted_sources": trusted_source_summary,
        "trusted_source_secret_summary": dict(policy_snapshot.get("trusted_source_secret_summary", {})),
        "runtime_constraints": {
            "valid": bool(policy_snapshot.get("runtime_constraints_valid", False)),
            "errors": list(policy_snapshot.get("runtime_constraints_errors", [])),
            "constraints": dict(policy_snapshot.get("runtime_constraints", {})),
            "payload": dict(policy_snapshot.get("runtime_constraints", {})),
            "enforcement": constraint_enforcement,
            "execution_profile": str(policy_snapshot.get("execution_profile", "")),
            "workspace_policy": dict(policy_snapshot.get("workspace_policy", {})),
        },
        "runtime_envelope": runtime_envelope,
        "operator_paths": {
            "operator_root": str(operator_root_path),
            "state_root": str(state_root_path),
            "runtime_constraints_path": str(policy_snapshot.get("runtime_constraints_path", "")),
            "runtime_envelope_spec_path": str(policy_snapshot.get("runtime_envelope_spec_path", "")),
            "trusted_source_bindings_path": str(policy_snapshot.get("trusted_source_bindings_path", "")),
            "trusted_source_secrets_path": str(policy_snapshot.get("trusted_source_secrets_path", "")),
            "effective_operator_session_path": str(policy_snapshot.get("effective_operator_session_path", "")),
            "operator_launch_event_ledger_path": str(policy_snapshot.get("operator_launch_event_ledger_path", "")),
            "operator_runtime_launch_plan_path": str(policy_snapshot.get("operator_runtime_launch_plan_path", "")),
            "directive_state_path": str(directive_state_path),
            "bucket_state_path": str(bucket_state_path),
            "branch_registry_path": str(branch_registry_path),
            "governance_memory_authority_path": str(governance_memory_authority_path),
            "self_structure_state_path": str(self_structure_state_path),
        },
    }
