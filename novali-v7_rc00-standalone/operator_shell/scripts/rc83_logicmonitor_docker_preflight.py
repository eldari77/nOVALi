from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operator_shell.observability.config import (
    endpoint_hint_for,
    resolve_live_collector_endpoint,
)
from operator_shell.observability.rc83 import (
    resolve_rc83_artifact_root,
    write_summary_artifacts,
)

def _truthy(raw_value: str | bool | None) -> bool:
    return str(raw_value or "").strip().lower() in {"1", "true", "yes", "on"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _safe_endpoint(endpoint: str) -> str:
    normalized = str(endpoint or "").strip()
    if not normalized:
        return ""
    try:
        parts = urlsplit(normalized)
    except ValueError:
        return ""
    if parts.username or parts.password or parts.query or parts.fragment:
        return ""
    return normalized


def _docker_run(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
    )


def _markdown_summary(summary: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# rc83 Docker Preflight Summary",
            "",
            f"- Result: {summary.get('result', '<unknown>')}",
            f"- Docker available: {summary.get('docker_available', False)}",
            f"- Matching container found: {summary.get('matching_container_found', 'unknown')}",
            f"- Endpoint hint: {summary.get('endpoint_network_hint', '<none>')}",
            f"- Safe status line: {summary.get('safe_status_line', '<none>')}",
            f"- Safe port mapping line: {summary.get('safe_port_mapping_line', '<none>')}",
            f"- Summary: {summary.get('summary', '')}",
        ]
    )


def run_docker_preflight(
    *,
    env: Mapping[str, str] | None = None,
    docker_run: Callable[[list[str]], Any] = _docker_run,
) -> dict[str, Any]:
    env = env or os.environ
    artifact_root = resolve_rc83_artifact_root(ROOT, env=env)
    selected_endpoint = resolve_live_collector_endpoint(env)
    safe_endpoint = _safe_endpoint(selected_endpoint)
    network_hint = endpoint_hint_for(selected_endpoint)
    container_name = str(env.get("RC83_LMOTEL_CONTAINER_NAME") or "").strip()

    if not _truthy(env.get("RC83_DOCKER_PREFLIGHT")):
        summary = {
            "schema_name": "novali_rc83_logicmonitor_docker_preflight_summary_v1",
            "generated_at": _now_iso(),
            "result": "skipped",
            "summary": "Docker preflight skipped because RC83_DOCKER_PREFLIGHT=true was not set.",
            "docker_available": False,
            "matching_container_found": "unknown",
            "safe_status_line": "",
            "safe_port_mapping_line": "",
            "selected_endpoint": safe_endpoint,
            "endpoint_network_hint": network_hint,
            "no_secrets_captured": True,
        }
        write_summary_artifacts(
            artifact_root=artifact_root,
            json_name="logicmonitor_docker_preflight_summary.json",
            markdown_name="logicmonitor_docker_preflight_summary.md",
            summary=summary,
            markdown=_markdown_summary(summary),
        )
        return summary

    version_result = docker_run(["docker", "--version"])
    if int(getattr(version_result, "returncode", 1)) != 0:
        summary = {
            "schema_name": "novali_rc83_logicmonitor_docker_preflight_summary_v1",
            "generated_at": _now_iso(),
            "result": "skipped",
            "summary": "Docker CLI is unavailable on this host, so no collector preflight was performed.",
            "docker_available": False,
            "matching_container_found": "unknown",
            "safe_status_line": "",
            "safe_port_mapping_line": "",
            "selected_endpoint": safe_endpoint,
            "endpoint_network_hint": network_hint,
            "no_secrets_captured": True,
        }
        write_summary_artifacts(
            artifact_root=artifact_root,
            json_name="logicmonitor_docker_preflight_summary.json",
            markdown_name="logicmonitor_docker_preflight_summary.md",
            summary=summary,
            markdown=_markdown_summary(summary),
        )
        return summary

    ps_args = [
        "docker",
        "ps",
        "--format",
        "{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}",
    ]
    if container_name:
        ps_args.extend(["--filter", f"name={container_name}"])
    ps_result = docker_run(ps_args)
    ps_lines = [line.strip() for line in str(getattr(ps_result, "stdout", "") or "").splitlines() if line.strip()]
    matching_container_found: str | bool = "unknown" if not container_name else False
    safe_status_line = ps_lines[0] if ps_lines else ""
    if container_name:
        matching_container_found = bool(ps_lines)

    safe_port_mapping_line = ""
    if container_name and matching_container_found:
        port_result = docker_run(["docker", "port", container_name])
        if int(getattr(port_result, "returncode", 1)) == 0:
            safe_port_mapping_line = (
                str(getattr(port_result, "stdout", "") or "").strip().splitlines()[0]
                if str(getattr(port_result, "stdout", "") or "").strip()
                else ""
            )

    summary = {
        "schema_name": "novali_rc83_logicmonitor_docker_preflight_summary_v1",
        "generated_at": _now_iso(),
        "result": "success" if int(getattr(ps_result, "returncode", 1)) == 0 else "failure",
        "summary": (
            "Docker collector preflight completed with read-only summary commands only."
            if int(getattr(ps_result, "returncode", 1)) == 0
            else "Docker collector preflight could not complete a safe docker ps summary."
        ),
        "docker_available": True,
        "matching_container_found": matching_container_found,
        "safe_status_line": safe_status_line,
        "safe_port_mapping_line": safe_port_mapping_line,
        "selected_endpoint": safe_endpoint,
        "endpoint_network_hint": network_hint,
        "no_secrets_captured": True,
    }
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name="logicmonitor_docker_preflight_summary.json",
        markdown_name="logicmonitor_docker_preflight_summary.md",
        summary=summary,
        markdown=_markdown_summary(summary),
    )
    return summary


def main() -> int:
    summary = run_docker_preflight()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if str(summary.get("result", "")).strip() in {"success", "skipped"} else 1


if __name__ == "__main__":
    sys.exit(main())
