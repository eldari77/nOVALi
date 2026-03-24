from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .governed_execution import (
    governed_execution_controller_summary_for_workspace,
    governed_execution_session_summary_for_workspace,
)
from .policy import (
    EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION,
    EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING,
)


GUI_PROFILE_SCHEMA_NAME = "OperatorGuiProfile"
GUI_PROFILE_SCHEMA_VERSION = "operator_gui_profile_v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_path_string(value: Any) -> str:
    if value in {None, ""}:
        return ""
    try:
        return str(Path(str(value)).resolve())
    except OSError:
        return str(value)


def _is_under_path_string(candidate: Any, root: Any) -> bool:
    candidate_text = _normalize_path_string(candidate)
    root_text = _normalize_path_string(root)
    if not candidate_text or not root_text:
        return False
    try:
        Path(candidate_text).resolve().relative_to(Path(root_text).resolve())
        return True
    except ValueError:
        return False


def _json_dump(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def stable_runtime_constraints_signature(payload: dict[str, Any] | None) -> str:
    comparable = dict(payload or {})
    comparable.pop("generated_at", None)
    return _json_dump(comparable)


def _normalized_runtime_constraints_section(snapshot: dict[str, Any]) -> dict[str, Any]:
    raw_runtime = dict(snapshot.get("runtime_constraints", {}))
    if any(key in raw_runtime for key in ("valid", "errors", "enforcement")):
        constraints_payload = dict(raw_runtime.get("constraints", {}))
        enforcement = dict(raw_runtime.get("enforcement", {}))
        valid = bool(raw_runtime.get("valid", snapshot.get("runtime_constraints_valid", False)))
        errors = list(raw_runtime.get("errors", snapshot.get("runtime_constraints_errors", [])))
        path = str(raw_runtime.get("path", snapshot.get("runtime_constraints_path", "")))
        payload = dict(raw_runtime.get("payload", {})) or {
            **dict(snapshot.get("runtime_constraints", {})),
            **{
                "execution_profile": raw_runtime.get("execution_profile", snapshot.get("execution_profile", "")),
                "workspace_policy": raw_runtime.get("workspace_policy", snapshot.get("workspace_policy", {})),
                "constraints": constraints_payload,
            },
        }
    else:
        constraints_payload = raw_runtime
        enforcement = dict(snapshot.get("runtime_constraint_enforcement", {}))
        valid = bool(snapshot.get("runtime_constraints_valid", False))
        errors = list(snapshot.get("runtime_constraints_errors", []))
        path = str(snapshot.get("runtime_constraints_path", ""))
        payload = raw_runtime
    return {
        "valid": valid,
        "errors": errors,
        "payload": payload,
        "constraints": constraints_payload,
        "enforcement": enforcement,
        "path": path,
    }


def _normalized_runtime_envelope_section(snapshot: dict[str, Any]) -> dict[str, Any]:
    raw_envelope = dict(snapshot.get("runtime_envelope", {}))
    if any(key in raw_envelope for key in ("valid", "errors", "effective")):
        valid = bool(raw_envelope.get("valid", snapshot.get("runtime_envelope_spec_valid", False)))
        errors = list(raw_envelope.get("errors", snapshot.get("runtime_envelope_spec_errors", [])))
        spec = dict(raw_envelope.get("spec", snapshot.get("runtime_envelope_spec", {})))
        effective = dict(raw_envelope.get("effective", snapshot.get("effective_runtime_envelope", {})))
        path = str(raw_envelope.get("path", snapshot.get("runtime_envelope_spec_path", "")))
        backend_probe = dict(raw_envelope.get("backend_probe", snapshot.get("runtime_backend_probe", {})))
    else:
        valid = bool(snapshot.get("runtime_envelope_spec_valid", False))
        errors = list(snapshot.get("runtime_envelope_spec_errors", []))
        spec = dict(snapshot.get("runtime_envelope_spec", {}))
        effective = dict(snapshot.get("effective_runtime_envelope", {}))
        path = str(snapshot.get("runtime_envelope_spec_path", ""))
        backend_probe = dict(snapshot.get("runtime_backend_probe", {}))
    return {
        "valid": valid,
        "errors": errors,
        "spec": spec,
        "effective": effective,
        "path": path,
        "backend_probe": backend_probe,
    }


def _normalized_trusted_sources_section(snapshot: dict[str, Any]) -> dict[str, Any]:
    raw_trusted = dict(snapshot.get("trusted_sources", {}))
    summary_source = raw_trusted if raw_trusted else dict(snapshot.get("trusted_source_summary", {}))
    availability = dict(snapshot.get("trusted_source_availability", {}))
    sources = list(raw_trusted.get("sources", []))
    if not sources:
        sources = list(availability.get("sources", []))
    return {
        "ready_sources": list(summary_source.get("ready_sources", [])),
        "attention_required_sources": list(summary_source.get("attention_required_sources", [])),
        "disabled_sources": list(summary_source.get("disabled_sources", [])),
        "summary": dict(summary_source.get("summary", {})),
        "sources": sources,
    }


def _normalized_operator_status_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(snapshot)
    normalized["runtime_constraints"] = _normalized_runtime_constraints_section(snapshot)
    normalized["runtime_envelope"] = _normalized_runtime_envelope_section(snapshot)
    normalized["trusted_sources"] = _normalized_trusted_sources_section(snapshot)
    if "launch_context" not in normalized:
        normalized["launch_context"] = {
            "canonical_human_launcher": "python -m novali_v5.web_operator",
            "equivalent_convenience_launcher": "python -m novali_v5",
            "transitional_desktop_launcher": "python -m novali_v5.operator_shell",
            "current_launch_mode": str(snapshot.get("current_launch_mode", "")),
            "effective_operator_session_valid": bool(snapshot.get("effective_operator_session_valid", False)),
            "effective_operator_session_errors": list(snapshot.get("effective_operator_session_errors", [])),
            "last_launch_event": dict(snapshot.get("last_launch_event", {})),
        }
    return normalized


def operator_gui_profile_path(root: str | Path) -> Path:
    return Path(root) / "operator_gui_profile.local.json"


def build_default_operator_gui_profile(package_root: str | Path | None = None) -> dict[str, Any]:
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    return {
        "schema_name": GUI_PROFILE_SCHEMA_NAME,
        "schema_version": GUI_PROFILE_SCHEMA_VERSION,
        "updated_at": "",
        "recent_directive_file": str(package_root_path / "directives" / "novali_v5_bootstrap_directive_v1.json"),
        "recent_state_root": str(package_root_path / "data"),
        "recent_resume_mode": "new_bootstrap",
        "recent_launch_action": "bootstrap_only",
        "recent_trusted_source_ids": [],
        "display_preferences": {
            "show_raw_json_sections": False,
        },
    }


def sanitize_operator_gui_profile(
    payload: dict[str, Any] | None,
    *,
    package_root: str | Path | None = None,
) -> dict[str, Any]:
    defaults = build_default_operator_gui_profile(package_root)
    source = dict(payload or {})
    preferences = dict(source.get("display_preferences", {}))
    recent_sources = [
        str(item).strip()
        for item in list(source.get("recent_trusted_source_ids", []))
        if str(item).strip()
    ]
    cleaned = {
        "schema_name": GUI_PROFILE_SCHEMA_NAME,
        "schema_version": GUI_PROFILE_SCHEMA_VERSION,
        "updated_at": str(source.get("updated_at", "")),
        "recent_directive_file": str(source.get("recent_directive_file", defaults["recent_directive_file"])),
        "recent_state_root": str(source.get("recent_state_root", defaults["recent_state_root"])),
        "recent_resume_mode": (
            str(source.get("recent_resume_mode", defaults["recent_resume_mode"]))
            if str(source.get("recent_resume_mode", defaults["recent_resume_mode"])) in {"new_bootstrap", "resume_existing"}
            else str(defaults["recent_resume_mode"])
        ),
        "recent_launch_action": (
            str(source.get("recent_launch_action", defaults["recent_launch_action"]))
            if str(source.get("recent_launch_action", defaults["recent_launch_action"]))
            in {"bootstrap_only", "governed_execution", "proposal_analytics", "proposal_recommend"}
            else str(defaults["recent_launch_action"])
        ),
        "recent_trusted_source_ids": recent_sources[:16],
        "display_preferences": {
            "show_raw_json_sections": bool(
                preferences.get(
                    "show_raw_json_sections",
                    defaults["display_preferences"]["show_raw_json_sections"],
                )
            ),
        },
    }
    return cleaned


def load_operator_gui_profile(
    *,
    root: str | Path,
    package_root: str | Path | None = None,
) -> dict[str, Any]:
    path = operator_gui_profile_path(root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        payload = {}
    return sanitize_operator_gui_profile(payload, package_root=package_root)


def save_operator_gui_profile(
    payload: dict[str, Any],
    *,
    root: str | Path,
    package_root: str | Path | None = None,
) -> dict[str, Any]:
    path = operator_gui_profile_path(root)
    cleaned = sanitize_operator_gui_profile(payload, package_root=package_root)
    cleaned["updated_at"] = _now()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_dump(cleaned), encoding="utf-8")
    return cleaned


def inspect_directive_wrapper(
    directive_path: str | Path | None,
    *,
    resume_mode: str = "new_bootstrap",
) -> dict[str, Any]:
    path_text = str(directive_path or "").strip()
    if resume_mode == "resume_existing":
        if not path_text:
            return {
                "path": "",
                "exists": False,
                "is_valid": True,
                "severity": "info",
                "summary": "Resume mode selected. A directive file is optional because startup will validate the frozen operator session and persisted canonical state.",
                "details": [],
            }
    if not path_text:
        return {
            "path": "",
            "exists": False,
            "is_valid": False,
            "severity": "error",
            "summary": "Select a formal directive bootstrap JSON file before starting a new bootstrap.",
            "details": ["directive file path is empty"],
        }
    path = Path(path_text)
    if not path.exists():
        return {
            "path": path_text,
            "exists": False,
            "is_valid": False,
            "severity": "error",
            "summary": f"Directive file not found: {path_text}",
            "details": ["directive file does not exist"],
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "path": path_text,
            "exists": True,
            "is_valid": False,
            "severity": "error",
            "summary": "Directive wrapper is not valid JSON.",
            "details": [f"json error: {exc}"],
        }
    if not isinstance(payload, dict):
        return {
            "path": path_text,
            "exists": True,
            "is_valid": False,
            "severity": "error",
            "summary": "Directive wrapper must decode to a JSON object.",
            "details": ["top-level payload is not an object"],
        }
    details: list[str] = []
    if str(payload.get("schema_name", "")) != "NOVALIDirectiveBootstrapFile":
        details.append("schema_name must be NOVALIDirectiveBootstrapFile")
    if str(payload.get("schema_version", "")) != "novali_directive_bootstrap_file_v1":
        details.append("schema_version must be novali_directive_bootstrap_file_v1")
    if not isinstance(payload.get("directive_spec"), dict):
        details.append("directive_spec object is required")
    if not isinstance(payload.get("bootstrap_context"), dict):
        details.append("bootstrap_context object is required")
    if details:
        return {
            "path": path_text,
            "exists": True,
            "is_valid": False,
            "severity": "error",
            "summary": "Directive wrapper failed formal bootstrap wrapper checks.",
            "details": details,
        }
    directive_spec = dict(payload.get("directive_spec", {}))
    bootstrap_context = dict(payload.get("bootstrap_context", {}))
    return {
        "path": path_text,
        "exists": True,
        "is_valid": True,
        "severity": "success",
        "summary": (
            "Directive wrapper looks valid for directive-first bootstrap. "
            f"directive_id={directive_spec.get('directive_id', '') or '<missing>'}, "
            f"active_branch={bootstrap_context.get('active_branch', '') or '<missing>'}"
        ),
        "details": [],
    }


def format_enforcement_class_label(value: str) -> str:
    mapping = {
        "hard_enforced": "Hard enforced",
        "watchdog_enforced": "Watchdog enforced",
        "unsupported_on_this_platform": "Unsupported on this platform",
        "not_requested": "Not requested",
    }
    return mapping.get(str(value), str(value).replace("_", " ").title())


def format_secret_source_label(secret_source: str, secret_present: bool) -> str:
    source = str(secret_source)
    if source == "environment_variable":
        return "Environment variable present" if secret_present else "Environment variable missing"
    if source == "local_secret_store":
        return "Local secret stored" if secret_present else "Local secret missing"
    if source == "no_secret_required":
        return "No secret required"
    if source == "missing_credential_ref":
        return "Credential reference missing"
    if source == "unsupported_strategy":
        return "Unsupported credential strategy"
    return source.replace("_", " ").title()


def _format_operator_error_for_display(error: str) -> str:
    lowered = str(error).lower()
    if "resume requires an existing frozen operator session snapshot" in lowered:
        return "Resume refused because no frozen operator session is available yet."
    if "session payload hash" in lowered or "does not match its frozen session hash" in lowered:
        return "Resume refused because the frozen operator session appears tampered or internally inconsistent."
    if "operator_policy_root does not match" in lowered:
        return "Frozen operator session does not match the current operator policy root."
    if "package_root does not match" in lowered:
        return "Frozen operator session does not match the current package root."
    if "trusted source binding is enabled but not ready" in lowered:
        return f"Trusted source launch preflight failed: {error}"
    if "allowed_write_roots" in lowered:
        return f"Runtime write-boundary policy is invalid: {error}"
    if "working_directory" in lowered:
        return f"Working-directory policy is invalid: {error}"
    if "credential_ref" in lowered:
        return f"Trusted-source credential reference is invalid: {error}"
    if "selected runtime backend is unavailable" in lowered:
        return f"Selected runtime backend is unavailable: {error}"
    if "required backend translation could not be satisfied honestly" in lowered:
        return f"Runtime envelope could not satisfy a required backend translation: {error}"
    if "local_docker backend currently supports only local trusted sources" in lowered:
        return f"Local Docker backend currently supports only local trusted sources: {error}"
    if "runtime constraints" in lowered:
        return f"Runtime constraint policy is invalid: {error}"
    return str(error)


def _action_label(*, launch_kind: str, directive_file: str) -> str:
    if str(launch_kind) == "bootstrap_only":
        return "Resume" if not str(directive_file).strip() else "Activation"
    return "Governed execution"


def _refusal_reason_label(text: str) -> str:
    lowered = str(text).lower()
    if "directive clarification required" in lowered:
        return "Directive Clarification Required"
    if "governance blocked" in lowered:
        return "Governance Blocked"
    if "operator constraint blocked" in lowered:
        return "Operator Constraint Blocked"
    if "launch refused" in lowered:
        return "Launch Refused"
    return ""


def summarize_latest_launch_attempt(launch_context: dict[str, Any]) -> dict[str, Any]:
    context = dict(launch_context or {})
    last_launch_event = dict(context.get("last_launch_event", {}))
    effective_session = dict(context.get("effective_operator_session", {}))
    event_type = str(last_launch_event.get("event_type", "")).strip()
    session_id = str(last_launch_event.get("session_id", "")).strip()
    effective_session_id = str(effective_session.get("session_id", "")).strip()
    latest_attempt_matches_session = bool(session_id and session_id == effective_session_id)

    launch_kind = str(last_launch_event.get("launch_kind", "") or effective_session.get("launch_kind", "")).strip()
    directive_file = str(last_launch_event.get("directive_file", "")).strip()
    if not directive_file and latest_attempt_matches_session:
        directive_file = str(effective_session.get("directive_file", "")).strip()
    action_label = _action_label(launch_kind=launch_kind, directive_file=directive_file)

    if not event_type:
        return {
            "headline": "No launch attempt has been recorded yet.",
            "details": [],
            "outcome_class": "no_attempt_recorded",
        }

    if event_type == "launch_refused_preflight":
        mapped_errors = [
            _format_operator_error_for_display(item)
            for item in list(last_launch_event.get("errors", []))
        ]
        details = [f"Attempt kind: {launch_kind or '<unknown>'}"]
        details.extend(f"Refusal reason: {item}" for item in mapped_errors)
        if effective_session_id:
            details.append(
                "Frozen session note: the current frozen session may reflect an earlier successful run; "
                "this latest attempt was refused before a new process started."
            )
        return {
            "headline": "Launch refused before process start.",
            "details": details,
            "outcome_class": "launch_refused_preflight",
        }

    if event_type == "launch_started":
        return {
            "headline": "Launch started and is awaiting a completion record.",
            "details": [
                f"Attempt kind: {launch_kind or '<unknown>'}",
                f"Session id: {session_id or '<missing>'}",
            ],
            "outcome_class": "launch_started",
        }

    if event_type == "launch_completed":
        status = str(last_launch_event.get("status", "")).strip()
        exit_code = int(last_launch_event.get("exit_code", 0) or 0)
        failure_reason = str(last_launch_event.get("failure_reason", "")).strip()
        refusal_reason = _refusal_reason_label(failure_reason)
        details = [f"Attempt kind: {launch_kind or '<unknown>'}"]
        if latest_attempt_matches_session and effective_session_id:
            details.append(f"Frozen session: {effective_session_id}")
        if status == "terminated_by_watchdog":
            details.append(
                "Watchdog: "
                f"{last_launch_event.get('watchdog_constraint_id', '')} / "
                f"{last_launch_event.get('watchdog_enforcement_class', '')} / "
                f"{last_launch_event.get('watchdog_reason', '')}"
            )
            return {
                "headline": f"Process terminated by watchdog — {action_label} failed.",
                "details": details,
                "outcome_class": "watchdog_failed",
            }
        if exit_code == 0:
            return {
                "headline": f"Process finished — {action_label} completed.",
                "details": details,
                "outcome_class": "completed",
            }
        if refusal_reason:
            details.append(f"Refusal reason: {refusal_reason}")
            return {
                "headline": f"Process finished — {action_label} refused: {refusal_reason}.",
                "details": details,
                "outcome_class": "refused",
            }
        if failure_reason:
            details.append(f"Failure reason: {failure_reason}")
        return {
            "headline": f"Process finished — {action_label} failed.",
            "details": details,
            "outcome_class": "failed",
        }

    return {
        "headline": f"Latest launch event recorded: {event_type}",
        "details": [],
        "outcome_class": "unknown_event",
    }


def summarize_constraint_rows(snapshot: dict[str, Any]) -> dict[str, Any]:
    normalized_snapshot = _normalized_operator_status_snapshot(snapshot)
    runtime_constraints = dict(normalized_snapshot.get("runtime_constraints", {}))
    runtime_envelope = dict(normalized_snapshot.get("runtime_envelope", {}))
    normalized = dict(runtime_constraints.get("constraints", {}))
    enforcement = dict(runtime_constraints.get("enforcement", {}))
    envelope_translation = dict(dict(runtime_envelope.get("effective", {})).get("constraint_translation", {}))
    rows: list[dict[str, Any]] = []
    supported = 0
    unsupported = 0
    watchdog = 0
    for constraint_id in sorted(enforcement.keys()):
        info = dict(enforcement.get(constraint_id, {}))
        enforcement_class = str(info.get("enforcement_class", ""))
        requested_value = info.get("requested_value")
        row = {
            "constraint_id": constraint_id,
            "requested_value": requested_value,
            "requested_display": "None" if requested_value is None else str(requested_value),
            "enforcement_class": enforcement_class,
            "enforcement_label": format_enforcement_class_label(enforcement_class),
            "reason": str(info.get("reason", "")),
        }
        rows.append(row)
        if enforcement_class == "hard_enforced":
            supported += 1
        elif enforcement_class == "watchdog_enforced":
            watchdog += 1
        elif enforcement_class == "unsupported_on_this_platform":
            unsupported += 1
    for constraint_id in sorted(envelope_translation.keys()):
        info = dict(envelope_translation.get(constraint_id, {}))
        enforcement_class = str(info.get("enforcement_class", ""))
        row = {
            "constraint_id": f"envelope::{constraint_id}",
            "requested_value": info.get("requested_value"),
            "requested_display": "None" if info.get("requested_value") is None else str(info.get("requested_value")),
            "enforcement_class": enforcement_class,
            "enforcement_label": format_enforcement_class_label(enforcement_class),
            "reason": str(info.get("reason", "")),
        }
        rows.append(row)
        if enforcement_class == "hard_enforced":
            supported += 1
        elif enforcement_class == "watchdog_enforced":
            watchdog += 1
        elif enforcement_class == "unsupported_on_this_platform":
            unsupported += 1
    return {
        "rows": rows,
        "valid": bool(runtime_constraints.get("valid", False)) and bool(runtime_envelope.get("valid", True)),
        "errors": list(runtime_constraints.get("errors", [])) + list(runtime_envelope.get("errors", [])),
        "hard_enforced_count": supported,
        "watchdog_enforced_count": watchdog,
        "unsupported_count": unsupported,
        "normalized_constraints": normalized,
        "runtime_envelope": runtime_envelope,
    }


def summarize_trusted_source_rows(snapshot: dict[str, Any]) -> dict[str, Any]:
    normalized_snapshot = _normalized_operator_status_snapshot(snapshot)
    trusted_sources = dict(normalized_snapshot.get("trusted_sources", {}))
    secret_summary = dict(normalized_snapshot.get("trusted_source_secret_summary", {}))
    availability_rows = list(dict(trusted_sources).get("sources", []))
    secret_rows = {
        str(row.get("source_id", "")): dict(row)
        for row in list(secret_summary.get("bindings", []))
    }
    rows: list[dict[str, Any]] = []
    for row in availability_rows:
        source_id = str(row.get("source_id", ""))
        secret_row = dict(secret_rows.get(source_id, {}))
        rows.append(
            {
                "source_id": source_id,
                "enabled": bool(row.get("enabled", False)),
                "enabled_label": "Enabled" if bool(row.get("enabled", False)) else "Disabled",
                "source_kind": str(row.get("source_kind", "")),
                "credential_strategy": str(row.get("credential_strategy", "")),
                "availability_class": str(row.get("availability_class", "")),
                "availability_reason": str(row.get("availability_reason", "")),
                "ready_for_launch": bool(row.get("ready_for_launch", False)),
                "secret_source": str(secret_row.get("secret_source", row.get("resolved_secret_source", ""))),
                "secret_source_label": format_secret_source_label(
                    str(secret_row.get("secret_source", row.get("resolved_secret_source", ""))),
                    bool(secret_row.get("secret_present", False)),
                ),
                "secret_present": bool(secret_row.get("secret_present", False)),
                "credential_ref": str(row.get("credential_ref", "")),
                "path_hint": str(row.get("path_hint", "")),
            }
        )
    return {
        "rows": rows,
        "summary": dict(trusted_sources.get("summary", {})),
        "ready_sources": list(trusted_sources.get("ready_sources", [])),
        "attention_required_sources": list(trusted_sources.get("attention_required_sources", [])),
        "disabled_sources": list(trusted_sources.get("disabled_sources", [])),
    }


def build_launch_readiness(
    *,
    resume_mode: str,
    launch_action: str,
    state_root: str,
    directive_summary: dict[str, Any],
    operator_status_snapshot: dict[str, Any],
    constraints_dirty: bool,
) -> dict[str, Any]:
    normalized_snapshot = _normalized_operator_status_snapshot(operator_status_snapshot)
    blocking_reasons: list[str] = []
    warnings: list[str] = []
    runtime_constraints = dict(normalized_snapshot.get("runtime_constraints", {}))
    runtime_envelope = dict(normalized_snapshot.get("runtime_envelope", {}))
    runtime_constraints_path = str(runtime_constraints.get("path", "")).strip()
    runtime_envelope_path = str(runtime_envelope.get("path", "")).strip()
    runtime_constraint_payload = dict(runtime_constraints.get("payload", {}))
    workspace_policy = dict(runtime_constraint_payload.get("workspace_policy", {}))
    execution_profile = str(
        runtime_constraint_payload.get(
            "execution_profile",
            normalized_snapshot.get("execution_profile", ""),
        )
    ).strip()
    selected_launch = f"{str(resume_mode).strip() or '<missing>'} + {str(launch_action).strip() or '<missing>'}"
    expected_execution_profile = ""
    workflow_lane = "Operator review / proposal lane"
    operator_next_action = "Review launch posture"
    operator_next_action_detail = (
        "Check directive state, runtime policy, and frozen session readiness before launching."
    )
    if str(launch_action) == "bootstrap_only":
        expected_execution_profile = EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION
        workflow_lane = "Bootstrap-only initialization"
        operator_next_action = "Run bootstrap-only initialization"
        operator_next_action_detail = (
            "Use new_bootstrap + bootstrap_only first so NOVALI can create canonical frozen state."
        )
    elif str(launch_action) == "governed_execution":
        expected_execution_profile = EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING
        workflow_lane = "Governed execution"
        operator_next_action = "Resume governed execution"
        operator_next_action_detail = (
            "Use resume_existing + governed_execution after bootstrap is complete and the governed profile is restored."
        )
    elif str(launch_action) == "proposal_analytics":
        workflow_lane = "Proposal analytics"
        operator_next_action = "Inspect proposal analytics"
        operator_next_action_detail = (
            "This action reviews the current proposal state without replacing canonical bootstrap or governed execution."
        )
    elif str(launch_action) == "proposal_recommend":
        workflow_lane = "Proposal recommendation"
        operator_next_action = "Inspect proposal recommendation"
        operator_next_action_detail = (
            "This action prepares recommendation detail only; bounded runtime work still uses governed_execution."
        )

    profile_matches_selected_action: bool | None = None
    profile_alignment_label = "No execution-profile dependency recorded for this launch action."
    profile_alignment_detail = (
        "The saved runtime profile is still shown below so the operator can confirm what will be used at launch time."
    )
    if expected_execution_profile:
        profile_matches_selected_action = execution_profile == expected_execution_profile
        if profile_matches_selected_action:
            profile_alignment_label = "Selected action and saved runtime profile are aligned."
            profile_alignment_detail = (
                f"{selected_launch} will use {expected_execution_profile} as expected."
            )
        else:
            selected_profile = execution_profile or "<missing>"
            profile_alignment_label = f"Selected action expects {expected_execution_profile}."
            profile_alignment_detail = (
                f"{selected_launch} is selected, but the saved execution profile is {selected_profile}. "
                f"Save runtime policy with {expected_execution_profile} before launch."
            )
            warnings.append(profile_alignment_detail)

    if constraints_dirty:
        dirty_reason = "Save / Apply runtime constraints and envelope before launch."
        if runtime_constraints_path:
            dirty_reason += f" Applied source: {runtime_constraints_path}"
        if runtime_envelope_path:
            dirty_reason += f" Envelope source: {runtime_envelope_path}"
        blocking_reasons.append(dirty_reason)

    if not bool(runtime_constraints.get("valid", False)):
        runtime_errors = list(runtime_constraints.get("errors", []))
        if runtime_errors:
            for item in runtime_errors:
                blocking_reasons.append(_format_operator_error_for_display(str(item)))
        else:
            invalid_reason = "Runtime constraint policy is not valid."
            if runtime_constraints_path:
                invalid_reason += f" Source: {runtime_constraints_path}"
            blocking_reasons.append(invalid_reason)

    if not bool(runtime_envelope.get("valid", False)):
        envelope_errors = list(runtime_envelope.get("errors", []))
        if envelope_errors:
            for item in envelope_errors:
                blocking_reasons.append(_format_operator_error_for_display(str(item)))
        else:
            invalid_reason = "Runtime envelope policy is not valid."
            if runtime_envelope_path:
                invalid_reason += f" Source: {runtime_envelope_path}"
            blocking_reasons.append(invalid_reason)

    trusted_sources = summarize_trusted_source_rows(normalized_snapshot)
    if trusted_sources["attention_required_sources"]:
        blocking_reasons.append(
            "Trusted sources require operator attention before launch: "
            + ", ".join(trusted_sources["attention_required_sources"])
        )

    if str(resume_mode) == "new_bootstrap":
        if not bool(directive_summary.get("is_valid", False)):
            blocking_reasons.append(str(directive_summary.get("summary", "")))
        state_root_text = _normalize_path_string(state_root)
        allowed_write_roots = list(dict(runtime_constraint_payload.get("constraints", {})).get("allowed_write_roots", []))
        if state_root_text and allowed_write_roots and not any(
            _is_under_path_string(state_root_text, root_item)
            for root_item in allowed_write_roots
        ):
            blocking_reasons.append(
                "Fresh bootstrap requires the selected state root to be inside an operator-approved writable root. "
                "Use bootstrap_only initialization first or switch to a profile that includes the state root."
            )
    else:
        session_valid = bool(normalized_snapshot.get("effective_operator_session_valid", False))
        if not session_valid:
            session_errors = list(normalized_snapshot.get("effective_operator_session_errors", []))
            if session_errors:
                for item in session_errors:
                    blocking_reasons.append(_format_operator_error_for_display(str(item)))
            else:
                blocking_reasons.append("Resume requires a valid frozen operator session.")

    constraint_summary = summarize_constraint_rows(normalized_snapshot)
    unsupported_rows = [
        row
        for row in list(constraint_summary.get("rows", []))
        if row.get("enforcement_class") == "unsupported_on_this_platform"
    ]
    if unsupported_rows:
        warnings.append(
            "Some runtime controls remain unsupported on this platform and are displayed for awareness only: "
            + ", ".join(row["constraint_id"] for row in unsupported_rows)
        )

    if str(launch_action) == "governed_execution":
        warnings.append(
            "governed_execution continues through the canonical governed runtime after bootstrap; it is not the same as bootstrap_only initialization."
        )
    if str(resume_mode) == "new_bootstrap" and str(launch_action) == "governed_execution":
        warnings.append(
            "governed_execution assumes canonical bootstrap state already exists. For a first run, use new_bootstrap + bootstrap_only first."
        )
    if str(resume_mode) == "resume_existing" and str(launch_action) == "bootstrap_only":
        warnings.append(
            "resume_existing + bootstrap_only only re-enters bootstrap state review; bounded post-bootstrap work still uses resume_existing + governed_execution."
        )
    if execution_profile == "bounded_active_workspace_coding":
        workspace_root = str(workspace_policy.get("workspace_root", "")).strip()
        if workspace_root:
            warnings.append(
                "bounded_active_workspace_coding permits writes only inside the frozen active workspace and approved generated/log roots: "
                + workspace_root
            )

    can_launch = len(blocking_reasons) == 0
    headline = (
        "Ready for canonical operator launch."
        if can_launch
        else "Launch blocked until operator issues are resolved."
    )
    return {
        "can_launch": can_launch,
        "headline": headline,
        "selected_launch": selected_launch,
        "workflow_lane": workflow_lane,
        "selected_execution_profile": execution_profile,
        "expected_execution_profile": expected_execution_profile,
        "profile_matches_selected_action": profile_matches_selected_action,
        "profile_alignment_label": profile_alignment_label,
        "profile_alignment_detail": profile_alignment_detail,
        "operator_next_action": operator_next_action,
        "operator_next_action_detail": operator_next_action_detail,
        "blocking_reasons": blocking_reasons,
        "warnings": warnings,
        "summary": render_launch_readiness(readiness={
            "headline": headline,
            "selected_launch": selected_launch,
            "workflow_lane": workflow_lane,
            "selected_execution_profile": execution_profile,
            "expected_execution_profile": expected_execution_profile,
            "profile_matches_selected_action": profile_matches_selected_action,
            "profile_alignment_label": profile_alignment_label,
            "profile_alignment_detail": profile_alignment_detail,
            "operator_next_action": operator_next_action,
            "operator_next_action_detail": operator_next_action_detail,
            "blocking_reasons": blocking_reasons,
            "warnings": warnings,
        }),
    }


def render_launch_readiness(*, readiness: dict[str, Any]) -> str:
    lines = [str(readiness.get("headline", ""))]
    selected_launch = str(readiness.get("selected_launch", "")).strip()
    workflow_lane = str(readiness.get("workflow_lane", "")).strip()
    expected_execution_profile = str(readiness.get("expected_execution_profile", "")).strip()
    selected_execution_profile = str(readiness.get("selected_execution_profile", "")).strip()
    profile_alignment_label = str(readiness.get("profile_alignment_label", "")).strip()
    profile_alignment_detail = str(readiness.get("profile_alignment_detail", "")).strip()
    operator_next_action = str(readiness.get("operator_next_action", "")).strip()
    operator_next_action_detail = str(readiness.get("operator_next_action_detail", "")).strip()
    blocking = list(readiness.get("blocking_reasons", []))
    warnings = list(readiness.get("warnings", []))
    if selected_launch:
        lines.extend(["", f"Selected launch: {selected_launch}"])
    if workflow_lane:
        lines.append(f"Workflow lane: {workflow_lane}")
    if expected_execution_profile:
        lines.append(f"Expected execution profile: {expected_execution_profile}")
        lines.append(f"Saved execution profile: {selected_execution_profile or '<missing>'}")
    if profile_alignment_label:
        lines.append(f"Runtime policy check: {profile_alignment_label}")
    if profile_alignment_detail:
        lines.append(f"Policy guidance: {profile_alignment_detail}")
    if operator_next_action:
        lines.append(f"Operator next action: {operator_next_action}")
    if operator_next_action_detail:
        lines.append(f"Action detail: {operator_next_action_detail}")
    if blocking:
        lines.append("")
        lines.append("Blocking reasons:")
        lines.extend(f"- {item}" for item in blocking)
    if warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {item}" for item in warnings)
    return "\n".join(line for line in lines if line is not None).strip()


def build_launch_refusal_summary(message: str, errors: list[str]) -> dict[str, Any]:
    mapped_errors = [_format_operator_error_for_display(item) for item in list(errors)]
    headline = "Launch refused before process start."
    if any("tampered" in item.lower() or "frozen operator session" in item.lower() for item in mapped_errors):
        headline = "Launch refused before process start — frozen operator session absent or incoherent."
    elif any("selected runtime backend is unavailable" in item.lower() for item in mapped_errors):
        headline = "Launch refused before process start — selected runtime backend is unavailable."
    elif any("local_docker backend currently supports only local trusted sources" in item.lower() for item in mapped_errors):
        headline = "Launch refused before process start — Docker mode currently requires local-only trusted sources."
    elif any("trusted source" in item.lower() for item in mapped_errors):
        headline = "Launch refused before process start — trusted-source configuration is not launch-ready."
    elif any("runtime" in item.lower() or "working-directory" in item.lower() for item in mapped_errors):
        headline = "Launch refused before process start — operator runtime policy is invalid."
    elif str(message).strip():
        headline = f"Launch refused before process start — {str(message).strip()}."
    return {
        "headline": headline,
        "details": mapped_errors,
        "summary": "\n".join([headline, "", *[f"- {item}" for item in mapped_errors]]).strip(),
    }


def build_launch_result_summary(result: dict[str, Any]) -> dict[str, Any]:
    status = str(result.get("status", "")).strip()
    exit_code = int(result.get("exit_code", 0) or 0)
    session = dict(result.get("session", {}))
    backend_kind = str(result.get("backend_kind", "")).strip()
    launch_plan = dict(result.get("launch_plan", {}))
    launch_plan_summary = dict(launch_plan.get("summary", {}))
    launch_kind = str(session.get("launch_kind", "")).strip()
    directive_file = str(session.get("directive_file", "")).strip()
    execution_profile = str(
        session.get(
            "execution_profile",
            dict(session.get("effective_runtime_constraints", {})).get("execution_profile", ""),
        )
    ).strip()
    workspace_policy = dict(
        session.get(
            "workspace_policy",
            dict(session.get("effective_runtime_constraints", {})).get("workspace_policy", {}),
        )
    )
    governed_summary = governed_execution_session_summary_for_workspace(
        str(workspace_policy.get("workspace_root", "")).strip()
    )
    governed_controller = governed_execution_controller_summary_for_workspace(
        str(workspace_policy.get("workspace_root", "")).strip()
    )
    action_label = _action_label(launch_kind=launch_kind, directive_file=directive_file)
    last_failure_reason = str(result.get("failure_reason", "")).strip()
    details: list[str] = []
    if status == "terminated_by_watchdog":
        headline = f"Process terminated by watchdog — {action_label} failed."
        details.append(
            "Watchdog: "
            f"{result.get('watchdog_constraint_id')} / {result.get('watchdog_enforcement_class')} / "
            f"{result.get('watchdog_reason')}"
        )
    elif exit_code == 0:
        if launch_kind == "governed_execution":
            headline = "Process finished — Governed execution cycle completed."
        else:
            headline = f"Process finished — {action_label} completed."
    else:
        refusal_reason = _refusal_reason_label(last_failure_reason)
        if refusal_reason:
            headline = f"Process finished — {action_label} refused: {refusal_reason}."
            details.append(f"Refusal reason: {refusal_reason}")
        else:
            headline = f"Process finished — {action_label} failed."
            if last_failure_reason:
                details.append(f"Failure reason: {last_failure_reason}")
    if session:
        details.append(f"Frozen session: {session.get('session_id', '')}")
        if backend_kind:
            details.append(f"Runtime backend: {backend_kind}")
        if execution_profile:
            details.append(f"Execution profile: {execution_profile}")
        if str(workspace_policy.get("workspace_root", "")).strip():
            details.append(
                "Active workspace: "
                f"{workspace_policy.get('workspace_id', '')} -> {workspace_policy.get('workspace_root', '')}"
            )
        if str(governed_summary.get("status", "")).strip():
            details.append(f"Bounded work status: {governed_summary.get('status', '')}")
        work_cycle = dict(governed_summary.get("work_cycle", {}))
        if str(governed_controller.get("controller_mode", "")).strip():
            details.append(f"Controller mode: {governed_controller.get('controller_mode', '')}")
        if governed_controller.get("cycles_completed") not in {None, ""}:
            details.append(f"Cycles completed: {governed_controller.get('cycles_completed')}")
        if str(governed_controller.get("stop_reason", "")).strip():
            details.append(f"Stop reason: {governed_controller.get('stop_reason', '')}")
        if str(work_cycle.get("cycle_kind", "")).strip():
            details.append(f"Bounded work cycle: {work_cycle.get('cycle_kind', '')}")
        if str(work_cycle.get("invocation_model", "")).strip():
            if str(governed_controller.get("controller_mode", "")).strip() == "multi_cycle":
                details.append(
                    "Execution model: multi-cycle governed_execution may continue through several bounded cycles until completion, no-work, failure, or the operator-selected cap."
                )
            else:
                details.append(
                    "Execution model: one bounded cycle runs per governed_execution launch; re-run governed_execution to advance."
                )
        if str(work_cycle.get("implementation_bundle_kind", "")).strip():
            details.append(f"Implementation bundle: {work_cycle.get('implementation_bundle_kind', '')}")
        if str(work_cycle.get("summary_artifact_path", "")).strip():
            details.append(f"Bounded work summary: {work_cycle.get('summary_artifact_path', '')}")
        output_paths = list(work_cycle.get("output_artifact_paths", []))
        if output_paths:
            details.append(f"Bounded work outputs: {len(output_paths)}")
        new_paths = list(work_cycle.get("newly_created_paths", []))
        if new_paths:
            details.append(f"New bounded work files: {len(new_paths)}")
        if str(work_cycle.get("next_recommended_cycle", "")).strip():
            details.append(f"Next recommended cycle: {work_cycle.get('next_recommended_cycle', '')}")
        if str(launch_plan_summary.get("image", "")).strip():
            details.append(f"Launch plan image: {launch_plan_summary.get('image', '')}")
        details.append(f"Directive file: {directive_file or '<resume>'}")
        details.append(f"Runtime event log: {session.get('runtime_event_log_path', '')}")
    if str(result.get("launch_plan_path", "")).strip():
        details.append(f"Launch plan artifact: {result.get('launch_plan_path', '')}")
    details.append(f"Process status: {status or '<missing>'} / exit={exit_code} / mode={result.get('startup_mode', '')}")
    return {
        "headline": headline,
        "details": details,
        "summary": "\n".join([headline, "", *[f"- {item}" for item in details]]).strip(),
    }


def render_trusted_sources_summary(snapshot: dict[str, Any]) -> str:
    summary = summarize_trusted_source_rows(snapshot)
    lines = [
        "Trusted Sources",
        "",
        f"Ready: {len(summary['ready_sources'])}",
        f"Attention required: {len(summary['attention_required_sources'])}",
        f"Disabled: {len(summary['disabled_sources'])}",
        "",
    ]
    for row in summary["rows"]:
        lines.append(
            f"- {row['source_id']}: {row['enabled_label']}, {row['source_kind']}, "
            f"{row['availability_class']}, secret={row['secret_source_label']}"
        )
        if row["availability_reason"]:
            lines.append(f"  reason: {row['availability_reason']}")
    return "\n".join(lines).strip()


def render_constraints_summary(snapshot: dict[str, Any]) -> str:
    summary = summarize_constraint_rows(snapshot)
    normalized_snapshot = _normalized_operator_status_snapshot(snapshot)
    runtime_constraints = dict(normalized_snapshot.get("runtime_constraints", {}))
    runtime_envelope = dict(normalized_snapshot.get("runtime_envelope", {}))
    envelope_spec = dict(runtime_envelope.get("spec", {}))
    constraint_payload = dict(runtime_constraints.get("payload", {}))
    governed_execution_policy = dict(constraint_payload.get("governed_execution", {}))
    workspace_policy = dict(constraint_payload.get("workspace_policy", {}))
    lines = [
        "Runtime Constraints and Envelope",
        "",
        f"Valid: {summary['valid']}",
        f"Hard enforced: {summary['hard_enforced_count']}",
        f"Watchdog enforced: {summary['watchdog_enforced_count']}",
        f"Unsupported: {summary['unsupported_count']}",
        "",
    ]
    if str(constraint_payload.get("execution_profile", "")).strip():
        lines.append(f"Execution profile: {constraint_payload.get('execution_profile', '')}")
    if str(governed_execution_policy.get("mode", "")).strip():
        lines.append(f"Governed execution mode: {governed_execution_policy.get('mode', '')}")
    if governed_execution_policy.get("max_cycles_per_invocation") not in {None, ""}:
        lines.append(
            "Max cycles per invocation: "
            f"{governed_execution_policy.get('max_cycles_per_invocation')}"
        )
    if str(workspace_policy.get("workspace_root", "")).strip():
        lines.append(
            "Active workspace: "
            f"{workspace_policy.get('workspace_id', '')} -> {workspace_policy.get('workspace_root', '')}"
        )
    if str(workspace_policy.get("generated_output_root", "")).strip():
        lines.append(f"Generated output root: {workspace_policy.get('generated_output_root', '')}")
    protected_hints = list(workspace_policy.get("protected_root_hints", []))
    if protected_hints:
        lines.append("Protected roots (summary):")
        lines.extend(f"- {item}" for item in protected_hints)
    if lines[-1] != "":
        lines.append("")
    if str(runtime_constraints.get("path", "")).strip():
        lines.extend(
            [
                f"Applied source: {runtime_constraints.get('path', '')}",
                "",
            ]
        )
    if str(runtime_envelope.get("path", "")).strip():
        lines.extend(
            [
                f"Envelope source: {runtime_envelope.get('path', '')}",
                f"Selected backend: {envelope_spec.get('backend_kind', '') or '<missing>'}",
                "",
            ]
        )
    if summary["errors"]:
        lines.append("Validation errors:")
        lines.extend(f"- {_format_operator_error_for_display(item)}" for item in summary["errors"])
        lines.append("")
    for row in summary["rows"]:
        lines.append(
            f"- {row['constraint_id']}: {row['requested_display']} "
            f"[{row['enforcement_label']}]"
        )
        if row["reason"]:
            lines.append(f"  reason: {row['reason']}")
    return "\n".join(lines).strip()


def render_dashboard_summary(snapshot: dict[str, Any]) -> str:
    normalized_snapshot = _normalized_operator_status_snapshot(snapshot)
    artifact_presence = dict(normalized_snapshot.get("artifact_presence", {}))
    posture = dict(normalized_snapshot.get("canonical_posture", {}))
    launch_context = dict(normalized_snapshot.get("launch_context", {}))
    last_launch_plan = dict(launch_context.get("last_launch_plan", {}))
    trusted_sources = summarize_trusted_source_rows(normalized_snapshot)
    constraint_summary = summarize_constraint_rows(normalized_snapshot)
    runtime_envelope = dict(normalized_snapshot.get("runtime_envelope", {}))
    envelope_spec = dict(runtime_envelope.get("spec", {}))
    effective_envelope = dict(runtime_envelope.get("effective", {}))
    runtime_constraints = dict(normalized_snapshot.get("runtime_constraints", {}))
    runtime_constraint_payload = dict(runtime_constraints.get("payload", {}))
    workspace_policy = dict(runtime_constraint_payload.get("workspace_policy", {}))
    governed_execution = dict(normalized_snapshot.get("governed_execution", {}))
    latest_attempt = summarize_latest_launch_attempt(launch_context)
    operator_paths = dict(normalized_snapshot.get("operator_paths", {}))

    lines = [
        "NOVALI Operator Dashboard",
        "",
        "Canonical posture:",
        f"- active branch: {posture.get('active_branch', '') or '<missing>'}",
        f"- branch state: {posture.get('current_branch_state', '') or '<missing>'}",
        f"- operating stance: {posture.get('current_operating_stance', '') or '<missing>'}",
        f"- held baseline: {posture.get('held_baseline_template', '') or '<missing>'}",
        f"- routing status: {posture.get('routing_status', '') or '<missing>'}",
        "",
        "Launch context:",
        f"- canonical launcher: {launch_context.get('canonical_human_launcher', '')}",
        f"- current launch mode: {launch_context.get('current_launch_mode', '') or '<none recorded>'}",
        f"- frozen session valid: {launch_context.get('effective_operator_session_valid', False)}",
        f"- latest attempt: {latest_attempt.get('headline', '')}",
    ]
    session_errors = list(launch_context.get("effective_operator_session_errors", []))
    if session_errors:
        lines.append("- frozen session issues:")
        lines.extend(f"  - {_format_operator_error_for_display(item)}" for item in session_errors)
    latest_attempt_details = list(latest_attempt.get("details", []))
    if latest_attempt_details:
        lines.append("- latest attempt details:")
        lines.extend(f"  - {item}" for item in latest_attempt_details)
    if last_launch_plan:
        last_launch_plan_summary = dict(last_launch_plan.get("summary", {}))
        lines.append(f"- latest launch-plan backend: {last_launch_plan.get('backend_kind', '') or '<none>'}")
        if str(last_launch_plan_summary.get("image", "")).strip():
            lines.append(f"- latest launch-plan image: {last_launch_plan_summary.get('image', '')}")
        if str(operator_paths.get("operator_runtime_launch_plan_path", "")).strip():
            lines.append(
                f"- latest launch-plan artifact: {operator_paths.get('operator_runtime_launch_plan_path', '')}"
            )
    lines.extend(
        [
            "",
            "Canonical artifact presence:",
            f"- directive_state: {artifact_presence.get('directive_state_present', False)}",
            f"- bucket_state: {artifact_presence.get('bucket_state_present', False)}",
            f"- branch_registry: {artifact_presence.get('branch_registry_present', False)}",
            f"- governance_memory_authority: {artifact_presence.get('governance_memory_authority_present', False)}",
            f"- self_structure_state: {artifact_presence.get('self_structure_state_present', False)}",
            f"- canonical state available: {artifact_presence.get('canonical_state_available', False)}",
            "",
            "Trusted source summary:",
            f"- ready: {len(trusted_sources['ready_sources'])}",
            f"- attention required: {len(trusted_sources['attention_required_sources'])}",
            f"- disabled: {len(trusted_sources['disabled_sources'])}",
        ]
    )
    for row in trusted_sources["rows"]:
        lines.append(
            f"  - {row['source_id']}: {row['availability_class']} / {row['secret_source_label']}"
        )
    lines.extend(
        [
            "",
            "Runtime enforcement summary:",
            f"- hard enforced: {constraint_summary['hard_enforced_count']}",
            f"- watchdog enforced: {constraint_summary['watchdog_enforced_count']}",
            f"- unsupported: {constraint_summary['unsupported_count']}",
            f"- execution profile: {runtime_constraint_payload.get('execution_profile', '') or '<missing>'}",
            f"- selected backend: {envelope_spec.get('backend_kind', '') or '<missing>'}",
            f"- envelope valid: {runtime_envelope.get('valid', False)}",
        ]
    )
    if str(workspace_policy.get("workspace_root", "")).strip():
        lines.append(
            "- active workspace: "
            f"{workspace_policy.get('workspace_id', '')} -> {workspace_policy.get('workspace_root', '')}"
        )
    if str(governed_execution.get("status", "")).strip():
        lines.append(f"- bounded work status: {governed_execution.get('status', '')}")
    if str(governed_execution.get("reason", "")).strip():
        lines.append(f"- bounded work reason: {governed_execution.get('reason', '')}")
    governed_controller = dict(governed_execution.get("controller", {}))
    if str(governed_controller.get("controller_mode", "")).strip():
        lines.append(f"- controller mode: {governed_controller.get('controller_mode', '')}")
    if governed_controller.get("cycles_completed") not in {None, ""}:
        lines.append(f"- cycles completed: {governed_controller.get('cycles_completed')}")
    if str(governed_controller.get("stop_reason", "")).strip():
        lines.append(f"- stop reason: {governed_controller.get('stop_reason', '')}")
    governed_work_cycle = dict(governed_execution.get("work_cycle", {}))
    if str(governed_work_cycle.get("cycle_kind", "")).strip():
        lines.append(f"- bounded work cycle: {governed_work_cycle.get('cycle_kind', '')}")
    if str(governed_work_cycle.get("invocation_model", "")).strip():
        if str(governed_controller.get("controller_mode", "")).strip() == "multi_cycle":
            lines.append(
                "- execution model: multi-cycle governed_execution may continue until completion, no-work, failure, or cap"
            )
        else:
            lines.append(
                "- execution model: one bounded cycle runs per governed_execution launch"
            )
    if str(governed_work_cycle.get("implementation_bundle_kind", "")).strip():
        lines.append(
            f"- implementation bundle: {governed_work_cycle.get('implementation_bundle_kind', '')}"
        )
    governed_outputs = list(governed_work_cycle.get("output_artifact_paths", []))
    if governed_outputs:
        lines.append(f"- bounded work outputs: {len(governed_outputs)}")
        lines.extend(f"  - {item}" for item in governed_outputs[:6])
    new_paths = list(governed_work_cycle.get("newly_created_paths", []))
    if new_paths:
        lines.append(f"- new bounded work files: {len(new_paths)}")
        lines.extend(f"  + {item}" for item in new_paths[:6])
    if str(governed_work_cycle.get("next_recommended_cycle", "")).strip():
        lines.append(
            f"- next recommended cycle: {governed_work_cycle.get('next_recommended_cycle', '')}"
        )
    selected_backend = dict(dict(effective_envelope.get("backend_probe", {})).get("backends", {})).get(
        str(envelope_spec.get("backend_kind", "")),
        {},
    )
    if selected_backend:
        lines.append(
            "- backend availability: "
            f"{selected_backend.get('availability_class', '')} / "
            f"{selected_backend.get('reason', '')}"
        )
    unsupported_rows = [
        row for row in list(constraint_summary["rows"])
        if row["enforcement_class"] == "unsupported_on_this_platform"
    ]
    if unsupported_rows:
        lines.append(
            "- unsupported controls: "
            + ", ".join(row["constraint_id"] for row in unsupported_rows)
        )
    return "\n".join(lines).strip()
