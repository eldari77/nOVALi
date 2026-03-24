from __future__ import annotations

import builtins
import copy
import io
import json
import multiprocessing
import os
import shutil
import subprocess
import sys
import threading
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
    OperatorConstraintViolationError,
    OperatorPolicyMutationRefusedError,
)
from .policy import (
    load_effective_operator_session_from_file,
    validate_effective_operator_session,
)


_INSTALLED = False
_SESSION: dict[str, Any] = {}
_STATE: dict[str, Any] = {}
_ORIGINALS: dict[str, Any] = {}
_SPAWNED_SUBPROCESSES: list[subprocess.Popen[Any]] = []
_SPAWNED_MP_PROCESSES: list[multiprocessing.Process] = []


def _normalize_path(value: Any) -> str:
    if value in {None, ""}:
        return ""
    try:
        return str(Path(str(value)).resolve())
    except OSError:
        return str(value)


def _is_under_path(candidate: str | Path, root: str | Path) -> bool:
    try:
        Path(str(candidate)).resolve().relative_to(Path(str(root)).resolve())
        return True
    except ValueError:
        return False


def _is_write_mode(mode: Any) -> bool:
    if mode is None:
        return False
    text = str(mode)
    return any(flag in text for flag in ("w", "a", "x", "+"))


def _load_runtime_state() -> dict[str, Any]:
    return _STATE


def _emit_runtime_event(payload: dict[str, Any]) -> None:
    if not _STATE or "runtime_event_log_path" not in _STATE:
        return
    log_path = Path(str(_STATE["runtime_event_log_path"]))
    try:
        _ORIGINALS["os.makedirs"](str(log_path.parent), exist_ok=True)
        with _ORIGINALS["io.open"](log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
    except Exception:
        return


def _raise_violation(
    exc_type: type[OperatorConstraintViolationError],
    message: str,
    *,
    constraint_id: str,
    enforcement_class: str,
    path: str = "",
    operation: str = "",
) -> None:
    _emit_runtime_event(
        {
            "event_type": "operator_constraint_violation",
            "timestamp": time.time(),
            "constraint_id": constraint_id,
            "enforcement_class": enforcement_class,
            "path": path,
            "operation": operation,
            "message": message,
        }
    )
    raise exc_type(message, constraint_id=constraint_id, enforcement_class=enforcement_class)


def _check_write_path(path_value: Any, operation: str) -> str:
    state = _load_runtime_state()
    normalized = _normalize_path(path_value)
    if not normalized:
        return normalized
    operator_root = str(state.get("operator_root", ""))
    if operator_root and _is_under_path(normalized, operator_root):
        _raise_violation(
            OperatorPolicyMutationRefusedError,
            "runtime cannot mutate operator-owned policy or frozen effective session files",
            constraint_id="operator_policy_mutation_lock",
            enforcement_class="hard_enforced",
            path=normalized,
            operation=operation,
        )
    allowed_roots = list(state.get("allowed_write_roots", []))
    if allowed_roots and not any(_is_under_path(normalized, root) for root in allowed_roots):
        _raise_violation(
            OperatorConstraintViolationError,
            "write target is outside the operator-approved runtime write boundary",
            constraint_id="allowed_write_roots",
            enforcement_class="hard_enforced",
            path=normalized,
            operation=operation,
        )
    return normalized


def _check_cwd_target(path_value: Any) -> str:
    state = _load_runtime_state()
    normalized = _normalize_path(path_value)
    working_directory = str(state.get("working_directory", ""))
    if normalized and working_directory and not _is_under_path(normalized, working_directory):
        _raise_violation(
            OperatorConstraintViolationError,
            "runtime cannot leave the operator-selected working-directory boundary",
            constraint_id="working_directory",
            enforcement_class="hard_enforced",
            path=normalized,
            operation="os.chdir",
        )
    return normalized


def _prune_spawn_trackers() -> None:
    global _SPAWNED_SUBPROCESSES, _SPAWNED_MP_PROCESSES
    live_subprocesses: list[subprocess.Popen[Any]] = []
    for proc in list(_SPAWNED_SUBPROCESSES):
        try:
            if proc.poll() is None:
                live_subprocesses.append(proc)
        except Exception:
            continue
    live_mp: list[multiprocessing.Process] = []
    for proc in list(_SPAWNED_MP_PROCESSES):
        try:
            if proc.is_alive():
                live_mp.append(proc)
        except Exception:
            continue
    _SPAWNED_SUBPROCESSES = live_subprocesses
    _SPAWNED_MP_PROCESSES = live_mp


def _check_subprocess_spawn(operation: str) -> None:
    state = _load_runtime_state()
    subprocess_mode = str(state.get("subprocess_mode", "disabled"))
    max_child_processes = int(state.get("max_child_processes", 0) or 0)
    _prune_spawn_trackers()
    current_child_processes = len(_SPAWNED_SUBPROCESSES) + len(_SPAWNED_MP_PROCESSES)
    if subprocess_mode == "disabled":
        _raise_violation(
            OperatorConstraintViolationError,
            "subprocess spawning is disabled by operator runtime policy",
            constraint_id="subprocess_mode",
            enforcement_class="hard_enforced",
            operation=operation,
        )
    if subprocess_mode == "bounded" and current_child_processes >= max_child_processes:
        _raise_violation(
            OperatorConstraintViolationError,
            "subprocess spawn limit has been reached for this runtime session",
            constraint_id="max_child_processes",
            enforcement_class="hard_enforced",
            operation=operation,
        )


def _check_thread_start() -> None:
    state = _load_runtime_state()
    max_python_threads = int(state.get("max_python_threads", 0) or 0)
    if max_python_threads <= 0:
        _raise_violation(
            OperatorConstraintViolationError,
            "starting additional Python threads is disabled by operator runtime policy",
            constraint_id="max_python_threads",
            enforcement_class="hard_enforced",
            operation="threading.Thread.start",
        )
    if threading.active_count() >= max_python_threads:
        _raise_violation(
            OperatorConstraintViolationError,
            "Python thread limit reached for this runtime session",
            constraint_id="max_python_threads",
            enforcement_class="hard_enforced",
            operation="threading.Thread.start",
        )


def _install_write_guards() -> None:
    def guarded_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any):
        if not isinstance(file, int) and _is_write_mode(mode):
            _check_write_path(file, "open")
        return _ORIGINALS["builtins.open"](file, mode, *args, **kwargs)

    def guarded_io_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any):
        if not isinstance(file, int) and _is_write_mode(mode):
            _check_write_path(file, "io.open")
        return _ORIGINALS["io.open"](file, mode, *args, **kwargs)

    def guarded_os_open(path: Any, flags: int, *args: Any, **kwargs: Any):
        write_flags = (
            os.O_WRONLY
            | os.O_RDWR
            | os.O_APPEND
            | os.O_CREAT
            | os.O_TRUNC
        )
        if int(flags) & write_flags:
            _check_write_path(path, "os.open")
        return _ORIGINALS["os.open"](path, flags, *args, **kwargs)

    def guarded_remove(path: Any, *args: Any, **kwargs: Any):
        _check_write_path(path, "os.remove")
        return _ORIGINALS["os.remove"](path, *args, **kwargs)

    def guarded_unlink(path: Any, *args: Any, **kwargs: Any):
        _check_write_path(path, "os.unlink")
        return _ORIGINALS["os.unlink"](path, *args, **kwargs)

    def guarded_rename(src: Any, dst: Any, *args: Any, **kwargs: Any):
        _check_write_path(src, "os.rename")
        _check_write_path(dst, "os.rename")
        return _ORIGINALS["os.rename"](src, dst, *args, **kwargs)

    def guarded_replace(src: Any, dst: Any, *args: Any, **kwargs: Any):
        _check_write_path(src, "os.replace")
        _check_write_path(dst, "os.replace")
        return _ORIGINALS["os.replace"](src, dst, *args, **kwargs)

    def guarded_mkdir(path: Any, *args: Any, **kwargs: Any):
        if not Path(str(path)).exists():
            _check_write_path(path, "os.mkdir")
        return _ORIGINALS["os.mkdir"](path, *args, **kwargs)

    def guarded_makedirs(name: Any, mode: int = 0o777, exist_ok: bool = False):
        if not Path(str(name)).exists():
            _check_write_path(name, "os.makedirs")
        return _ORIGINALS["os.makedirs"](name, mode=mode, exist_ok=exist_ok)

    def guarded_rmdir(path: Any, *args: Any, **kwargs: Any):
        _check_write_path(path, "os.rmdir")
        return _ORIGINALS["os.rmdir"](path, *args, **kwargs)

    def guarded_utime(path: Any, *args: Any, **kwargs: Any):
        _check_write_path(path, "os.utime")
        return _ORIGINALS["os.utime"](path, *args, **kwargs)

    def guarded_chdir(path: Any):
        _check_cwd_target(path)
        return _ORIGINALS["os.chdir"](path)

    builtins.open = guarded_open
    io.open = guarded_io_open
    os.open = guarded_os_open
    os.remove = guarded_remove
    os.unlink = guarded_unlink
    os.rename = guarded_rename
    os.replace = guarded_replace
    os.mkdir = guarded_mkdir
    os.makedirs = guarded_makedirs
    os.rmdir = guarded_rmdir
    os.utime = guarded_utime
    os.chdir = guarded_chdir


def _install_process_guards() -> None:
    original_popen = _ORIGINALS["subprocess.Popen"]

    class GuardedPopen(original_popen):  # type: ignore[misc, valid-type]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            _check_subprocess_spawn("subprocess.Popen")
            super().__init__(*args, **kwargs)
            _SPAWNED_SUBPROCESSES.append(self)

    def guarded_os_system(command: str) -> int:
        _check_subprocess_spawn("os.system")
        return _ORIGINALS["os.system"](command)

    def guarded_process_start(proc: multiprocessing.Process, *args: Any, **kwargs: Any):
        _check_subprocess_spawn("multiprocessing.Process.start")
        result = _ORIGINALS["multiprocessing.Process.start"](proc, *args, **kwargs)
        _SPAWNED_MP_PROCESSES.append(proc)
        return result

    def guarded_thread_start(thread: threading.Thread, *args: Any, **kwargs: Any):
        _check_thread_start()
        return _ORIGINALS["threading.Thread.start"](thread, *args, **kwargs)

    subprocess.Popen = GuardedPopen
    os.system = guarded_os_system
    multiprocessing.Process.start = guarded_process_start
    threading.Thread.start = guarded_thread_start


def _install_shutil_guards() -> None:
    def guarded_copyfile(src: Any, dst: Any, *args: Any, **kwargs: Any):
        _check_write_path(dst, "shutil.copyfile")
        return _ORIGINALS["shutil.copyfile"](src, dst, *args, **kwargs)

    def guarded_copy2(src: Any, dst: Any, *args: Any, **kwargs: Any):
        _check_write_path(dst, "shutil.copy2")
        return _ORIGINALS["shutil.copy2"](src, dst, *args, **kwargs)

    def guarded_copytree(src: Any, dst: Any, *args: Any, **kwargs: Any):
        _check_write_path(dst, "shutil.copytree")
        return _ORIGINALS["shutil.copytree"](src, dst, *args, **kwargs)

    def guarded_move(src: Any, dst: Any, *args: Any, **kwargs: Any):
        _check_write_path(src, "shutil.move")
        _check_write_path(dst, "shutil.move")
        return _ORIGINALS["shutil.move"](src, dst, *args, **kwargs)

    def guarded_rmtree(path: Any, *args: Any, **kwargs: Any):
        _check_write_path(path, "shutil.rmtree")
        return _ORIGINALS["shutil.rmtree"](path, *args, **kwargs)

    shutil.copyfile = guarded_copyfile
    shutil.copy2 = guarded_copy2
    shutil.copytree = guarded_copytree
    shutil.move = guarded_move
    shutil.rmtree = guarded_rmtree


def install_runtime_guard_from_environment() -> dict[str, Any]:
    global _INSTALLED, _SESSION, _STATE
    if _INSTALLED:
        return copy.deepcopy(_SESSION)

    startup_mode = str(os.environ.get(STARTUP_MODE_ENV, "")).strip()
    runtime_role = os.environ.get(OPERATOR_CONTEXT_ENV, "").strip().lower()
    runtime_lock = os.environ.get(OPERATOR_RUNTIME_LOCK_ENV, "").strip()

    if startup_mode == STARTUP_MODE_CANONICAL_OPERATOR and (
        runtime_role != OPERATOR_ROLE_RUNTIME or runtime_lock != "1"
    ):
        _raise_violation(
            OperatorConstraintViolationError,
            "canonical operator startup requires a frozen operator session and runtime lock before governed execution",
            constraint_id="canonical_operator_session_required",
            enforcement_class="hard_enforced",
        )

    if runtime_role != OPERATOR_ROLE_RUNTIME:
        return {}
    if runtime_lock != "1":
        return {}

    session_path = os.environ.get(OPERATOR_SESSION_FILE_ENV, "").strip()
    if not session_path:
        _raise_violation(
            OperatorConstraintViolationError,
            "runtime lock is enabled but no frozen operator session file was provided",
            constraint_id="operator_session_file",
            enforcement_class="hard_enforced",
        )

    session = load_effective_operator_session_from_file(session_path)
    session_errors = validate_effective_operator_session(
        session,
        operator_root=os.environ.get(OPERATOR_POLICY_ROOT_ENV, ""),
        package_root=session.get("package_root", ""),
    )
    if session_errors:
        _raise_violation(
            OperatorConstraintViolationError,
            "effective operator session is invalid and runtime launch must refuse",
            constraint_id="effective_operator_session",
            enforcement_class="hard_enforced",
            operation="session_validation",
            path=session_path,
        )

    constraints = dict(dict(session.get("effective_runtime_constraints", {})).get("constraints", {}))
    _SESSION = copy.deepcopy(session)
    _STATE = {
        "operator_root": _normalize_path(session.get("operator_policy_root", os.environ.get(OPERATOR_POLICY_ROOT_ENV, ""))),
        "working_directory": _normalize_path(constraints.get("working_directory", "")),
        "allowed_write_roots": [_normalize_path(item) for item in list(constraints.get("allowed_write_roots", []))],
        "max_python_threads": int(constraints.get("max_python_threads", 0) or 0),
        "max_child_processes": int(constraints.get("max_child_processes", 0) or 0),
        "subprocess_mode": str(constraints.get("subprocess_mode", "disabled")),
        "runtime_event_log_path": _normalize_path(session.get("runtime_event_log_path", "")),
    }

    _ORIGINALS["builtins.open"] = builtins.open
    _ORIGINALS["io.open"] = io.open
    _ORIGINALS["os.open"] = os.open
    _ORIGINALS["os.remove"] = os.remove
    _ORIGINALS["os.unlink"] = os.unlink
    _ORIGINALS["os.rename"] = os.rename
    _ORIGINALS["os.replace"] = os.replace
    _ORIGINALS["os.mkdir"] = os.mkdir
    _ORIGINALS["os.makedirs"] = os.makedirs
    _ORIGINALS["os.rmdir"] = os.rmdir
    _ORIGINALS["os.utime"] = os.utime
    _ORIGINALS["os.chdir"] = os.chdir
    _ORIGINALS["os.system"] = os.system
    _ORIGINALS["subprocess.Popen"] = subprocess.Popen
    _ORIGINALS["multiprocessing.Process.start"] = multiprocessing.Process.start
    _ORIGINALS["threading.Thread.start"] = threading.Thread.start
    _ORIGINALS["shutil.copyfile"] = shutil.copyfile
    _ORIGINALS["shutil.copy2"] = shutil.copy2
    _ORIGINALS["shutil.copytree"] = shutil.copytree
    _ORIGINALS["shutil.move"] = shutil.move
    _ORIGINALS["shutil.rmtree"] = shutil.rmtree

    sys.dont_write_bytecode = True
    _install_write_guards()
    _install_process_guards()
    _install_shutil_guards()
    _INSTALLED = True
    _emit_runtime_event(
        {
            "event_type": "operator_runtime_guard_installed",
            "timestamp": time.time(),
            "session_id": str(session.get("session_id", "")),
        }
    )
    return copy.deepcopy(_SESSION)


def get_effective_operator_session() -> dict[str, Any]:
    return copy.deepcopy(_SESSION)
