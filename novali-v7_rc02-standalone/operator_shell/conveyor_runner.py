from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping, Protocol


CONTAINER_CHECKOUT_PATH = "/novali/checkout/checkout.json"
CONTAINER_WORKSPACE_PATH = "/novali/workspace"
CONTAINER_OUTBOX_PATH = "/novali/outbox"
CONTAINER_INBOX_PATH = "/novali/inbox"
CONTAINER_PROGRESS_PATH = "/novali/progress"
CONTAINER_CAMPAIGN_DRAFT_PATH = "/novali/campaign_drafts"
CONTAINER_CAMPAIGN_CANONICAL_PATH = "/novali/campaign_canonical"
CONTAINER_SUPPORT_PACKS_PATH = "/novali/support_packs"


class ConveyorChildRunner(Protocol):
    def available(self) -> bool:
        ...

    def plan_child_container(self, child: dict[str, Any]) -> dict[str, Any]:
        ...

    def spawn_child_container(self, child: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
        ...

    def inspect_child_container(self, child: dict[str, Any]) -> dict[str, Any]:
        ...

    def stop_child_container(self, child: dict[str, Any]) -> dict[str, Any]:
        ...

    def remove_child_container(self, child: dict[str, Any]) -> dict[str, Any]:
        ...

    def collect_return_packet(self, child: dict[str, Any]) -> dict[str, Any]:
        ...


def _mount_arg(host_path: str | Path, container_path: str, *, readonly: bool) -> str:
    suffix = ",readonly" if readonly else ""
    return f"type=bind,source={host_path},target={container_path}{suffix}"


def _normalize_root(value: str | Path) -> str:
    return str(value or "").replace("\\", "/").rstrip("/")


class DockerConveyorChildRunner:
    def __init__(
        self,
        *,
        image: str = "novali-v7-standalone:local",
        docker_cli: str = "docker",
        memory_limit: str = "512m",
        cpu_limit: str = "0.5",
        run_timeout_seconds: int = 300,
        host_bind_root: str = "",
        container_bind_root: str = "",
    ) -> None:
        self.image = str(image or "novali-v7-standalone:local")
        self.docker_cli = str(docker_cli or "docker")
        self.memory_limit = str(memory_limit or "512m")
        self.cpu_limit = str(cpu_limit or "0.5")
        self.run_timeout_seconds = int(run_timeout_seconds or 300)
        self.host_bind_root = _normalize_root(
            host_bind_root or os.environ.get("NOVALI_CONVEYOR_HOST_BIND_ROOT", "")
        )
        self.container_bind_root = _normalize_root(
            container_bind_root or os.environ.get("NOVALI_CONVEYOR_CONTAINER_BIND_ROOT", "")
        )

    def available(self) -> bool:
        try:
            result = subprocess.run(
                [self.docker_cli, "version", "--format", "{{json .Server}}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0

    def plan_child_container(self, child: dict[str, Any]) -> dict[str, Any]:
        child_run_id = str(child.get("child_run_id", "") or "child")
        container_name = "novali-child-" + "".join(
            char if char.isalnum() or char in {"-", "_"} else "-"
            for char in child_run_id.lower()
        )[:80]
        checkout_path = self._host_bind_path(str(child.get("checkout_path", "")))
        workspace_root = self._host_bind_path(str(child.get("workspace_root", "")))
        outbox_path = self._host_bind_path(str(child.get("outbox_path", "")))
        inbox_path = self._host_bind_path(str(child.get("inbox_path", "")))
        progress_path = self._host_bind_path(str(child.get("progress_path", "")))
        campaign_draft_path = self._host_bind_path(str(child.get("campaign_draft_path", "")))
        campaign_canonical_path = self._host_bind_path(str(child.get("campaign_canonical_path", "")))
        support_pack_checkout_path = self._host_bind_path(str(child.get("support_pack_checkout_path", "")))
        child_execution_mode = str(child.get("child_execution_mode", "") or "oneshot_return")
        command = [
            self.docker_cli,
            "run",
            "-d",
            "--name",
            container_name,
            "--workdir",
            CONTAINER_WORKSPACE_PATH,
            "--network",
            "none",
            "--user",
            "65532:65532",
            "--cap-drop=ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--memory",
            self.memory_limit,
            "--cpus",
            self.cpu_limit,
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=64m",
            "--mount",
            _mount_arg(checkout_path, CONTAINER_CHECKOUT_PATH, readonly=True),
            "--mount",
            _mount_arg(workspace_root, CONTAINER_WORKSPACE_PATH, readonly=False),
            "--mount",
            _mount_arg(outbox_path, CONTAINER_OUTBOX_PATH, readonly=False),
        ]
        if inbox_path:
            command.extend(["--mount", _mount_arg(inbox_path, CONTAINER_INBOX_PATH, readonly=False)])
        if progress_path:
            command.extend(["--mount", _mount_arg(progress_path, CONTAINER_PROGRESS_PATH, readonly=False)])
        if campaign_draft_path:
            command.extend(["--mount", _mount_arg(campaign_draft_path, CONTAINER_CAMPAIGN_DRAFT_PATH, readonly=False)])
        if campaign_canonical_path:
            command.extend(["--mount", _mount_arg(campaign_canonical_path, CONTAINER_CAMPAIGN_CANONICAL_PATH, readonly=True)])
        if support_pack_checkout_path:
            command.extend(["--mount", _mount_arg(support_pack_checkout_path, CONTAINER_SUPPORT_PACKS_PATH, readonly=True)])
        command.extend(
            [
                "--env",
                "NOVALI_CONVEYOR_CHILD=1",
                "--env",
                f"NOVALI_CONVEYOR_CHILD_RUN_ID={child_run_id}",
                "--env",
                "PYTHONPATH=/workspace/novali",
                self.image,
                "python",
                "-m",
                "operator_shell.conveyor_child",
                "--checkout",
                CONTAINER_CHECKOUT_PATH,
                "--workspace",
                CONTAINER_WORKSPACE_PATH,
                "--outbox",
                CONTAINER_OUTBOX_PATH,
            ]
        )
        if child_execution_mode == "resident_campaign":
            command.append("--resident")
            if inbox_path:
                command.extend(["--inbox", CONTAINER_INBOX_PATH])
            if progress_path:
                command.extend(["--progress", CONTAINER_PROGRESS_PATH])
        return {
            "spawn_mode": "docker_child_container",
            "container_name": container_name,
            "container_image": self.image,
            "docker_cli": self.docker_cli,
            "docker_command": command,
            "checkout_container_path": CONTAINER_CHECKOUT_PATH,
            "workspace_container_path": CONTAINER_WORKSPACE_PATH,
            "outbox_container_path": CONTAINER_OUTBOX_PATH,
            "inbox_container_path": CONTAINER_INBOX_PATH if inbox_path else "",
            "progress_container_path": CONTAINER_PROGRESS_PATH if progress_path else "",
            "campaign_draft_container_path": CONTAINER_CAMPAIGN_DRAFT_PATH if campaign_draft_path else "",
            "campaign_canonical_container_path": CONTAINER_CAMPAIGN_CANONICAL_PATH if campaign_canonical_path else "",
            "outbox_path": str(outbox_path),
            "inbox_path": str(inbox_path),
            "progress_path": str(progress_path),
            "campaign_draft_path": str(campaign_draft_path),
            "campaign_canonical_path": str(campaign_canonical_path),
            "support_pack_checkout_path": str(support_pack_checkout_path),
            "support_pack_container_path": CONTAINER_SUPPORT_PACKS_PATH if support_pack_checkout_path else "",
            "child_execution_mode": child_execution_mode,
            "network_policy": "deny_all",
            "run_as_user": "65532:65532",
            "memory_limit": self.memory_limit,
            "cpu_limit": self.cpu_limit,
            "host_bind_root": self.host_bind_root,
            "container_bind_root": self.container_bind_root,
        }

    def _host_bind_path(self, value: str | Path) -> str:
        text = _normalize_root(value)
        if self.host_bind_root and self.container_bind_root:
            if text == self.container_bind_root:
                return self.host_bind_root
            prefix = self.container_bind_root + "/"
            if text.startswith(prefix):
                suffix = text[len(prefix) :]
                return f"{self.host_bind_root}/{suffix}"
        if self.host_bind_root and text and not Path(text).is_absolute() and not text.startswith("/"):
            return f"{self.host_bind_root}/{text}"
        return str(value)

    def spawn_child_container(self, child: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
        try:
            result = subprocess.run(
                [str(item) for item in list(plan.get("docker_command", []))],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "spawn_state": "docker_spawn_failed", "error": str(exc)}
        container_id = str(result.stdout or "").strip()
        if result.returncode != 0 or not container_id:
            return {
                "ok": False,
                "spawn_state": "docker_spawn_failed",
                "exit_code": result.returncode,
                "stderr": str(result.stderr or "").strip()[:500],
            }
        return {
            "ok": True,
            "spawn_state": "docker_child_container_running",
            "container_id": container_id,
            "container_name": str(plan.get("container_name", "")),
        }

    def inspect_child_container(self, child: dict[str, Any]) -> dict[str, Any]:
        container_ref = str(child.get("container_id", "") or child.get("container_name", "")).strip()
        if not container_ref:
            return {"state": "unknown", "error": "container_ref_missing"}
        try:
            result = subprocess.run(
                [self.docker_cli, "inspect", "--format", "{{json .State}}", container_ref],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"state": "unknown", "error": str(exc)}
        if result.returncode != 0:
            return {
                "state": "unknown",
                "error": str(result.stderr or "").strip()[:500],
                "exit_code": result.returncode,
            }
        try:
            state_payload = json.loads(str(result.stdout or "{}"))
        except json.JSONDecodeError:
            state_payload = {}
        status = str(state_payload.get("Status", "") or "").lower()
        exit_code = state_payload.get("ExitCode")
        return {
            "state": "exited" if status == "exited" else "running" if status == "running" else status or "unknown",
            "exit_code": exit_code,
            "raw_state": state_payload,
        }

    def stop_child_container(self, child: dict[str, Any]) -> dict[str, Any]:
        container_ref = str(child.get("container_id", "") or child.get("container_name", "")).strip()
        if not container_ref:
            return {"ok": False, "state": "stop_failed", "error": "container_ref_missing"}
        try:
            result = subprocess.run(
                [self.docker_cli, "rm", "-f", container_ref],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "state": "stop_failed", "error": str(exc)}
        return {
            "ok": result.returncode == 0,
            "state": "stopped" if result.returncode == 0 else "stop_failed",
            "stderr": str(result.stderr or "").strip()[:500],
        }

    def remove_child_container(self, child: dict[str, Any]) -> dict[str, Any]:
        container_ref = str(child.get("container_id", "") or child.get("container_name", "")).strip()
        if not container_ref:
            return {"ok": False, "state": "remove_failed", "error": "container_ref_missing"}
        try:
            result = subprocess.run(
                [self.docker_cli, "rm", container_ref],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "state": "remove_failed", "error": str(exc)}
        stderr = str(result.stderr or "").strip()
        already_removed = result.returncode != 0 and "No such container" in stderr
        return {
            "ok": result.returncode == 0 or already_removed,
            "state": "removed" if result.returncode == 0 else "already_removed" if already_removed else "remove_failed",
            "stderr": stderr[:500],
        }

    def collect_return_packet(self, child: dict[str, Any]) -> dict[str, Any]:
        outbox = Path(str(child.get("outbox_path", "")))
        packet_path = outbox / "return_packet.json"
        if not packet_path.exists():
            return {}
        try:
            payload = json.loads(packet_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}


class SimulatedConveyorChildRunner:
    def available(self) -> bool:
        return True

    def plan_child_container(self, child: dict[str, Any]) -> dict[str, Any]:
        return {
            "spawn_mode": "simulated_child_container",
            "container_name": "",
            "container_image": "",
            "docker_command": [],
            "outbox_path": str(child.get("outbox_path", "")),
        }

    def spawn_child_container(self, child: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "spawn_state": "simulated_child_container_running", "container_id": ""}

    def inspect_child_container(self, child: dict[str, Any]) -> dict[str, Any]:
        return {"state": str(child.get("state", "running") or "running"), "exit_code": None}

    def stop_child_container(self, child: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "state": "stopped"}

    def remove_child_container(self, child: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "state": "removed"}

    def collect_return_packet(self, child: dict[str, Any]) -> dict[str, Any]:
        return {}


def runner_from_scheduler(scheduler: Mapping[str, Any]) -> ConveyorChildRunner:
    mode = str(scheduler.get("runner_mode", "simulated") or "simulated").strip().lower()
    if mode in {"docker", "auto"}:
        docker = DockerConveyorChildRunner(
            image=str(scheduler.get("docker_image", "novali-v7-standalone:local") or "novali-v7-standalone:local"),
            docker_cli=str(scheduler.get("docker_cli", "docker") or "docker"),
            memory_limit=str(scheduler.get("child_memory_limit", "512m") or "512m"),
            cpu_limit=str(scheduler.get("child_cpu_limit", "0.5") or "0.5"),
            host_bind_root=str(scheduler.get("host_bind_root", "") or ""),
            container_bind_root=str(scheduler.get("container_bind_root", "") or ""),
        )
        if mode == "docker" or docker.available():
            return docker
    return SimulatedConveyorChildRunner()
