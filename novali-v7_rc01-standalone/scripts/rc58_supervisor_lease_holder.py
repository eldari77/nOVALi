from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Hold an rc58 long-run supervisor lease open for duplicate-launch proof."
    )
    parser.add_argument("--session-artifact", required=True)
    parser.add_argument("--owner-id", default="rc58-lease-holder")
    parser.add_argument("--lease-seconds", type=int, default=180)
    args = parser.parse_args()

    session_artifact = Path(args.session_artifact).resolve()
    if not session_artifact.exists():
        raise SystemExit(f"session artifact does not exist: {session_artifact}")
    session_payload = json.loads(session_artifact.read_text(encoding="utf-8"))
    long_run = dict(session_payload.get("long_run_session", {}))
    if not long_run:
        raise SystemExit("session artifact does not contain long_run_session")

    stop_requested = False

    def _request_stop(_signum: int, _frame: object) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)

    while not stop_requested:
        now = datetime.now(timezone.utc)
        long_run["generated_at"] = now.isoformat()
        long_run["supervisor_enabled"] = True
        long_run["active_process_id"] = os.getpid()
        long_run["active_invocation_id"] = str(args.owner_id)
        long_run["lease_owner_id"] = str(args.owner_id)
        long_run["lease_acquired_at"] = now.isoformat()
        long_run["lease_expires_at"] = (
            now + timedelta(seconds=max(int(args.lease_seconds), 1))
        ).isoformat()
        long_run["lease_state"] = "active"
        long_run["stale_recovery_available"] = False
        long_run["last_heartbeat_at"] = now.isoformat()
        long_run["operator_summary"] = (
            "A bounded supervisor owner currently holds this long-run session lease for duplicate-launch proof."
        )
        long_run["recommended_next_action"] = (
            "Wait for the active supervisor lease to release or become stale before launching another continuation."
        )
        long_run["duplicate_launch_blocked"] = False
        long_run["duplicate_launch_reason"] = ""
        session_payload["generated_at"] = now.isoformat()
        session_payload["long_run_session"] = long_run
        _write_json(session_artifact, session_payload)
        time.sleep(0.5)

    long_run["generated_at"] = _now()
    session_payload["generated_at"] = long_run["generated_at"]
    session_payload["long_run_session"] = long_run
    _write_json(session_artifact, session_payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
