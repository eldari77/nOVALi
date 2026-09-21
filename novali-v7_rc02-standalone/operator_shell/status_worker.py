from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence


VALID_STATUS_WORKER_KINDS = {"operator-state", "autonomy-status", "long-run-state"}
DEFAULT_STATUS_WORKER_TIMEOUT_SECONDS = 8.0


class StatusWorkerError(ValueError):
    pass


def _env_bool(name: str, default: bool = False) -> bool:
    raw = str(os.environ.get(name, "")).strip().lower()
    if not raw:
        return default
    return raw not in {"0", "false", "no", "off", "disabled"}


def _mapping_bool(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = str(env.get(name, "")).strip().lower()
    if not raw:
        return default
    return raw not in {"0", "false", "no", "off", "disabled"}


def status_worker_environment(base_env: Mapping[str, str] | None = None) -> dict[str, str]:
    env = dict(base_env or os.environ)
    env["NOVALI_STATUS_WORKER"] = "true"
    if not _mapping_bool(env, "NOVALI_STATUS_WORKER_OTEL_ENABLED", False):
        env["NOVALI_OTEL_ENABLED"] = "false"
    return env


def _coerce_timeout(timeout_seconds: float | int | None) -> float:
    if timeout_seconds is None:
        raw = os.environ.get("NOVALI_STATUS_WORKER_TIMEOUT_SECONDS", "")
        try:
            timeout_seconds = float(raw) if raw.strip() else DEFAULT_STATUS_WORKER_TIMEOUT_SECONDS
        except ValueError:
            timeout_seconds = DEFAULT_STATUS_WORKER_TIMEOUT_SECONDS
    return max(0.1, float(timeout_seconds))


def _validate_kind(kind: str) -> str:
    normalized = str(kind or "").strip()
    if normalized not in VALID_STATUS_WORKER_KINDS:
        raise StatusWorkerError(
            "status worker kind must be one of "
            + ", ".join(sorted(VALID_STATUS_WORKER_KINDS))
        )
    return normalized


def _default_command(
    *,
    kind: str,
    package_root: Path,
    operator_root: Path,
    state_root: Path,
) -> list[str]:
    return [
        sys.executable,
        "-m",
        "operator_shell.status_worker",
        "--kind",
        kind,
        "--package-root",
        str(package_root),
        "--operator-root",
        str(operator_root),
        "--state-root",
        str(state_root),
    ]


def _parse_worker_stdout(stdout: str) -> dict[str, Any]:
    lines = [line.strip() for line in str(stdout or "").splitlines() if line.strip()]
    if not lines:
        raise json.JSONDecodeError("empty stdout", "", 0)
    payload = json.loads(lines[-1])
    if not isinstance(payload, dict):
        raise json.JSONDecodeError("worker stdout was not a JSON object", lines[-1], 0)
    return payload


def invoke_status_worker(
    kind: str,
    *,
    package_root: str | Path,
    operator_root: str | Path,
    state_root: str | Path,
    timeout_seconds: float | int | None = None,
    command: Sequence[str] | None = None,
) -> dict[str, Any]:
    normalized_kind = _validate_kind(kind)
    started_at = time.perf_counter()
    package_path = Path(package_root)
    operator_path = Path(operator_root)
    state_path = Path(state_root)
    worker_command = (
        list(command)
        if command is not None
        else _default_command(
            kind=normalized_kind,
            package_root=package_path,
            operator_root=operator_path,
            state_root=state_path,
        )
    )
    timeout = _coerce_timeout(timeout_seconds)
    try:
        completed = subprocess.run(
            worker_command,
            cwd=str(package_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            env=status_worker_environment(os.environ),
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "payload": {},
            "rich_worker_kind": normalized_kind,
            "rich_worker_duration_ms": round((time.perf_counter() - started_at) * 1000.0, 3),
            "rich_worker_exit_code": "",
            "rich_worker_error": "timeout",
            "rich_worker_stderr": "",
        }
    duration_ms = round((time.perf_counter() - started_at) * 1000.0, 3)
    if int(completed.returncode or 0) != 0:
        return {
            "ok": False,
            "payload": {},
            "rich_worker_kind": normalized_kind,
            "rich_worker_duration_ms": duration_ms,
            "rich_worker_exit_code": int(completed.returncode or 0),
            "rich_worker_error": "nonzero_exit",
            "rich_worker_stderr": str(completed.stderr or "").strip()[:2000],
        }
    try:
        payload = _parse_worker_stdout(str(completed.stdout or ""))
    except json.JSONDecodeError:
        return {
            "ok": False,
            "payload": {},
            "rich_worker_kind": normalized_kind,
            "rich_worker_duration_ms": duration_ms,
            "rich_worker_exit_code": int(completed.returncode or 0),
            "rich_worker_error": "json_parse_failure",
            "rich_worker_stderr": str(completed.stderr or "").strip()[:2000],
        }
    return {
        "ok": True,
        "payload": payload,
        "rich_worker_kind": normalized_kind,
        "rich_worker_duration_ms": duration_ms,
        "rich_worker_exit_code": int(completed.returncode or 0),
        "rich_worker_error": "",
        "rich_worker_stderr": str(completed.stderr or "").strip()[:2000],
    }


def build_status_payload(
    *,
    kind: str,
    package_root: str | Path,
    operator_root: str | Path,
    state_root: str | Path,
) -> dict[str, Any]:
    normalized_kind = _validate_kind(kind)
    from .autonomy import autonomy_status
    from .web_operator import OperatorWebService

    service = OperatorWebService(
        package_root=package_root,
        operator_root=operator_root,
        state_root=state_root,
    )
    if normalized_kind == "operator-state":
        return service.current_shell_state_payload()
    if normalized_kind == "autonomy-status":
        return autonomy_status(operator_root)
    if normalized_kind == "long-run-state":
        return service.shell_long_run_state_payload(allow_rich_fallback=False)
    raise StatusWorkerError(f"unsupported status worker kind: {normalized_kind}")


def main(argv: Sequence[str] | None = None) -> int:
    os.environ.update(status_worker_environment(os.environ))
    parser = argparse.ArgumentParser(description="Build one Novali rich status payload in a bounded worker.")
    parser.add_argument("--kind", required=True, choices=sorted(VALID_STATUS_WORKER_KINDS))
    parser.add_argument("--package-root", required=True)
    parser.add_argument("--operator-root", required=True)
    parser.add_argument("--state-root", required=True)
    args = parser.parse_args(argv)
    payload = build_status_payload(
        kind=args.kind,
        package_root=args.package_root,
        operator_root=args.operator_root,
        state_root=args.state_root,
    )
    print(json.dumps(payload, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
