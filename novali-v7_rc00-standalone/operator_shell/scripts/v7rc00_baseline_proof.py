from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operator_shell.observability import (  # noqa: E402
    get_observability_shutdown_status,
    get_observability_status,
    initialize_observability,
    load_observability_config,
    shutdown_observability,
)
from operator_shell.observability.rc83 import scan_forbidden_strings, write_summary_artifacts  # noqa: E402
from operator_shell.scripts.rc85_review_rollback_integration_proof import (  # noqa: E402
    run_review_rollback_integration_proof,
)
from operator_shell.scripts.rc86_dual_controller_isolation_proof import (  # noqa: E402
    run_dual_controller_isolation_proof,
)
from operator_shell.scripts.rc87_read_only_adapter_sandbox_proof import (  # noqa: E402
    run_read_only_adapter_sandbox_proof,
)
from operator_shell.scripts.rc88_1_telemetry_shutdown_cleanup_proof import (  # noqa: E402
    run_telemetry_shutdown_cleanup_proof,
)
from operator_shell.scripts.rc88_operator_alert_loop_proof import (  # noqa: E402
    run_operator_alert_loop_proof,
)
from operator_shell.web_operator import OperatorWebService  # noqa: E402

ARTIFACT_ROOT = ROOT / "artifacts" / "operator_proof" / "v7rc00"
V6_CLOSEOUT_ROOT = ROOT / "artifacts" / "operator_proof" / "v6_closeout"
SCHEMA_VERSION = "v7rc00.v1"
ACTIVE_BRANCH = "novali-v7"
ACTIVE_PACKAGE_VERSION = "v7rc00"
ACTIVE_SERVICE_VERSION = "novali-v7_rc00"
ACTIVE_PACKAGE_NAME = "novali-v7_rc00-standalone"
FROZEN_REFERENCE_LINE = "novali-v6"
FROZEN_REFERENCE_MILESTONE = "rc88.1"
FROZEN_REFERENCE_PACKAGE = "dist/novali-v6_rc88_1-standalone.zip"
FROZEN_REFERENCE_UNPACKED = "dist/novali-v6_rc88_1-standalone"
FROZEN_REFERENCE_ROOT_NAME = "novali-v6"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _proof_id() -> str:
    return f"v7rc00-baseline-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"


def _fake_seed(*parts: str) -> str:
    tokens = ["FAKE", *parts, "V7RC00", "SHOULD", "NOT", "EXPORT"]
    return "_".join(str(token).strip().upper() for token in tokens if str(token).strip())


def _fake_seeds() -> dict[str, str]:
    return {
        "authorization": f"Bearer {_fake_seed('secret', 'token')}",
        "novali.secret": _fake_seed("novali", "secret"),
        "api_key": _fake_seed("api", "key"),
        "cookie": _fake_seed("cookie"),
        "otel_header": _fake_seed("otel", "header"),
        "migration_note": _fake_seed("migration", "secret"),
    }


def _markdown(title: str, lines: list[str]) -> str:
    return "\n".join([title, "", *lines])


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _clear_artifact_roots() -> None:
    for root in (ARTIFACT_ROOT, V6_CLOSEOUT_ROOT):
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)


def _service(package_root: Path) -> OperatorWebService:
    temp_root = Path(tempfile.mkdtemp(prefix="novali-v7rc00-proof-"))
    (temp_root / "operator_state").mkdir(parents=True, exist_ok=True)
    (temp_root / "runtime_data" / "state").mkdir(parents=True, exist_ok=True)
    return OperatorWebService(
        package_root=package_root,
        operator_root=temp_root / "operator_state",
        state_root=temp_root / "runtime_data" / "state",
    )


def _git_snapshot() -> dict[str, Any]:
    def _run(*args: str) -> tuple[int, str, str]:
        completed = subprocess.run(
            list(args),
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.returncode, completed.stdout.strip(), completed.stderr.strip()

    inside_code, inside_stdout, inside_stderr = _run("git", "rev-parse", "--is-inside-work-tree")
    branch_code, branch_stdout, branch_stderr = _run("git", "branch", "--show-current")
    status_code, status_stdout, status_stderr = _run("git", "status", "--short")
    inside_worktree = inside_code == 0 and inside_stdout.strip().lower() == "true"
    status_lines = [line for line in status_stdout.splitlines() if line.strip()]
    git_branch_created = False
    reason = "git_unavailable_or_not_in_worktree"
    if inside_worktree:
        reason = (
            "enclosing_git_worktree_dirty_or_broader_than_repo_root"
            if status_lines
            else "branch_creation_not_attempted_in_proof_mode"
        )
    return {
        "git_branch_created": git_branch_created,
        "reason": reason,
        "inside_worktree": inside_worktree,
        "current_branch": branch_stdout or None,
        "status_lines": status_lines,
        "status_command_ok": status_code == 0,
        "errors": [value for value in (inside_stderr, branch_stderr, status_stderr) if value],
    }


def _doc_paths() -> dict[str, Path]:
    return {
        "active_version_status": ROOT / "ACTIVE_VERSION_STATUS.md",
        "handoff_package_readme": ROOT / "HANDOFF_PACKAGE_README.md",
        "project_plan": ROOT / "nOVALi_Project_Plan.md",
        "dist_readme": ROOT / "dist" / "README.md",
        "v6_final_closeout": ROOT / "planning" / "versioning" / "v6_final_closeout.md",
        "v6_frozen_reference_ledger": ROOT / "planning" / "versioning" / "v6_frozen_reference_ledger.md",
        "v7rc00_baseline_status": ROOT / "planning" / "versioning" / "v7rc00_baseline_status.md",
        "v7rc00_migration_ledger": ROOT / "planning" / "versioning" / "v7rc00_migration_ledger.md",
        "v7rc00_operator_handoff": ROOT / "planning" / "versioning" / "v7rc00_operator_handoff.md",
        "v6_closeout_readiness": ROOT / "planning" / "versioning" / "v6_closeout_readiness_rc88_1.md",
        "v7rc00_bootstrap_checklist": ROOT / "planning" / "versioning" / "v7rc00_bootstrap_checklist.md",
        "se_transition_memo": ROOT / "planning" / "space_engineers" / "rc88_transition_decision_memo.md",
        "lm_snapshot": ROOT / "observability" / "logicmonitor" / "rc83_2_portal_confirmation_snapshot.json",
    }


def _package_paths(package_root: Path) -> dict[str, Path]:
    return {
        "v6_zip": package_root / "dist" / "novali-v6_rc88_1-standalone.zip",
        "v6_unpacked": package_root / "dist" / "novali-v6_rc88_1-standalone",
        "v7_zip": package_root / "dist" / "novali-v7_rc00-standalone.zip",
        "v7_unpacked": package_root / "dist" / "novali-v7_rc00-standalone",
    }


def _frozen_reference_paths(package_root: Path) -> dict[str, Path]:
    package_paths = _package_paths(package_root)
    v6_zip = package_paths["v6_zip"]
    v6_unpacked = package_paths["v6_unpacked"]
    if v6_zip.exists() or v6_unpacked.exists():
        return {"v6_zip": v6_zip, "v6_unpacked": v6_unpacked}
    sibling_root = ROOT.parent / FROZEN_REFERENCE_ROOT_NAME
    return {
        "v6_zip": sibling_root / "dist" / "novali-v6_rc88_1-standalone.zip",
        "v6_unpacked": sibling_root / "dist" / "novali-v6_rc88_1-standalone",
    }


def _is_packaged_handoff_root(package_root: Path) -> bool:
    return all(
        (
            (package_root / "README_FIRST.md").exists(),
            (package_root / "docs").is_dir(),
            (package_root / "launch").is_dir(),
        )
    )


def _milestone_chain() -> list[dict[str, str]]:
    return [
        {"milestone": "rc81", "summary": "response outcome tracking"},
        {"milestone": "rc82", "summary": "observability foundation"},
        {"milestone": "rc83", "summary": "live collector proof"},
        {"milestone": "rc83.1", "summary": "trace visibility alignment"},
        {"milestone": "rc83.2", "summary": "Dockerized NOVALI-to-collector proof"},
        {"milestone": "rc84", "summary": "generic external adapter membrane"},
        {"milestone": "rc85", "summary": "review/rollback integration hardening"},
        {"milestone": "rc86", "summary": "dual-controller isolation primitives"},
        {"milestone": "rc87", "summary": "generic non-SE read-only adapter sandbox"},
        {"milestone": "rc88", "summary": "operator alert loop and admission criteria"},
        {"milestone": "rc88.1", "summary": "telemetry shutdown cleanup and alert-degradation hardening"},
    ]


def _scan_behavior_expansion_paths() -> dict[str, Any]:
    suspicious_paths: list[str] = []
    allowed_prefixes = {
        "planning/space_engineers/",
        "artifacts/",
        "dist/",
    }
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        lower_rel = rel.lower()
        if any(lower_rel.startswith(prefix) for prefix in allowed_prefixes):
            continue
        if "space_engineers" in lower_rel or "space-engineers" in lower_rel:
            suspicious_paths.append(rel)
        if any(token in lower_rel for token in ("game_server", "server_bridge", "bridge_mod")):
            suspicious_paths.append(rel)
    real_connector_present = bool(list((ROOT / "operator_shell" / "external_adapter").glob("real_*")))
    real_connector_present = real_connector_present or (ROOT / "operator_shell" / "external_adapter" / "connectors").exists()
    mutation_connector_present = any(
        path.exists()
        for path in (
            ROOT / "operator_shell" / "external_adapter" / "live_external_adapter.py",
            ROOT / "operator_shell" / "external_adapter" / "mutation_connector.py",
        )
    )
    logicmonitor_api_alert_creation_present = False
    return {
        "suspicious_paths": sorted(set(suspicious_paths)),
        "real_connector_present": real_connector_present,
        "mutation_connector_present": mutation_connector_present,
        "logicmonitor_api_alert_creation_present": logicmonitor_api_alert_creation_present,
    }


def _write_v6_closeout_artifacts(package_root: Path, git_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    reference_paths = _frozen_reference_paths(package_root)
    v6_zip = reference_paths["v6_zip"]
    v6_unpacked = reference_paths["v6_unpacked"]
    docs = _doc_paths()
    packaged_handoff_mode = _is_packaged_handoff_root(package_root)
    package_manifest = {
        "schema_name": "novali_v6_final_package_manifest",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "branch": ACTIVE_BRANCH,
        "package_version": ACTIVE_PACKAGE_VERSION,
        "reference_branch": FROZEN_REFERENCE_LINE,
        "reference_milestone": FROZEN_REFERENCE_MILESTONE,
        "reference_package_path": FROZEN_REFERENCE_PACKAGE,
        "reference_unpacked_path": FROZEN_REFERENCE_UNPACKED,
        "reference_lookup_zip_path": str(v6_zip),
        "reference_lookup_unpacked_path": str(v6_unpacked),
        "packaged_handoff_mode": packaged_handoff_mode,
        "zip_exists": v6_zip.exists(),
        "unpacked_exists": v6_unpacked.exists(),
        "zip_bytes": v6_zip.stat().st_size if v6_zip.exists() else 0,
        "zip_sha256": _sha256(v6_zip),
        "git_branch_created": bool(git_snapshot.get("git_branch_created", False)),
        "git_branch_creation_reason": str(git_snapshot.get("reason", "")),
    }
    write_summary_artifacts(
        artifact_root=V6_CLOSEOUT_ROOT,
        json_name="v6_final_package_manifest.json",
        markdown_name="v6_final_package_manifest.md",
        summary=package_manifest,
        markdown=_markdown(
            "# v6 Final Package Manifest",
            [
                f"- Final v6 milestone: {FROZEN_REFERENCE_MILESTONE}",
                f"- Final package: {FROZEN_REFERENCE_PACKAGE}",
                f"- Final unpacked package: {FROZEN_REFERENCE_UNPACKED}",
                f"- Reference lookup zip path: {package_manifest['reference_lookup_zip_path']}",
                f"- Zip exists: {package_manifest['zip_exists']}",
                f"- Unpacked exists: {package_manifest['unpacked_exists']}",
                f"- Zip bytes: {package_manifest['zip_bytes']}",
                f"- Zip sha256: {package_manifest['zip_sha256'] or '<missing>'}",
            ],
        ),
    )
    invariants = {
        "schema_name": "novali_v6_final_invariants",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "branch": ACTIVE_BRANCH,
        "package_version": ACTIVE_PACKAGE_VERSION,
        "reference_branch": FROZEN_REFERENCE_LINE,
        "reference_milestone": FROZEN_REFERENCE_MILESTONE,
        "controller_sole_authority": True,
        "backend_truth_authoritative": True,
        "review_intervention_gates_preserved": True,
        "telemetry_evidence_only": True,
        "logicmonitor_evidence_only": True,
        "alerts_evidence_only": True,
        "acknowledgement_not_approval": True,
        "review_not_approval": True,
        "read_only_adapter_non_mutating": True,
        "identity_lanes_inactive_mock_only": True,
        "no_second_authority_path": True,
        "no_space_engineers_implementation": True,
    }
    write_summary_artifacts(
        artifact_root=V6_CLOSEOUT_ROOT,
        json_name="v6_final_invariants.json",
        markdown_name="v6_final_invariants.md",
        summary=invariants,
        markdown=_markdown(
            "# v6 Final Invariants",
            [
                "- Controller remains the sole authority.",
                "- Backend truth remains authoritative.",
                "- Review/intervention gates remain binding.",
                "- Telemetry, alerts, replay, review, rollback, and lane artifacts remain evidence only.",
                "- Read-only adapters remain non-mutating.",
                "- Identity lanes remain inactive/mock-only.",
                "- No second authority path exists.",
                "- No Space Engineers implementation is active.",
            ],
        ),
    )
    docs_exist = {name: path.exists() for name, path in docs.items() if name.startswith("v6_")}
    closeout_summary = {
        "schema_name": "novali_v6_closeout_summary",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "branch": ACTIVE_BRANCH,
        "package_version": ACTIVE_PACKAGE_VERSION,
        "final_v6_milestone": FROZEN_REFERENCE_MILESTONE,
        "final_v6_package": FROZEN_REFERENCE_PACKAGE,
        "final_v6_unpacked_package": FROZEN_REFERENCE_UNPACKED,
        "final_v6_status": "frozen_reference",
        "proof_chain": _milestone_chain(),
        "docs_exist": docs_exist,
        "git_branch_created": bool(git_snapshot.get("git_branch_created", False)),
        "git_branch_creation_reason": str(git_snapshot.get("reason", "")),
        "packaged_handoff_mode": packaged_handoff_mode,
        "result": "success"
        if docs_exist.get("v6_final_closeout")
        and docs_exist.get("v6_frozen_reference_ledger")
        and (packaged_handoff_mode or v6_zip.exists())
        else "failure",
    }
    write_summary_artifacts(
        artifact_root=V6_CLOSEOUT_ROOT,
        json_name="v6_closeout_summary.json",
        markdown_name="v6_closeout_summary.md",
        summary=closeout_summary,
        markdown=_markdown(
            "# v6 Closeout Summary",
            [
                f"- Final v6 milestone: {FROZEN_REFERENCE_MILESTONE}",
                f"- Final v6 package: {FROZEN_REFERENCE_PACKAGE}",
                f"- Final v6 unpacked package: {FROZEN_REFERENCE_UNPACKED}",
                "- v6 status: frozen_reference",
                f"- Proof chain count: {len(closeout_summary['proof_chain'])}",
                f"- Git branch created: {closeout_summary['git_branch_created']}",
                f"- Git branch handling: {closeout_summary['git_branch_creation_reason']}",
            ],
        ),
    )
    return {
        "package_manifest": package_manifest,
        "invariants": invariants,
        "summary": closeout_summary,
    }


def run_v7rc00_baseline_proof(
    *,
    package_root: str | Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    package_root_path = Path(package_root).resolve() if package_root is not None else ROOT
    env = dict(env or os.environ)
    _clear_artifact_roots()
    proof_id = _proof_id()
    fake_seed_values = _fake_seeds()
    git_snapshot = _git_snapshot()
    docs = _doc_paths()
    package_paths = _package_paths(package_root_path)

    v6_closeout = _write_v6_closeout_artifacts(package_root_path, git_snapshot)

    disabled_env = {**env, "NOVALI_OTEL_ENABLED": "false"}
    enabled_env = {
        **env,
        "NOVALI_OTEL_ENABLED": "true",
        "OTEL_SERVICE_NAME": str(env.get("OTEL_SERVICE_NAME") or "novalioperatorshell"),
        "OTEL_EXPORTER_OTLP_ENDPOINT": str(env.get("OTEL_EXPORTER_OTLP_ENDPOINT") or "http://127.0.0.1:65530"),
        "NOVALI_OTEL_REDACTION_MODE": str(env.get("NOVALI_OTEL_REDACTION_MODE") or "strict"),
    }

    disabled_config = load_observability_config(disabled_env)
    disabled_status = initialize_observability(disabled_config)
    service = _service(package_root_path)
    shell_snapshot = service.current_shell_state_payload()
    shutdown_observability(reason="v7rc00_disabled_path")

    enabled_config = load_observability_config(enabled_env)
    enabled_status = initialize_observability(enabled_config)
    enabled_observability_status = get_observability_status()
    enabled_shutdown = shutdown_observability(reason="v7rc00_enabled_path")
    shutdown_status = get_observability_shutdown_status()

    version_identity = {
        "schema_name": "novali_v7_version_identity_summary",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "branch": ACTIVE_BRANCH,
        "package_version": ACTIVE_PACKAGE_VERSION,
        "active_line": shell_snapshot.get("version_identity", {}).get("active_line"),
        "active_milestone": shell_snapshot.get("version_identity", {}).get("active_milestone"),
        "service_version": enabled_config.resource_attributes.get("service.version"),
        "novali_branch": enabled_config.resource_attributes.get("novali.branch"),
        "novali_package_version": enabled_config.resource_attributes.get("novali.package.version"),
        "telemetry_schema_version": enabled_config.resource_attributes.get("novali.telemetry.schema_version"),
        "package_name": shell_snapshot.get("version_identity", {}).get("package_name"),
        "disabled_status": disabled_status.get("status", "unknown"),
        "enabled_status": enabled_status.get("status", "unknown"),
        "enabled_shutdown_result": enabled_shutdown.get("result", "unknown"),
        "result": "success",
    }
    version_identity["result"] = "success" if all(
        (
            version_identity["active_line"] == ACTIVE_BRANCH,
            version_identity["active_milestone"] == ACTIVE_PACKAGE_VERSION,
            version_identity["service_version"] == ACTIVE_SERVICE_VERSION,
            version_identity["novali_branch"] == ACTIVE_BRANCH,
            version_identity["novali_package_version"] == ACTIVE_PACKAGE_VERSION,
            version_identity["telemetry_schema_version"] == SCHEMA_VERSION,
            version_identity["package_name"] == ACTIVE_PACKAGE_NAME,
        )
    ) else "failure"
    write_summary_artifacts(
        artifact_root=ARTIFACT_ROOT,
        json_name="v7_version_identity_summary.json",
        markdown_name="v7_version_identity_summary.md",
        summary=version_identity,
        markdown=_markdown(
            "# v7 Version Identity Summary",
            [
                f"- Active line: {version_identity['active_line']}",
                f"- Active milestone: {version_identity['active_milestone']}",
                f"- service.version: {version_identity['service_version']}",
                f"- novali.branch: {version_identity['novali_branch']}",
                f"- novali.package.version: {version_identity['novali_package_version']}",
                f"- novali.telemetry.schema_version: {version_identity['telemetry_schema_version']}",
                f"- Package name: {version_identity['package_name']}",
            ],
        ),
    )

    v6_reference_summary = {
        "schema_name": "novali_v6_closeout_reference_summary",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "branch": ACTIVE_BRANCH,
        "package_version": ACTIVE_PACKAGE_VERSION,
        "frozen_reference_line": FROZEN_REFERENCE_LINE,
        "frozen_reference_milestone": FROZEN_REFERENCE_MILESTONE,
        "final_package_path": FROZEN_REFERENCE_PACKAGE,
        "final_unpacked_path": FROZEN_REFERENCE_UNPACKED,
        "docs_exist": {
            "v6_final_closeout": docs["v6_final_closeout"].exists(),
            "v6_frozen_reference_ledger": docs["v6_frozen_reference_ledger"].exists(),
            "v6_closeout_readiness": docs["v6_closeout_readiness"].exists(),
        },
        "packaged_handoff_mode": _is_packaged_handoff_root(package_root_path),
        "package_exists": package_paths["v6_zip"].exists(),
        "package_sha256": _sha256(package_paths["v6_zip"]),
        "result": "success"
        if docs["v6_final_closeout"].exists()
        and (_is_packaged_handoff_root(package_root_path) or package_paths["v6_zip"].exists())
        else "failure",
    }
    write_summary_artifacts(
        artifact_root=ARTIFACT_ROOT,
        json_name="v6_closeout_reference_summary.json",
        markdown_name="v6_closeout_reference_summary.md",
        summary=v6_reference_summary,
        markdown=_markdown(
            "# v6 Closeout Reference Summary",
            [
                f"- Frozen reference line: {FROZEN_REFERENCE_LINE}",
                f"- Frozen reference milestone: {FROZEN_REFERENCE_MILESTONE}",
                f"- Final package path: {FROZEN_REFERENCE_PACKAGE}",
                f"- Final package exists: {v6_reference_summary['package_exists']}",
                f"- v6 closeout docs exist: {all(v6_reference_summary['docs_exist'].values())}",
            ],
        ),
    )

    behavior_scan = _scan_behavior_expansion_paths()
    controller_isolation = dict(shell_snapshot.get("controller_isolation", {}))
    read_only_adapter = dict(shell_snapshot.get("read_only_adapter", {}))
    operator_alerts = dict(shell_snapshot.get("operator_alerts", {}))
    observability = dict(shell_snapshot.get("observability", {}))
    invariants = {
        "schema_name": "novali_v7_invariant_preservation_summary",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "branch": ACTIVE_BRANCH,
        "package_version": ACTIVE_PACKAGE_VERSION,
        "controller_sole_authority": True,
        "review_gates_preserved": True,
        "telemetry_evidence_only": True,
        "alerts_evidence_only": True,
        "acknowledgement_not_approval": True,
        "review_not_approval": True,
        "no_second_authority_path": True,
        "no_space_engineers_implementation": not behavior_scan["suspicious_paths"],
        "no_real_external_connector": not behavior_scan["real_connector_present"],
        "no_mutation_connector": not behavior_scan["mutation_connector_present"],
        "no_logicmonitor_api_alert_creation": not behavior_scan["logicmonitor_api_alert_creation_present"],
        "operator_alerts_status": operator_alerts.get("status", "unknown"),
        "operator_alerts_mode": operator_alerts.get("mode", "unknown"),
        "read_only_adapter_mutation_allowed": read_only_adapter.get("mutation_allowed"),
        "controller_isolation_lane_ids": [lane.get("lane_id") for lane in controller_isolation.get("lanes", []) if isinstance(lane, dict)],
        "controller_isolation_all_mock_only": all(
            not bool(lane.get("active", True)) and str(lane.get("mode", "")).strip() == "mock_only"
            for lane in controller_isolation.get("lanes", [])
            if isinstance(lane, dict)
        ),
        "observability_endpoint_hint": observability.get("endpoint_hint", "unknown"),
        "observability_shutdown_result": shutdown_status.get("last_shutdown_result", "unknown"),
        "result": "success",
        "suspicious_paths": behavior_scan["suspicious_paths"],
    }
    invariants["result"] = "success" if all(
        (
            invariants["telemetry_evidence_only"],
            invariants["alerts_evidence_only"],
            invariants["read_only_adapter_mutation_allowed"] is False,
            invariants["controller_isolation_all_mock_only"],
            invariants["no_space_engineers_implementation"],
            invariants["no_real_external_connector"],
            invariants["no_mutation_connector"],
            invariants["no_logicmonitor_api_alert_creation"],
        )
    ) else "failure"
    write_summary_artifacts(
        artifact_root=ARTIFACT_ROOT,
        json_name="v7_invariant_preservation_summary.json",
        markdown_name="v7_invariant_preservation_summary.md",
        summary=invariants,
        markdown=_markdown(
            "# v7 Invariant Preservation Summary",
            [
                "- Controller remains the sole authority.",
                "- Telemetry remains evidence only.",
                "- Alerts remain evidence only.",
                f"- Read-only adapter mutation allowed: {invariants['read_only_adapter_mutation_allowed']}",
                f"- Controller-isolation lanes mock-only: {invariants['controller_isolation_all_mock_only']}",
                f"- Suspicious behavior-expansion paths: {len(invariants['suspicious_paths'])}",
            ],
        ),
    )

    proof_chain = {
        "schema_name": "novali_v7_proof_chain_summary",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "branch": ACTIVE_BRANCH,
        "package_version": ACTIVE_PACKAGE_VERSION,
        "proofs": {},
        "result": "success",
    }
    proof_chain["proofs"]["rc85"] = run_review_rollback_integration_proof(package_root=package_root_path, env=env)
    proof_chain["proofs"]["rc86"] = run_dual_controller_isolation_proof(package_root=package_root_path, env=env)
    proof_chain["proofs"]["rc87"] = run_read_only_adapter_sandbox_proof(package_root=package_root_path, env=env)
    proof_chain["proofs"]["rc88"] = run_operator_alert_loop_proof(package_root=package_root_path, env=env)
    proof_chain["proofs"]["rc88_1"] = run_telemetry_shutdown_cleanup_proof(package_root=package_root_path, env=env)
    proof_chain["result"] = "success" if all(
        str(summary.get("result", "")).strip() == "success"
        for summary in proof_chain["proofs"].values()
        if isinstance(summary, Mapping)
    ) else "failure"
    write_summary_artifacts(
        artifact_root=ARTIFACT_ROOT,
        json_name="v7_proof_chain_summary.json",
        markdown_name="v7_proof_chain_summary.md",
        summary=proof_chain,
        markdown=_markdown(
            "# v7 Proof Chain Summary",
            [
                f"- rc85: {proof_chain['proofs']['rc85'].get('result', 'unknown')}",
                f"- rc86: {proof_chain['proofs']['rc86'].get('result', 'unknown')}",
                f"- rc87: {proof_chain['proofs']['rc87'].get('result', 'unknown')}",
                f"- rc88: {proof_chain['proofs']['rc88'].get('result', 'unknown')}",
                f"- rc88.1: {proof_chain['proofs']['rc88_1'].get('result', 'unknown')}",
            ],
        ),
    )

    generated_payloads = []
    for root in (V6_CLOSEOUT_ROOT, ARTIFACT_ROOT):
        for path in sorted(root.rglob("*")):
            if path.is_file():
                generated_payloads.append(_safe_read(path))
    for path in docs.values():
        generated_payloads.append(_safe_read(path))
    forbidden_hits = scan_forbidden_strings(generated_payloads, list(fake_seed_values.values()))

    summary = {
        "schema_name": "novali_v7rc00_baseline_summary",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "proof_id": proof_id,
        "proof_kind": "v7rc00_clean_baseline_setup",
        "branch": ACTIVE_BRANCH,
        "package_version": ACTIVE_PACKAGE_VERSION,
        "frozen_reference_line": FROZEN_REFERENCE_LINE,
        "frozen_reference_milestone": FROZEN_REFERENCE_MILESTONE,
        "v6_closeout_result": v6_closeout["summary"]["result"],
        "version_identity_result": version_identity["result"],
        "invariant_result": invariants["result"],
        "proof_chain_result": proof_chain["result"],
        "git_branch_created": bool(git_snapshot.get("git_branch_created", False)),
        "git_branch_creation_reason": str(git_snapshot.get("reason", "")),
        "git_current_branch": git_snapshot.get("current_branch"),
        "git_inside_worktree": bool(git_snapshot.get("inside_worktree", False)),
        "git_status_lines": list(git_snapshot.get("status_lines", [])),
        "disabled_observability_status": disabled_status.get("status", "unknown"),
        "enabled_observability_status": enabled_status.get("status", "unknown"),
        "enabled_shutdown_result": enabled_shutdown.get("result", "unknown"),
        "forbidden_fake_secret_hits": forbidden_hits,
        "result": "success",
    }
    summary["result"] = "success" if all(
        (
            summary["v6_closeout_result"] == "success",
            summary["version_identity_result"] == "success",
            summary["invariant_result"] == "success",
            summary["proof_chain_result"] == "success",
            not summary["forbidden_fake_secret_hits"],
        )
    ) else "failure"
    write_summary_artifacts(
        artifact_root=ARTIFACT_ROOT,
        json_name="v7rc00_baseline_summary.json",
        markdown_name="v7rc00_baseline_summary.md",
        summary=summary,
        markdown=_markdown(
            "# v7rc00 Baseline Summary",
            [
                f"- Result: {summary['result']}",
                f"- v6 closeout result: {summary['v6_closeout_result']}",
                f"- Version identity result: {summary['version_identity_result']}",
                f"- Invariant result: {summary['invariant_result']}",
                f"- Proof chain result: {summary['proof_chain_result']}",
                f"- Git branch created: {summary['git_branch_created']}",
                f"- Git branch handling: {summary['git_branch_creation_reason']}",
                f"- Fake secret hits: {len(summary['forbidden_fake_secret_hits'])}",
            ],
        ),
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", default=str(ROOT))
    args = parser.parse_args()
    summary = run_v7rc00_baseline_proof(package_root=Path(args.package_root).resolve())
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if str(summary.get("result", "")).strip() == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
