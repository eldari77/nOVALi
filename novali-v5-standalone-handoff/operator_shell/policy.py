from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from .common import (
    OPERATOR_CONTEXT_ENV,
    OPERATOR_ROLE_RUNTIME,
    OperatorPolicyMutationRefusedError,
)
from .envelope import (
    build_default_operator_runtime_envelope_spec,
    operator_runtime_launch_plan_latest_path,
    operator_runtime_envelope_spec_path,
    probe_runtime_backend_capabilities,
    validate_operator_runtime_envelope_spec,
)


RUNTIME_CONSTRAINTS_SCHEMA_NAME = "OperatorRuntimeConstraints"
RUNTIME_CONSTRAINTS_SCHEMA_VERSION = "operator_runtime_constraints_v1"
TRUSTED_SOURCE_BINDINGS_SCHEMA_NAME = "TrustedSourceBindings"
TRUSTED_SOURCE_BINDINGS_SCHEMA_VERSION = "trusted_source_bindings_v1"
TRUSTED_SOURCE_SECRETS_SCHEMA_NAME = "TrustedSourceSecretsLocal"
TRUSTED_SOURCE_SECRETS_SCHEMA_VERSION = "trusted_source_secrets_local_v1"
EFFECTIVE_OPERATOR_SESSION_SCHEMA_NAME = "EffectiveOperatorSession"
EFFECTIVE_OPERATOR_SESSION_SCHEMA_VERSION = "effective_operator_session_v1"
OPERATOR_LAUNCH_EVENT_SCHEMA_NAME = "OperatorLaunchEvent"
OPERATOR_LAUNCH_EVENT_SCHEMA_VERSION = "operator_launch_event_v1"

SUPPORTED_SOURCE_KINDS = {
    "local_path",
    "local_bundle",
    "network_api",
}
SUPPORTED_CREDENTIAL_STRATEGIES = {
    "none",
    "env_var",
    "local_secret_store",
}
EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION = "bootstrap_only_initialization"
EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING = "bounded_active_workspace_coding"
SUPPORTED_EXECUTION_PROFILES = {
    EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION,
    EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING,
}
ACTIVE_WORKSPACE_ROOT_NAME = "novali-active_workspace"
ACTIVE_WORKSPACE_LAYOUT_DIRECTORIES = (
    "src",
    "tests",
    "docs",
    "artifacts",
    "plans",
)


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def _stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _session_payload_without_hashes(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in dict(payload).items()
        if key != "frozen_hashes"
    }


def default_operator_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        root = Path(local_app_data) / "NOVALI" / "operator_state"
    else:
        root = Path.home() / ".novali_operator"
    root.mkdir(parents=True, exist_ok=True)
    return root


def operator_runtime_constraints_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "operator_runtime_constraints_latest.json"


def trusted_source_bindings_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "trusted_source_bindings_latest.json"


def trusted_source_secrets_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "trusted_source_secrets.local.json"


def effective_operator_session_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "effective_operator_session_latest.json"


def operator_launch_event_ledger_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "operator_launch_events.jsonl"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_stable_json(payload), encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("", encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _require_operator_mutation_rights() -> None:
    if os.environ.get(OPERATOR_CONTEXT_ENV, "").strip().lower() == OPERATOR_ROLE_RUNTIME:
        raise OperatorPolicyMutationRefusedError(
            "operator-owned policy cannot be mutated from runtime context",
            constraint_id="operator_policy_mutation_lock",
            enforcement_class="hard_enforced",
        )


def _normalize_path(value: Any) -> str:
    if value in {None, ""}:
        return ""
    try:
        return str(Path(str(value)).resolve())
    except OSError:
        return str(value)


def _is_under_path(candidate: Path, root: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def default_runtime_state_root(package_root: str | Path | None = None) -> Path:
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    candidate = package_root_path / "runtime_data" / "state"
    return candidate if candidate.parent.exists() else package_root_path / "data"


def default_runtime_logs_root(package_root: str | Path | None = None) -> Path:
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    candidate = package_root_path / "runtime_data" / "logs"
    return candidate if candidate.parent.exists() else package_root_path / "logs"


def default_generated_output_root(package_root: str | Path | None = None) -> Path:
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    candidate = package_root_path / "runtime_data" / "generated"
    return candidate if candidate.parent.exists() else package_root_path / "data" / "generated"


def active_workspace_base_root(package_root: str | Path | None = None) -> Path:
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    return package_root_path / ACTIVE_WORKSPACE_ROOT_NAME


def sanitize_workspace_id(value: Any, *, fallback: str = "workspace_default") -> str:
    text = str(value or "").strip()
    token = "".join(
        character if character.isalnum() or character in {"-", "_", "."} else "_"
        for character in text
    ).strip("._-")
    return token or fallback


def active_workspace_root(
    package_root: str | Path | None = None,
    *,
    workspace_id: Any,
) -> Path:
    return active_workspace_base_root(package_root) / sanitize_workspace_id(
        workspace_id,
        fallback="workspace_default",
    )


def protected_runtime_root_hints(
    package_root: str | Path | None = None,
    *,
    operator_root: str | Path | None = None,
) -> list[str]:
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    operator_root_path = default_operator_root() if operator_root is None else Path(operator_root)
    rows = [
        package_root_path / "main.py",
        package_root_path / "theory" / "nined_core.py",
        package_root_path / "directive_inputs",
        default_runtime_state_root(package_root_path),
        operator_root_path,
    ]
    unique: list[str] = []
    seen: set[str] = set()
    for item in rows:
        normalized = _normalize_path(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


def ensure_active_workspace_layout(
    package_root: str | Path | None = None,
    *,
    workspace_id: Any,
) -> dict[str, Any]:
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    base_root = active_workspace_base_root(package_root_path)
    base_root.mkdir(parents=True, exist_ok=True)
    clean_workspace_id = sanitize_workspace_id(workspace_id, fallback="workspace_default")
    workspace_root = base_root / clean_workspace_id
    workspace_root.mkdir(parents=True, exist_ok=True)
    layout_paths: dict[str, str] = {}
    for directory_name in ACTIVE_WORKSPACE_LAYOUT_DIRECTORIES:
        target = workspace_root / directory_name
        target.mkdir(parents=True, exist_ok=True)
        layout_paths[directory_name] = _normalize_path(target)
    generated_output_root = default_generated_output_root(package_root_path)
    generated_output_root.mkdir(parents=True, exist_ok=True)
    log_root = default_runtime_logs_root(package_root_path)
    log_root.mkdir(parents=True, exist_ok=True)
    return {
        "workspace_base_root": _normalize_path(base_root),
        "workspace_id": clean_workspace_id,
        "workspace_root": _normalize_path(workspace_root),
        "working_directory": layout_paths.get("src", _normalize_path(workspace_root)),
        "layout_directories": list(ACTIVE_WORKSPACE_LAYOUT_DIRECTORIES),
        "layout_paths": layout_paths,
        "generated_output_root": _normalize_path(generated_output_root),
        "log_root": _normalize_path(log_root),
    }


def build_runtime_constraints_for_profile(
    package_root: str | Path | None = None,
    *,
    operator_root: str | Path | None = None,
    execution_profile: str = EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION,
    workspace_id: Any = "",
) -> dict[str, Any]:
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    operator_root_path = default_operator_root() if operator_root is None else Path(operator_root)
    profile_name = str(execution_profile or EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION).strip()
    if profile_name not in SUPPORTED_EXECUTION_PROFILES:
        profile_name = EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION

    state_root = default_runtime_state_root(package_root_path)
    state_root.mkdir(parents=True, exist_ok=True)
    log_root = default_runtime_logs_root(package_root_path)
    log_root.mkdir(parents=True, exist_ok=True)
    generated_output_root = default_generated_output_root(package_root_path)
    generated_output_root.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema_name": RUNTIME_CONSTRAINTS_SCHEMA_NAME,
        "schema_version": RUNTIME_CONSTRAINTS_SCHEMA_VERSION,
        "generated_at": _now(),
        "required_for_launch": True,
        "execution_profile": profile_name,
        "workspace_policy": {
            "workspace_base_root": _normalize_path(active_workspace_base_root(package_root_path)),
            "workspace_id": "",
            "workspace_root": "",
            "working_directory": "",
            "layout_directories": list(ACTIVE_WORKSPACE_LAYOUT_DIRECTORIES),
            "layout_paths": {},
            "generated_output_root": _normalize_path(generated_output_root),
            "log_root": _normalize_path(log_root),
            "protected_root_hints": protected_runtime_root_hints(
                package_root_path,
                operator_root=operator_root_path,
            ),
        },
        "constraints": {
            "max_memory_mb": 2048,
            "max_python_threads": 8,
            "max_child_processes": 0,
            "subprocess_mode": "disabled",
            "working_directory": _normalize_path(package_root_path),
            "allowed_write_roots": [
                _normalize_path(state_root),
                _normalize_path(log_root),
            ],
            "session_time_limit_seconds": 600,
            "cpu_utilization_cap_pct": None,
            "network_egress_mode": "unsupported",
            "request_rate_limit_per_minute": None,
        },
    }

    if profile_name == EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING:
        workspace_layout = ensure_active_workspace_layout(
            package_root_path,
            workspace_id=workspace_id,
        )
        payload["workspace_policy"] = {
            **dict(payload.get("workspace_policy", {})),
            **workspace_layout,
            "protected_root_hints": protected_runtime_root_hints(
                package_root_path,
                operator_root=operator_root_path,
            ),
        }
        payload["constraints"]["working_directory"] = str(workspace_layout["working_directory"])
        payload["constraints"]["allowed_write_roots"] = [
            str(workspace_layout["workspace_root"]),
            str(workspace_layout["generated_output_root"]),
            str(workspace_layout["log_root"]),
        ]
    return payload


def build_default_runtime_constraints(package_root: str | Path | None = None) -> dict[str, Any]:
    return build_runtime_constraints_for_profile(
        package_root,
        execution_profile=EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION,
    )


def build_default_trusted_source_bindings(package_root: str | Path | None = None) -> dict[str, Any]:
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    novali_v4_root = package_root_path.parent / "novali-v4"
    return {
        "schema_name": TRUSTED_SOURCE_BINDINGS_SCHEMA_NAME,
        "schema_version": TRUSTED_SOURCE_BINDINGS_SCHEMA_VERSION,
        "generated_at": _now(),
        "bindings": [
            {
                "source_id": "local_repo:novali-v5",
                "source_kind": "local_path",
                "enabled": True,
                "credential_strategy": "none",
                "credential_ref": "",
                "path_hint": _normalize_path(package_root_path),
            },
            {
                "source_id": "local_artifacts:novali-v5/data",
                "source_kind": "local_path",
                "enabled": True,
                "credential_strategy": "none",
                "credential_ref": "",
                "path_hint": _normalize_path(package_root_path / "data"),
            },
            {
                "source_id": "local_logs:logs",
                "source_kind": "local_path",
                "enabled": True,
                "credential_strategy": "none",
                "credential_ref": "",
                "path_hint": _normalize_path(package_root_path / "logs"),
            },
            {
                "source_id": "local_repo:novali-v4",
                "source_kind": "local_path",
                "enabled": novali_v4_root.exists(),
                "credential_strategy": "none",
                "credential_ref": "",
                "path_hint": _normalize_path(novali_v4_root),
            },
            {
                "source_id": "trusted_benchmark_pack_v1",
                "source_kind": "local_bundle",
                "enabled": True,
                "credential_strategy": "none",
                "credential_ref": "",
                "path_hint": _normalize_path(package_root_path / "benchmarks" / "trusted_benchmark_pack_v1"),
            },
            {
                "source_id": "openai_api",
                "source_kind": "network_api",
                "enabled": False,
                "credential_strategy": "env_var",
                "credential_ref": "OPENAI_API_KEY",
                "path_hint": "",
            },
        ],
    }


def build_default_trusted_source_secrets() -> dict[str, Any]:
    return {
        "schema_name": TRUSTED_SOURCE_SECRETS_SCHEMA_NAME,
        "schema_version": TRUSTED_SOURCE_SECRETS_SCHEMA_VERSION,
        "generated_at": _now(),
        "secrets_by_source": {},
    }


def initialize_operator_policy_files(
    *,
    root: str | Path | None = None,
    package_root: str | Path | None = None,
) -> dict[str, str]:
    _require_operator_mutation_rights()
    constraints_path = operator_runtime_constraints_path(root)
    envelope_path = operator_runtime_envelope_spec_path(root)
    bindings_path = trusted_source_bindings_path(root)
    secrets_path = trusted_source_secrets_path(root)
    if not constraints_path.exists():
        _write_json(constraints_path, build_default_runtime_constraints(package_root))
    if not envelope_path.exists():
        _write_json(envelope_path, build_default_operator_runtime_envelope_spec(package_root))
    if not bindings_path.exists():
        _write_json(bindings_path, build_default_trusted_source_bindings(package_root))
    if not secrets_path.exists():
        _write_json(secrets_path, build_default_trusted_source_secrets())
    return {
        "operator_runtime_constraints_path": str(constraints_path),
        "operator_runtime_envelope_spec_path": str(envelope_path),
        "trusted_source_bindings_path": str(bindings_path),
        "trusted_source_secrets_path": str(secrets_path),
    }


def load_runtime_constraints(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(operator_runtime_constraints_path(root))


def load_runtime_envelope_spec(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(operator_runtime_envelope_spec_path(root))


def load_runtime_constraints_or_default(
    *,
    root: str | Path | None = None,
    package_root: str | Path | None = None,
) -> dict[str, Any]:
    payload = load_runtime_constraints(root)
    return payload if payload else build_default_runtime_constraints(package_root)


def load_runtime_envelope_spec_or_default(
    *,
    root: str | Path | None = None,
    package_root: str | Path | None = None,
) -> dict[str, Any]:
    payload = load_runtime_envelope_spec(root)
    return payload if payload else build_default_operator_runtime_envelope_spec(package_root)


def load_trusted_source_bindings(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(trusted_source_bindings_path(root))


def load_trusted_source_bindings_or_default(
    *,
    root: str | Path | None = None,
    package_root: str | Path | None = None,
) -> dict[str, Any]:
    payload = load_trusted_source_bindings(root)
    return payload if payload else build_default_trusted_source_bindings(package_root)


def load_trusted_source_secrets(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(trusted_source_secrets_path(root))


def load_trusted_source_secrets_or_default(root: str | Path | None = None) -> dict[str, Any]:
    payload = load_trusted_source_secrets(root)
    return payload if payload else build_default_trusted_source_secrets()


def save_runtime_constraints(payload: dict[str, Any], *, root: str | Path | None = None) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(operator_runtime_constraints_path(root), payload)


def save_runtime_envelope_spec(payload: dict[str, Any], *, root: str | Path | None = None) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(operator_runtime_envelope_spec_path(root), payload)


def save_trusted_source_bindings(payload: dict[str, Any], *, root: str | Path | None = None) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(trusted_source_bindings_path(root), payload)


def save_trusted_source_secrets(payload: dict[str, Any], *, root: str | Path | None = None) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(trusted_source_secrets_path(root), payload)


def validate_runtime_constraints(
    payload: dict[str, Any],
    *,
    package_root: str | Path | None = None,
    operator_root: str | Path | None = None,
) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    operator_root_path = default_operator_root() if operator_root is None else Path(operator_root)
    errors: list[str] = []
    if str(payload.get("schema_name", "")) != RUNTIME_CONSTRAINTS_SCHEMA_NAME:
        errors.append(f"schema_name must be {RUNTIME_CONSTRAINTS_SCHEMA_NAME}")
    if str(payload.get("schema_version", "")) != RUNTIME_CONSTRAINTS_SCHEMA_VERSION:
        errors.append(f"schema_version must be {RUNTIME_CONSTRAINTS_SCHEMA_VERSION}")

    constraints = dict(payload.get("constraints", {}))
    execution_profile = str(
        payload.get("execution_profile", EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION)
    ).strip() or EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION
    if execution_profile not in SUPPORTED_EXECUTION_PROFILES:
        errors.append(
            "execution_profile must be one of "
            + ", ".join(sorted(SUPPORTED_EXECUTION_PROFILES))
        )
    workspace_policy = dict(payload.get("workspace_policy", {}))
    required_keys = {
        "max_memory_mb",
        "max_python_threads",
        "max_child_processes",
        "subprocess_mode",
        "working_directory",
        "allowed_write_roots",
        "session_time_limit_seconds",
    }
    missing = sorted(required_keys - set(constraints.keys()))
    if missing:
        errors.append(f"missing runtime constraint fields: {', '.join(missing)}")

    def _positive_int(name: str) -> int | None:
        value = constraints.get(name)
        if value in {None, ""}:
            return None
        try:
            coerced = int(value)
        except (TypeError, ValueError):
            errors.append(f"{name} must be an integer or null")
            return None
        if coerced < 0:
            errors.append(f"{name} must be >= 0")
        return coerced

    max_memory_mb = _positive_int("max_memory_mb")
    max_python_threads = _positive_int("max_python_threads")
    max_child_processes = _positive_int("max_child_processes")
    session_time_limit_seconds = _positive_int("session_time_limit_seconds")

    subprocess_mode = str(constraints.get("subprocess_mode", "disabled"))
    if subprocess_mode not in {"disabled", "bounded", "allow"}:
        errors.append("subprocess_mode must be one of disabled, bounded, allow")
    if subprocess_mode == "disabled" and (max_child_processes or 0) != 0:
        errors.append("max_child_processes must be 0 when subprocess_mode is disabled")
    if subprocess_mode == "bounded" and (max_child_processes or 0) <= 0:
        errors.append("max_child_processes must be > 0 when subprocess_mode is bounded")

    working_directory = Path(str(constraints.get("working_directory", "")))
    if not str(working_directory).strip():
        errors.append("working_directory must not be empty")
    elif not working_directory.exists():
        errors.append("working_directory must exist")

    allowed_write_roots = [Path(str(item)) for item in list(constraints.get("allowed_write_roots", []))]
    if not allowed_write_roots:
        errors.append("allowed_write_roots must not be empty")
    normalized_roots: list[str] = []
    seen_roots: set[str] = set()
    for root in allowed_write_roots:
        normalized_root = _normalize_path(root)
        if not normalized_root:
            errors.append("allowed_write_roots must not contain empty entries")
            continue
        if normalized_root in seen_roots:
            continue
        seen_roots.add(normalized_root)
        normalized_roots.append(normalized_root)
        if not root.exists():
            errors.append(f"allowed_write_root does not exist: {root}")
        if _is_under_path(Path(normalized_root), operator_root_path) or _is_under_path(operator_root_path, Path(normalized_root)):
            errors.append("allowed_write_roots must not include or contain the operator policy root")

    cpu_utilization_cap_pct = constraints.get("cpu_utilization_cap_pct")
    request_rate_limit_per_minute = constraints.get("request_rate_limit_per_minute")
    network_egress_mode = str(constraints.get("network_egress_mode", "unsupported"))

    normalized_workspace_policy = {
        "workspace_base_root": _normalize_path(active_workspace_base_root(package_root_path)),
        "workspace_id": "",
        "workspace_root": "",
        "working_directory": "",
        "layout_directories": list(ACTIVE_WORKSPACE_LAYOUT_DIRECTORIES),
        "layout_paths": {},
        "generated_output_root": _normalize_path(default_generated_output_root(package_root_path)),
        "log_root": _normalize_path(default_runtime_logs_root(package_root_path)),
        "protected_root_hints": protected_runtime_root_hints(
            package_root_path,
            operator_root=operator_root_path,
        ),
    }

    if execution_profile == EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING:
        raw_workspace_id = str(
            workspace_policy.get("workspace_id", payload.get("workspace_id", ""))
        ).strip()
        if not raw_workspace_id:
            errors.append("workspace_policy.workspace_id is required for bounded_active_workspace_coding")
        workspace_layout = ensure_active_workspace_layout(
            package_root_path,
            workspace_id=raw_workspace_id or "workspace_default",
        )
        normalized_workspace_policy = {
            **normalized_workspace_policy,
            **workspace_layout,
            "protected_root_hints": protected_runtime_root_hints(
                package_root_path,
                operator_root=operator_root_path,
            ),
        }
        expected_working_directory = str(normalized_workspace_policy["working_directory"])
        if _normalize_path(working_directory) != expected_working_directory:
            errors.append(
                "working_directory must match the bounded active workspace execution profile"
            )
        expected_allowed_write_roots = [
            str(normalized_workspace_policy["workspace_root"]),
            str(normalized_workspace_policy["generated_output_root"]),
            str(normalized_workspace_policy["log_root"]),
        ]
        if set(normalized_roots) != set(expected_allowed_write_roots):
            errors.append(
                "allowed_write_roots must match the bounded active workspace execution profile"
            )
        normalized_roots = expected_allowed_write_roots
        working_directory = Path(expected_working_directory)
    else:
        normalized_workspace_policy["workspace_id"] = str(workspace_policy.get("workspace_id", "")).strip()

    normalized = {
        "schema_name": RUNTIME_CONSTRAINTS_SCHEMA_NAME,
        "schema_version": RUNTIME_CONSTRAINTS_SCHEMA_VERSION,
        "generated_at": str(payload.get("generated_at", "")) or _now(),
        "required_for_launch": bool(payload.get("required_for_launch", True)),
        "execution_profile": execution_profile,
        "workspace_policy": normalized_workspace_policy,
        "constraints": {
            "max_memory_mb": max_memory_mb,
            "max_python_threads": max_python_threads,
            "max_child_processes": max_child_processes,
            "subprocess_mode": subprocess_mode,
            "working_directory": _normalize_path(working_directory),
            "allowed_write_roots": normalized_roots,
            "session_time_limit_seconds": session_time_limit_seconds,
            "cpu_utilization_cap_pct": cpu_utilization_cap_pct,
            "network_egress_mode": network_egress_mode,
            "request_rate_limit_per_minute": request_rate_limit_per_minute,
        },
    }

    enforcement = {
        "max_memory_mb": {
            "enforcement_class": "watchdog_enforced" if sys.platform.startswith("win") else "unsupported_on_this_platform",
            "reason": (
                "Windows launcher polls child working-set memory and terminates on violation"
                if sys.platform.startswith("win")
                else "memory watchdog backend is only implemented for Windows in this slice"
            ),
            "requested_value": max_memory_mb,
        },
        "max_python_threads": {
            "enforcement_class": "hard_enforced",
            "reason": "Python thread starts are intercepted inside the runtime guard",
            "requested_value": max_python_threads,
        },
        "max_child_processes": {
            "enforcement_class": "hard_enforced",
            "reason": "Python subprocess and multiprocessing starts are intercepted inside the runtime guard",
            "requested_value": max_child_processes,
        },
        "subprocess_mode": {
            "enforcement_class": "hard_enforced",
            "reason": "Python subprocess spawning APIs are blocked or bounded inside the runtime guard",
            "requested_value": subprocess_mode,
        },
        "working_directory": {
            "enforcement_class": "hard_enforced",
            "reason": "launcher sets the child working directory and the runtime guard blocks cwd escapes",
            "requested_value": _normalize_path(working_directory),
        },
        "allowed_write_roots": {
            "enforcement_class": "hard_enforced",
            "reason": "runtime guard blocks normal Python mutation calls outside operator-approved write roots",
            "requested_value": normalized_roots,
        },
        "session_time_limit_seconds": {
            "enforcement_class": "watchdog_enforced",
            "reason": "launcher terminates the child process when the session time budget is exceeded",
            "requested_value": session_time_limit_seconds,
        },
        "cpu_utilization_cap_pct": {
            "enforcement_class": "unsupported_on_this_platform",
            "reason": "no conservative CPU throttling claim is made in this first operator slice",
            "requested_value": cpu_utilization_cap_pct,
        },
        "network_egress_mode": {
            "enforcement_class": "unsupported_on_this_platform",
            "reason": "no network egress sandbox is claimed in this first operator slice",
            "requested_value": network_egress_mode,
        },
        "request_rate_limit_per_minute": {
            "enforcement_class": "unsupported_on_this_platform",
            "reason": "request-rate ceilings are not claimed in this first operator slice",
            "requested_value": request_rate_limit_per_minute,
        },
        "execution_profile": {
            "enforcement_class": "hard_enforced",
            "reason": "operator-selected execution profile freezes the working directory and writable-root policy before launch",
            "requested_value": execution_profile,
        },
        "active_workspace_root": {
            "enforcement_class": (
                "hard_enforced"
                if execution_profile == EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING
                else "not_requested"
            ),
            "reason": (
                "bounded coding runs are restricted to the explicit active workspace plus approved generated-output roots"
                if execution_profile == EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING
                else "bootstrap-only initialization does not require an active coding workspace"
            ),
            "requested_value": str(normalized_workspace_policy.get("workspace_root", "")),
        },
    }
    return errors, normalized, enforcement


def validate_trusted_source_bindings(
    payload: dict[str, Any],
    *,
    secrets_payload: dict[str, Any] | None = None,
) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    errors: list[str] = []
    if str(payload.get("schema_name", "")) != TRUSTED_SOURCE_BINDINGS_SCHEMA_NAME:
        errors.append(f"schema_name must be {TRUSTED_SOURCE_BINDINGS_SCHEMA_NAME}")
    if str(payload.get("schema_version", "")) != TRUSTED_SOURCE_BINDINGS_SCHEMA_VERSION:
        errors.append(f"schema_version must be {TRUSTED_SOURCE_BINDINGS_SCHEMA_VERSION}")

    raw_bindings = list(payload.get("bindings", []))
    if not raw_bindings:
        errors.append("trusted source bindings must contain at least one binding")

    secrets_by_source = dict(dict(secrets_payload or {}).get("secrets_by_source", {}))
    normalized_bindings: list[dict[str, Any]] = []
    availability_rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for index, item in enumerate(raw_bindings):
        binding = dict(item)
        source_id = str(binding.get("source_id", "")).strip()
        source_kind = str(binding.get("source_kind", "")).strip()
        enabled = bool(binding.get("enabled", False))
        credential_strategy = str(binding.get("credential_strategy", "none")).strip() or "none"
        credential_ref = str(binding.get("credential_ref", "")).strip()
        path_hint = _normalize_path(binding.get("path_hint", ""))

        if not source_id:
            errors.append(f"binding[{index}] source_id is required")
            source_id = f"binding_{index}"
        if source_id in seen_ids:
            errors.append(f"duplicate trusted source binding: {source_id}")
        seen_ids.add(source_id)

        if source_kind not in SUPPORTED_SOURCE_KINDS:
            errors.append(f"{source_id}: source_kind must be one of {sorted(SUPPORTED_SOURCE_KINDS)}")
        if credential_strategy not in SUPPORTED_CREDENTIAL_STRATEGIES:
            errors.append(
                f"{source_id}: credential_strategy must be one of {sorted(SUPPORTED_CREDENTIAL_STRATEGIES)}"
            )
        if any(key in binding for key in {"credential_value", "secret", "api_key", "access_token"}):
            errors.append(f"{source_id}: raw secrets must not appear in trusted_source_bindings_latest.json")

        resolved_secret_value, resolved_secret_source = resolve_trusted_source_secret(
            binding,
            secrets_payload={"secrets_by_source": secrets_by_source},
        )
        env_credential_present = bool(
            credential_strategy == "env_var" and str(resolved_secret_value).strip()
        )
        local_secret_key = credential_ref or source_id
        local_secret_present = bool(
            credential_strategy == "local_secret_store" and str(resolved_secret_value).strip()
        )
        path_exists = bool(path_hint and Path(path_hint).exists())

        ready_for_launch = False
        availability_class = "disabled"
        availability_reason = "source is disabled"
        if enabled:
            if source_kind in {"local_path", "local_bundle"}:
                ready_for_launch = path_exists
                availability_class = "ready" if ready_for_launch else "missing_path"
                availability_reason = (
                    "local trusted source path is present"
                    if ready_for_launch
                    else "local trusted source path is missing"
                )
                if not path_hint:
                    errors.append(f"{source_id}: path_hint is required for local trusted sources")
            elif source_kind == "network_api":
                if credential_strategy == "none":
                    errors.append(f"{source_id}: enabled network_api bindings require a credential strategy")
                    availability_class = "missing_credential"
                    availability_reason = "enabled network API source has no credential strategy"
                elif credential_strategy == "env_var":
                    ready_for_launch = env_credential_present
                    availability_class = "ready" if ready_for_launch else "missing_credential"
                    availability_reason = (
                        "required environment credential is present"
                        if ready_for_launch
                        else "required environment credential is missing"
                    )
                    if not credential_ref:
                        errors.append(f"{source_id}: credential_ref is required for env_var strategy")
                elif credential_strategy == "local_secret_store":
                    ready_for_launch = local_secret_present
                    availability_class = "ready" if ready_for_launch else "missing_credential"
                    availability_reason = (
                        "required local secret is present"
                        if ready_for_launch
                        else "required local secret is missing"
                    )

        normalized_bindings.append(
            {
                "source_id": source_id,
                "source_kind": source_kind,
                "enabled": enabled,
                "credential_strategy": credential_strategy,
                "credential_ref": credential_ref,
                "path_hint": path_hint,
            }
        )
        availability_rows.append(
            {
                "source_id": source_id,
                "source_kind": source_kind,
                "enabled": enabled,
                "credential_strategy": credential_strategy,
                "credential_ref": credential_ref,
                "path_hint": path_hint,
                "path_exists": path_exists,
                "env_credential_present": env_credential_present,
                "local_secret_present": local_secret_present,
                "resolved_secret_source": resolved_secret_source,
                "ready_for_launch": ready_for_launch,
                "availability_class": availability_class,
                "availability_reason": availability_reason,
            }
        )

    normalized = {
        "schema_name": TRUSTED_SOURCE_BINDINGS_SCHEMA_NAME,
        "schema_version": TRUSTED_SOURCE_BINDINGS_SCHEMA_VERSION,
        "generated_at": str(payload.get("generated_at", "")) or _now(),
        "bindings": normalized_bindings,
    }
    availability = {
        "checked_at": _now(),
        "sources": availability_rows,
        "summary": {
            "ready_count": sum(1 for item in availability_rows if item["ready_for_launch"]),
            "enabled_count": sum(1 for item in availability_rows if item["enabled"]),
            "disabled_count": sum(1 for item in availability_rows if not item["enabled"]),
            "missing_path_count": sum(1 for item in availability_rows if item["availability_class"] == "missing_path"),
            "missing_credential_count": sum(
                1 for item in availability_rows if item["availability_class"] == "missing_credential"
            ),
        },
    }
    return errors, normalized, availability


def summarize_trusted_source_availability(availability: dict[str, Any]) -> dict[str, Any]:
    rows = list(availability.get("sources", []))
    return {
        "ready_sources": [item["source_id"] for item in rows if item.get("ready_for_launch")],
        "attention_required_sources": [
            item["source_id"]
            for item in rows
            if item.get("enabled") and not item.get("ready_for_launch")
        ],
        "disabled_sources": [item["source_id"] for item in rows if not item.get("enabled")],
        "summary": dict(availability.get("summary", {})),
    }


def resolve_trusted_source_secret(
    binding: dict[str, Any],
    *,
    secrets_payload: dict[str, Any] | None = None,
) -> tuple[str, str]:
    binding = dict(binding)
    strategy = str(binding.get("credential_strategy", "none")).strip() or "none"
    credential_ref = str(binding.get("credential_ref", "")).strip()
    source_id = str(binding.get("source_id", "")).strip()
    if strategy == "none":
        return "", "no_secret_required"
    if strategy == "env_var":
        if not credential_ref:
            return "", "missing_credential_ref"
        return str(os.environ.get(credential_ref, "")), "environment_variable"
    if strategy == "local_secret_store":
        secrets_by_source = dict(dict(secrets_payload or {}).get("secrets_by_source", {}))
        secret_key = credential_ref or source_id
        return str(secrets_by_source.get(secret_key, "")), "local_secret_store"
    return "", "unsupported_strategy"


def validate_effective_operator_session(
    payload: dict[str, Any],
    *,
    operator_root: str | Path | None = None,
    package_root: str | Path | None = None,
) -> list[str]:
    errors: list[str] = []
    if str(payload.get("schema_name", "")) != EFFECTIVE_OPERATOR_SESSION_SCHEMA_NAME:
        errors.append(f"schema_name must be {EFFECTIVE_OPERATOR_SESSION_SCHEMA_NAME}")
    if str(payload.get("schema_version", "")) != EFFECTIVE_OPERATOR_SESSION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {EFFECTIVE_OPERATOR_SESSION_SCHEMA_VERSION}")

    required_fields = [
        "session_id",
        "created_at",
        "operator_policy_root",
        "package_root",
        "runtime_event_log_path",
        "effective_runtime_constraints",
        "runtime_constraint_enforcement",
        "operator_runtime_envelope_spec",
        "effective_runtime_envelope",
        "trusted_source_bindings",
        "trusted_source_availability",
        "frozen_hashes",
    ]
    for field_name in required_fields:
        if not payload.get(field_name):
            errors.append(f"effective session is missing required field: {field_name}")
    if errors:
        return errors

    if operator_root is not None and _normalize_path(payload.get("operator_policy_root", "")) != _normalize_path(operator_root):
        errors.append("effective session operator_policy_root does not match the expected operator root")
    if package_root is not None and _normalize_path(payload.get("package_root", "")) != _normalize_path(package_root):
        errors.append("effective session package_root does not match the expected package root")

    mutation_lock = dict(payload.get("operator_runtime_mutation_lock", {}))
    if not bool(mutation_lock.get("enabled", False)):
        errors.append("effective session must enable operator_runtime_mutation_lock")

    frozen_hashes = dict(payload.get("frozen_hashes", {}))
    expected_session_hash = str(frozen_hashes.get("session_payload_sha256", ""))
    actual_session_hash = _stable_hash(_session_payload_without_hashes(payload))
    if expected_session_hash != actual_session_hash:
        errors.append("effective session payload hash does not match its frozen session hash")

    runtime_constraints = dict(payload.get("effective_runtime_constraints", {}))
    expected_runtime_hash = str(frozen_hashes.get("runtime_constraints_sha256", ""))
    if expected_runtime_hash != _stable_hash(runtime_constraints):
        errors.append("effective runtime constraints hash does not match the frozen session hash")

    runtime_envelope_spec = dict(payload.get("operator_runtime_envelope_spec", {}))
    expected_runtime_envelope_hash = str(frozen_hashes.get("runtime_envelope_spec_sha256", ""))
    if expected_runtime_envelope_hash != _stable_hash(runtime_envelope_spec):
        errors.append("operator runtime envelope spec hash does not match the frozen session hash")

    effective_runtime_envelope = dict(payload.get("effective_runtime_envelope", {}))
    expected_effective_envelope_hash = str(frozen_hashes.get("effective_runtime_envelope_sha256", ""))
    if expected_effective_envelope_hash != _stable_hash(effective_runtime_envelope):
        errors.append("effective runtime envelope hash does not match the frozen session hash")

    trusted_source_bindings = dict(payload.get("trusted_source_bindings", {}))
    expected_bindings_hash = str(frozen_hashes.get("trusted_source_bindings_sha256", ""))
    if expected_bindings_hash != _stable_hash(trusted_source_bindings):
        errors.append("trusted source bindings hash does not match the frozen session hash")

    runtime_errors, _, _ = validate_runtime_constraints(
        runtime_constraints,
        package_root=package_root,
        operator_root=operator_root,
    )
    if runtime_errors:
        errors.append("effective runtime constraints are internally invalid")
        errors.extend([f"runtime_constraints::{item}" for item in runtime_errors])

    binding_errors, _, _ = validate_trusted_source_bindings(
        trusted_source_bindings,
        secrets_payload={"secrets_by_source": {}},
    )
    if binding_errors:
        errors.append("effective trusted source bindings are internally invalid")
        errors.extend([f"trusted_source_bindings::{item}" for item in binding_errors])

    envelope_errors, _, _ = validate_operator_runtime_envelope_spec(
        runtime_envelope_spec,
        runtime_constraints=runtime_constraints,
        trusted_source_bindings=trusted_source_bindings,
        enforce_backend_availability=False,
    )
    if envelope_errors:
        errors.append("effective operator runtime envelope is internally invalid")
        errors.extend([f"runtime_envelope::{item}" for item in envelope_errors])
    return errors


def load_effective_operator_session_from_file(path: str | Path) -> dict[str, Any]:
    return _load_json(Path(path))


def load_last_operator_launch_event(root: str | Path | None = None) -> dict[str, Any]:
    path = operator_launch_event_ledger_path(root)
    try:
        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except FileNotFoundError:
        return {}
    for line in reversed(lines):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return {}


def _default_runtime_event_log_path(
    *,
    normalized_constraints: dict[str, Any],
    package_root: Path,
    session_id: str,
) -> Path:
    workspace_policy = dict(normalized_constraints.get("workspace_policy", {}))
    preferred_log_root = Path(
        str(workspace_policy.get("log_root", default_runtime_logs_root(package_root)))
    )
    if preferred_log_root.exists():
        return preferred_log_root / "runtime_events" / f"{session_id}.jsonl"
    allowed_roots = [
        Path(item)
        for item in list(dict(normalized_constraints.get("constraints", {})).get("allowed_write_roots", []))
    ]
    for root in allowed_roots:
        if root.exists():
            return root / "runtime_events" / f"{session_id}.jsonl"
    return package_root / "logs" / "runtime_events" / f"{session_id}.jsonl"


def validate_existing_resume_session(
    *,
    root: str | Path | None = None,
    package_root: str | Path | None = None,
) -> tuple[dict[str, Any], list[str]]:
    session_path = effective_operator_session_path(root)
    existing_session = load_effective_operator_session_from_file(session_path)
    if not existing_session:
        return {}, ["resume requires an existing frozen operator session snapshot"]
    errors = validate_effective_operator_session(
        existing_session,
        operator_root=root,
        package_root=package_root,
    )
    return existing_session, errors


def freeze_effective_operator_session(
    *,
    root: str | Path | None = None,
    package_root: str | Path | None = None,
    directive_file: str | Path | None = None,
    clarification_file: str | Path | None = None,
    state_root: str | Path | None = None,
    entry_script: str | Path | None = None,
    runtime_args: list[str] | None = None,
    launch_kind: str = "bootstrap_only",
) -> tuple[dict[str, Any], list[str]]:
    operator_root = default_operator_root() if root is None else Path(root)
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    if directive_file is None:
        _, resume_errors = validate_existing_resume_session(
            root=operator_root,
            package_root=package_root_path,
        )
        if resume_errors:
            return {}, resume_errors

    runtime_constraints_payload = load_runtime_constraints(root)
    runtime_envelope_payload = load_runtime_envelope_spec(root)
    trusted_source_bindings_payload = load_trusted_source_bindings(root)
    trusted_source_secrets_payload = load_trusted_source_secrets_or_default(root)

    errors: list[str] = []
    if not runtime_constraints_payload:
        errors.append("operator runtime constraints file is missing")
    if not runtime_envelope_payload:
        errors.append("operator runtime envelope spec file is missing")
    if not trusted_source_bindings_payload:
        errors.append("trusted source bindings file is missing")
    if errors:
        return {}, errors

    runtime_errors, normalized_constraints, enforcement = validate_runtime_constraints(
        runtime_constraints_payload,
        package_root=package_root_path,
        operator_root=operator_root,
    )
    bindings_errors, normalized_bindings, availability = validate_trusted_source_bindings(
        trusted_source_bindings_payload,
        secrets_payload=trusted_source_secrets_payload,
    )
    envelope_errors, normalized_envelope, effective_envelope = validate_operator_runtime_envelope_spec(
        runtime_envelope_payload,
        runtime_constraints=normalized_constraints,
        trusted_source_bindings=normalized_bindings,
    )
    errors.extend(runtime_errors)
    errors.extend(bindings_errors)
    errors.extend(envelope_errors)

    execution_profile = str(
        normalized_constraints.get(
            "execution_profile",
            EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION,
        )
    ).strip() or EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION
    workspace_policy = dict(normalized_constraints.get("workspace_policy", {}))
    workspace_id = str(workspace_policy.get("workspace_id", "")).strip()
    workspace_root = str(workspace_policy.get("workspace_root", "")).strip()
    allowed_write_roots = list(
        dict(normalized_constraints.get("constraints", {})).get("allowed_write_roots", [])
    )

    if str(launch_kind).strip() == "governed_execution":
        if execution_profile != EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING:
            errors.append(
                "governed_execution requires a coding-capable saved runtime policy; "
                f"current execution_profile is {execution_profile or '<missing>'}"
            )
        if not workspace_id or not workspace_root:
            errors.append(
                "governed_execution requires workspace_id and workspace_root to be materialized "
                "from the saved bounded coding profile"
            )
        elif not any(
            _is_under_path(Path(workspace_root), Path(root_item))
            for root_item in allowed_write_roots
        ):
            errors.append(
                "governed_execution requires the active workspace root to be inside an "
                "operator-approved writable root"
            )

    normalized_state_root = _normalize_path(state_root)
    if directive_file is not None and normalized_state_root:
        if allowed_write_roots and not any(
            _is_under_path(Path(normalized_state_root), Path(root_item))
            for root_item in allowed_write_roots
        ):
            errors.append(
                "fresh bootstrap requires state_root to be inside an operator-approved writable root; "
                "use bootstrap_only initialization first or select a profile that includes the state root"
            )

    if bool(runtime_constraints_payload.get("required_for_launch", True)):
        for item in list(availability.get("sources", [])):
            if item.get("enabled") and not item.get("ready_for_launch"):
                errors.append(
                    f"trusted source binding is enabled but not ready: {item.get('source_id')} ({item.get('availability_reason')})"
                )

    if errors:
        return {}, errors

    session_id = f"operator_session::{uuid.uuid4()}"
    runtime_event_log = _default_runtime_event_log_path(
        normalized_constraints=normalized_constraints,
        package_root=package_root_path,
        session_id=session_id.replace("::", "_"),
    )
    runtime_event_log.parent.mkdir(parents=True, exist_ok=True)
    session = {
        "schema_name": EFFECTIVE_OPERATOR_SESSION_SCHEMA_NAME,
        "schema_version": EFFECTIVE_OPERATOR_SESSION_SCHEMA_VERSION,
        "created_at": _now(),
        "session_id": session_id,
        "operator_policy_root": _normalize_path(operator_root),
        "package_root": _normalize_path(package_root_path),
        "state_root": _normalize_path(state_root),
        "directive_file": _normalize_path(directive_file),
        "clarification_file": _normalize_path(clarification_file),
        "entry_script": _normalize_path(entry_script),
        "launch_kind": str(launch_kind),
        "execution_profile": str(normalized_constraints.get("execution_profile", "")),
        "workspace_policy": dict(normalized_constraints.get("workspace_policy", {})),
        "runtime_args": [str(item) for item in list(runtime_args or [])],
        "runtime_event_log_path": _normalize_path(runtime_event_log),
        "effective_runtime_constraints": normalized_constraints,
        "runtime_constraint_enforcement": enforcement,
        "operator_runtime_envelope_spec": normalized_envelope,
        "effective_runtime_envelope": effective_envelope,
        "trusted_source_bindings": normalized_bindings,
        "trusted_source_availability": availability,
        "trusted_source_summary": summarize_trusted_source_availability(availability),
        "operator_runtime_mutation_lock": {
            "enabled": True,
            "lock_owner": "operator_shell",
            "reason": "runtime sessions may read effective constraints but may not mutate operator-owned policy",
        },
        "frozen_hashes": {
            "runtime_constraints_sha256": _stable_hash(normalized_constraints),
            "runtime_envelope_spec_sha256": _stable_hash(normalized_envelope),
            "effective_runtime_envelope_sha256": _stable_hash(effective_envelope),
            "trusted_source_bindings_sha256": _stable_hash(normalized_bindings),
            "session_payload_sha256": "",
        },
    }
    session["frozen_hashes"]["session_payload_sha256"] = _stable_hash(
        {key: value for key, value in session.items() if key != "frozen_hashes"}
    )
    _write_json(effective_operator_session_path(root), session)
    return session, []


def record_operator_launch_event(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    ledger_row = {
        "schema_name": OPERATOR_LAUNCH_EVENT_SCHEMA_NAME,
        "schema_version": OPERATOR_LAUNCH_EVENT_SCHEMA_VERSION,
        **dict(payload),
    }
    _append_jsonl(operator_launch_event_ledger_path(root), ledger_row)


def read_operator_status_snapshot(
    *,
    root: str | Path | None = None,
    package_root: str | Path | None = None,
) -> dict[str, Any]:
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    runtime_payload = load_runtime_constraints(root)
    runtime_envelope_payload = load_runtime_envelope_spec(root)
    bindings_payload = load_trusted_source_bindings(root)
    secrets_payload = load_trusted_source_secrets_or_default(root)

    runtime_errors, normalized_constraints, enforcement = validate_runtime_constraints(
        runtime_payload if runtime_payload else build_default_runtime_constraints(package_root_path),
        package_root=package_root_path,
        operator_root=root,
    )
    binding_errors, normalized_bindings, availability = validate_trusted_source_bindings(
        bindings_payload if bindings_payload else build_default_trusted_source_bindings(package_root_path),
        secrets_payload=secrets_payload,
    )
    backend_probe = probe_runtime_backend_capabilities()
    envelope_errors, normalized_envelope, effective_envelope = validate_operator_runtime_envelope_spec(
        runtime_envelope_payload if runtime_envelope_payload else build_default_operator_runtime_envelope_spec(package_root_path),
        runtime_constraints=normalized_constraints,
        trusted_source_bindings=normalized_bindings,
        backend_probe=backend_probe,
    )
    if not runtime_envelope_payload:
        envelope_errors = ["operator runtime envelope spec file is missing", *list(envelope_errors)]
    session = load_effective_operator_session_from_file(effective_operator_session_path(root))
    session_errors = validate_effective_operator_session(
        session,
        operator_root=root,
        package_root=package_root_path,
    ) if session else ["no frozen operator session has been materialized yet"]
    last_launch_event = load_last_operator_launch_event(root)
    latest_launch_plan_path = operator_runtime_launch_plan_latest_path(root)
    latest_launch_plan = _load_json(latest_launch_plan_path)
    secret_binding_rows = []
    for binding in list(normalized_bindings.get("bindings", [])):
        secret_value, secret_source = resolve_trusted_source_secret(binding, secrets_payload=secrets_payload)
        secret_binding_rows.append(
            {
                "source_id": str(binding.get("source_id", "")),
                "credential_strategy": str(binding.get("credential_strategy", "")),
                "credential_ref": str(binding.get("credential_ref", "")),
                "secret_source": secret_source,
                "secret_present": bool(str(secret_value).strip()),
            }
        )
    return {
        "operator_root": _normalize_path(default_operator_root() if root is None else Path(root)),
        "runtime_constraints_path": str(operator_runtime_constraints_path(root)),
        "runtime_envelope_spec_path": str(operator_runtime_envelope_spec_path(root)),
        "trusted_source_bindings_path": str(trusted_source_bindings_path(root)),
        "trusted_source_secrets_path": str(trusted_source_secrets_path(root)),
        "effective_operator_session_path": str(effective_operator_session_path(root)),
        "operator_launch_event_ledger_path": str(operator_launch_event_ledger_path(root)),
        "operator_runtime_launch_plan_path": str(latest_launch_plan_path),
        "runtime_constraints_valid": len(runtime_errors) == 0,
        "runtime_constraints_errors": runtime_errors,
        "runtime_constraints": normalized_constraints,
        "runtime_constraint_enforcement": enforcement,
        "execution_profile": str(normalized_constraints.get("execution_profile", "")),
        "workspace_policy": dict(normalized_constraints.get("workspace_policy", {})),
        "runtime_envelope_spec_valid": len(envelope_errors) == 0,
        "runtime_envelope_spec_errors": envelope_errors,
        "runtime_envelope_spec": normalized_envelope,
        "effective_runtime_envelope": effective_envelope,
        "runtime_backend_probe": backend_probe,
        "trusted_source_bindings_valid": len(binding_errors) == 0,
        "trusted_source_binding_errors": binding_errors,
        "trusted_source_bindings": normalized_bindings,
        "trusted_source_availability": availability,
        "trusted_source_summary": summarize_trusted_source_availability(availability),
        "trusted_source_secret_summary": {
            "bindings": secret_binding_rows,
        },
        "effective_operator_session_valid": len(session_errors) == 0,
        "effective_operator_session_errors": session_errors,
        "effective_operator_session": session,
        "last_launch_event": last_launch_event,
        "last_launch_plan": latest_launch_plan,
    }
