from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operator_shell.handoff_package import CANONICAL_IMAGE_TAG
from operator_shell.observability import mark_dockerized_agent_probe_result
from operator_shell.observability.config import (
    DEFAULT_LOGICMONITOR_PROOF_SERVICE_NAME,
    endpoint_hint_for,
    service_name_is_logicmonitor_safe,
)
from operator_shell.observability.rc83 import load_json_file, scan_forbidden_strings, write_summary_artifacts
from operator_shell.observability.rc83_2 import (
    DEFAULT_DOCKERIZED_NETWORK,
    DOCKERIZED_AGENT_TRACE_SUMMARY_NAME,
    DOCKER_NETWORK_PREFLIGHT_SUMMARY_NAME,
    dockerized_mapping_status,
    dockerized_protocol_attempts,
    load_portal_confirmation_status,
    normalize_dockerized_endpoint_mode,
    normalize_dockerized_protocol_selection,
    resolve_dockerized_probe_endpoint,
    resolve_rc83_2_artifact_root,
)
from operator_shell.observability.redaction import redact_value

CONTAINER_ARTIFACT_ROOT = "/workspace/novali/artifacts/operator_proof/rc83_2"
DEFAULT_CONTAINER_NAME = "novali-rc83-2-probe"
DEFAULT_COLLECTOR_CONTAINER_NAME = ""
CONTAINER_COMMAND = ["python", "operator_shell/scripts/rc83_2_container_trace_probe.py"]


def _now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()


def _truthy(raw_value: str | bool | None) -> bool:
    return str(raw_value or "").strip().lower() in {"1", "true", "yes", "on"}


def _docker_run(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
    )


def _fake_seed(suffix: str) -> str:
    return f"FAKE_{suffix}_RC83_2_SHOULD_NOT_EXPORT"


FAKE_SEEDS = (
    _fake_seed("SECRET_TOKEN"),
    _fake_seed("NOVALI_SECRET"),
    _fake_seed("API_KEY"),
    _fake_seed("COOKIE"),
    _fake_seed("OTEL_HEADER"),
)


def _resolve_image(env: Mapping[str, str]) -> str:
    return str(env.get("RC83_2_NOVALI_IMAGE") or CANONICAL_IMAGE_TAG).strip() or CANONICAL_IMAGE_TAG


def _resolve_container_name(env: Mapping[str, str]) -> str:
    return str(env.get("RC83_2_NOVALI_CONTAINER_NAME") or DEFAULT_CONTAINER_NAME).strip() or DEFAULT_CONTAINER_NAME


def _resolve_collector_container_name(env: Mapping[str, str]) -> str:
    return (
        str(env.get("RC83_2_LMOTEL_CONTAINER_NAME") or env.get("RC83_LMOTEL_CONTAINER_NAME") or "")
        .strip()
        or DEFAULT_COLLECTOR_CONTAINER_NAME
    )


def _resolve_network_name(env: Mapping[str, str], endpoint_mode: str) -> str:
    if endpoint_mode != "same_network":
        return ""
    return str(env.get("RC83_2_DOCKER_NETWORK") or DEFAULT_DOCKERIZED_NETWORK).strip() or DEFAULT_DOCKERIZED_NETWORK


def sanitize_container_output(output: str, *, max_lines: int = 120, max_chars: int = 12000) -> str:
    lines = str(output or "").splitlines()
    if len(lines) > max_lines:
        half = max_lines // 2
        lines = lines[:half] + ["... output truncated ..."] + lines[-half:]
    sanitized_lines = [str(redact_value(line) or "").rstrip() for line in lines]
    sanitized = "\n".join(sanitized_lines).strip()
    if len(sanitized) > max_chars:
        sanitized = sanitized[: max_chars - 24].rstrip() + "\n... output truncated ..."
    return sanitized


def _markdown_preflight(summary: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# rc83.2 Docker Network Preflight Summary",
            "",
            f"- Result: {summary.get('result', '<unknown>')}",
            f"- Docker available: {summary.get('docker_available', False)}",
            f"- NOVALI image: {summary.get('novali_image', '<none>')}",
            f"- NOVALI image available: {summary.get('novali_image_available', False)}",
            f"- Collector container found: {summary.get('collector_container_found', 'unknown')}",
            f"- Endpoint mode: {summary.get('endpoint_mode', '<none>')}",
            f"- Protocol selection: {summary.get('protocol_selection', '<none>')}",
            f"- Endpoint hint: {summary.get('endpoint_hint', '<none>')}",
            f"- Docker network: {summary.get('docker_network_used', '<none>')}",
            f"- Collector attached to selected network: {summary.get('collector_attached_to_network', 'unknown')}",
            f"- Summary: {summary.get('summary', '')}",
        ]
    )


def _markdown_probe(summary: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# rc83.2 Dockerized Agent Trace Probe Summary",
            "",
            f"- Result: {summary.get('result', '<unknown>')}",
            f"- Proof ID: {summary.get('proof_id', '<none>')}",
            f"- Image: {summary.get('novali_image', '<none>')}",
            f"- Container name: {summary.get('novali_container_name', '<none>')}",
            f"- Collector container: {summary.get('collector_container_name', '<none>')}",
            f"- Endpoint mode: {summary.get('endpoint_mode', '<none>')}",
            f"- Endpoint hint: {summary.get('endpoint_hint', '<none>')}",
            f"- Protocol: {summary.get('otlp_protocol', '<none>')}",
            f"- Service name: {summary.get('service_name', '<none>')}",
            f"- Mapping complete: {summary.get('lm_mapping_attributes_complete', False)}",
            f"- Mapping missing: {', '.join(summary.get('lm_mapping_missing', [])) or '<none>'}",
            f"- Docker network: {summary.get('docker_network_used', '<none>')}",
            f"- Container runtime proven: {summary.get('container_runtime_proven', False)}",
            f"- App-to-collector result: {summary.get('app_to_collector_result', '<unknown>')}",
            f"- Exporter crashed: {summary.get('exporter_crashed', False)}",
            f"- Redaction proof passed: {summary.get('redaction_proof_passed', False)}",
            f"- Portal confirmation: {summary.get('portal_confirmation_state', 'not_recorded')}",
            f"- No secrets captured: {summary.get('no_secrets_captured', False)}",
            f"- Summary: {summary.get('summary', '')}",
        ]
    )


def _write_output_artifact(artifact_root: Path, text: str) -> Path:
    artifact_root.mkdir(parents=True, exist_ok=True)
    output_path = artifact_root / "dockerized_agent_trace_probe_container_output.txt"
    output_path.write_text(str(text).rstrip() + "\n", encoding="utf-8")
    return output_path


def run_docker_network_preflight(
    *,
    env: Mapping[str, str] | None = None,
    docker_run: Callable[[list[str]], Any] = _docker_run,
) -> dict[str, Any]:
    env = dict(env or os.environ)
    artifact_root = resolve_rc83_2_artifact_root(ROOT, env=env)
    endpoint_mode = normalize_dockerized_endpoint_mode(env.get("RC83_2_ENDPOINT_MODE"))
    protocol_selection = normalize_dockerized_protocol_selection(env.get("RC83_2_OTLP_PROTOCOL"))
    selected_protocol = dockerized_protocol_attempts(protocol_selection)[0]
    image_name = _resolve_image(env)
    collector_name = _resolve_collector_container_name(env)
    network_name = _resolve_network_name(env, endpoint_mode)
    endpoint = resolve_dockerized_probe_endpoint(
        env=env,
        protocol=selected_protocol,
        endpoint_mode=endpoint_mode,
    )
    endpoint_hint = endpoint_hint_for(endpoint)

    if not _truthy(env.get("RC83_2_DOCKERIZED_TRACE_PROOF")):
        summary = {
            "schema_name": "novali_rc83_2_docker_network_preflight_summary_v1",
            "generated_at": _now_iso(),
            "result": "skipped",
            "summary": "Dockerized proof preflight skipped because RC83_2_DOCKERIZED_TRACE_PROOF=true was not set.",
            "docker_available": False,
            "novali_image": image_name,
            "novali_image_available": False,
            "collector_container_name": collector_name or None,
            "collector_container_found": "unknown",
            "endpoint_mode": endpoint_mode,
            "protocol_selection": protocol_selection,
            "protocol_attempts": dockerized_protocol_attempts(protocol_selection),
            "endpoint_hint": endpoint_hint,
            "docker_network_used": network_name or None,
            "collector_attached_to_network": "unknown",
            "no_secrets_captured": True,
        }
        write_summary_artifacts(
            artifact_root=artifact_root,
            json_name="docker_network_preflight_summary.json",
            markdown_name="docker_network_preflight_summary.md",
            summary=summary,
            markdown=_markdown_preflight(summary),
        )
        return summary

    version_result = docker_run(["docker", "--version"])
    if int(getattr(version_result, "returncode", 1)) != 0:
        summary = {
            "schema_name": "novali_rc83_2_docker_network_preflight_summary_v1",
            "generated_at": _now_iso(),
            "result": "skipped",
            "summary": "Docker CLI is unavailable on this host, so the Dockerized proof was not run.",
            "docker_available": False,
            "novali_image": image_name,
            "novali_image_available": False,
            "collector_container_name": collector_name or None,
            "collector_container_found": "unknown",
            "endpoint_mode": endpoint_mode,
            "protocol_selection": protocol_selection,
            "protocol_attempts": dockerized_protocol_attempts(protocol_selection),
            "endpoint_hint": endpoint_hint,
            "docker_network_used": network_name or None,
            "collector_attached_to_network": "unknown",
            "no_secrets_captured": True,
        }
        write_summary_artifacts(
            artifact_root=artifact_root,
            json_name="docker_network_preflight_summary.json",
            markdown_name="docker_network_preflight_summary.md",
            summary=summary,
            markdown=_markdown_preflight(summary),
        )
        return summary

    image_result = docker_run(
        ["docker", "image", "ls", "--format", "{{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.Size}}", image_name]
    )
    image_lines = [
        line.strip()
        for line in str(getattr(image_result, "stdout", "") or "").splitlines()
        if line.strip()
    ]
    image_available = any(line.split("\t", 1)[0] == image_name for line in image_lines)

    ps_args = [
        "docker",
        "ps",
        "--format",
        "{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}\t{{.Networks}}",
    ]
    if collector_name:
        ps_args.extend(["--filter", f"name={collector_name}"])
    ps_result = docker_run(ps_args)
    ps_lines = [
        line.strip()
        for line in str(getattr(ps_result, "stdout", "") or "").splitlines()
        if line.strip()
    ]
    collector_safe_status_line = ps_lines[0] if ps_lines else ""
    collector_networks = []
    if ps_lines:
        collector_networks = [
            part.strip()
            for part in (ps_lines[0].split("\t")[4] if len(ps_lines[0].split("\t")) >= 5 else "").split(",")
            if part.strip()
        ]

    network_available = False
    network_created = False
    if endpoint_mode == "same_network":
        network_result = docker_run(["docker", "network", "ls", "--format", "{{.Name}}\t{{.Driver}}\t{{.Scope}}"])
        network_lines = [
            line.strip()
            for line in str(getattr(network_result, "stdout", "") or "").splitlines()
            if line.strip()
        ]
        network_available = any(line.split("\t", 1)[0] == network_name for line in network_lines)
        if network_name and not network_available:
            create_result = docker_run(["docker", "network", "create", "--driver", "bridge", network_name])
            if int(getattr(create_result, "returncode", 1)) == 0:
                network_available = True
                network_created = True

    collector_attached_to_network: str | bool = "unknown"
    if endpoint_mode == "same_network":
        collector_attached_to_network = bool(network_name and network_name in collector_networks)

    summary = {
        "schema_name": "novali_rc83_2_docker_network_preflight_summary_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "summary": (
            "Dockerized probe preflight completed with safe Docker summary commands only."
            if image_available
            else "Dockerized probe preflight completed, but the requested NOVALI image is not available locally."
        ),
        "docker_available": True,
        "novali_image": image_name,
        "novali_image_available": image_available,
        "collector_container_name": collector_name or None,
        "collector_container_found": (bool(ps_lines) if collector_name else "unknown"),
        "collector_safe_status_line": collector_safe_status_line,
        "endpoint_mode": endpoint_mode,
        "protocol_selection": protocol_selection,
        "protocol_attempts": dockerized_protocol_attempts(protocol_selection),
        "endpoint_hint": endpoint_hint,
        "docker_network_used": network_name or None,
        "docker_network_available": network_available if endpoint_mode == "same_network" else "n/a",
        "docker_network_created": network_created,
        "collector_attached_to_network": collector_attached_to_network,
        "collector_networks": collector_networks,
        "no_secrets_captured": True,
    }
    if endpoint_mode == "same_network" and network_name == "bridge":
        summary["summary"] += " Default bridge networking may not provide reliable container-name DNS; prefer a user-defined bridge network."
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name="docker_network_preflight_summary.json",
        markdown_name="docker_network_preflight_summary.md",
        summary=summary,
        markdown=_markdown_preflight(summary),
    )
    return summary


def build_container_environment(
    *,
    env: Mapping[str, str] | None,
    protocol: str,
    endpoint_mode: str,
) -> dict[str, str]:
    env = dict(env or os.environ)
    prepared = {
        "NOVALI_OTEL_ENABLED": "true",
        "OTEL_EXPORTER_OTLP_PROTOCOL": protocol,
        "OTEL_EXPORTER_OTLP_ENDPOINT": resolve_dockerized_probe_endpoint(
            env=env,
            protocol=protocol,
            endpoint_mode=endpoint_mode,
        ),
        "OTEL_SERVICE_NAME": str(env.get("OTEL_SERVICE_NAME") or DEFAULT_LOGICMONITOR_PROOF_SERVICE_NAME).strip()
        or DEFAULT_LOGICMONITOR_PROOF_SERVICE_NAME,
        "NOVALI_OTEL_REDACTION_MODE": str(env.get("NOVALI_OTEL_REDACTION_MODE") or "strict").strip()
        or "strict",
        "NOVALI_OBSERVABILITY_STATUS_DETAIL": "compact",
        "RC83_2_ENDPOINT_MODE": endpoint_mode,
        "RC83_2_OTLP_PROTOCOL": protocol,
        "RC83_2_NOVALI_IMAGE": _resolve_image(env),
        "RC83_2_NOVALI_CONTAINER_NAME": _resolve_container_name(env),
        "RC83_2_LMOTEL_CONTAINER_NAME": _resolve_collector_container_name(env),
        "RC83_2_DOCKER_NETWORK": _resolve_network_name(env, endpoint_mode),
        "RC83_2_PROOF_ARTIFACT_ROOT": CONTAINER_ARTIFACT_ROOT,
    }
    for key in (
        "NOVALI_LM_HOST_NAME",
        "NOVALI_LM_IP",
        "NOVALI_LM_RESOURCE_TYPE",
        "NOVALI_LM_RESOURCE_GROUP",
    ):
        value = str(env.get(key) or "").strip()
        if value:
            prepared[key] = value
    if (
        prepared.get("NOVALI_LM_HOST_NAME")
        and prepared.get("NOVALI_LM_IP")
        and not prepared.get("NOVALI_LM_RESOURCE_TYPE")
    ):
        prepared["NOVALI_LM_RESOURCE_TYPE"] = "host"
    return prepared


def build_docker_run_command(
    *,
    env: Mapping[str, str] | None,
    protocol: str,
    endpoint_mode: str,
    host_artifact_root: Path,
) -> list[str]:
    env = dict(env or os.environ)
    container_name = _resolve_container_name(env)
    network_name = _resolve_network_name(env, endpoint_mode)
    prepared_env = build_container_environment(env=env, protocol=protocol, endpoint_mode=endpoint_mode)
    command = ["docker", "run", "--rm", "--name", container_name]
    if endpoint_mode == "same_network" and network_name:
        command.extend(["--network", network_name])
    if endpoint_mode in {"host_gateway", "host_published"} and platform.system().lower() != "windows":
        command.extend(["--add-host", "host.docker.internal:host-gateway"])
    command.extend(["-v", f"{host_artifact_root}:{CONTAINER_ARTIFACT_ROOT}"])
    for key, value in prepared_env.items():
        command.extend(["-e", f"{key}={value}"])
    command.append(_resolve_image(env))
    command.extend(CONTAINER_COMMAND)
    return command


def run_dockerized_trace_probe(
    *,
    env: Mapping[str, str] | None = None,
    docker_run: Callable[[list[str]], Any] = _docker_run,
) -> dict[str, Any]:
    env = dict(env or os.environ)
    artifact_root = resolve_rc83_2_artifact_root(ROOT, env=env)
    artifact_root.mkdir(parents=True, exist_ok=True)
    preflight = run_docker_network_preflight(env=env, docker_run=docker_run)
    endpoint_mode = normalize_dockerized_endpoint_mode(env.get("RC83_2_ENDPOINT_MODE"))
    service_name = (
        str(env.get("OTEL_SERVICE_NAME") or DEFAULT_LOGICMONITOR_PROOF_SERVICE_NAME).strip()
        or DEFAULT_LOGICMONITOR_PROOF_SERVICE_NAME
    )
    mapping = dockerized_mapping_status(service_name=service_name, env=env)
    portal_confirmation = load_portal_confirmation_status(package_root=ROOT, env=env)
    protocol_attempts = dockerized_protocol_attempts(env.get("RC83_2_OTLP_PROTOCOL"))
    output_sections: list[str] = []
    attempt_records: list[dict[str, Any]] = []
    selected_summary: dict[str, Any] = {}
    summary_path = artifact_root / DOCKERIZED_AGENT_TRACE_SUMMARY_NAME

    if not _truthy(env.get("RC83_2_DOCKERIZED_TRACE_PROOF")):
        summary = {
            "schema_name": "novali_rc83_2_dockerized_agent_trace_probe_summary_v1",
            "generated_at": _now_iso(),
            "result": "skipped",
            "summary": "Dockerized agent trace probe skipped because RC83_2_DOCKERIZED_TRACE_PROOF=true was not set.",
            "opt_in_enabled": False,
            "proof_id": None,
            "novali_image": _resolve_image(env),
            "novali_container_name": _resolve_container_name(env),
            "collector_container_name": _resolve_collector_container_name(env) or None,
            "endpoint_mode": endpoint_mode,
            "endpoint_hint": endpoint_hint_for(
                resolve_dockerized_probe_endpoint(
                    env=env,
                    protocol=protocol_attempts[0],
                    endpoint_mode=endpoint_mode,
                )
            ),
            "otlp_protocol": protocol_attempts[0],
            "service_name": service_name,
            "service_name_lm_safe": service_name_is_logicmonitor_safe(service_name),
            "lm_mapping_attributes_complete": bool(mapping["complete"]),
            "lm_mapping_missing": list(mapping["missing"]),
            "docker_network_used": _resolve_network_name(env, endpoint_mode) or None,
            "docker_network_mode": endpoint_mode,
            "container_runtime_proven": False,
            "app_to_collector_result": "not_run",
            "exporter_crashed": False,
            "redaction_proof_passed": True,
            "portal_confirmation_state": portal_confirmation.get("confirmation_state", "not_recorded"),
            "no_secrets_captured": True,
            "attempts": [],
        }
        write_summary_artifacts(
            artifact_root=artifact_root,
            json_name="dockerized_agent_trace_probe_summary.json",
            markdown_name="dockerized_agent_trace_probe_summary.md",
            summary=summary,
            markdown=_markdown_probe(summary),
        )
        _write_output_artifact(artifact_root, "Dockerized probe skipped.\n")
        mark_dockerized_agent_probe_result(
            enabled=False,
            result="skipped",
            probe_id=None,
            probe_time=summary["generated_at"],
            endpoint_hint=summary["endpoint_hint"],
            endpoint_mode=endpoint_mode,
            network_mode=endpoint_mode,
            otlp_protocol=summary["otlp_protocol"],
            service_name=service_name,
            service_name_lm_safe=bool(summary["service_name_lm_safe"]),
            lm_mapping_attributes_complete=bool(mapping["complete"]),
            lm_mapping_missing=list(mapping["missing"]),
            container_runtime_proven=False,
            no_secrets_captured=True,
        )
        return summary

    if preflight.get("docker_available") is False:
        summary = {
            "schema_name": "novali_rc83_2_dockerized_agent_trace_probe_summary_v1",
            "generated_at": _now_iso(),
            "result": "skipped",
            "summary": "Dockerized agent trace probe skipped because Docker is unavailable on this host.",
            "opt_in_enabled": True,
            "proof_id": None,
            "novali_image": _resolve_image(env),
            "novali_container_name": _resolve_container_name(env),
            "collector_container_name": _resolve_collector_container_name(env) or None,
            "endpoint_mode": endpoint_mode,
            "endpoint_hint": preflight.get("endpoint_hint", "unset"),
            "otlp_protocol": protocol_attempts[0],
            "service_name": service_name,
            "service_name_lm_safe": service_name_is_logicmonitor_safe(service_name),
            "lm_mapping_attributes_complete": bool(mapping["complete"]),
            "lm_mapping_missing": list(mapping["missing"]),
            "docker_network_used": _resolve_network_name(env, endpoint_mode) or None,
            "docker_network_mode": endpoint_mode,
            "container_runtime_proven": False,
            "app_to_collector_result": "not_run",
            "exporter_crashed": False,
            "redaction_proof_passed": True,
            "portal_confirmation_state": portal_confirmation.get("confirmation_state", "not_recorded"),
            "no_secrets_captured": True,
            "attempts": [],
        }
        write_summary_artifacts(
            artifact_root=artifact_root,
            json_name="dockerized_agent_trace_probe_summary.json",
            markdown_name="dockerized_agent_trace_probe_summary.md",
            summary=summary,
            markdown=_markdown_probe(summary),
        )
        _write_output_artifact(artifact_root, "Docker CLI unavailable.\n")
        mark_dockerized_agent_probe_result(
            enabled=True,
            result="skipped",
            probe_id=None,
            probe_time=summary["generated_at"],
            endpoint_hint=str(summary["endpoint_hint"]),
            endpoint_mode=endpoint_mode,
            network_mode=endpoint_mode,
            otlp_protocol=summary["otlp_protocol"],
            service_name=service_name,
            service_name_lm_safe=bool(summary["service_name_lm_safe"]),
            lm_mapping_attributes_complete=bool(mapping["complete"]),
            lm_mapping_missing=list(mapping["missing"]),
            container_runtime_proven=False,
            no_secrets_captured=True,
        )
        return summary

    if not bool(preflight.get("novali_image_available")):
        summary = {
            "schema_name": "novali_rc83_2_dockerized_agent_trace_probe_summary_v1",
            "generated_at": _now_iso(),
            "result": "failure",
            "summary": "Dockerized agent trace probe could not run because the requested NOVALI image is not available locally.",
            "opt_in_enabled": True,
            "proof_id": None,
            "novali_image": _resolve_image(env),
            "novali_container_name": _resolve_container_name(env),
            "collector_container_name": _resolve_collector_container_name(env) or None,
            "endpoint_mode": endpoint_mode,
            "endpoint_hint": preflight.get("endpoint_hint", "unset"),
            "otlp_protocol": protocol_attempts[0],
            "service_name": service_name,
            "service_name_lm_safe": service_name_is_logicmonitor_safe(service_name),
            "lm_mapping_attributes_complete": bool(mapping["complete"]),
            "lm_mapping_missing": list(mapping["missing"]),
            "docker_network_used": _resolve_network_name(env, endpoint_mode) or None,
            "docker_network_mode": endpoint_mode,
            "container_runtime_proven": False,
            "app_to_collector_result": "not_run",
            "exporter_crashed": False,
            "redaction_proof_passed": True,
            "portal_confirmation_state": portal_confirmation.get("confirmation_state", "not_recorded"),
            "no_secrets_captured": True,
            "attempts": [],
        }
        write_summary_artifacts(
            artifact_root=artifact_root,
            json_name="dockerized_agent_trace_probe_summary.json",
            markdown_name="dockerized_agent_trace_probe_summary.md",
            summary=summary,
            markdown=_markdown_probe(summary),
        )
        _write_output_artifact(artifact_root, "Requested NOVALI image unavailable.\n")
        mark_dockerized_agent_probe_result(
            enabled=True,
            result="failure",
            probe_id=None,
            probe_time=summary["generated_at"],
            endpoint_hint=str(summary["endpoint_hint"]),
            endpoint_mode=endpoint_mode,
            network_mode=endpoint_mode,
            otlp_protocol=summary["otlp_protocol"],
            service_name=service_name,
            service_name_lm_safe=bool(summary["service_name_lm_safe"]),
            lm_mapping_attributes_complete=bool(mapping["complete"]),
            lm_mapping_missing=list(mapping["missing"]),
            container_runtime_proven=False,
            no_secrets_captured=True,
        )
        return summary

    for protocol in protocol_attempts:
        command = build_docker_run_command(
            env=env,
            protocol=protocol,
            endpoint_mode=endpoint_mode,
            host_artifact_root=artifact_root,
        )
        result = docker_run(command)
        combined_output = "\n".join(
            [
                f"=== protocol:{protocol} returncode:{int(getattr(result, 'returncode', 1))} ===",
                sanitize_container_output(str(getattr(result, "stdout", "") or "")),
                sanitize_container_output(str(getattr(result, "stderr", "") or "")),
            ]
        ).strip()
        output_sections.append(combined_output)
        attempt_summary = load_json_file(summary_path)
        attempt_records.append(
            {
                "protocol": protocol,
                "returncode": int(getattr(result, "returncode", 1)),
                "result": str(attempt_summary.get("result", "unknown") or "unknown"),
            }
        )
        if attempt_summary:
            selected_summary = dict(attempt_summary)
            selected_summary["container_returncode"] = int(getattr(result, "returncode", 1))
        if str(selected_summary.get("result", "")).strip() == "success":
            break

    output_text = "\n\n".join(section for section in output_sections if section).strip() or "No container output captured."
    output_path = _write_output_artifact(artifact_root, output_text)
    if not selected_summary:
        missing_probe_script = (
            "rc83_2_container_trace_probe.py" in output_text
            and "can't open file" in output_text.lower()
        )
        selected_summary = {
            "schema_name": "novali_rc83_2_dockerized_agent_trace_probe_summary_v1",
            "generated_at": _now_iso(),
            "result": "failure",
            "summary": (
                "Dockerized NOVALI proof container did not produce a proof summary artifact because the image predates rc83.2 and must be rebuilt."
                if missing_probe_script
                else "Dockerized NOVALI proof container did not produce a proof summary artifact."
            ),
            "proof_id": None,
            "otlp_protocol": protocol_attempts[-1],
            "service_name": service_name,
            "service_name_lm_safe": service_name_is_logicmonitor_safe(service_name),
            "lm_mapping_attributes_complete": bool(mapping["complete"]),
            "lm_mapping_missing": list(mapping["missing"]),
            "container_runtime_proven": False,
            "exporter_crashed": True,
            "app_to_collector_result": "failure",
        }

    selected_summary.update(
        {
            "schema_name": "novali_rc83_2_dockerized_agent_trace_probe_summary_v1",
            "novali_image": _resolve_image(env),
            "novali_container_name": _resolve_container_name(env),
            "collector_container_name": _resolve_collector_container_name(env) or None,
            "endpoint_mode": endpoint_mode,
            "endpoint_hint": selected_summary.get(
                "endpoint_hint",
                endpoint_hint_for(
                    resolve_dockerized_probe_endpoint(
                        env=env,
                        protocol=str(selected_summary.get("otlp_protocol", protocol_attempts[-1])),
                        endpoint_mode=endpoint_mode,
                    )
                ),
            ),
            "docker_network_used": _resolve_network_name(env, endpoint_mode) or None,
            "docker_network_mode": endpoint_mode,
            "portal_confirmation_state": portal_confirmation.get("confirmation_state", "not_recorded"),
            "attempts": attempt_records,
            "container_output_artifact": str(output_path),
            "docker_network_preflight_artifact": str(
                artifact_root / DOCKER_NETWORK_PREFLIGHT_SUMMARY_NAME
            ),
        }
    )

    forbidden_hits = scan_forbidden_strings(
        [
            json.dumps(selected_summary, sort_keys=True, default=str),
            output_text,
            json.dumps(preflight, sort_keys=True, default=str),
        ],
        FAKE_SEEDS,
    )
    no_secrets_captured = not forbidden_hits and bool(selected_summary.get("no_secrets_captured", True))
    selected_summary["no_secrets_captured"] = no_secrets_captured
    if forbidden_hits:
        selected_summary.update(
            {
                "result": "failure",
                "summary": "Dockerized NOVALI proof failed because fake secret seed text appeared in local proof material.",
                "forbidden_hits": forbidden_hits,
                "redaction_proof_passed": False,
            }
        )

    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name="dockerized_agent_trace_probe_summary.json",
        markdown_name="dockerized_agent_trace_probe_summary.md",
        summary=selected_summary,
        markdown=_markdown_probe(selected_summary),
    )
    mark_dockerized_agent_probe_result(
        enabled=True,
        result=str(selected_summary.get("result", "failure")),
        probe_id=str(selected_summary.get("proof_id", "")).strip() or None,
        probe_time=str(selected_summary.get("generated_at", "")).strip() or None,
        endpoint_hint=str(selected_summary.get("endpoint_hint", "unset")),
        endpoint_mode=endpoint_mode,
        network_mode=endpoint_mode,
        otlp_protocol=str(selected_summary.get("otlp_protocol", "unknown")),
        service_name=str(selected_summary.get("service_name", service_name)),
        service_name_lm_safe=bool(selected_summary.get("service_name_lm_safe", False)),
        lm_mapping_attributes_complete=bool(
            selected_summary.get("lm_mapping_attributes_complete", False)
        ),
        lm_mapping_missing=list(selected_summary.get("lm_mapping_missing", [])),
        container_runtime_proven=bool(selected_summary.get("container_runtime_proven", False)),
        container_hostname=str(selected_summary.get("container_hostname", "")).strip() or None,
        no_secrets_captured=no_secrets_captured,
    )
    return selected_summary


def main() -> int:
    summary = run_dockerized_trace_probe()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if str(summary.get("result", "")).strip() in {"success", "skipped"} else 1


if __name__ == "__main__":
    sys.exit(main())
