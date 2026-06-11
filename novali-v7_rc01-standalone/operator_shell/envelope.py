from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any


OPERATOR_RUNTIME_ENVELOPE_SCHEMA_NAME = "OperatorRuntimeEnvelopeSpec"
OPERATOR_RUNTIME_ENVELOPE_SCHEMA_VERSION = "operator_runtime_envelope_spec_v1"
EFFECTIVE_OPERATOR_RUNTIME_ENVELOPE_SCHEMA_NAME = "EffectiveOperatorRuntimeEnvelope"
EFFECTIVE_OPERATOR_RUNTIME_ENVELOPE_SCHEMA_VERSION = "effective_operator_runtime_envelope_v1"
OPERATOR_RUNTIME_LAUNCH_PLAN_SCHEMA_NAME = "OperatorRuntimeLaunchPlan"
OPERATOR_RUNTIME_LAUNCH_PLAN_SCHEMA_VERSION = "operator_runtime_launch_plan_v1"

BACKEND_LOCAL_GUARDED = "local_guarded"
BACKEND_LOCAL_DOCKER = "local_docker"
BACKEND_K8S_JOB = "k8s_job"
BACKEND_K8S_POD = "k8s_pod"

SUPPORTED_BACKEND_KINDS = {
    BACKEND_LOCAL_GUARDED,
    BACKEND_LOCAL_DOCKER,
}
RESERVED_BACKEND_KINDS = {
    BACKEND_K8S_JOB,
    BACKEND_K8S_POD,
}
KNOWN_BACKEND_KINDS = SUPPORTED_BACKEND_KINDS | RESERVED_BACKEND_KINDS

SUPPORTED_NETWORK_POLICY_INTENTS = {
    "deny_all",
}
SUPPORTED_WRITABLE_MOUNT_POLICIES = {
    "explicit_operator_roots_only",
}
SUPPORTED_ROOT_FILESYSTEM_MODES = {
    "read_only_root",
}
SUPPORTED_SUBPROCESS_POLICY_SOURCES = {
    "inherit_runtime_constraints",
}
KNOWN_REQUIRED_TRANSLATIONS = {
    "memory_limit",
    "cpu_limit_cpus",
    "session_timeout",
    "writable_mount_policy",
    "root_filesystem_mode",
    "subprocess_policy",
    "working_directory_boundary",
    "network_policy_intent",
    "trusted_source_local_mounts",
    "non_root_execution",
}

CONTAINER_PACKAGE_ROOT = PurePosixPath("/workspace/novali")
CONTAINER_DIRECTIVE_ROOT = PurePosixPath("/workspace/operator_inputs")
CONTAINER_TRUSTED_SOURCE_ROOT = PurePosixPath("/workspace/trusted_sources")
CONTAINER_REFERENCE_ROOT = PurePosixPath("/workspace/reference")
CONTAINER_EXTERNAL_WRITE_ROOT = PurePosixPath("/workspace/external_write_roots")
CONTAINER_OPERATOR_SESSION_PATH = PurePosixPath("/operator_state/effective_operator_session_runtime.json")


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


def _is_under_path(candidate: str | Path, root: str | Path) -> bool:
    try:
        Path(str(candidate)).resolve().relative_to(Path(str(root)).resolve())
        return True
    except ValueError:
        return False


def _sanitize_token(value: Any, *, fallback: str = "item") -> str:
    token = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()).strip("._-")
    return token or fallback


def _normalize_container_path(value: Any) -> str:
    if isinstance(value, PurePosixPath):
        return str(value)
    text = str(value or "").strip().replace("\\", "/")
    if not text:
        return ""
    return str(PurePosixPath(text))


def _join_container_path(base: str | PurePosixPath, relative: str | Path | PurePosixPath | None = None) -> PurePosixPath:
    current = PurePosixPath(_normalize_container_path(base))
    if relative in {None, ""}:
        return current
    if isinstance(relative, PurePosixPath):
        parts = relative.parts
    else:
        parts = Path(str(relative)).parts
    for part in parts:
        cleaned = str(part).replace("\\", "/").strip("/")
        if not cleaned or cleaned == ".":
            continue
        current /= cleaned
    return current


def default_operator_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        root = Path(local_app_data) / "NOVALI" / "operator_state"
    else:
        root = Path.home() / ".novali_operator"
    root.mkdir(parents=True, exist_ok=True)
    return root


def operator_runtime_envelope_spec_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "operator_runtime_envelope_spec_latest.json"


def runtime_session_runtime_view_dir(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    target = base / "runtime_session_views"
    target.mkdir(parents=True, exist_ok=True)
    return target


def operator_runtime_launch_plan_dir(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    target = base / "launch_plans"
    target.mkdir(parents=True, exist_ok=True)
    return target


def operator_runtime_launch_plan_latest_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "operator_runtime_launch_plan_latest.json"


def build_default_operator_runtime_envelope_spec(
    package_root: str | Path | None = None,
) -> dict[str, Any]:
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    return {
        "schema_name": OPERATOR_RUNTIME_ENVELOPE_SCHEMA_NAME,
        "schema_version": OPERATOR_RUNTIME_ENVELOPE_SCHEMA_VERSION,
        "generated_at": _now(),
        "required_for_launch": True,
        "backend_kind": BACKEND_LOCAL_GUARDED,
        "launch_mode": "canonical_operator",
        "required_backend_translations": [],
        "constraint_intents": {
            "memory_limit_source": "inherit_runtime_constraints",
            "cpu_limit_cpus": None,
            "session_timeout_source": "inherit_runtime_constraints",
            "working_directory_source": "inherit_runtime_constraints",
            "writable_mount_policy": "explicit_operator_roots_only",
            "root_filesystem_mode": "read_only_root",
            "subprocess_policy_source": "inherit_runtime_constraints",
            "network_policy_intent": "deny_all",
        },
        "backend_settings": {
            "local_guarded": {
                "enabled": True,
                "notes": "Existing operator-policy, launcher, and runtime-guard path.",
            },
            "local_docker": {
                "image": "python:3.12-slim",
                "docker_cli": "docker",
                "read_only_root_filesystem": True,
                "run_as_non_root": True,
                "drop_all_capabilities": True,
                "no_new_privileges": True,
                "tmpfs_size_mb": 64,
                "network_mode": "none",
                "mount_package_root_read_only": True,
                "allow_enabled_network_api_sources": False,
                "experimental": True,
                "package_root_hint": _normalize_path(package_root_path),
            },
            "reserved_future_backends": sorted(RESERVED_BACKEND_KINDS),
        },
    }


def probe_runtime_backend_capabilities(
    *,
    docker_cli: str = "docker",
    timeout_seconds: float = 1.0,
) -> dict[str, Any]:
    local_guarded = {
        "backend_kind": BACKEND_LOCAL_GUARDED,
        "available": True,
        "availability_class": "ready",
        "reason": "local guarded execution is available through the existing launcher/runtime-guard path",
    }
    local_docker: dict[str, Any] = {
        "backend_kind": BACKEND_LOCAL_DOCKER,
        "available": False,
        "availability_class": "backend_unavailable",
        "reason": "docker backend has not been probed yet",
        "docker_cli": str(docker_cli),
    }
    try:
        result = subprocess.run(
            [str(docker_cli), "version", "--format", "{{json .Server}}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=max(0.5, float(timeout_seconds)),
            check=False,
        )
    except FileNotFoundError:
        local_docker["reason"] = f"docker CLI not found: {docker_cli}"
    except subprocess.TimeoutExpired:
        local_docker["reason"] = "docker backend probe timed out"
    except Exception as exc:
        local_docker["reason"] = f"docker backend probe failed: {exc}"
    else:
        if int(result.returncode) != 0:
            detail = (result.stderr or result.stdout or "").strip()
            local_docker["reason"] = detail[:300] or "docker version probe failed"
        else:
            try:
                server = json.loads(result.stdout.strip() or "{}")
            except json.JSONDecodeError:
                server = {}
            local_docker.update(
                {
                    "available": True,
                    "availability_class": "ready",
                    "reason": "docker backend is available for local single-host envelope launches",
                    "server_version": str(server.get("Version", "")).strip(),
                    "server_platform": str(server.get("Os", "")).strip(),
                }
            )

    reserved = [
        {
            "backend_kind": backend_kind,
            "available": False,
            "availability_class": "deferred",
            "reason": "reserved for later orchestration-tier implementation",
        }
        for backend_kind in sorted(RESERVED_BACKEND_KINDS)
    ]
    return {
        "checked_at": _now(),
        "backends": {
            BACKEND_LOCAL_GUARDED: local_guarded,
            BACKEND_LOCAL_DOCKER: local_docker,
            **{item["backend_kind"]: item for item in reserved},
        },
        "available_backends": [
            backend_kind
            for backend_kind, item in {
                BACKEND_LOCAL_GUARDED: local_guarded,
                BACKEND_LOCAL_DOCKER: local_docker,
            }.items()
            if bool(item.get("available", False))
        ],
    }


def _constraint_requested_value(
    runtime_constraints: dict[str, Any],
    field_name: str,
) -> Any:
    return dict(runtime_constraints.get("constraints", {})).get(field_name)


def _build_field_record(
    *,
    requested_value: Any,
    enforcement_class: str,
    reason: str,
    backend_value: Any = None,
) -> dict[str, Any]:
    return {
        "requested_value": requested_value,
        "backend_value": backend_value,
        "enforcement_class": str(enforcement_class),
        "reason": str(reason),
    }


def validate_operator_runtime_envelope_spec(
    payload: dict[str, Any],
    *,
    runtime_constraints: dict[str, Any] | None = None,
    trusted_source_bindings: dict[str, Any] | None = None,
    backend_probe: dict[str, Any] | None = None,
    enforce_backend_availability: bool = True,
) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    errors: list[str] = []
    if str(payload.get("schema_name", "")) != OPERATOR_RUNTIME_ENVELOPE_SCHEMA_NAME:
        errors.append(f"schema_name must be {OPERATOR_RUNTIME_ENVELOPE_SCHEMA_NAME}")
    if str(payload.get("schema_version", "")) != OPERATOR_RUNTIME_ENVELOPE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {OPERATOR_RUNTIME_ENVELOPE_SCHEMA_VERSION}")

    backend_kind = str(payload.get("backend_kind", BACKEND_LOCAL_GUARDED)).strip() or BACKEND_LOCAL_GUARDED
    if backend_kind not in KNOWN_BACKEND_KINDS:
        errors.append(f"backend_kind must be one of {sorted(KNOWN_BACKEND_KINDS)}")
    if backend_kind in RESERVED_BACKEND_KINDS:
        errors.append(f"backend_kind {backend_kind} is reserved for future work and is not implemented in this slice")

    intents = dict(payload.get("constraint_intents", {}))
    backend_settings = dict(payload.get("backend_settings", {}))
    docker_settings = dict(backend_settings.get(BACKEND_LOCAL_DOCKER, {}))
    required_backend_translations = [
        str(item).strip()
        for item in list(payload.get("required_backend_translations", []))
        if str(item).strip()
    ]
    unknown_required = sorted(set(required_backend_translations) - KNOWN_REQUIRED_TRANSLATIONS)
    if unknown_required:
        errors.append(
            "required_backend_translations contains unknown items: " + ", ".join(unknown_required)
        )

    cpu_limit_cpus = intents.get("cpu_limit_cpus")
    if cpu_limit_cpus in {"", None}:
        normalized_cpu_limit = None
    else:
        try:
            normalized_cpu_limit = float(cpu_limit_cpus)
        except (TypeError, ValueError):
            normalized_cpu_limit = None
            errors.append("constraint_intents.cpu_limit_cpus must be a positive number or null")
        else:
            if normalized_cpu_limit <= 0:
                errors.append("constraint_intents.cpu_limit_cpus must be > 0 when set")

    writable_mount_policy = str(
        intents.get("writable_mount_policy", "explicit_operator_roots_only")
    ).strip() or "explicit_operator_roots_only"
    if writable_mount_policy not in SUPPORTED_WRITABLE_MOUNT_POLICIES:
        errors.append(
            "constraint_intents.writable_mount_policy must be one of "
            + ", ".join(sorted(SUPPORTED_WRITABLE_MOUNT_POLICIES))
        )

    root_filesystem_mode = str(intents.get("root_filesystem_mode", "read_only_root")).strip() or "read_only_root"
    if root_filesystem_mode not in SUPPORTED_ROOT_FILESYSTEM_MODES:
        errors.append(
            "constraint_intents.root_filesystem_mode must be one of "
            + ", ".join(sorted(SUPPORTED_ROOT_FILESYSTEM_MODES))
        )

    subprocess_policy_source = str(
        intents.get("subprocess_policy_source", "inherit_runtime_constraints")
    ).strip() or "inherit_runtime_constraints"
    if subprocess_policy_source not in SUPPORTED_SUBPROCESS_POLICY_SOURCES:
        errors.append(
            "constraint_intents.subprocess_policy_source must be one of "
            + ", ".join(sorted(SUPPORTED_SUBPROCESS_POLICY_SOURCES))
        )

    network_policy_intent = str(intents.get("network_policy_intent", "deny_all")).strip() or "deny_all"
    if network_policy_intent not in SUPPORTED_NETWORK_POLICY_INTENTS:
        errors.append(
            "constraint_intents.network_policy_intent must be one of "
            + ", ".join(sorted(SUPPORTED_NETWORK_POLICY_INTENTS))
        )

    docker_image = str(docker_settings.get("image", "python:3.12-slim")).strip()
    docker_cli = str(docker_settings.get("docker_cli", "docker")).strip() or "docker"
    if backend_kind == BACKEND_LOCAL_DOCKER and not docker_image:
        errors.append("backend_settings.local_docker.image must not be empty for local_docker launches")

    backend_probe = dict(backend_probe or probe_runtime_backend_capabilities(docker_cli=docker_cli))
    backend_rows = dict(backend_probe.get("backends", {}))
    selected_backend_probe = dict(backend_rows.get(backend_kind, {}))
    if (
        backend_kind in SUPPORTED_BACKEND_KINDS
        and enforce_backend_availability
        and not bool(selected_backend_probe.get("available", backend_kind == BACKEND_LOCAL_GUARDED))
    ):
        errors.append(
            f"selected runtime backend is unavailable: {backend_kind} ({selected_backend_probe.get('reason', 'unknown reason')})"
        )

    runtime_constraints = dict(runtime_constraints or {})
    trusted_source_bindings = dict(trusted_source_bindings or {})
    enabled_bindings = [
        dict(item)
        for item in list(trusted_source_bindings.get("bindings", []))
        if bool(dict(item).get("enabled", False))
    ]
    enabled_network_bindings = [
        str(item.get("source_id", ""))
        for item in enabled_bindings
        if str(item.get("source_kind", "")) == "network_api"
    ]
    if backend_kind == BACKEND_LOCAL_DOCKER and enabled_network_bindings:
        errors.append(
            "local_docker backend currently supports only local trusted sources; enabled network_api bindings must be disabled first: "
            + ", ".join(enabled_network_bindings)
        )

    field_enforcement: dict[str, Any] = {}
    max_memory_mb = _constraint_requested_value(runtime_constraints, "max_memory_mb")
    max_child_processes = _constraint_requested_value(runtime_constraints, "max_child_processes")
    subprocess_mode = _constraint_requested_value(runtime_constraints, "subprocess_mode")
    working_directory = _constraint_requested_value(runtime_constraints, "working_directory")
    allowed_write_roots = list(dict(runtime_constraints.get("constraints", {})).get("allowed_write_roots", []))
    session_time_limit_seconds = _constraint_requested_value(runtime_constraints, "session_time_limit_seconds")

    if backend_kind == BACKEND_LOCAL_DOCKER:
        field_enforcement["memory_limit"] = _build_field_record(
            requested_value=max_memory_mb,
            backend_value=(None if max_memory_mb in {None, ""} else f"{int(max_memory_mb)}m"),
            enforcement_class="hard_enforced" if max_memory_mb not in {None, ""} else "not_requested",
            reason="translated to docker --memory for local_docker launches",
        )
        field_enforcement["cpu_limit_cpus"] = _build_field_record(
            requested_value=normalized_cpu_limit,
            backend_value=normalized_cpu_limit,
            enforcement_class="hard_enforced" if normalized_cpu_limit is not None else "not_requested",
            reason=(
                "translated to docker --cpus for local_docker launches"
                if normalized_cpu_limit is not None
                else "no CPU quota intent requested"
            ),
        )
        field_enforcement["session_timeout"] = _build_field_record(
            requested_value=session_time_limit_seconds,
            backend_value=session_time_limit_seconds,
            enforcement_class="watchdog_enforced",
            reason="launcher watchdog remains outside the container and terminates docker run on timeout",
        )
        field_enforcement["writable_mount_policy"] = _build_field_record(
            requested_value=writable_mount_policy,
            backend_value="explicit_rw_mounts_only",
            enforcement_class="hard_enforced",
            reason="docker launch plan mounts only operator-approved writable roots as read-write",
        )
        field_enforcement["root_filesystem_mode"] = _build_field_record(
            requested_value=root_filesystem_mode,
            backend_value="--read-only",
            enforcement_class="hard_enforced",
            reason="docker launch plan uses a read-only root filesystem plus explicit writable mounts",
        )
        field_enforcement["subprocess_policy"] = _build_field_record(
            requested_value={"subprocess_mode": subprocess_mode, "max_child_processes": max_child_processes},
            backend_value="runtime_guard_inside_container",
            enforcement_class="hard_enforced",
            reason="the runtime guard remains active inside the container using a derived frozen runtime session",
        )
        field_enforcement["working_directory_boundary"] = _build_field_record(
            requested_value=working_directory,
            backend_value=str(CONTAINER_PACKAGE_ROOT),
            enforcement_class="hard_enforced",
            reason="docker launch sets a bounded workdir and the runtime guard blocks cwd escapes",
        )
        field_enforcement["network_policy_intent"] = _build_field_record(
            requested_value=network_policy_intent,
            backend_value="--network none" if network_policy_intent == "deny_all" else None,
            enforcement_class="hard_enforced" if network_policy_intent == "deny_all" else "unsupported_on_this_platform",
            reason=(
                "docker launch plan uses --network none for deny_all intent"
                if network_policy_intent == "deny_all"
                else "only deny_all network policy intent is implemented in this local_docker slice"
            ),
        )
        field_enforcement["trusted_source_local_mounts"] = _build_field_record(
            requested_value=[str(item.get("source_id", "")) for item in enabled_bindings],
            backend_value="read_only_bind_mounts",
            enforcement_class="hard_enforced",
            reason="enabled local trusted sources are mounted read-only into the container launch plan",
        )
        field_enforcement["non_root_execution"] = _build_field_record(
            requested_value=bool(docker_settings.get("run_as_non_root", True)),
            backend_value="65532:65532",
            enforcement_class="hard_enforced" if bool(docker_settings.get("run_as_non_root", True)) else "unsupported_on_this_platform",
            reason=(
                "docker launch uses a non-root numeric user"
                if bool(docker_settings.get("run_as_non_root", True))
                else "local_docker must keep non-root execution enabled in this conservative slice"
            ),
        )
    else:
        field_enforcement["memory_limit"] = _build_field_record(
            requested_value=max_memory_mb,
            backend_value=max_memory_mb,
            enforcement_class="watchdog_enforced" if sys.platform.startswith("win") else "unsupported_on_this_platform",
            reason=(
                "Windows launcher polls child working-set memory and terminates on violation"
                if sys.platform.startswith("win")
                else "memory watchdog backend is only implemented for Windows in the current local_guarded slice"
            ),
        )
        field_enforcement["cpu_limit_cpus"] = _build_field_record(
            requested_value=normalized_cpu_limit,
            backend_value=None,
            enforcement_class="unsupported_on_this_platform",
            reason="local guarded execution does not claim OS-level CPU throttling",
        )
        field_enforcement["session_timeout"] = _build_field_record(
            requested_value=session_time_limit_seconds,
            backend_value=session_time_limit_seconds,
            enforcement_class="watchdog_enforced",
            reason="launcher watchdog terminates the child process when the session time budget is exceeded",
        )
        field_enforcement["writable_mount_policy"] = _build_field_record(
            requested_value=writable_mount_policy,
            backend_value=allowed_write_roots,
            enforcement_class="hard_enforced",
            reason="runtime guard blocks normal Python mutation outside operator-approved write roots",
        )
        field_enforcement["root_filesystem_mode"] = _build_field_record(
            requested_value=root_filesystem_mode,
            backend_value=None,
            enforcement_class="unsupported_on_this_platform",
            reason="local guarded execution does not claim OS-level read-only root filesystem enforcement",
        )
        field_enforcement["subprocess_policy"] = _build_field_record(
            requested_value={"subprocess_mode": subprocess_mode, "max_child_processes": max_child_processes},
            backend_value="runtime_guard",
            enforcement_class="hard_enforced",
            reason="runtime guard blocks or bounds subprocess APIs inside the governed process",
        )
        field_enforcement["working_directory_boundary"] = _build_field_record(
            requested_value=working_directory,
            backend_value=working_directory,
            enforcement_class="hard_enforced",
            reason="launcher sets the working directory and runtime guard blocks cwd escapes",
        )
        field_enforcement["network_policy_intent"] = _build_field_record(
            requested_value=network_policy_intent,
            backend_value=None,
            enforcement_class="unsupported_on_this_platform",
            reason="local guarded execution does not claim a host network sandbox",
        )
        field_enforcement["trusted_source_local_mounts"] = _build_field_record(
            requested_value=[str(item.get("source_id", "")) for item in enabled_bindings],
            backend_value="host_local_paths",
            enforcement_class="hard_enforced",
            reason="local trusted sources stay on host paths and remain outside directive authority",
        )
        field_enforcement["non_root_execution"] = _build_field_record(
            requested_value=None,
            backend_value=None,
            enforcement_class="unsupported_on_this_platform",
            reason="local guarded execution does not claim OS-level user isolation",
        )

    for field_name in required_backend_translations:
        record = dict(field_enforcement.get(field_name, {}))
        if record.get("enforcement_class") not in {"hard_enforced", "watchdog_enforced"}:
            errors.append(
                f"required backend translation could not be satisfied honestly: {field_name} ({record.get('reason', 'no reason available')})"
            )

    normalized = {
        "schema_name": OPERATOR_RUNTIME_ENVELOPE_SCHEMA_NAME,
        "schema_version": OPERATOR_RUNTIME_ENVELOPE_SCHEMA_VERSION,
        "generated_at": str(payload.get("generated_at", "")) or _now(),
        "required_for_launch": bool(payload.get("required_for_launch", True)),
        "backend_kind": backend_kind,
        "launch_mode": str(payload.get("launch_mode", "canonical_operator")) or "canonical_operator",
        "required_backend_translations": required_backend_translations,
        "constraint_intents": {
            "memory_limit_source": "inherit_runtime_constraints",
            "cpu_limit_cpus": normalized_cpu_limit,
            "session_timeout_source": "inherit_runtime_constraints",
            "working_directory_source": "inherit_runtime_constraints",
            "writable_mount_policy": writable_mount_policy,
            "root_filesystem_mode": root_filesystem_mode,
            "subprocess_policy_source": subprocess_policy_source,
            "network_policy_intent": network_policy_intent,
        },
        "backend_settings": {
            "local_guarded": {
                "enabled": True,
                "notes": "Existing operator-policy, launcher, and runtime-guard path.",
            },
            "local_docker": {
                "image": docker_image,
                "docker_cli": docker_cli,
                "read_only_root_filesystem": bool(docker_settings.get("read_only_root_filesystem", True)),
                "run_as_non_root": bool(docker_settings.get("run_as_non_root", True)),
                "drop_all_capabilities": bool(docker_settings.get("drop_all_capabilities", True)),
                "no_new_privileges": bool(docker_settings.get("no_new_privileges", True)),
                "tmpfs_size_mb": int(docker_settings.get("tmpfs_size_mb", 64) or 64),
                "network_mode": str(docker_settings.get("network_mode", "none")) or "none",
                "mount_package_root_read_only": bool(docker_settings.get("mount_package_root_read_only", True)),
                "allow_enabled_network_api_sources": bool(docker_settings.get("allow_enabled_network_api_sources", False)),
                "experimental": bool(docker_settings.get("experimental", True)),
            },
            "reserved_future_backends": sorted(RESERVED_BACKEND_KINDS),
        },
    }

    effective = {
        "schema_name": EFFECTIVE_OPERATOR_RUNTIME_ENVELOPE_SCHEMA_NAME,
        "schema_version": EFFECTIVE_OPERATOR_RUNTIME_ENVELOPE_SCHEMA_VERSION,
        "generated_at": _now(),
        "backend_kind": backend_kind,
        "launch_mode": str(normalized.get("launch_mode", "")),
        "backend_probe": backend_probe,
        "selected_backend": selected_backend_probe,
        "constraint_translation": field_enforcement,
        "summary": {
            "hard_enforced_count": sum(
                1 for item in field_enforcement.values() if item.get("enforcement_class") == "hard_enforced"
            ),
            "watchdog_enforced_count": sum(
                1 for item in field_enforcement.values() if item.get("enforcement_class") == "watchdog_enforced"
            ),
            "unsupported_count": sum(
                1 for item in field_enforcement.values() if item.get("enforcement_class") == "unsupported_on_this_platform"
            ),
            "not_requested_count": sum(
                1 for item in field_enforcement.values() if item.get("enforcement_class") == "not_requested"
            ),
            "enabled_trusted_source_count": len(enabled_bindings),
            "enabled_network_source_count": len(enabled_network_bindings),
        },
        "refusal_conditions": list(errors),
    }
    return errors, normalized, effective


def _register_mount(
    mounts: list[dict[str, Any]],
    *,
    host_path: str | Path,
    container_path: str | Path,
    access_mode: str,
    purpose: str,
    is_file: bool = False,
) -> None:
    normalized_host = _normalize_path(host_path)
    if not normalized_host:
        return
    normalized_container = _normalize_container_path(container_path)
    for item in mounts:
        if item["host_path"] == normalized_host and item["container_path"] == normalized_container:
            return
    mounts.append(
        {
            "host_path": normalized_host,
            "container_path": normalized_container,
            "access_mode": access_mode,
            "purpose": purpose,
            "is_file": bool(is_file),
        }
    )


def _map_host_path_to_container(
    path_value: str | Path | None,
    mounts: list[dict[str, Any]],
) -> str:
    if not path_value:
        return ""
    candidate = Path(str(path_value)).resolve()
    best_match: dict[str, Any] | None = None
    best_length = -1
    for mount in mounts:
        if bool(mount.get("is_file", False)):
            host_path = Path(str(mount["host_path"])).resolve()
            if candidate == host_path and len(str(host_path)) > best_length:
                best_length = len(str(host_path))
                best_match = mount
            continue
        host_root = Path(str(mount["host_path"])).resolve()
        try:
            relative = candidate.relative_to(host_root)
        except ValueError:
            continue
        if len(str(host_root)) > best_length:
            best_length = len(str(host_root))
            best_match = {**mount, "_relative": relative}
    if best_match is None:
        return ""
    if bool(best_match.get("is_file", False)):
        return _normalize_container_path(best_match["container_path"])
    relative = Path(str(best_match.get("_relative", "")))
    return str(_join_container_path(best_match["container_path"], relative))


def _container_mounts_for_local_docker(
    *,
    session: dict[str, Any],
    package_root: Path,
    runtime_session_host_path: Path,
    directive_file: str | Path | None,
    clarification_file: str | Path | None,
    state_root: str | Path | None,
) -> tuple[list[dict[str, Any]], dict[str, str], list[str]]:
    mounts: list[dict[str, Any]] = []
    path_labels: dict[str, str] = {}
    errors: list[str] = []

    _register_mount(
        mounts,
        host_path=package_root,
        container_path=CONTAINER_PACKAGE_ROOT,
        access_mode="ro",
        purpose="package_root",
    )
    _register_mount(
        mounts,
        host_path=runtime_session_host_path,
        container_path=CONTAINER_OPERATOR_SESSION_PATH,
        access_mode="ro",
        purpose="derived_runtime_session",
        is_file=True,
    )

    runtime_constraints = dict(dict(session.get("effective_runtime_constraints", {})).get("constraints", {}))
    for index, root in enumerate(list(runtime_constraints.get("allowed_write_roots", []))):
        host_root = Path(str(root)).resolve()
        if _is_under_path(host_root, package_root):
            relative = host_root.relative_to(package_root)
            container_root = _join_container_path(CONTAINER_PACKAGE_ROOT, relative)
        else:
            container_root = _join_container_path(CONTAINER_EXTERNAL_WRITE_ROOT, f"root_{index}")
        _register_mount(
            mounts,
            host_path=host_root,
            container_path=container_root,
            access_mode="rw",
            purpose="allowed_write_root",
        )

    if directive_file:
        directive_host = Path(str(directive_file)).resolve()
        existing = _map_host_path_to_container(directive_host, mounts)
        if existing:
            path_labels["directive_file"] = existing
        else:
            directive_container = CONTAINER_DIRECTIVE_ROOT / "directive_bootstrap.json"
            _register_mount(
                mounts,
                host_path=directive_host,
                container_path=directive_container,
                access_mode="ro",
                purpose="directive_file",
                is_file=True,
            )
            path_labels["directive_file"] = str(directive_container)

    if clarification_file:
        clarification_host = Path(str(clarification_file)).resolve()
        existing = _map_host_path_to_container(clarification_host, mounts)
        if existing:
            path_labels["clarification_file"] = existing
        else:
            clarification_container = CONTAINER_DIRECTIVE_ROOT / "clarification_responses.json"
            _register_mount(
                mounts,
                host_path=clarification_host,
                container_path=clarification_container,
                access_mode="ro",
                purpose="clarification_file",
                is_file=True,
            )
            path_labels["clarification_file"] = str(clarification_container)

    if state_root:
        mapped_state_root = _map_host_path_to_container(state_root, mounts)
        if not mapped_state_root:
            state_root_host = Path(str(state_root)).resolve()
            if directive_file is None and state_root_host.exists():
                resume_state_container = _join_container_path(
                    CONTAINER_REFERENCE_ROOT,
                    "persisted_state",
                )
                _register_mount(
                    mounts,
                    host_path=state_root_host,
                    container_path=resume_state_container,
                    access_mode="ro",
                    purpose="state_root_resume",
                )
                path_labels["state_root"] = str(resume_state_container)
            else:
                errors.append(
                    f"state_root is not inside the package root or an operator-approved writable mount: {state_root}"
                )
        else:
            path_labels["state_root"] = mapped_state_root

    trusted_bindings = dict(session.get("trusted_source_bindings", {}))
    for binding in list(trusted_bindings.get("bindings", [])):
        row = dict(binding)
        if not bool(row.get("enabled", False)):
            continue
        source_kind = str(row.get("source_kind", ""))
        if source_kind not in {"local_path", "local_bundle"}:
            continue
        host_path_hint = str(row.get("path_hint", "")).strip()
        if not host_path_hint:
            continue
        if _map_host_path_to_container(host_path_hint, mounts):
            continue
        host_path = Path(host_path_hint).resolve()
        if not host_path.exists():
            errors.append(f"enabled trusted source path is missing for docker mount planning: {host_path}")
            continue
        if _is_under_path(host_path, package_root):
            relative = host_path.relative_to(package_root)
            container_path = _join_container_path(CONTAINER_PACKAGE_ROOT, relative)
        elif host_path.name.lower().startswith("novali-v"):
            container_path = _join_container_path(
                CONTAINER_REFERENCE_ROOT,
                _sanitize_token(host_path.name, fallback="reference"),
            )
        else:
            container_path = _join_container_path(
                CONTAINER_TRUSTED_SOURCE_ROOT,
                _sanitize_token(row.get("source_id", ""), fallback="source"),
            )
        _register_mount(
            mounts,
            host_path=host_path,
            container_path=container_path,
            access_mode="ro",
            purpose=f"trusted_source:{row.get('source_id', '')}",
        )

    return mounts, path_labels, errors


def build_operator_runtime_launch_plan(
    *,
    session: dict[str, Any],
    package_root: str | Path,
    operator_root: str | Path,
    entry_script: str | Path,
    runtime_args: list[str] | None = None,
    directive_file: str | Path | None = None,
    clarification_file: str | Path | None = None,
    state_root: str | Path | None = None,
) -> tuple[dict[str, Any], list[str]]:
    package_root_path = Path(package_root).resolve()
    operator_root_path = Path(operator_root).resolve()
    entry_script_path = Path(entry_script).resolve()
    runtime_args = [str(item) for item in list(runtime_args or [])]

    envelope_spec = dict(session.get("operator_runtime_envelope_spec", {}))
    runtime_constraints = dict(session.get("effective_runtime_constraints", {}))
    trusted_source_bindings = dict(session.get("trusted_source_bindings", {}))
    errors, normalized_envelope, effective_envelope = validate_operator_runtime_envelope_spec(
        envelope_spec,
        runtime_constraints=runtime_constraints,
        trusted_source_bindings=trusted_source_bindings,
        enforce_backend_availability=True,
    )
    if errors:
        return {}, errors

    backend_kind = str(normalized_envelope.get("backend_kind", BACKEND_LOCAL_GUARDED))
    runtime_constraint_payload = dict(session.get("effective_runtime_constraints", {}))
    workspace_policy = dict(runtime_constraint_payload.get("workspace_policy", {}))
    execution_profile = str(runtime_constraint_payload.get("execution_profile", "")).strip()
    if backend_kind == BACKEND_LOCAL_GUARDED:
        plan = {
            "schema_name": OPERATOR_RUNTIME_LAUNCH_PLAN_SCHEMA_NAME,
            "schema_version": OPERATOR_RUNTIME_LAUNCH_PLAN_SCHEMA_VERSION,
            "generated_at": _now(),
            "backend_kind": BACKEND_LOCAL_GUARDED,
            "launch_mode": str(normalized_envelope.get("launch_mode", "")),
            "session_id": str(session.get("session_id", "")),
            "experimental": False,
            "entry_script": str(entry_script_path),
            "runtime_args": runtime_args,
            "execution_profile": execution_profile,
            "workspace_id": str(workspace_policy.get("workspace_id", "")),
            "workspace_root": str(workspace_policy.get("workspace_root", "")),
            "host_working_directory": str(
                Path(str(dict(runtime_constraints.get("constraints", {})).get("working_directory", package_root_path))).resolve()
            ),
            "working_directory": str(
                Path(str(dict(runtime_constraints.get("constraints", {})).get("working_directory", package_root_path))).resolve()
            ),
            "command": [sys.executable, str(entry_script_path), *runtime_args],
            "constraint_translation": dict(effective_envelope.get("constraint_translation", {})),
            "summary": {
                "backend_kind": BACKEND_LOCAL_GUARDED,
                "execution_profile": execution_profile,
                "workspace_id": str(workspace_policy.get("workspace_id", "")),
                "workspace_root": str(workspace_policy.get("workspace_root", "")),
                "operator_runtime_envelope_path": str(operator_runtime_envelope_spec_path(operator_root_path)),
                "effective_operator_session_path": str(operator_root_path / "effective_operator_session_latest.json"),
            },
        }
        return plan, []

    docker_settings = dict(dict(normalized_envelope.get("backend_settings", {})).get(BACKEND_LOCAL_DOCKER, {}))
    runtime_session_host_path = runtime_session_runtime_view_dir(operator_root_path) / (
        _sanitize_token(session.get("session_id", "runtime_session"), fallback="runtime_session") + "_docker_runtime.json"
    )
    mounts, path_labels, mount_errors = _container_mounts_for_local_docker(
        session=session,
        package_root=package_root_path,
        runtime_session_host_path=runtime_session_host_path,
        directive_file=directive_file,
        clarification_file=clarification_file,
        state_root=state_root,
    )
    if mount_errors:
        return {}, mount_errors

    mapped_entry_script = _map_host_path_to_container(entry_script_path, mounts)
    if not mapped_entry_script:
        return {}, [f"entry_script is not available inside the docker launch envelope: {entry_script_path}"]

    container_working_directory = _map_host_path_to_container(
        dict(runtime_constraints.get("constraints", {})).get("working_directory", ""),
        mounts,
    )
    if not container_working_directory:
        return {}, ["working_directory could not be mapped into the docker launch envelope"]

    constraint_translation = dict(effective_envelope.get("constraint_translation", {}))
    container_name = "novali_" + _sanitize_token(session.get("session_id", "runtime"), fallback="runtime")
    docker_command: list[str] = [
        str(docker_settings.get("docker_cli", "docker")),
        "run",
        "--rm",
        "--name",
        container_name,
        "--workdir",
        container_working_directory,
        "--read-only",
        "--network",
        "none",
        "--security-opt",
        "no-new-privileges:true",
        "--cap-drop=ALL",
        "--user",
        "65532:65532",
        "--tmpfs",
        f"/tmp:rw,nosuid,nodev,size={int(docker_settings.get('tmpfs_size_mb', 64) or 64)}m",
    ]
    memory_record = dict(constraint_translation.get("memory_limit", {}))
    if memory_record.get("backend_value"):
        docker_command.extend(["--memory", str(memory_record.get("backend_value"))])
    cpu_record = dict(constraint_translation.get("cpu_limit_cpus", {}))
    if cpu_record.get("backend_value") not in {None, ""}:
        docker_command.extend(["--cpus", str(cpu_record.get("backend_value"))])

    mount_plan: list[dict[str, Any]] = []
    for mount in mounts:
        host_path = str(mount["host_path"])
        container_path = str(mount["container_path"])
        read_only = str(mount.get("access_mode", "ro")) == "ro"
        type_flag = "file" if bool(mount.get("is_file", False)) else "dir"
        mount_plan.append(
            {
                "type": type_flag,
                "host_path": host_path,
                "container_path": container_path,
                "access_mode": str(mount.get("access_mode", "ro")),
                "purpose": str(mount.get("purpose", "")),
            }
        )
        docker_command.extend(
            [
                "--mount",
                "type=bind,"
                + f"source={host_path},target={container_path}"
                + (",readonly" if read_only else ""),
            ]
        )

    docker_env = {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "HOME": "/tmp",
        "NOVALI_OPERATOR_CONTEXT_ROLE": "runtime",
        "NOVALI_OPERATOR_RUNTIME_LOCK": "1",
        "NOVALI_STARTUP_MODE": "canonical_operator",
        "NOVALI_OPERATOR_POLICY_ROOT": str(CONTAINER_OPERATOR_SESSION_PATH.parent),
        "NOVALI_OPERATOR_SESSION_FILE": str(CONTAINER_OPERATOR_SESSION_PATH),
    }
    for key, value in docker_env.items():
        docker_command.extend(["--env", f"{key}={value}"])

    translated_args: list[str] = []
    directive_text = str(directive_file) if directive_file else ""
    clarification_text = str(clarification_file) if clarification_file else ""
    state_root_text = str(state_root) if state_root else ""
    for item in runtime_args:
        if directive_text and item == directive_text:
            translated_args.append(str(path_labels.get("directive_file", item)))
        elif clarification_text and item == clarification_text:
            translated_args.append(str(path_labels.get("clarification_file", item)))
        elif state_root_text and item == state_root_text:
            translated_args.append(str(path_labels.get("state_root", item)))
        else:
            translated_args.append(str(item))

    docker_command.extend(
        [
            str(docker_settings.get("image", "python:3.12-slim")),
            "python",
            mapped_entry_script,
            *translated_args,
        ]
    )

    plan = {
        "schema_name": OPERATOR_RUNTIME_LAUNCH_PLAN_SCHEMA_NAME,
        "schema_version": OPERATOR_RUNTIME_LAUNCH_PLAN_SCHEMA_VERSION,
        "generated_at": _now(),
        "backend_kind": BACKEND_LOCAL_DOCKER,
        "launch_mode": str(normalized_envelope.get("launch_mode", "")),
        "session_id": str(session.get("session_id", "")),
        "experimental": bool(docker_settings.get("experimental", True)),
        "entry_script": str(entry_script_path),
        "runtime_args": runtime_args,
        "execution_profile": execution_profile,
        "workspace_id": str(workspace_policy.get("workspace_id", "")),
        "workspace_root": str(workspace_policy.get("workspace_root", "")),
        "host_working_directory": str(package_root_path),
        "container_entry_script": mapped_entry_script,
        "container_name": container_name,
        "working_directory": container_working_directory,
        "runtime_session_host_path": str(runtime_session_host_path),
        "runtime_session_container_path": str(CONTAINER_OPERATOR_SESSION_PATH),
        "docker_command": docker_command,
        "docker_environment": docker_env,
        "mount_plan": mount_plan,
        "container_path_overrides": path_labels,
        "constraint_translation": constraint_translation,
        "summary": {
            "backend_kind": BACKEND_LOCAL_DOCKER,
            "execution_profile": execution_profile,
            "workspace_id": str(workspace_policy.get("workspace_id", "")),
            "workspace_root": str(workspace_policy.get("workspace_root", "")),
            "image": str(docker_settings.get("image", "")),
            "network_mode": "none",
            "read_only_root_filesystem": True,
            "non_root_execution": True,
            "mount_count": len(mount_plan),
        },
    }
    return plan, []


def build_container_runtime_session_view(
    *,
    session: dict[str, Any],
    launch_plan: dict[str, Any],
) -> dict[str, Any]:
    payload = json.loads(json.dumps(session))
    mounts = list(launch_plan.get("mount_plan", []))
    overrides = dict(launch_plan.get("container_path_overrides", {}))

    runtime_constraints = dict(payload.get("effective_runtime_constraints", {}))
    constraint_values = dict(runtime_constraints.get("constraints", {}))
    constraint_values["working_directory"] = str(launch_plan.get("working_directory", ""))
    constraint_values["allowed_write_roots"] = [
        str(mount.get("container_path", ""))
        for mount in mounts
        if str(mount.get("purpose", "")) == "allowed_write_root" and str(mount.get("access_mode", "")) == "rw"
    ]
    runtime_constraints["constraints"] = constraint_values
    workspace_policy = dict(runtime_constraints.get("workspace_policy", {}))
    if workspace_policy:
        for key in (
            "workspace_base_root",
            "workspace_root",
            "working_directory",
            "generated_output_root",
            "log_root",
        ):
            mapped = _map_host_path_to_container(workspace_policy.get(key, ""), mounts)
            if mapped:
                workspace_policy[key] = mapped
        layout_paths = {}
        for key, value in dict(workspace_policy.get("layout_paths", {})).items():
            mapped = _map_host_path_to_container(value, mounts)
            layout_paths[str(key)] = mapped or str(value)
        workspace_policy["layout_paths"] = layout_paths
        protected_root_hints = []
        for item in list(workspace_policy.get("protected_root_hints", [])):
            mapped = _map_host_path_to_container(item, mounts)
            protected_root_hints.append(mapped or str(item))
        workspace_policy["protected_root_hints"] = protected_root_hints
        runtime_constraints["workspace_policy"] = workspace_policy
    payload["effective_runtime_constraints"] = runtime_constraints

    if payload.get("directive_file"):
        payload["directive_file"] = str(overrides.get("directive_file", payload.get("directive_file", "")))
    if payload.get("clarification_file"):
        payload["clarification_file"] = str(overrides.get("clarification_file", payload.get("clarification_file", "")))
    if payload.get("state_root"):
        payload["state_root"] = str(overrides.get("state_root", payload.get("state_root", "")))

    payload["package_root"] = str(CONTAINER_PACKAGE_ROOT)
    payload["operator_policy_root"] = str(CONTAINER_OPERATOR_SESSION_PATH.parent)
    payload["entry_script"] = str(launch_plan.get("container_entry_script", payload.get("entry_script", "")))
    payload["runtime_event_log_path"] = _map_host_path_to_container(
        payload.get("runtime_event_log_path", ""),
        mounts,
    )

    trusted_source_bindings = dict(payload.get("trusted_source_bindings", {}))
    remapped_bindings = []
    for binding in list(trusted_source_bindings.get("bindings", [])):
        row = dict(binding)
        path_hint = str(row.get("path_hint", "")).strip()
        if path_hint:
            mapped = _map_host_path_to_container(path_hint, mounts)
            if mapped:
                row["path_hint"] = mapped
        remapped_bindings.append(row)
    trusted_source_bindings["bindings"] = remapped_bindings
    payload["trusted_source_bindings"] = trusted_source_bindings

    from .policy import _stable_hash, _session_payload_without_hashes  # local import to avoid cycle

    payload["frozen_hashes"]["runtime_constraints_sha256"] = _stable_hash(payload["effective_runtime_constraints"])
    payload["frozen_hashes"]["trusted_source_bindings_sha256"] = _stable_hash(payload["trusted_source_bindings"])
    if payload.get("operator_runtime_envelope_spec"):
        payload["frozen_hashes"]["runtime_envelope_spec_sha256"] = _stable_hash(payload["operator_runtime_envelope_spec"])
    if payload.get("effective_runtime_envelope"):
        payload["frozen_hashes"]["effective_runtime_envelope_sha256"] = _stable_hash(payload["effective_runtime_envelope"])
    payload["frozen_hashes"]["session_payload_sha256"] = _stable_hash(_session_payload_without_hashes(payload))
    return payload
