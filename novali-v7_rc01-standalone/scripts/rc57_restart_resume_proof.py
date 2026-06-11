from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operator_shell import policy
from operator_shell.launcher import launch_novali_main
from tests.test_operator_shell import (
    _load_example_payload,
    _write_json,
    _write_valid_coding_operator_policy,
    _write_valid_operator_policy,
)


def _request_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _start_server(*, package_root: Path, operator_root: Path, state_root: Path, artifacts_dir: Path) -> tuple[subprocess.Popen[str], dict]:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "rc57_operator_state_server.py"),
        "--package-root",
        str(package_root),
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
        cwd=str(ROOT),
    )
    deadline = time.time() + 20
    ready_payload: dict | None = None
    assert process.stdout is not None
    while time.time() < deadline:
        line = process.stdout.readline()
        if not line:
            if process.poll() is not None:
                stderr_text = process.stderr.read() if process.stderr else ""
                raise RuntimeError(f"rc57 proof server exited early: {stderr_text}")
            continue
        if line.startswith("RC57_SERVER_READY "):
            ready_payload = json.loads(line.removeprefix("RC57_SERVER_READY ").strip())
            break
    if ready_payload is None:
        process.terminate()
        raise RuntimeError("rc57 proof server did not become ready in time")
    return process, ready_payload


def _stop_server(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def _write_markdown_summary(path: Path, summary: dict) -> None:
    checkpoint_rows = list(dict(summary.get("checkpoint_inventory", {})).get("checkpoint_rows", []))
    lines = [
        "# RC57 Restart / Resume Summary",
        "",
        f"- Session id: `{summary.get('session_id', '')}`",
        f"- Workspace id: `{summary.get('workspace_id', '')}`",
        f"- Restart method: `{summary.get('restart_method', '')}`",
        f"- Resume from checkpoint: `{summary.get('resumed_from_checkpoint_id', '')}`",
        f"- Resumed cycle number: `{summary.get('resumed_cycle_number', 0)}`",
        f"- Final lifecycle state: `{summary.get('final_state', '')}`",
        f"- Final halt/completion reason: `{summary.get('final_reason', '')}`",
        "",
        "## Checkpoints",
        *[
            f"- `{row.get('checkpoint_id', '')}` at cycle `{row.get('global_cycle_index', 0)}`"
            for row in checkpoint_rows
        ],
    ]
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts-dir", required=True)
    parser.add_argument("--package-root", default=str(ROOT))
    args = parser.parse_args()

    artifacts_dir = Path(args.artifacts_dir).resolve()
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    package_root = Path(args.package_root).resolve()

    with tempfile.TemporaryDirectory(prefix="rc57_restart_resume_") as tmp:
        temp_root = Path(tmp)
        operator_root = temp_root / "operator"
        state_root = temp_root / "state"
        directive_path = temp_root / "directive.json"
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
            raise RuntimeError(f"bootstrap failed: {bootstrap_result}")

        coding_payload = _write_valid_coding_operator_policy(
            operator_root=operator_root,
            workspace_id="workspace_long_run_proof",
            governed_execution_mode=policy.GOVERNED_EXECUTION_MODE_MULTI_CYCLE,
            max_cycles_per_invocation=2,
        )
        runtime_constraints = policy.load_runtime_constraints(root=operator_root)
        governed_execution_policy = dict(runtime_constraints.get("governed_execution", {}))
        governed_execution_policy["max_total_cycles"] = 3
        governed_execution_policy["max_restart_attempts"] = 3
        governed_execution_policy["max_wall_clock_seconds"] = 900
        runtime_constraints["governed_execution"] = governed_execution_policy
        policy.save_runtime_constraints(runtime_constraints, root=operator_root)

        workspace_root = Path(str(dict(coding_payload.get("workspace_policy", {})).get("workspace_root", "")))
        session_artifact = workspace_root / "artifacts" / "governed_execution_session_latest.json"
        checkpoint_inventory_path = workspace_root / "artifacts" / "governed_execution_checkpoint_inventory_latest.json"

        first = launch_novali_main(
            package_root=ROOT,
            operator_root=operator_root,
            directive_file=None,
            state_root=state_root,
            launch_action="governed_execution",
        )
        if int(first.get("exit_code", 1)) != 0:
            raise RuntimeError(f"first governed run failed: {first}")
        first_session = json.loads(session_artifact.read_text(encoding="utf-8"))
        first_long_run = dict(first_session.get("long_run_session", {}))

        first_server, first_server_ready = _start_server(
            package_root=package_root,
            operator_root=operator_root,
            state_root=state_root,
            artifacts_dir=artifacts_dir / "server_run_01",
        )
        try:
            first_server_state = _request_json(f"{first_server_ready['base_url']}/shell/api/long-run-state")
        finally:
            _stop_server(first_server)

        second_server, second_server_ready = _start_server(
            package_root=package_root,
            operator_root=operator_root,
            state_root=state_root,
            artifacts_dir=artifacts_dir / "server_run_02",
        )
        try:
            resumed_state = _request_json(f"{second_server_ready['base_url']}/shell/api/long-run-state")
            operator_state = _request_json(f"{second_server_ready['base_url']}/shell/api/operator-state")
            try:
                intervention_state = _request_json(
                    f"{second_server_ready['base_url']}/shell/api/intervention-state"
                )
            except Exception as exc:  # pragma: no cover - proof artifact should preserve the exact blocker
                intervention_state = {
                    "error": str(exc),
                }

            second = launch_novali_main(
                package_root=ROOT,
                operator_root=operator_root,
                directive_file=None,
                state_root=state_root,
                launch_action="governed_execution",
            )
            if int(second.get("exit_code", 1)) != 0:
                raise RuntimeError(f"second governed run failed: {second}")
        finally:
            _stop_server(second_server)

        final_session = json.loads(session_artifact.read_text(encoding="utf-8"))
        final_long_run_session = dict(final_session.get("long_run_session", {}))
        checkpoint_inventory = json.loads(checkpoint_inventory_path.read_text(encoding="utf-8"))

        long_run_sample_path = artifacts_dir / "long_run_session_sample.json"
        checkpoint_inventory_copy_path = artifacts_dir / "checkpoint_inventory.json"
        summary_json_path = artifacts_dir / "restart_resume_summary.json"
        summary_md_path = artifacts_dir / "restart_resume_summary.md"

        long_run_sample_path.write_text(
            json.dumps(final_long_run_session, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        checkpoint_inventory_copy_path.write_text(
            json.dumps(checkpoint_inventory, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        summary = {
            "seed_artifacts": {
                "directive_path": str(directive_path),
                "operator_root": str(operator_root),
                "state_root": str(state_root),
                "workspace_root": str(workspace_root),
            },
            "session_id": str(final_long_run_session.get("session_id", "")),
            "workspace_id": str(final_long_run_session.get("workspace_id", "")),
            "checkpoint_ids": [
                str(row.get("checkpoint_id", ""))
                for row in list(checkpoint_inventory.get("checkpoint_rows", []))
            ],
            "interruption_point": "after the first bounded invocation wrote checkpoint 2 and before invocation 2 resumed",
            "restart_method": "forced operator-state server restart against the same persisted operator/state roots",
            "resumed_from_checkpoint_id": str(
                dict(resumed_state.get("long_run", {})).get("latest_checkpoint_id", "")
            ),
            "resumed_cycle_number": int(final_long_run_session.get("current_cycle", 0) or 0),
            "final_state": str(final_long_run_session.get("lifecycle_state", "")),
            "final_reason": str(
                final_long_run_session.get("halt_reason", "")
                or final_long_run_session.get("completion_state", "")
            ),
            "first_server_state": first_server_state,
            "resumed_state": resumed_state,
            "operator_state": operator_state,
            "intervention_state": intervention_state,
            "checkpoint_inventory": checkpoint_inventory,
            "residual_blockers": [],
        }
        summary_json_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _write_markdown_summary(summary_md_path, summary)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
