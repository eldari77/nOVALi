from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


GOVERNED_PROCESS_RECONCILIATION_SCHEMA_NAME = "novali_governed_process_reconciliation_v1"
GOVERNED_PROCESS_RECONCILIATION_SCHEMA_VERSION = "1.0"

CURRENT_OWNER = "current_owner"
COMPLETED_BUT_ALIVE = "completed_but_alive"
ORPHANED_GOVERNED_CHILD = "orphaned_governed_child"
DEAD_RECORD = "dead_record"
UNKNOWN_LIVE_PROCESS = "unknown_live_process"

_TERMINABLE_CLASSIFICATIONS = {COMPLETED_BUT_ALIVE, ORPHANED_GOVERNED_CHILD}
_COMPLETED_OR_SUPERSEDED_STATUSES = {
    "completed",
    "complete",
    "finished",
    "success",
    "failed",
    "error",
    "spawn_failed",
    "pre_spawn_timeout",
    "refused_preflight",
    "refused_memory_pressure_guard",
    "refused_adaptive_window",
    "superseded",
    "cancelled",
    "canceled",
    "terminated",
}

PidChecker = Callable[[int], bool]
CommandReader = Callable[[int], str | list[str]]
Terminator = Callable[[int], None]


def _empty_process_memory_snapshot(pid: int, *, error_type: str = "") -> dict[str, Any]:
    return {
        "pid": int(pid or 0),
        "available": False,
        "error_type": error_type,
        "vm_rss_bytes": 0,
        "vm_size_bytes": 0,
        "threads": 0,
        "rss_bytes": 0,
        "pss_bytes": 0,
        "private_dirty_bytes": 0,
        "anonymous_bytes": 0,
        "swap_bytes": 0,
        "vm_rss_mib": 0.0,
        "vm_size_mib": 0.0,
        "rss_mib": 0.0,
        "pss_mib": 0.0,
        "private_dirty_mib": 0.0,
        "anonymous_mib": 0.0,
        "swap_mib": 0.0,
    }


def _bytes_to_mib(value: int) -> float:
    return max(0, int(value or 0)) / (1024 * 1024)


def _parse_status_kib_fields(text: str) -> dict[str, int]:
    fields: dict[str, int] = {}
    for raw_line in str(text or "").splitlines():
        if ":" not in raw_line:
            continue
        name, raw_value = raw_line.split(":", 1)
        parts = raw_value.strip().split()
        if not parts:
            continue
        if name in {"VmRSS", "VmSize"}:
            try:
                fields[name] = int(parts[0]) * 1024
            except ValueError:
                fields[name] = 0
        elif name == "Threads":
            try:
                fields[name] = int(parts[0])
            except ValueError:
                fields[name] = 0
    return fields


def _parse_smaps_rollup_kib_fields(text: str) -> dict[str, int]:
    field_map = {
        "Rss": "rss_bytes",
        "Pss": "pss_bytes",
        "Private_Dirty": "private_dirty_bytes",
        "Anonymous": "anonymous_bytes",
        "Swap": "swap_bytes",
    }
    parsed: dict[str, int] = {}
    for raw_line in str(text or "").splitlines():
        if ":" not in raw_line:
            continue
        name, raw_value = raw_line.split(":", 1)
        key = field_map.get(name.strip())
        if not key:
            continue
        parts = raw_value.strip().split()
        if not parts:
            continue
        try:
            parsed[key] = int(parts[0]) * 1024
        except ValueError:
            parsed[key] = 0
    return parsed


def read_process_memory_snapshot(
    pid: int,
    *,
    proc_root: str | Path = Path("/proc"),
) -> dict[str, Any]:
    pid = int(pid or 0)
    snapshot = _empty_process_memory_snapshot(pid)
    if pid <= 0:
        snapshot["error_type"] = "invalid_pid"
        return snapshot
    process_root = Path(proc_root) / str(pid)
    status_path = process_root / "status"
    try:
        status_text = status_path.read_text(encoding="utf-8", errors="ignore")
    except FileNotFoundError:
        snapshot["error_type"] = "process_status_missing"
        return snapshot
    except OSError as exc:
        snapshot["error_type"] = type(exc).__name__
        return snapshot

    status_fields = _parse_status_kib_fields(status_text)
    snapshot.update(
        {
            "available": True,
            "error_type": "",
            "vm_rss_bytes": int(status_fields.get("VmRSS", 0) or 0),
            "vm_size_bytes": int(status_fields.get("VmSize", 0) or 0),
            "threads": int(status_fields.get("Threads", 0) or 0),
        }
    )
    try:
        smaps_text = (process_root / "smaps_rollup").read_text(
            encoding="utf-8",
            errors="ignore",
        )
    except OSError:
        smaps_text = ""
    snapshot.update(_parse_smaps_rollup_kib_fields(smaps_text))
    for key in (
        "vm_rss",
        "vm_size",
        "rss",
        "pss",
        "private_dirty",
        "anonymous",
        "swap",
    ):
        snapshot[f"{key}_mib"] = _bytes_to_mib(int(snapshot.get(f"{key}_bytes", 0) or 0))
    return snapshot


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True), encoding="utf-8")


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(payload), sort_keys=True) + "\n")


def _read_jsonl(path: Path, *, limit: int = 500) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return rows
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def pid_is_running(pid: int) -> bool:
    pid = int(pid or 0)
    if pid <= 0:
        return False
    if sys.platform.startswith("win"):
        try:
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION,
                False,
                pid,
            )
            if not handle:
                return False
            exit_code = ctypes.c_ulong()
            active = bool(
                ctypes.windll.kernel32.GetExitCodeProcess(
                    handle,
                    ctypes.byref(exit_code),
                )
                and int(exit_code.value) == 259
            )
            ctypes.windll.kernel32.CloseHandle(handle)
            return active
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def read_process_command(pid: int) -> str:
    pid = int(pid or 0)
    if pid <= 0:
        return ""
    proc_cmdline = Path("/proc") / str(pid) / "cmdline"
    if proc_cmdline.exists():
        try:
            return " ".join(
                part for part in proc_cmdline.read_text(encoding="utf-8", errors="ignore").split("\x00") if part
            )
        except OSError:
            return ""
    if sys.platform.startswith("win"):
        command = [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "$p = Get-CimInstance Win32_Process -Filter \"ProcessId = "
                + str(pid)
                + "\"; if ($p) { $p.CommandLine }"
            ),
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ""
        return str(result.stdout or "").strip()
    return ""


def _read_process_commands_windows(pids: Iterable[int]) -> dict[int, str]:
    pid_values = sorted({int(pid) for pid in pids if int(pid or 0) > 0})
    if not pid_values or not sys.platform.startswith("win"):
        return {}
    id_literal = ",".join(str(pid) for pid in pid_values)
    script = (
        "$ids = @("
        + id_literal
        + "); "
        "$rows = Get-CimInstance Win32_Process | "
        "Where-Object { $ids -contains [int]$_.ProcessId } | "
        "Select-Object ProcessId,CommandLine; "
        "$rows | ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=4.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    try:
        payload = json.loads(str(result.stdout or "").strip() or "[]")
    except json.JSONDecodeError:
        return {}
    rows = payload if isinstance(payload, list) else [payload]
    commands: dict[int, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            pid = int(row.get("ProcessId", 0) or 0)
        except (TypeError, ValueError):
            pid = 0
        if pid > 0:
            commands[pid] = str(row.get("CommandLine", "") or "")
    return commands


def terminate_process(pid: int) -> None:
    os.kill(int(pid), signal.SIGTERM)


def is_governed_command(command: str | list[str]) -> bool:
    if isinstance(command, list):
        text = " ".join(str(part) for part in command)
    else:
        text = str(command or "")
    normalized = text.replace("\\", "/").lower()
    return "--governed-execution" in normalized and (
        "main.py" in normalized or "operator_shell" in normalized or "novali" in normalized
    )


def _extract_pid(value: Mapping[str, Any]) -> int:
    for key in ("pid", "process_id", "active_process_id", "launcher_pid"):
        try:
            pid = int(value.get(key, 0) or 0)
        except (TypeError, ValueError):
            pid = 0
        if pid > 0:
            return pid
    return 0


def _attempt_paths(operator_root: Path, *, limit: int = 50) -> Iterable[Path]:
    latest = operator_root / "governed_start_attempt_latest.json"
    yielded: set[Path] = set()
    if latest.exists():
        yielded.add(latest.resolve())
        yield latest
    attempts_dir = operator_root / "governed_start_attempts"
    if attempts_dir.exists():
        candidates = sorted(attempts_dir.glob("*.json"), key=lambda path: path.name)
        for path in candidates[-max(1, int(limit or 1)):]:
            resolved = path.resolve()
            if resolved in yielded:
                continue
            yield path


def _collect_evidence(
    operator_root: Path,
    tracked_processes: Iterable[Mapping[str, Any]] | None,
) -> dict[int, dict[str, Any]]:
    evidence: dict[int, dict[str, Any]] = {}

    def _row(pid: int) -> dict[str, Any]:
        return evidence.setdefault(
            pid,
            {
                "pid": pid,
                "attempts": [],
                "launch_events": [],
                "tracked_process": {},
                "latest_status": "",
                "latest_phase": "",
                "completed_evidence": False,
                "spawn_evidence": False,
            },
        )

    for path in _attempt_paths(operator_root):
        attempt = _read_json(path)
        pid = _extract_pid(attempt)
        if pid <= 0:
            continue
        row = _row(pid)
        row["attempts"].append(
            {
                "path": str(path),
                "attempt_id": str(attempt.get("attempt_id", "")),
                "status": str(attempt.get("status", "")),
                "launch_phase": str(attempt.get("launch_phase", "")),
                "updated_at": str(attempt.get("updated_at", "")),
            }
        )
        status = str(attempt.get("status", "")).strip()
        phase = str(attempt.get("launch_phase", "")).strip()
        row["latest_status"] = status or row["latest_status"]
        row["latest_phase"] = phase or row["latest_phase"]
        row["spawn_evidence"] = row["spawn_evidence"] or phase == "process_spawn" or status == "spawned"
        row["completed_evidence"] = row["completed_evidence"] or status in _COMPLETED_OR_SUPERSEDED_STATUSES

    for event in _read_jsonl(operator_root / "operator_launch_events.jsonl", limit=50):
        pid = _extract_pid(event)
        if pid <= 0:
            continue
        row = _row(pid)
        event_type = str(event.get("event_type") or event.get("type") or event.get("phase") or "").strip()
        phase = str(event.get("phase") or event.get("launch_phase") or "").strip()
        row["launch_events"].append(
            {
                "event_type": event_type,
                "phase": phase,
                "status": str(event.get("status", "")),
                "exit_code": event.get("exit_code", ""),
                "created_at": str(event.get("created_at") or event.get("timestamp") or ""),
            }
        )
        if "spawn" in event_type or "spawn" in phase:
            row["spawn_evidence"] = True
        if "completed" in event_type or "complete" in event_type:
            row["completed_evidence"] = True
        if event.get("exit_code", "") != "":
            row["completed_evidence"] = True

    for tracked in list(tracked_processes or []):
        pid = _extract_pid(tracked)
        if pid <= 0:
            continue
        row = _row(pid)
        row["tracked_process"] = dict(tracked)
        row["spawn_evidence"] = True

    return evidence


def _current_active_pid(long_run: Mapping[str, Any] | None) -> int:
    long_run = dict(long_run or {})
    try:
        return int(long_run.get("active_process_id", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _current_session_active(long_run: Mapping[str, Any] | None) -> bool:
    long_run = dict(long_run or {})
    return str(long_run.get("lease_state", "")).strip() == "active" or str(
        long_run.get("lifecycle_state", "")
    ).strip() in {"running", "active"}


def _classify(
    *,
    pid: int,
    evidence: Mapping[str, Any],
    alive: bool,
    command: str | list[str],
    active_pid: int,
    current_active: bool,
) -> str:
    if not alive:
        return DEAD_RECORD
    if pid == active_pid and current_active:
        return CURRENT_OWNER
    governed_command = is_governed_command(command)
    if bool(evidence.get("completed_evidence", False)) and governed_command:
        return COMPLETED_BUT_ALIVE
    if governed_command and bool(evidence.get("spawn_evidence", False)):
        return ORPHANED_GOVERNED_CHILD
    return UNKNOWN_LIVE_PROCESS


def reconcile_governed_processes(
    operator_root: str | Path,
    *,
    long_run: Mapping[str, Any] | None = None,
    tracked_processes: Iterable[Mapping[str, Any]] | None = None,
    terminate: bool = False,
    record_ledger: bool | None = None,
    pid_checker: PidChecker | None = None,
    command_reader: CommandReader | None = None,
    terminator: Terminator | None = None,
) -> dict[str, Any]:
    root = Path(operator_root)
    checker = pid_checker or pid_is_running
    killer = terminator or terminate_process
    generated_at = _now()
    started = time.perf_counter()
    evidence_by_pid = _collect_evidence(root, tracked_processes)
    active_pid = _current_active_pid(long_run)
    current_active = _current_session_active(long_run)
    if active_pid > 0:
        evidence_by_pid.setdefault(
            active_pid,
            {
                "pid": active_pid,
                "attempts": [],
                "launch_events": [],
                "tracked_process": {},
                "latest_status": "",
                "latest_phase": "",
                "completed_evidence": False,
                "spawn_evidence": True,
            },
        )

    alive_by_pid: dict[int, bool] = {}
    for pid in sorted(evidence_by_pid):
        try:
            alive_by_pid[pid] = bool(checker(pid))
        except Exception:
            alive_by_pid[pid] = False
    command_map = (
        {}
        if command_reader is not None
        else _read_process_commands_windows(pid for pid, alive in alive_by_pid.items() if alive)
    )

    process_rows: list[dict[str, Any]] = []
    blocking_reasons: list[str] = []
    terminated_count = 0
    unknown_live_count = 0
    failed_termination_count = 0
    for pid in sorted(evidence_by_pid):
        evidence = evidence_by_pid[pid]
        alive = bool(alive_by_pid.get(pid, False))
        command: str | list[str] = ""
        if alive:
            if command_reader is None and pid in command_map:
                command = command_map.get(pid, "")
            else:
                try:
                    command = (command_reader or read_process_command)(pid)
                except Exception:
                    command = ""
        classification = _classify(
            pid=pid,
            evidence=evidence,
            alive=alive,
            command=command,
            active_pid=active_pid,
            current_active=current_active,
        )
        termination_status = "not_requested"
        termination_error = ""
        command_matches_governed = is_governed_command(command)
        if (
            terminate
            and alive
            and classification in _TERMINABLE_CLASSIFICATIONS
            and command_matches_governed
            and pid != active_pid
        ):
            try:
                killer(pid)
                termination_status = "terminated"
                terminated_count += 1
            except Exception as exc:
                termination_status = "failed"
                termination_error = f"{type(exc).__name__}: {exc}"
                failed_termination_count += 1
                blocking_reasons.append(
                    f"failed to terminate stale governed process pid {pid}: {termination_error}"
                )
        elif classification == UNKNOWN_LIVE_PROCESS:
            unknown_live_count += 1
            blocking_reasons.append(
                f"unknown live process pid {pid} has governed launch evidence but cannot be safely classified"
            )

        process_rows.append(
            {
                "pid": pid,
                "alive": alive,
                "classification": classification,
                "command_matches_governed": command_matches_governed,
                "latest_status": str(evidence.get("latest_status", "")),
                "latest_phase": str(evidence.get("latest_phase", "")),
                "attempts": list(evidence.get("attempts", []) or []),
                "launch_events": list(evidence.get("launch_events", []) or []),
                "tracked_process": dict(evidence.get("tracked_process", {}) or {}),
                "termination_status": termination_status,
                "termination_error": termination_error,
            }
        )

    payload = {
        "schema_name": GOVERNED_PROCESS_RECONCILIATION_SCHEMA_NAME,
        "schema_version": GOVERNED_PROCESS_RECONCILIATION_SCHEMA_VERSION,
        "generated_at": generated_at,
        "policy": "terminate_old_pids",
        "terminate_requested": bool(terminate),
        "can_start": not blocking_reasons,
        "blocking_reasons": blocking_reasons,
        "summary": {
            "process_count": len(process_rows),
            "current_owner_count": sum(1 for row in process_rows if row["classification"] == CURRENT_OWNER),
            "completed_but_alive_count": sum(
                1 for row in process_rows if row["classification"] == COMPLETED_BUT_ALIVE
            ),
            "orphaned_governed_child_count": sum(
                1 for row in process_rows if row["classification"] == ORPHANED_GOVERNED_CHILD
            ),
            "dead_record_count": sum(1 for row in process_rows if row["classification"] == DEAD_RECORD),
            "unknown_live_process_count": unknown_live_count,
            "terminated_count": terminated_count,
            "failed_termination_count": failed_termination_count,
        },
        "long_run_owner": {
            "active_process_id": active_pid,
            "active": current_active,
            "lease_state": str(dict(long_run or {}).get("lease_state", "")),
            "lifecycle_state": str(dict(long_run or {}).get("lifecycle_state", "")),
        },
        "processes": process_rows,
        "duration_ms": round((time.perf_counter() - started) * 1000.0, 3),
    }
    _write_json(root / "governed_process_reconciliation_latest.json", payload)
    should_record_ledger = (
        bool(record_ledger)
        if record_ledger is not None
        else bool(
            terminate
            or blocking_reasons
            or terminated_count
            or failed_termination_count
        )
    )
    if should_record_ledger:
        _append_jsonl(root / "governed_process_reconciliations.jsonl", payload)
    return payload
