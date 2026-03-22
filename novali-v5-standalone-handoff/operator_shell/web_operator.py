from __future__ import annotations

import argparse
import html
import json
import os
import re
import threading
import urllib.parse
from datetime import datetime, timezone
from email.parser import BytesParser
from email.policy import default as email_policy
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .acceptance import (
    build_manual_acceptance_evidence,
    render_manual_acceptance_markdown,
    write_manual_acceptance_report,
)
from .directive_scaffold import build_standalone_directive_payload
from .envelope import (
    BACKEND_LOCAL_DOCKER,
    BACKEND_LOCAL_GUARDED,
    build_default_operator_runtime_envelope_spec,
    operator_runtime_envelope_spec_path,
    validate_operator_runtime_envelope_spec,
)
from .gui_presenter import (
    build_launch_readiness,
    build_launch_refusal_summary,
    build_launch_result_summary,
    inspect_directive_wrapper,
    render_constraints_summary,
    render_dashboard_summary,
    render_launch_readiness,
    render_trusted_sources_summary,
)
from .launcher import (
    OperatorLaunchRefusedError,
    build_operator_dashboard_snapshot,
    launch_novali_main,
)
from .policy import (
    EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION,
    EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING,
    build_runtime_constraints_for_profile,
    default_operator_root,
    initialize_operator_policy_files,
    load_runtime_envelope_spec_or_default,
    load_runtime_constraints_or_default,
    load_trusted_source_bindings_or_default,
    operator_runtime_constraints_path,
    read_operator_status_snapshot,
    save_runtime_envelope_spec,
    save_runtime_constraints,
    validate_runtime_constraints,
)


WEB_PROFILE_SCHEMA_NAME = "OperatorWebProfile"
WEB_PROFILE_SCHEMA_VERSION = "operator_web_profile_v1"
DEFAULT_WEB_HOST = "127.0.0.1"
DEFAULT_CONTAINER_HOST = "0.0.0.0"
DEFAULT_WEB_PORT = 8787


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dump(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def _normalize_path(value: Any) -> str:
    if value in {None, ""}:
        return ""
    try:
        return str(Path(str(value)).resolve())
    except OSError:
        return str(value)


def _slug(value: str, *, fallback: str) -> str:
    token = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()).strip("._-")
    return token or fallback


def default_web_bind_host(*, container_mode: bool = False) -> str:
    return DEFAULT_CONTAINER_HOST if container_mode else DEFAULT_WEB_HOST


def default_web_state_root(package_root: str | Path) -> Path:
    package_root_path = Path(package_root)
    runtime_state = package_root_path / "runtime_data" / "state"
    return runtime_state if runtime_state.parent.exists() else package_root_path / "data"


def directive_input_root(package_root: str | Path, operator_root: str | Path) -> Path:
    package_root_path = Path(package_root)
    operator_root_path = Path(operator_root)
    candidate = package_root_path / "directive_inputs"
    return candidate if candidate.exists() else operator_root_path / "directive_inputs"


def acceptance_evidence_root(package_root: str | Path, state_root: str | Path) -> Path:
    package_root_path = Path(package_root)
    state_root_path = Path(state_root)
    candidate = package_root_path / "runtime_data" / "acceptance_evidence"
    if candidate.parent.exists():
        return candidate
    return state_root_path / "acceptance_evidence"


def sample_directive_paths(package_root: str | Path) -> list[dict[str, str]]:
    package_root_path = Path(package_root)
    candidates = [
        package_root_path / "samples" / "directives",
        package_root_path / "manual_acceptance_samples",
    ]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for directory in candidates:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            normalized = _normalize_path(path)
            if normalized in seen:
                continue
            seen.add(normalized)
            label = path.name
            if "incomplete" in path.name:
                label = f"{path.name} (refusal sample)"
            elif "valid" in path.name:
                label = f"{path.name} (valid sample)"
            rows.append({"label": label, "path": normalized})
    return rows


def operator_web_profile_path(root: str | Path) -> Path:
    return Path(root) / "operator_web_profile.local.json"


def build_default_operator_web_profile(
    *,
    package_root: str | Path,
    state_root: str | Path | None = None,
) -> dict[str, Any]:
    package_root_path = Path(package_root)
    state_root_path = Path(state_root) if state_root is not None else default_web_state_root(package_root_path)
    default_directive = ""
    if not (package_root_path / "directive_inputs").exists():
        bootstrap_directive = package_root_path / "directives" / "novali_v5_bootstrap_directive_v1.json"
        default_directive = _normalize_path(bootstrap_directive) if bootstrap_directive.exists() else ""
    return {
        "schema_name": WEB_PROFILE_SCHEMA_NAME,
        "schema_version": WEB_PROFILE_SCHEMA_VERSION,
        "updated_at": "",
        "recent_directive_file": default_directive,
        "recent_state_root": _normalize_path(state_root_path),
        "recent_resume_mode": "new_bootstrap",
        "recent_launch_action": "bootstrap_only",
    }


def sanitize_operator_web_profile(
    payload: dict[str, Any] | None,
    *,
    package_root: str | Path,
    state_root: str | Path | None = None,
) -> dict[str, Any]:
    defaults = build_default_operator_web_profile(package_root=package_root, state_root=state_root)
    source = dict(payload or {})
    resume_mode = str(source.get("recent_resume_mode", defaults["recent_resume_mode"])).strip()
    launch_action = str(source.get("recent_launch_action", defaults["recent_launch_action"])).strip()
    return {
        "schema_name": WEB_PROFILE_SCHEMA_NAME,
        "schema_version": WEB_PROFILE_SCHEMA_VERSION,
        "updated_at": str(source.get("updated_at", "")),
        "recent_directive_file": str(source.get("recent_directive_file", defaults["recent_directive_file"])),
        "recent_state_root": str(source.get("recent_state_root", defaults["recent_state_root"])),
        "recent_resume_mode": resume_mode if resume_mode in {"new_bootstrap", "resume_existing"} else defaults["recent_resume_mode"],
        "recent_launch_action": (
            launch_action
            if launch_action in {"bootstrap_only", "governed_execution", "proposal_analytics", "proposal_recommend"}
            else defaults["recent_launch_action"]
        ),
    }


def load_operator_web_profile(
    *,
    root: str | Path,
    package_root: str | Path,
    state_root: str | Path | None = None,
) -> dict[str, Any]:
    path = operator_web_profile_path(root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        payload = {}
    return sanitize_operator_web_profile(payload, package_root=package_root, state_root=state_root)


def save_operator_web_profile(
    payload: dict[str, Any],
    *,
    root: str | Path,
    package_root: str | Path,
    state_root: str | Path | None = None,
) -> dict[str, Any]:
    cleaned = sanitize_operator_web_profile(payload, package_root=package_root, state_root=state_root)
    cleaned["updated_at"] = _now()
    path = operator_web_profile_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_dump(cleaned), encoding="utf-8")
    return cleaned


class OperatorWebService:
    def __init__(
        self,
        *,
        package_root: str | Path | None = None,
        operator_root: str | Path | None = None,
        state_root: str | Path | None = None,
    ) -> None:
        self.package_root = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
        self.operator_root = Path(operator_root) if operator_root is not None else default_operator_root()
        self.state_root = Path(state_root) if state_root is not None else default_web_state_root(self.package_root)
        self.directive_root = directive_input_root(self.package_root, self.operator_root)
        self.evidence_root = acceptance_evidence_root(self.package_root, self.state_root)
        self._lock = threading.Lock()
        self.last_action_summary: dict[str, Any] = {
            "headline": "No launch attempt has been made from the web operator yet.",
            "details": [],
            "summary": "No launch attempt has been made from the web operator yet.",
        }
        self.last_export_path = ""
        self.last_export_json_path = ""
        initialize_operator_policy_files(root=self.operator_root, package_root=self.package_root)
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.directive_root.mkdir(parents=True, exist_ok=True)
        self.evidence_root.mkdir(parents=True, exist_ok=True)
        self.profile = load_operator_web_profile(
            root=self.operator_root,
            package_root=self.package_root,
            state_root=self.state_root,
        )

    @property
    def directive_file(self) -> str:
        return str(self.profile.get("recent_directive_file", "")).strip()

    @property
    def resume_mode(self) -> str:
        return str(self.profile.get("recent_resume_mode", "new_bootstrap")).strip()

    @property
    def launch_action(self) -> str:
        return str(self.profile.get("recent_launch_action", "bootstrap_only")).strip()

    def _persist_profile(self) -> None:
        self.profile = save_operator_web_profile(
            {
                "recent_directive_file": self.directive_file,
                "recent_state_root": _normalize_path(self.state_root),
                "recent_resume_mode": self.resume_mode,
                "recent_launch_action": self.launch_action,
            },
            root=self.operator_root,
            package_root=self.package_root,
            state_root=self.state_root,
        )

    def update_profile(
        self,
        *,
        directive_file: str | None = None,
        state_root: str | None = None,
        resume_mode: str | None = None,
        launch_action: str | None = None,
    ) -> None:
        if directive_file is not None:
            self.profile["recent_directive_file"] = str(directive_file).strip()
        if state_root is not None:
            self.state_root = Path(str(state_root).strip() or self.state_root)
            self.state_root.mkdir(parents=True, exist_ok=True)
            self.evidence_root = acceptance_evidence_root(self.package_root, self.state_root)
            self.evidence_root.mkdir(parents=True, exist_ok=True)
            self.profile["recent_state_root"] = _normalize_path(self.state_root)
        if resume_mode is not None:
            self.profile["recent_resume_mode"] = str(resume_mode).strip()
        if launch_action is not None:
            self.profile["recent_launch_action"] = str(launch_action).strip()
        self._persist_profile()

    def current_operator_snapshot(self) -> dict[str, Any]:
        return read_operator_status_snapshot(root=self.operator_root, package_root=self.package_root)

    def is_packaged_handoff_context(self) -> bool:
        return bool((self.package_root / "handoff_layout_manifest.json").exists())

    def current_dashboard_snapshot(self) -> dict[str, Any]:
        return build_operator_dashboard_snapshot(
            package_root=self.package_root,
            operator_root=self.operator_root,
            state_root=self.state_root,
        )

    def current_directive_summary(self) -> dict[str, Any]:
        return inspect_directive_wrapper(self.directive_file, resume_mode=self.resume_mode)

    def current_launch_readiness(self) -> dict[str, Any]:
        return build_launch_readiness(
            resume_mode=self.resume_mode,
            launch_action=self.launch_action,
            state_root=_normalize_path(self.state_root),
            directive_summary=self.current_directive_summary(),
            operator_status_snapshot=self.current_operator_snapshot(),
            constraints_dirty=False,
        )

    def sample_directives(self) -> list[dict[str, str]]:
        return sample_directive_paths(self.package_root)

    def select_sample_directive(self, sample_path: str) -> None:
        self.update_profile(directive_file=sample_path, resume_mode="new_bootstrap")

    def save_uploaded_directive(self, *, filename: str, payload: bytes) -> Path:
        safe_name = _slug(Path(filename or "uploaded_directive.json").name, fallback="uploaded_directive")
        if not safe_name.lower().endswith(".json"):
            safe_name = f"{safe_name}.json"
        target = self.directive_root / safe_name
        target.write_bytes(payload)
        self.update_profile(directive_file=_normalize_path(target), resume_mode="new_bootstrap")
        return target

    def _runtime_payload_from_form(self, form_data: dict[str, str]) -> dict[str, Any]:
        execution_profile = (
            str(
                form_data.get(
                    "execution_profile",
                    EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION,
                )
            ).strip()
            or EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION
        )
        workspace_id = str(form_data.get("workspace_id", "")).strip()
        payload = build_runtime_constraints_for_profile(
            self.package_root,
            operator_root=self.operator_root,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
        )
        payload["constraints"].update(
            {
                "max_memory_mb": int(form_data.get("max_memory_mb", "").strip()),
                "max_python_threads": int(form_data.get("max_python_threads", "").strip()),
                "max_child_processes": int(form_data.get("max_child_processes", "").strip()),
                "subprocess_mode": str(form_data.get("subprocess_mode", "disabled")).strip() or "disabled",
                "session_time_limit_seconds": int(form_data.get("session_time_limit_seconds", "").strip()),
            }
        )
        return payload

    def _envelope_payload_from_form(self, form_data: dict[str, str]) -> dict[str, Any]:
        payload = build_default_operator_runtime_envelope_spec(self.package_root)
        payload["backend_kind"] = str(form_data.get("backend_kind", BACKEND_LOCAL_GUARDED)).strip() or BACKEND_LOCAL_GUARDED
        intents = dict(payload.get("constraint_intents", {}))
        cpu_limit_cpus = str(form_data.get("cpu_limit_cpus", "")).strip()
        intents["cpu_limit_cpus"] = None if not cpu_limit_cpus else float(cpu_limit_cpus)
        intents["network_policy_intent"] = (
            str(form_data.get("network_policy_intent", "deny_all")).strip() or "deny_all"
        )
        payload["constraint_intents"] = intents
        docker_settings = dict(payload.get("backend_settings", {}).get(BACKEND_LOCAL_DOCKER, {}))
        docker_settings["image"] = (
            str(form_data.get("docker_image", docker_settings.get("image", "python:3.12-slim"))).strip()
            or str(docker_settings.get("image", "python:3.12-slim"))
        )
        payload["backend_settings"][BACKEND_LOCAL_DOCKER] = docker_settings
        return payload

    def _runtime_form_defaults_from_payloads(
        self,
        *,
        runtime_payload: dict[str, Any],
        runtime_envelope: dict[str, Any],
    ) -> dict[str, str]:
        constraints = dict(runtime_payload.get("constraints", {}))
        execution_profile = str(
            runtime_payload.get(
                "execution_profile",
                EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION,
            )
        )
        workspace_policy = dict(runtime_payload.get("workspace_policy", {}))
        suggested_workspace_id = str(workspace_policy.get("workspace_id", "")).strip()
        if not suggested_workspace_id and self.directive_file:
            suggested_workspace_id = _slug(Path(self.directive_file).stem, fallback="workspace_default")
        intents = dict(runtime_envelope.get("constraint_intents", {}))
        docker_settings = dict(dict(runtime_envelope.get("backend_settings", {})).get(BACKEND_LOCAL_DOCKER, {}))
        cpu_value = intents.get("cpu_limit_cpus")
        return {
            "execution_profile": execution_profile,
            "workspace_id": suggested_workspace_id,
            "workspace_root": str(workspace_policy.get("workspace_root", "")),
            "generated_output_root": str(workspace_policy.get("generated_output_root", "")),
            "protected_root_hints": ";".join(list(workspace_policy.get("protected_root_hints", []))),
            "max_memory_mb": str(constraints.get("max_memory_mb", "")),
            "max_python_threads": str(constraints.get("max_python_threads", "")),
            "max_child_processes": str(constraints.get("max_child_processes", "")),
            "subprocess_mode": str(constraints.get("subprocess_mode", "disabled")),
            "working_directory": str(constraints.get("working_directory", "")),
            "allowed_write_roots": ";".join(list(constraints.get("allowed_write_roots", []))),
            "session_time_limit_seconds": str(constraints.get("session_time_limit_seconds", "")),
            "backend_kind": str(runtime_envelope.get("backend_kind", BACKEND_LOCAL_GUARDED)),
            "cpu_limit_cpus": "" if cpu_value in {None, ""} else str(cpu_value),
            "docker_image": str(docker_settings.get("image", "python:3.12-slim")),
            "network_policy_intent": str(intents.get("network_policy_intent", "deny_all")),
        }

    def runtime_form_defaults(self) -> dict[str, str]:
        runtime_payload = load_runtime_constraints_or_default(root=self.operator_root, package_root=self.package_root)
        runtime_envelope = load_runtime_envelope_spec_or_default(root=self.operator_root, package_root=self.package_root)
        return self._runtime_form_defaults_from_payloads(
            runtime_payload=runtime_payload,
            runtime_envelope=runtime_envelope,
        )

    def _render_runtime_policy_preview(self, runtime_defaults: dict[str, str]) -> str:
        lines = [
            "Attempted Runtime Policy",
            "",
            f"- execution profile: {runtime_defaults.get('execution_profile', '') or '<missing>'}",
            f"- workspace id: {runtime_defaults.get('workspace_id', '') or '<none>'}",
            f"- active workspace root: {runtime_defaults.get('workspace_root', '') or '<not required>'}",
            f"- generated output root: {runtime_defaults.get('generated_output_root', '') or '<missing>'}",
            f"- backend: {runtime_defaults.get('backend_kind', '') or '<missing>'}",
            f"- docker image: {runtime_defaults.get('docker_image', '') or '<n/a>'}",
            f"- session time limit: {runtime_defaults.get('session_time_limit_seconds', '') or '<missing>'}",
            f"- allowed write roots: {runtime_defaults.get('allowed_write_roots', '') or '<missing>'}",
        ]
        return "\n".join(lines)

    def save_runtime_policy(self, form_data: dict[str, str]) -> dict[str, Any]:
        try:
            runtime_payload = self._runtime_payload_from_form(form_data)
            envelope_payload = self._envelope_payload_from_form(form_data)
        except Exception as exc:
            return {
                "ok": False,
                "headline": "Runtime policy parsing failed.",
                "details": [str(exc)],
            }

        operator_snapshot = self.current_operator_snapshot()
        runtime_errors, normalized_runtime, _ = validate_runtime_constraints(
            runtime_payload,
            package_root=self.package_root,
            operator_root=self.operator_root,
        )
        envelope_errors, normalized_envelope, _ = validate_operator_runtime_envelope_spec(
            envelope_payload,
            runtime_constraints=normalized_runtime,
            trusted_source_bindings=load_trusted_source_bindings_or_default(
                root=self.operator_root,
                package_root=self.package_root,
            ),
            backend_probe=dict(operator_snapshot.get("runtime_backend_probe", {})),
            enforce_backend_availability=True,
        )
        errors = list(runtime_errors) + list(envelope_errors)
        if errors:
            attempted_defaults = self._runtime_form_defaults_from_payloads(
                runtime_payload=normalized_runtime or runtime_payload,
                runtime_envelope=normalized_envelope or envelope_payload,
            )
            details = list(errors)
            if (
                self.is_packaged_handoff_context()
                and str(form_data.get("backend_kind", "")).strip() == BACKEND_LOCAL_DOCKER
                and any(
                    "selected runtime backend is unavailable: local_docker" in str(item)
                    for item in errors
                )
            ):
                details.append(
                    "Standalone package hint: keep backend local_guarded in the packaged browser UI. "
                    "The current container already provides the Docker execution envelope, so nested "
                    "local_docker launches are not available in this slice."
                )
            details.append("Authoritative runtime policy remains unchanged because the requested values were not saved.")
            return {
                "ok": False,
                "headline": "Runtime policy was not saved.",
                "details": details,
                "runtime_form_override": attempted_defaults,
                "attempted_runtime_summary": self._render_runtime_policy_preview(attempted_defaults),
            }

        save_runtime_constraints(normalized_runtime, root=self.operator_root)
        save_runtime_envelope_spec(normalized_envelope, root=self.operator_root)
        workspace_policy = dict(normalized_runtime.get("workspace_policy", {}))
        return {
            "ok": True,
            "headline": "Runtime policy saved and applied for future launches.",
            "details": [
                f"Execution profile: {normalized_runtime.get('execution_profile', '')}",
                (
                    "Active workspace: "
                    f"{workspace_policy.get('workspace_id', '')} -> {workspace_policy.get('workspace_root', '')}"
                    if str(workspace_policy.get("workspace_root", "")).strip()
                    else "Active workspace: <not required for this profile>"
                ),
                f"Runtime constraints source: {operator_runtime_constraints_path(self.operator_root)}",
                f"Runtime envelope source: {operator_runtime_envelope_spec_path(self.operator_root)}",
            ],
        }

    def export_acceptance_evidence(self) -> dict[str, str]:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        markdown_path = self.evidence_root / f"web_acceptance_snapshot_{timestamp}.md"
        json_path = self.evidence_root / f"web_acceptance_snapshot_{timestamp}.json"
        evidence = build_manual_acceptance_evidence(
            package_root=self.package_root,
            operator_root=self.operator_root,
            state_root=self.state_root,
            directive_file=self.directive_file or None,
        )
        write_manual_acceptance_report(output_path=markdown_path, evidence=evidence)
        json_path.write_text(_json_dump(evidence), encoding="utf-8")
        self.last_export_path = str(markdown_path)
        self.last_export_json_path = str(json_path)
        return {
            "markdown_path": str(markdown_path),
            "json_path": str(json_path),
            "markdown": render_manual_acceptance_markdown(evidence),
        }

    def launch(self, *, resume_mode: str, launch_action: str, state_root: str) -> dict[str, Any]:
        self.update_profile(
            state_root=state_root,
            resume_mode=resume_mode,
            launch_action=launch_action,
        )
        directive_file = self.directive_file if self.resume_mode == "new_bootstrap" else None
        try:
            result = launch_novali_main(
                package_root=self.package_root,
                operator_root=self.operator_root,
                directive_file=directive_file,
                state_root=self.state_root,
                launch_action=self.launch_action,
            )
            summary = build_launch_result_summary(result)
            self.last_action_summary = summary
            return {
                "ok": int(result.get("exit_code", 0) or 0) == 0,
                "headline": summary.get("headline", ""),
                "details": list(summary.get("details", [])),
                "summary": summary.get("summary", ""),
            }
        except OperatorLaunchRefusedError as exc:
            summary = build_launch_refusal_summary(str(exc), list(exc.errors))
            self.last_action_summary = summary
            return {
                "ok": False,
                "headline": summary.get("headline", ""),
                "details": list(summary.get("details", [])),
                "summary": summary.get("summary", ""),
            }

    def scaffold_download_payload(self) -> tuple[str, bytes]:
        payload = build_standalone_directive_payload(
            package_root=self.package_root,
            directive_id="directive_browser_template_v1",
            directive_text="Initialize NOVALI from the localhost browser operator surface.",
            clarified_intent_summary=(
                "Bootstrap novali-v5 through the canonical operator flow and preserve artifact-backed "
                "governance authority before execution."
            ),
        )
        text = _json_dump(payload)
        return ("novali_browser_directive_template.json", text.encode("utf-8"))

    def render_home_page(self, *, notice: dict[str, Any] | None = None) -> str:
        dashboard = self.current_dashboard_snapshot()
        operator_snapshot = self.current_operator_snapshot()
        readiness = self.current_launch_readiness()
        directive_summary = self.current_directive_summary()
        trusted_summary = render_trusted_sources_summary(dashboard)
        constraints_summary = render_constraints_summary(operator_snapshot)
        dashboard_summary = render_dashboard_summary(dashboard)
        sample_rows = self.sample_directives()
        runtime_defaults = dict(notice.get("runtime_form_override", {})) if notice else {}
        if not runtime_defaults:
            runtime_defaults = self.runtime_form_defaults()
        attempted_runtime_summary = str(notice.get("attempted_runtime_summary", "")).strip() if notice else ""
        handoff_manifest_path = _normalize_path(self.package_root / "handoff_layout_manifest.json")
        image_manifest_path = _normalize_path(self.package_root / "image" / "image_archive_manifest.json")
        packaged_handoff_context = self.is_packaged_handoff_context()
        packaged_backend_guidance = (
            "Open Runtime Constraints And Envelope, keep backend <code>local_guarded</code> for the packaged "
            "single-container handoff, choose the execution profile you intend to use, then save runtime policy."
            if packaged_handoff_context
            else "Open <a href=\"#runtime-section\">Runtime Constraints And Envelope</a>, keep backend "
            "<code>local_docker</code> for the packaged Docker path, choose the execution profile you intend to use, "
            "then save runtime policy."
        )
        runtime_section_guidance = (
            "Launch uses the saved operator runtime policy only. In the packaged single-container handoff, "
            "keep backend <code>local_guarded</code> because the current container already provides the Docker "
            "execution envelope. Use <code>local_docker</code> only from an operator environment with direct Docker "
            "access. Unsupported controls remain unsupported and are shown for honesty only. The coding profile "
            "enables writes only inside <code>novali-active_workspace</code> plus approved generated/log roots; it "
            "does not grant broad repo mutation."
            if packaged_handoff_context
            else "Launch uses the saved operator runtime policy only. For the packaged Docker path, keep backend "
            "<code>local_docker</code>, keep the packaged image tag unless you have a deliberate replacement, and "
            "save this form before launching if you change any values. Unsupported controls remain unsupported and "
            "are shown for honesty only. The coding profile enables writes only inside "
            "<code>novali-active_workspace</code> plus approved generated/log roots; it does not grant broad repo "
            "mutation."
        )
        notice_block = ""
        if notice:
            headline = html.escape(str(notice.get("headline", "")))
            details = list(notice.get("details", []))
            notice_block = (
                "<section class='notice card'>"
                f"<h2>{headline}</h2>"
                + ("<ul>" + "".join(f"<li>{html.escape(str(item))}</li>" for item in details) + "</ul>" if details else "")
                + "</section>"
            )
        sample_buttons = "".join(
            "<form method='post' action='/directive/sample' class='inline-form'>"
            f"<input type='hidden' name='sample_path' value='{html.escape(row['path'])}' />"
            f"<button type='submit'>{html.escape(row['label'])}</button>"
            "</form>"
            for row in sample_rows
        ) or "<p>No packaged sample directives were found.</p>"
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>NOVALI Localhost Web Operator</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 24px; background: #f6f4ef; color: #182022; }}
    h1, h2 {{ margin-bottom: 0.4rem; }}
    .muted {{ color: #4a5b5f; }}
    .grid {{ display: grid; grid-template-columns: 1fr; gap: 16px; }}
    .card {{ background: #ffffff; border: 1px solid #d6d1c5; border-radius: 10px; padding: 16px; }}
    .inline-form {{ display: inline-block; margin: 4px 8px 4px 0; }}
    label {{ display: block; font-weight: 600; margin-top: 8px; }}
    input[type=text], input[type=number], select {{ width: 100%; padding: 8px; box-sizing: border-box; }}
    pre {{ width: 100%; box-sizing: border-box; white-space: pre-wrap; background: #f2efe8; padding: 12px; border-radius: 8px; overflow-x: auto; }}
    button {{ padding: 8px 12px; margin-top: 10px; }}
    code {{ background: #f2efe8; padding: 2px 4px; border-radius: 4px; }}
    .path {{ word-break: break-all; }}
  </style>
</head>
<body>
  <h1>NOVALI Localhost Web Operator</h1>
  <p class="muted">Local single-operator surface only. Default host launch binds to <code>127.0.0.1:{DEFAULT_WEB_PORT}</code>. Container wrappers may bind to <code>0.0.0.0</code> inside the container, but host exposure should stay mapped to localhost.</p>
  <p class="muted">Canonical authority remains unchanged: <code>operator shell -&gt; launcher -&gt; frozen session -&gt; bootstrap -&gt; governed execution</code>. This browser UI only drives that same path.</p>
  {notice_block}
  <div class="grid">
    <section class="card">
      <h2>First Run</h2>
      <p>If you are using the packaged standalone handoff, start here. Initialize first with <code>new_bootstrap</code> plus launch action <code>bootstrap_only</code>. After canonical state exists, bounded coding runs should use <code>resume_existing</code> plus <code>governed_execution</code> with the <code>bounded_active_workspace_coding</code> profile.</p>
      <ol>
        <li>Open the <a href="#directive-section">Directive</a> section and choose the valid sample or download a scaffold into <code>directive_inputs/</code>.</li>
        <li>Use the incomplete sample only when you want a clarification/refusal test.</li>
        <li>{packaged_backend_guidance}</li>
        <li>Open <a href="#launch-section">Launch / Resume</a>, use <code>bootstrap_only</code> for first-time initialization, then use <code>governed_execution</code> only when you want bounded post-bootstrap work.</li>
        <li>After launch, inspect <code>runtime_data/state/</code>, <code>runtime_data/logs/</code>, and <code>runtime_data/acceptance_evidence/</code>.</li>
      </ol>
      <p><strong>Happy-path sample:</strong> <code>samples/directives/standalone_valid_directive.example.json</code><br/>
      <strong>Refusal sample:</strong> <code>samples/directives/standalone_incomplete_directive.example.json</code></p>
      <p><strong>Package manifest:</strong> <span class="path">{html.escape(handoff_manifest_path)}</span><br/>
      <strong>Image manifest:</strong> <span class="path">{html.escape(image_manifest_path)}</span></p>
    </section>
    <section class="card" id="status-section">
      <h2>Status</h2>
      <p><strong>Last action:</strong> {html.escape(str(self.last_action_summary.get('headline', 'No action yet.')))}</p>
      <pre>{html.escape(str(self.last_action_summary.get('summary', 'No action yet.')))}</pre>
      <p><strong>Package root:</strong> <span class="path">{html.escape(_normalize_path(self.package_root))}</span></p>
      <p><strong>State root:</strong> <span class="path">{html.escape(_normalize_path(self.state_root))}</span></p>
      <p><strong>Operator root:</strong> <span class="path">{html.escape(_normalize_path(self.operator_root))}</span></p>
      <p><strong>Acceptance evidence root:</strong> <span class="path">{html.escape(_normalize_path(self.evidence_root))}</span></p>
      <p><strong>Directive input root:</strong> <span class="path">{html.escape(_normalize_path(self.directive_root))}</span></p>
      <pre>{html.escape(dashboard_summary)}</pre>
    </section>
    <section class="card" id="directive-section">
      <h2>Directive</h2>
      <p>Use a formal directive wrapper only. For a first packaged validation run, start with the valid sample below or download a scaffold. Guide: <code>DIRECTIVE_AUTHORING_GUIDE.md</code>. Template download: <a href="/directive/download-scaffold">novali_browser_directive_template.json</a></p>
      <form method="post" action="/directive/select">
        <label for="directive_path">Selected directive file</label>
        <input id="directive_path" type="text" name="directive_path" value="{html.escape(self.directive_file)}" />
        <button type="submit">Use Directive Path</button>
      </form>
      <form method="post" action="/directive/upload" enctype="multipart/form-data">
        <label for="directive_upload">Upload directive JSON</label>
        <input id="directive_upload" type="file" name="directive_upload" accept=".json,application/json" />
        <button type="submit">Upload Directive</button>
      </form>
      <div><label>Packaged samples</label>{sample_buttons}</div>
      <pre>{html.escape(str(directive_summary.get('summary', 'No directive selected.')))}</pre>
    </section>
    <section class="card" id="trusted-sources-section">
      <h2>Trusted Sources</h2>
      <p>Bindings and secrets remain outside directive authority. For packaged standalone validation, prefer placeholder or disabled network bindings unless you intentionally provide local credentials. This slice shows the persisted summary and safe guidance only; it does not add a second secret-authoring path.</p>
      <p>Bindings file: <code>{html.escape(str(operator_snapshot.get('trusted_source_bindings_path', '')))}</code><br/>Local secrets file: <code>{html.escape(str(operator_snapshot.get('trusted_source_secrets_path', '')))}</code><br/>Environment template: <code>standalone_docker/standalone.env.template</code></p>
      <pre>{html.escape(trusted_summary)}</pre>
    </section>
    <section class="card" id="runtime-section">
      <h2>Runtime Constraints And Envelope</h2>
      <p>{runtime_section_guidance}</p>
      <form method="post" action="/runtime/save">
        <label>Execution profile</label>
        <select name="execution_profile">
          <option value="{EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION}"{" selected" if runtime_defaults["execution_profile"] == EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION else ""}>{EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION}</option>
          <option value="{EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING}"{" selected" if runtime_defaults["execution_profile"] == EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING else ""}>{EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING}</option>
        </select>
        <label>Workspace id</label><input type="text" name="workspace_id" value="{html.escape(runtime_defaults['workspace_id'])}" />
        <label>Active workspace root</label><input type="text" name="workspace_root" value="{html.escape(runtime_defaults['workspace_root'])}" readonly />
        <label>Generated output root</label><input type="text" name="generated_output_root" value="{html.escape(runtime_defaults['generated_output_root'])}" readonly />
        <label>Protected roots (summary)</label><input type="text" name="protected_root_hints" value="{html.escape(runtime_defaults['protected_root_hints'])}" readonly />
        <label>Max memory (MB)</label><input type="number" name="max_memory_mb" value="{html.escape(runtime_defaults['max_memory_mb'])}" />
        <label>Max Python threads</label><input type="number" name="max_python_threads" value="{html.escape(runtime_defaults['max_python_threads'])}" />
        <label>Max child processes</label><input type="number" name="max_child_processes" value="{html.escape(runtime_defaults['max_child_processes'])}" />
        <label>Subprocess mode</label>
        <select name="subprocess_mode">
          <option value="disabled"{" selected" if runtime_defaults["subprocess_mode"] == "disabled" else ""}>disabled</option>
          <option value="bounded"{" selected" if runtime_defaults["subprocess_mode"] == "bounded" else ""}>bounded</option>
          <option value="allow"{" selected" if runtime_defaults["subprocess_mode"] == "allow" else ""}>allow</option>
        </select>
        <label>Working directory</label><input type="text" name="working_directory" value="{html.escape(runtime_defaults['working_directory'])}" readonly />
        <label>Allowed write roots (; separated)</label><input type="text" name="allowed_write_roots" value="{html.escape(runtime_defaults['allowed_write_roots'])}" readonly />
        <label>Session time limit (seconds)</label><input type="number" name="session_time_limit_seconds" value="{html.escape(runtime_defaults['session_time_limit_seconds'])}" />
        <label>Runtime backend</label>
        <select name="backend_kind">
          <option value="{BACKEND_LOCAL_GUARDED}"{" selected" if runtime_defaults["backend_kind"] == BACKEND_LOCAL_GUARDED else ""}>{BACKEND_LOCAL_GUARDED}</option>
          <option value="{BACKEND_LOCAL_DOCKER}"{" selected" if runtime_defaults["backend_kind"] == BACKEND_LOCAL_DOCKER else ""}>{BACKEND_LOCAL_DOCKER}</option>
        </select>
        <label>Docker CPU limit (cpus)</label><input type="text" name="cpu_limit_cpus" value="{html.escape(runtime_defaults['cpu_limit_cpus'])}" />
        <label>Docker image</label><input type="text" name="docker_image" value="{html.escape(runtime_defaults['docker_image'])}" />
        <label>Network policy intent</label>
        <select name="network_policy_intent">
          <option value="deny_all"{" selected" if runtime_defaults["network_policy_intent"] == "deny_all" else ""}>deny_all</option>
        </select>
        <button type="submit">Save Runtime Policy</button>
      </form>
      {("<p><strong>Attempted runtime policy (not saved)</strong></p><pre>" + html.escape(attempted_runtime_summary) + "</pre>") if attempted_runtime_summary else ""}
      <p><strong>Persisted runtime policy summary</strong></p>
      <pre>{html.escape(constraints_summary)}</pre>
    </section>
    <section class="card" id="launch-section">
      <h2>Launch / Resume</h2>
      <p>Recommended first launch: <code>new_bootstrap</code> + <code>bootstrap_only</code>. Use <code>resume_existing</code> only after a successful prior launch created persisted state and a frozen operator session. Use <code>governed_execution</code> when you want post-bootstrap governed work; the bounded coding profile is intended for that path.</p>
      <form method="post" action="/launch">
        <label>State root</label><input type="text" name="state_root" value="{html.escape(_normalize_path(self.state_root))}" />
        <label>Startup mode</label>
        <select name="resume_mode">
          <option value="new_bootstrap"{" selected" if self.resume_mode == "new_bootstrap" else ""}>new_bootstrap</option>
          <option value="resume_existing"{" selected" if self.resume_mode == "resume_existing" else ""}>resume_existing</option>
        </select>
        <label>Launch action</label>
        <select name="launch_action">
          <option value="bootstrap_only"{" selected" if self.launch_action == "bootstrap_only" else ""}>bootstrap_only</option>
          <option value="governed_execution"{" selected" if self.launch_action == "governed_execution" else ""}>governed_execution</option>
          <option value="proposal_analytics"{" selected" if self.launch_action == "proposal_analytics" else ""}>proposal_analytics</option>
          <option value="proposal_recommend"{" selected" if self.launch_action == "proposal_recommend" else ""}>proposal_recommend</option>
        </select>
        <button type="submit">Launch / Resume</button>
      </form>
      <pre>{html.escape(render_launch_readiness(readiness=readiness))}</pre>
    </section>
    <section class="card" id="evidence-section">
      <h2>Acceptance Evidence</h2>
      <p>Exports remain non-authoritative and are written under the operator-visible evidence root. Use them to capture the packaged happy path, refusal path, and any restart evidence without creating a second authority path.</p>
      <form method="post" action="/export"><button type="submit">Export Acceptance Snapshot</button></form>
      <p><strong>Last markdown export:</strong> <span class="path">{html.escape(self.last_export_path or '<none>')}</span></p>
      <p><strong>Last JSON export:</strong> <span class="path">{html.escape(self.last_export_json_path or '<none>')}</span></p>
    </section>
  </div>
</body>
</html>"""


def _html_response(handler: BaseHTTPRequestHandler, body: str, *, status: HTTPStatus = HTTPStatus.OK) -> None:
    payload = body.encode("utf-8")
    handler.send_response(int(status))
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def _download_response(
    handler: BaseHTTPRequestHandler,
    *,
    filename: str,
    content_type: str,
    payload: bytes,
) -> None:
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Disposition", f'attachment; filename="{filename}"')
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def _parse_urlencoded(handler: BaseHTTPRequestHandler) -> dict[str, str]:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    raw = handler.rfile.read(length).decode("utf-8")
    parsed = urllib.parse.parse_qs(raw, keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def _parse_multipart(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    content_type = str(handler.headers.get("Content-Type", ""))
    length = int(handler.headers.get("Content-Length", "0") or "0")
    raw = handler.rfile.read(length)
    if not raw or "multipart/form-data" not in content_type.lower():
        return {}
    header_block = (
        f"Content-Type: {content_type}\r\n"
        "MIME-Version: 1.0\r\n"
        "\r\n"
    ).encode("utf-8")
    form = BytesParser(policy=email_policy).parsebytes(header_block + raw)
    parsed: dict[str, Any] = {}
    if form.is_multipart():
        for field in form.iter_parts():
            field_name = str(field.get_param("name", header="content-disposition") or "").strip()
            if not field_name:
                continue
            filename = field.get_filename()
            payload = field.get_payload(decode=True) or b""
            if filename:
                parsed[field_name] = {
                    "filename": str(filename),
                    "value": payload,
                }
            else:
                charset = field.get_content_charset() or "utf-8"
                parsed[field_name] = payload.decode(charset, errors="replace")
    return parsed


def build_operator_web_app(
    *,
    package_root: str | Path | None = None,
    operator_root: str | Path | None = None,
    state_root: str | Path | None = None,
) -> OperatorWebService:
    return OperatorWebService(package_root=package_root, operator_root=operator_root, state_root=state_root)


def make_operator_web_handler(service: OperatorWebService) -> type[BaseHTTPRequestHandler]:
    class OperatorWebHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            if self.path == "/" or self.path.startswith("/?"):
                _html_response(self, service.render_home_page())
                return
            if self.path == "/healthz":
                _download_response(
                    self,
                    filename="healthz.txt",
                    content_type="text/plain; charset=utf-8",
                    payload=b"ok\n",
                )
                return
            if self.path == "/directive/download-scaffold":
                filename, payload = service.scaffold_download_payload()
                _download_response(
                    self,
                    filename=filename,
                    content_type="application/json; charset=utf-8",
                    payload=payload,
                )
                return
            _html_response(
                self,
                service.render_home_page(
                    notice={
                        "headline": "Requested page was not found.",
                        "details": [self.path],
                    }
                ),
                status=HTTPStatus.NOT_FOUND,
            )

        def do_POST(self) -> None:
            path = self.path
            with service._lock:
                if path == "/directive/select":
                    form = _parse_urlencoded(self)
                    service.update_profile(directive_file=str(form.get("directive_path", "")), resume_mode="new_bootstrap")
                    _html_response(
                        self,
                        service.render_home_page(
                            notice={
                                "headline": "Directive selection updated.",
                                "details": [str(service.current_directive_summary().get("summary", ""))],
                            }
                        ),
                    )
                    return
                if path == "/directive/sample":
                    form = _parse_urlencoded(self)
                    sample_path = str(form.get("sample_path", "")).strip()
                    service.select_sample_directive(sample_path)
                    _html_response(
                        self,
                        service.render_home_page(
                            notice={
                                "headline": "Sample directive selected.",
                                "details": [sample_path],
                            }
                        ),
                    )
                    return
                if path == "/directive/upload":
                    form = _parse_multipart(self)
                    upload = dict(form.get("directive_upload", {}))
                    if not upload:
                        notice = {
                            "headline": "No directive file was uploaded.",
                            "details": ["Choose a JSON file before submitting the upload form."],
                        }
                    else:
                        target = service.save_uploaded_directive(
                            filename=str(upload.get("filename", "")),
                            payload=bytes(upload.get("value", b"")),
                        )
                        notice = {
                            "headline": "Directive uploaded.",
                            "details": [str(target)],
                        }
                    _html_response(self, service.render_home_page(notice=notice))
                    return
                if path == "/runtime/save":
                    form = _parse_urlencoded(self)
                    result = service.save_runtime_policy(form)
                    _html_response(self, service.render_home_page(notice=result))
                    return
                if path == "/launch":
                    form = _parse_urlencoded(self)
                    result = service.launch(
                        resume_mode=str(form.get("resume_mode", "new_bootstrap")),
                        launch_action=str(form.get("launch_action", "bootstrap_only")),
                        state_root=str(form.get("state_root", _normalize_path(service.state_root))),
                    )
                    _html_response(self, service.render_home_page(notice=result))
                    return
                if path == "/export":
                    exported = service.export_acceptance_evidence()
                    _download_response(
                        self,
                        filename=Path(exported["markdown_path"]).name,
                        content_type="text/markdown; charset=utf-8",
                        payload=exported["markdown"].encode("utf-8"),
                    )
                    return
            _html_response(
                self,
                service.render_home_page(
                    notice={
                        "headline": "Requested action was not found.",
                        "details": [path],
                    }
                ),
                status=HTTPStatus.NOT_FOUND,
            )

    return OperatorWebHandler


def make_operator_web_server(
    *,
    service: OperatorWebService,
    host: str,
    port: int,
) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, int(port)), make_operator_web_handler(service))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Localhost browser-based operator surface for novali-v5. "
            "This server remains a thin surface over the existing launcher/frozen-session/bootstrap flow."
        )
    )
    parser.add_argument("--host", default=os.environ.get("NOVALI_WEB_HOST", DEFAULT_WEB_HOST))
    parser.add_argument("--port", type=int, default=int(os.environ.get("NOVALI_WEB_PORT", str(DEFAULT_WEB_PORT))))
    parser.add_argument("--package-root", default=os.environ.get("NOVALI_PACKAGE_ROOT", ""))
    parser.add_argument("--operator-root", default=os.environ.get("NOVALI_OPERATOR_ROOT", ""))
    parser.add_argument("--state-root", default=os.environ.get("NOVALI_STATE_ROOT", ""))
    args = parser.parse_args()

    package_root = Path(str(args.package_root).strip()) if str(args.package_root).strip() else Path(__file__).resolve().parents[1]
    operator_root = Path(str(args.operator_root).strip()) if str(args.operator_root).strip() else default_operator_root()
    state_root = Path(str(args.state_root).strip()) if str(args.state_root).strip() else default_web_state_root(package_root)

    service = build_operator_web_app(
        package_root=package_root,
        operator_root=operator_root,
        state_root=state_root,
    )
    server = make_operator_web_server(service=service, host=str(args.host), port=int(args.port))
    bound_host, bound_port = server.server_address
    print(
        "\n".join(
            [
                "NOVALI Localhost Web Operator",
                f"Listening on: http://{bound_host}:{bound_port}/",
                f"Package root: {package_root}",
                f"Operator root: {operator_root}",
                f"State root: {state_root}",
                "Local single-operator use only. Remote/multi-user security is not implemented in this slice.",
            ]
        )
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
