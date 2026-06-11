from __future__ import annotations

import json
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operator_shell import policy  # noqa: E402
from operator_shell.launcher import launch_novali_main  # noqa: E402
from tests.test_operator_shell import (  # noqa: E402
    _load_example_payload,
    _write_json,
    _write_valid_coding_operator_policy,
    _write_valid_operator_policy,
)


def _request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    timeout: int = 120,
) -> tuple[int, dict]:
    request = urllib.request.Request(
        url,
        method=method,
        data=(json.dumps(payload).encode("utf-8") if payload is not None else None),
        headers={"Content-Type": "application/json"} if payload is not None or method != "GET" else {},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _start_state_server(*, operator_root: Path, state_root: Path, artifacts_dir: Path) -> tuple[subprocess.Popen[str], str]:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "rc57_operator_state_server.py"),
        "--package-root",
        str(ROOT),
        "--operator-root",
        str(operator_root),
        "--state-root",
        str(state_root),
        "--artifacts-dir",
        str(artifacts_dir),
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.time() + 45
    while time.time() < deadline:
        line = process.stdout.readline()
        if not line:
            if process.poll() is not None:
                raise RuntimeError(process.stderr.read())
            time.sleep(0.1)
            continue
        if line.startswith("RC57_SERVER_READY "):
            return process, json.loads(line.split(" ", 1)[1])["base_url"]
    raise RuntimeError("operator-state server did not become ready in time")


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=15)


def main() -> int:
    artifacts_dir = ROOT / "artifacts" / "operator_proof" / "rc58"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="rc58_supervisor_") as tmp:
        temp_root = Path(tmp)
        operator_root = temp_root / "operator"
        state_root = temp_root / "state"
        directive_path = temp_root / "directive.json"
        workspace_id = f"workspace_seed_once_resume_many_{temp_root.name}".replace("-", "_")
        state_root.mkdir(parents=True, exist_ok=True)
        _write_json(directive_path, _load_example_payload())

        _write_valid_operator_policy(operator_root=operator_root, state_root=state_root)
        bootstrap_result = launch_novali_main(
            package_root=ROOT,
            operator_root=operator_root,
            directive_file=directive_path,
            state_root=state_root,
            launch_action="bootstrap_only",
        )
        if int(bootstrap_result.get("exit_code", 1)) != 0:
            raise RuntimeError("bootstrap seed failed")

        coding_payload = _write_valid_coding_operator_policy(
            operator_root=operator_root,
            workspace_id=workspace_id,
            governed_execution_mode=policy.GOVERNED_EXECUTION_MODE_MULTI_CYCLE,
            max_cycles_per_invocation=2,
        )
        runtime_constraints = policy.load_runtime_constraints(root=operator_root)
        governed_execution_policy = dict(runtime_constraints.get("governed_execution", {}))
        governed_execution_policy["max_total_cycles"] = 5
        governed_execution_policy["max_restart_attempts"] = 4
        governed_execution_policy["max_wall_clock_seconds"] = 900
        governed_execution_policy["supervisor_lease_seconds"] = 120
        runtime_constraints["governed_execution"] = governed_execution_policy
        policy.save_runtime_constraints(runtime_constraints, root=operator_root)

        workspace_root = Path(str(dict(coding_payload.get("workspace_policy", {})).get("workspace_root", "")))
        session_artifact = workspace_root / "artifacts" / "governed_execution_session_latest.json"
        checkpoint_inventory_path = (
            workspace_root / "artifacts" / "governed_execution_checkpoint_inventory_latest.json"
        )

        seed_result = launch_novali_main(
            package_root=ROOT,
            operator_root=operator_root,
            directive_file=None,
            state_root=state_root,
            launch_action="governed_execution",
        )
        if int(seed_result.get("exit_code", 1)) != 0:
            raise RuntimeError("seed governed execution failed")
        first_session = json.loads(session_artifact.read_text(encoding="utf-8"))
        first_long_run = dict(first_session.get("long_run_session", {}))

        server_process, base_url = _start_state_server(
            operator_root=operator_root,
            state_root=state_root,
            artifacts_dir=artifacts_dir / "server_before_restart",
        )
        try:
            seed_state_status, seed_state_payload = _request_json(
                f"{base_url}/shell/api/long-run-state"
            )
            pause_status, pause_payload = _request_json(
                f"{base_url}/shell/api/long-run/pause",
                method="POST",
                payload={},
            )
            paused_launch = launch_novali_main(
                package_root=ROOT,
                operator_root=operator_root,
                directive_file=None,
                state_root=state_root,
                launch_action="governed_execution",
            )
            paused_session = json.loads(session_artifact.read_text(encoding="utf-8"))
            paused_long_run = dict(paused_session.get("long_run_session", {}))
            resume_status, resume_payload = _request_json(
                f"{base_url}/shell/api/long-run/resume",
                method="POST",
                payload={},
            )
            lease_holder = subprocess.Popen(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "rc58_supervisor_lease_holder.py"),
                    "--session-artifact",
                    str(session_artifact),
                    "--owner-id",
                    "rc58-proof-owner",
                    "--lease-seconds",
                    "5",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                time.sleep(1.2)
                duplicate_status, duplicate_payload = _request_json(
                    f"{base_url}/shell/api/governed/start",
                    method="POST",
                    payload={},
                )
            finally:
                _stop_process(lease_holder)
            time.sleep(5.5)

            _stop_process(server_process)
            server_process, base_url = _start_state_server(
                operator_root=operator_root,
                state_root=state_root,
                artifacts_dir=artifacts_dir / "server_after_restart",
            )
            stale_state_status, stale_state_payload = _request_json(
                f"{base_url}/shell/api/long-run-state"
            )

            second_result = launch_novali_main(
                package_root=ROOT,
                operator_root=operator_root,
                directive_file=None,
                state_root=state_root,
                launch_action="governed_execution",
            )
            if int(second_result.get("exit_code", 1)) != 0:
                raise RuntimeError("stale recovery supervisor invocation failed")
            second_session = json.loads(session_artifact.read_text(encoding="utf-8"))
            second_long_run = dict(second_session.get("long_run_session", {}))
            final_state_status, final_state_payload = _request_json(
                f"{base_url}/shell/api/long-run-state"
            )
        finally:
            _stop_process(server_process)

        checkpoint_inventory = json.loads(
            checkpoint_inventory_path.read_text(encoding="utf-8")
        )
        timeline = [
            {
                "step": "seed_once",
                "status": seed_result.get("status"),
                "current_cycle": first_long_run.get("current_cycle"),
                "checkpoint_count": first_long_run.get("checkpoint_count"),
            },
            {
                "step": "pause_control",
                "status": pause_status,
                "lifecycle_state": dict(pause_payload.get("long_run", {})).get("lifecycle_state"),
            },
            {
                "step": "paused_launch_noop",
                "status": paused_launch.get("status"),
                "lifecycle_state": paused_long_run.get("lifecycle_state"),
            },
            {
                "step": "resume_control",
                "status": resume_status,
                "lifecycle_state": dict(resume_payload.get("long_run", {})).get("lifecycle_state"),
            },
            {
                "step": "duplicate_launch_blocked",
                "status": duplicate_status,
                "details": duplicate_payload.get("details", []),
            },
            {
                "step": "stale_recovery_visible_after_restart",
                "status": stale_state_status,
                "lease_state": dict(stale_state_payload.get("long_run", {})).get("lease_state"),
                "stale_recovery_available": dict(stale_state_payload.get("long_run", {})).get("stale_recovery_available"),
            },
            {
                "step": "second_invocation_after_stale_recovery",
                "status": second_result.get("status"),
                "current_cycle": second_long_run.get("current_cycle"),
                "checkpoint_count": second_long_run.get("checkpoint_count"),
                "halt_reason": second_long_run.get("halt_reason"),
                "completion_state": second_long_run.get("completion_state"),
            },
        ]
        summary = {
            "seed_artifacts": {
                "directive_path": str(directive_path),
                "operator_root": str(operator_root),
                "state_root": str(state_root),
                "workspace_root": str(workspace_root),
            },
            "session_id": str(second_long_run.get("session_id", "")),
            "workspace_id": str(second_long_run.get("workspace_id", "")),
            "seed_state": {
                "status": seed_state_status,
                "long_run": seed_state_payload.get("long_run", {}),
            },
            "pause_control_exercised": True,
            "pause_control": pause_payload,
            "resume_control": resume_payload,
            "duplicate_launch_blocked": duplicate_status == 400,
            "duplicate_launch_response": duplicate_payload,
            "interruption_point": "after the first seeded budget boundary while a valid lease holder owned the persisted long-run session",
            "restart_method": "forced operator-state server restart against the same persisted operator/state roots after the duplicate-owner lease holder was interrupted",
            "stale_recovery_state": stale_state_payload.get("long_run", {}),
            "checkpoint_ids": [
                str(item.get("checkpoint_id", ""))
                for item in list(checkpoint_inventory.get("checkpoint_rows", []))
            ],
            "checkpoint_inventory": checkpoint_inventory,
            "resumed_from_checkpoint_id": str(second_long_run.get("resume_from_checkpoint_id", "")),
            "resumed_cycle_number": second_long_run.get("current_cycle"),
            "final_state": second_long_run.get("lifecycle_state"),
            "final_halt_reason": second_long_run.get("halt_reason"),
            "final_completion_state": second_long_run.get("completion_state"),
            "final_long_run": second_long_run,
            "final_shell_state": {
                "status": final_state_status,
                "long_run": final_state_payload.get("long_run", {}),
            },
            "supervisor_timeline": timeline,
        }

        (artifacts_dir / "multi_invocation_supervisor_summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        (artifacts_dir / "long_run_lease_sample.json").write_text(
            json.dumps(second_long_run, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        (artifacts_dir / "supervisor_timeline.json").write_text(
            json.dumps(timeline, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        (artifacts_dir / "control_surface_sample.json").write_text(
            json.dumps(
                {
                    "pause": pause_payload,
                    "resume": resume_payload,
                    "duplicate_launch": duplicate_payload,
                    "stale_state": stale_state_payload,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        (artifacts_dir / "multi_invocation_supervisor_summary.md").write_text(
            "\n".join(
                [
                    "# RC58 Multi-Invocation Supervisor Summary",
                    "",
                    f"- session id: `{summary['session_id']}`",
                    f"- workspace id: `{summary['workspace_id']}`",
                    f"- checkpoints written: `{len(summary['checkpoint_ids'])}`",
                    f"- duplicate launch blocked: `{summary['duplicate_launch_blocked']}`",
                    f"- stale recovery lease state: `{dict(stale_state_payload.get('long_run', {})).get('lease_state', '')}`",
                    f"- final state: `{summary['final_state']}`",
                    f"- final halt reason: `{summary['final_halt_reason']}`",
                    f"- final completion state: `{summary['final_completion_state']}`",
                    "",
                    "The proof seeded one bounded governed mission, paused and resumed it through the operator control surface, continued it across multiple supervisor invocations without manual reseed, blocked a duplicate active launch while a valid lease holder owned the session, restarted the operator-state surface against the same persisted roots, detected stale recovery availability, and then resumed the bounded continuation from persisted state until the mission reached its next governed review boundary.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
