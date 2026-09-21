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
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operator_shell.observability import (  # noqa: E402
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
from operator_shell.scripts.v7rc00_baseline_proof import run_v7rc00_baseline_proof  # noqa: E402
from operator_shell.web_operator import OperatorWebService  # noqa: E402

ARTIFACT_ROOT = ROOT / "artifacts" / "operator_proof" / "v7rc00_topology_fix"
ACTIVE_BRANCH = "novali-v7"
ACTIVE_MILESTONE = "v7rc00"
ACTIVE_SERVICE_VERSION = "novali-v7_rc00"
ACTIVE_PACKAGE_NAME = "novali-v7_rc00-standalone"
FROZEN_REFERENCE_LINE = "novali-v6"
FROZEN_REFERENCE_MILESTONE = "rc88.1"
FROZEN_REFERENCE_PACKAGE_NAME = "novali-v6_rc88_1-standalone.zip"
WRONG_LOCATION_PACKAGE_NAME = "novali-v7_rc00-standalone.zip"
SCHEMA_VERSION = "v7rc00.v1"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _proof_id() -> str:
    return f"v7rc00-topology-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"


def _fake_seed(*parts: str) -> str:
    tokens = ["FAKE", *parts, "V7", "TOPOLOGY", "SHOULD", "NOT", "EXPORT"]
    return "_".join(str(token).strip().upper() for token in tokens if str(token).strip())


def _fake_seeds() -> dict[str, str]:
    return {
        "authorization": f"Bearer {_fake_seed('secret', 'token')}",
        "novali.secret": _fake_seed("novali", "secret"),
        "api_key": _fake_seed("api", "key"),
        "cookie": _fake_seed("cookie"),
        "topology_note": _fake_seed("topology", "secret"),
    }


def _markdown(title: str, lines: list[str]) -> str:
    return "\n".join([title, "", *lines])


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _service(package_root: Path) -> tuple[OperatorWebService, Path]:
    temp_root = Path(tempfile.mkdtemp(prefix="novali-v7-topology-proof-"))
    (temp_root / "operator_state").mkdir(parents=True, exist_ok=True)
    (temp_root / "runtime_data" / "state").mkdir(parents=True, exist_ok=True)
    service = OperatorWebService(
        package_root=package_root,
        operator_root=temp_root / "operator_state",
        state_root=temp_root / "runtime_data" / "state",
    )
    return service, temp_root


def _run_git_snapshot(cwd: Path) -> dict[str, Any]:
    def _run(*args: str) -> tuple[int, str, str]:
        completed = subprocess.run(
            list(args),
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.returncode, completed.stdout.strip(), completed.stderr.strip()

    inside_code, inside_stdout, inside_stderr = _run("git", "rev-parse", "--is-inside-work-tree")
    branch_code, branch_stdout, branch_stderr = _run("git", "branch", "--show-current")
    root_code, root_stdout, root_stderr = _run("git", "rev-parse", "--show-toplevel")
    status_code, status_stdout, status_stderr = _run("git", "status", "--short")
    status_lines = [line for line in status_stdout.splitlines() if line.strip()]
    return {
        "inside_worktree": inside_code == 0 and inside_stdout.lower() == "true",
        "current_branch": branch_stdout or None,
        "git_root": root_stdout or None,
        "git_dirty": bool(status_lines) if status_code == 0 else None,
        "status_lines": status_lines,
        "errors": [value for value in (inside_stderr, branch_stderr, root_stderr, status_stderr) if value],
        "status_command_ok": status_code == 0,
        "root_command_ok": root_code == 0,
        "branch_command_ok": branch_code == 0,
    }


def _scan_behavior_expansion_paths(root: Path) -> dict[str, Any]:
    suspicious_paths: list[str] = []
    allowed_prefixes = {
        "planning/space_engineers/",
        "artifacts/",
        "dist/",
    }
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        lower_rel = rel.lower()
        if any(lower_rel.startswith(prefix) for prefix in allowed_prefixes):
            continue
        if "space_engineers" in lower_rel or "space-engineers" in lower_rel:
            suspicious_paths.append(rel)
        if any(token in lower_rel for token in ("game_server", "server_bridge", "bridge_mod")):
            suspicious_paths.append(rel)
    return {
        "suspicious_paths": sorted(set(suspicious_paths)),
        "real_connector_present": (root / "operator_shell" / "external_adapter" / "connectors").exists(),
        "mutation_connector_present": any(
            candidate.exists()
            for candidate in (
                root / "operator_shell" / "external_adapter" / "live_external_adapter.py",
                root / "operator_shell" / "external_adapter" / "mutation_connector.py",
            )
        ),
        "logicmonitor_api_alert_creation_present": False,
    }


def _preflight_summary(source_root: Path, target_v7_root: Path) -> dict[str, Any]:
    git_snapshot = _run_git_snapshot(source_root)
    config = load_observability_config({"NOVALI_OTEL_ENABLED": "false"})
    status = initialize_observability(config)
    service, temp_root = _service(target_v7_root)
    try:
        shell_payload = service.current_shell_state_payload()
    finally:
        shutdown_observability(reason="v7rc00_topology_preflight")
        shutil.rmtree(temp_root, ignore_errors=True)
    warnings: list[str] = []
    if source_root.name != "novali-v6":
        warnings.append("current_root_basename_not_novali-v6")
    if not git_snapshot["inside_worktree"]:
        warnings.append("git_not_inside_worktree")
    if git_snapshot.get("git_dirty"):
        warnings.append("enclosing_git_worktree_dirty")
    if str(git_snapshot.get("git_root") or "").replace("\\", "/").rstrip("/") != str(source_root).replace("\\", "/").rstrip("/"):
        warnings.append("git_root_is_enclosing_parent_not_current_root")
    summary = {
        "schema_name": "novali_v7rc00_topology_preflight_summary",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "current_root": str(source_root),
        "current_root_basename": source_root.name,
        "parent_root": str(source_root.parent),
        "target_v7_root": str(target_v7_root),
        "target_v7_exists": target_v7_root.exists(),
        "git_inside_worktree": bool(git_snapshot["inside_worktree"]),
        "git_current_branch": git_snapshot["current_branch"],
        "git_root": git_snapshot["git_root"],
        "git_dirty": git_snapshot["git_dirty"],
        "old_v7_package_present": (source_root / "dist" / WRONG_LOCATION_PACKAGE_NAME).exists(),
        "final_v6_package_present": (source_root / "dist" / FROZEN_REFERENCE_PACKAGE_NAME).exists(),
        "active_identity_before_fix": {
            "active_line": shell_payload.get("version_identity", {}).get("active_line"),
            "active_milestone": shell_payload.get("version_identity", {}).get("active_milestone"),
            "service_version": config.resource_attributes.get("service.version"),
            "novali.branch": config.resource_attributes.get("novali.branch"),
            "novali.package.version": config.resource_attributes.get("novali.package.version"),
        },
        "safe_to_continue": source_root.name == "novali-v6" and target_v7_root.exists(),
        "warnings": warnings,
    }
    write_summary_artifacts(
        artifact_root=ARTIFACT_ROOT,
        json_name="preflight_summary.json",
        markdown_name="preflight_summary.md",
        summary=summary,
        markdown=_markdown(
            "# v7rc00 Topology Preflight Summary",
            [
                f"- Current root: {summary['current_root']}",
                f"- Target v7 root: {summary['target_v7_root']}",
                f"- Git current branch: {summary['git_current_branch'] or '<unknown>'}",
                f"- Git root: {summary['git_root'] or '<unknown>'}",
                f"- Git dirty: {summary['git_dirty']}",
                f"- Old wrong-location v7 package present: {summary['old_v7_package_present']}",
                f"- Final v6 package present: {summary['final_v6_package_present']}",
                f"- Safe to continue: {summary['safe_to_continue']}",
            ],
        ),
    )
    return summary


def _iter_scan_files(root: Path, package_root: Path) -> list[Path]:
    files = [
        root / "ACTIVE_VERSION_STATUS.md",
        root / "HANDOFF_PACKAGE_README.md",
        root / "nOVALi_Project_Plan.md",
        root / "dist" / "README.md",
        root / "planning" / "versioning" / "v7rc00_baseline_status.md",
        root / "planning" / "versioning" / "v7rc00_migration_ledger.md",
        root / "planning" / "versioning" / "v7rc00_operator_handoff.md",
        root / "planning" / "versioning" / "v7rc00_workspace_topology_fix.md",
        root / "data" / "branch_transition_status.json",
        root / "data" / "version_handoff_status.json",
    ]
    if package_root.exists():
        files.extend(
            [
                package_root / "README_FIRST.md",
                package_root / "handoff_layout_manifest.json",
                package_root / "image" / "image_archive_manifest.json",
                package_root / "docs" / "ACTIVE_VERSION_STATUS.md",
                package_root / "docs" / "HANDOFF_PACKAGE_README.md",
                package_root / "planning" / "versioning" / "v7rc00_workspace_topology_fix.md",
            ]
        )
    return [path for path in files if path.exists()]


def _classify_v6_reference(line: str) -> str:
    line_lower = line.lower()
    if "novali-v6" not in line_lower:
        return "ignore"
    if any(
        token in line_lower
        for token in (
            "frozen",
            "historical",
            "reference",
            "closeout",
            "final v6",
            "rc88.1",
            "superseded",
            "wrong physical topology",
            "wrong physical source root",
            "migration",
            "frozen physical source root",
            "reference_branch_root",
            "reference_read_roots",
            "completed_reference_branch",
            "completed_reference_version",
            "closeout_reference_package",
            "not from `novali-v6`",
            "rather than `novali-v6`",
            "wrong-location `novali-v6/dist/novali-v7_rc00",
            "wrong-location `novali-v6\\dist\\novali-v7_rc00",
        )
    ):
        return "allowed"
    if any(
        token in line_lower
        for token in (
            "active physical source root",
            "future v7 development",
            "active source root",
            "canonical topology",
            "topology-correct canonical package",
            "active_v7_metadata_on_existing_worktree_path",
            "\"branch_root\":",
            "\"operator_handoff_markdown\":",
        )
    ):
        return "forbidden"
    if "novali-v6/dist/novali-v7_rc00" in line_lower or "novali-v6\\dist\\novali-v7_rc00" in line_lower:
        return "forbidden"
    return "allowed"


def _path_audit(root: Path, package_root: Path) -> dict[str, Any]:
    scan_files = _iter_scan_files(root, package_root)
    allowed_count = 0
    forbidden_refs: list[str] = []
    for path in scan_files:
        for line_no, line in enumerate(_safe_read(path).splitlines(), start=1):
            classification = _classify_v6_reference(line)
            if classification == "allowed":
                allowed_count += 1
            elif classification == "forbidden":
                forbidden_refs.append(f"{path.relative_to(root).as_posix()}:{line_no}:{line.strip()}")
    summary = {
        "schema_name": "novali_v7rc00_topology_path_audit_summary",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "scanned_file_count": len(scan_files),
        "allowed_historical_v6_reference_count": allowed_count,
        "forbidden_active_v6_reference_count": len(forbidden_refs),
        "forbidden_active_v6_references": forbidden_refs,
        "result": "success" if not forbidden_refs else "failure",
    }
    write_summary_artifacts(
        artifact_root=ARTIFACT_ROOT,
        json_name="path_audit_summary.json",
        markdown_name="path_audit_summary.md",
        summary=summary,
        markdown=_markdown(
            "# v7rc00 Path Audit Summary",
            [
                f"- Scanned file count: {summary['scanned_file_count']}",
                f"- Allowed historical v6 reference count: {summary['allowed_historical_v6_reference_count']}",
                f"- Forbidden active v6 reference count: {summary['forbidden_active_v6_reference_count']}",
            ],
        ),
    )
    return summary


def _text_from_zip_member(package: zipfile.ZipFile, filename: str) -> str:
    try:
        return package.read(filename).decode("utf-8", errors="ignore")
    except KeyError:
        return ""


def run_workspace_topology_proof(
    *,
    package_root: str | Path | None = None,
    source_root: str | Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    package_root_path = Path(package_root).resolve() if package_root is not None else ROOT
    source_root_path = Path(source_root).resolve() if source_root is not None else ROOT.parent / "novali-v6"
    env = dict(env or os.environ)
    proof_id = _proof_id()
    fake_seed_values = _fake_seeds()

    preflight = _preflight_summary(source_root_path, ROOT)
    v7_package_root = ROOT / "dist" / ACTIVE_PACKAGE_NAME
    v7_zip = ROOT / "dist" / f"{ACTIVE_PACKAGE_NAME}.zip"
    path_audit = _path_audit(ROOT, v7_package_root)

    config = load_observability_config({"NOVALI_OTEL_ENABLED": "false"})
    status = initialize_observability(config)
    service, temp_root = _service(package_root_path)
    try:
        shell_payload = service.current_shell_state_payload()
    finally:
        shutdown_observability(reason="v7rc00_topology_identity")
        shutil.rmtree(temp_root, ignore_errors=True)

    physical_root_summary = {
        "schema_name": "novali_v7rc00_physical_root_summary",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "proof_id": proof_id,
        "physical_source_root": str(ROOT),
        "physical_source_root_basename": ROOT.name,
        "expected_basename": ACTIVE_BRANCH,
        "active_line": shell_payload.get("version_identity", {}).get("active_line"),
        "active_milestone": shell_payload.get("version_identity", {}).get("active_milestone"),
        "service_version": config.resource_attributes.get("service.version"),
        "novali.branch": config.resource_attributes.get("novali.branch"),
        "novali.package.version": config.resource_attributes.get("novali.package.version"),
        "result": "success"
        if all(
            (
                ROOT.name == ACTIVE_BRANCH,
                shell_payload.get("version_identity", {}).get("active_line") == ACTIVE_BRANCH,
                shell_payload.get("version_identity", {}).get("active_milestone") == ACTIVE_MILESTONE,
                config.resource_attributes.get("service.version") == ACTIVE_SERVICE_VERSION,
                config.resource_attributes.get("novali.branch") == ACTIVE_BRANCH,
                config.resource_attributes.get("novali.package.version") == ACTIVE_MILESTONE,
            )
        )
        else "failure",
    }
    write_summary_artifacts(
        artifact_root=ARTIFACT_ROOT,
        json_name="v7_physical_root_summary.json",
        markdown_name="v7_physical_root_summary.md",
        summary=physical_root_summary,
        markdown=_markdown(
            "# v7 Physical Root Summary",
            [
                f"- Physical source root: {physical_root_summary['physical_source_root']}",
                f"- Physical source basename: {physical_root_summary['physical_source_root_basename']}",
                f"- Active line: {physical_root_summary['active_line']}",
                f"- Active milestone: {physical_root_summary['active_milestone']}",
                f"- Service version: {physical_root_summary['service_version']}",
            ],
        ),
    )

    package_docs = {
        "README_FIRST.md": v7_package_root / "README_FIRST.md",
        "docs/ACTIVE_VERSION_STATUS.md": v7_package_root / "docs" / "ACTIVE_VERSION_STATUS.md",
        "docs/HANDOFF_PACKAGE_README.md": v7_package_root / "docs" / "HANDOFF_PACKAGE_README.md",
    }
    package_doc_misses = []
    for label, path in package_docs.items():
        package_doc_text = _safe_read(path).lower()
        if "novali-v7" not in package_doc_text or "future v7 development must start from `novali-v7`" not in package_doc_text:
            package_doc_misses.append(label)
    package_location_summary = {
        "schema_name": "novali_v7rc00_package_location_summary",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "proof_id": proof_id,
        "package_root": str(v7_package_root),
        "package_zip": str(v7_zip),
        "package_root_exists": v7_package_root.exists(),
        "package_zip_exists": v7_zip.exists(),
        "package_docs_missing_expectations": package_doc_misses,
        "old_wrong_location_v7_package": str(source_root_path / "dist" / WRONG_LOCATION_PACKAGE_NAME),
        "result": (
            "success"
            if v7_package_root.exists() and v7_zip.exists() and not package_doc_misses and path_audit["result"] == "success"
            else "failure"
        ),
    }
    write_summary_artifacts(
        artifact_root=ARTIFACT_ROOT,
        json_name="v7_package_location_summary.json",
        markdown_name="v7_package_location_summary.md",
        summary=package_location_summary,
        markdown=_markdown(
            "# v7 Package Location Summary",
            [
                f"- Package root exists: {package_location_summary['package_root_exists']}",
                f"- Package zip exists: {package_location_summary['package_zip_exists']}",
                f"- Package root: {package_location_summary['package_root']}",
                f"- Package zip: {package_location_summary['package_zip']}",
                f"- Package doc misses: {len(package_doc_misses)}",
            ],
        ),
    )

    v6_zip = source_root_path / "dist" / FROZEN_REFERENCE_PACKAGE_NAME
    v6_unpacked = source_root_path / "dist" / "novali-v6_rc88_1-standalone"
    marker_path = source_root_path / "MIGRATED_ACTIVE_V7_TO_SIBLING_DIRECTORY.md"
    v6_reference_summary = {
        "schema_name": "novali_v7rc00_v6_reference_integrity_summary",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "proof_id": proof_id,
        "frozen_reference_root": str(source_root_path),
        "frozen_reference_line": FROZEN_REFERENCE_LINE,
        "frozen_reference_milestone": FROZEN_REFERENCE_MILESTONE,
        "final_v6_zip_exists": v6_zip.exists(),
        "final_v6_unpacked_exists": v6_unpacked.exists(),
        "final_v6_zip_bytes": v6_zip.stat().st_size if v6_zip.exists() else 0,
        "final_v6_zip_sha256": _sha256(v6_zip),
        "wrong_location_v7_package_present": (source_root_path / "dist" / WRONG_LOCATION_PACKAGE_NAME).exists(),
        "superseded_marker_present": marker_path.exists(),
        "superseded_marker_path": str(marker_path),
        "result": (
            "success"
            if v6_zip.exists() and marker_path.exists()
            else "failure"
        ),
    }
    write_summary_artifacts(
        artifact_root=ARTIFACT_ROOT,
        json_name="v6_reference_integrity_summary.json",
        markdown_name="v6_reference_integrity_summary.md",
        summary=v6_reference_summary,
        markdown=_markdown(
            "# v6 Reference Integrity Summary",
            [
                f"- Frozen reference root: {v6_reference_summary['frozen_reference_root']}",
                f"- Final v6 zip exists: {v6_reference_summary['final_v6_zip_exists']}",
                f"- Final v6 unpacked exists: {v6_reference_summary['final_v6_unpacked_exists']}",
                f"- Final v6 zip bytes: {v6_reference_summary['final_v6_zip_bytes']}",
                f"- Superseded marker present: {v6_reference_summary['superseded_marker_present']}",
            ],
        ),
    )

    proof_chain = {
        "schema_name": "novali_v7rc00_topology_proof_chain_preservation_summary",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "proof_id": proof_id,
        "proofs": {},
        "result": "success",
    }
    proof_chain["proofs"]["rc85"] = run_review_rollback_integration_proof(package_root=package_root_path, env=env)
    proof_chain["proofs"]["rc86"] = run_dual_controller_isolation_proof(package_root=package_root_path, env=env)
    proof_chain["proofs"]["rc87"] = run_read_only_adapter_sandbox_proof(package_root=package_root_path, env=env)
    proof_chain["proofs"]["rc88"] = run_operator_alert_loop_proof(package_root=package_root_path, env=env)
    proof_chain["proofs"]["rc88_1"] = run_telemetry_shutdown_cleanup_proof(package_root=package_root_path, env=env)
    proof_chain["proofs"]["v7rc00"] = run_v7rc00_baseline_proof(package_root=package_root_path, env=env)
    proof_chain["result"] = (
        "success"
        if all(
            str(summary.get("result", "")).strip() == "success"
            for summary in proof_chain["proofs"].values()
            if isinstance(summary, Mapping)
        )
        else "failure"
    )
    write_summary_artifacts(
        artifact_root=ARTIFACT_ROOT,
        json_name="proof_chain_preservation_summary.json",
        markdown_name="proof_chain_preservation_summary.md",
        summary=proof_chain,
        markdown=_markdown(
            "# v7rc00 Topology Proof Chain Summary",
            [
                f"- rc85: {proof_chain['proofs']['rc85'].get('result', 'unknown')}",
                f"- rc86: {proof_chain['proofs']['rc86'].get('result', 'unknown')}",
                f"- rc87: {proof_chain['proofs']['rc87'].get('result', 'unknown')}",
                f"- rc88: {proof_chain['proofs']['rc88'].get('result', 'unknown')}",
                f"- rc88.1: {proof_chain['proofs']['rc88_1'].get('result', 'unknown')}",
                f"- v7rc00 baseline: {proof_chain['proofs']['v7rc00'].get('result', 'unknown')}",
            ],
        ),
    )

    behavior_scan = _scan_behavior_expansion_paths(ROOT)
    generated_payloads: list[str] = []
    for path in sorted(ARTIFACT_ROOT.rglob("*")):
        if path.is_file():
            generated_payloads.append(_safe_read(path))
    for path in _iter_scan_files(ROOT, v7_package_root):
        generated_payloads.append(_safe_read(path))
    for jsonl_path in sorted((ROOT / "data").rglob("*.jsonl")):
        generated_payloads.append(_safe_read(jsonl_path))
    if v7_zip.exists():
        with zipfile.ZipFile(v7_zip) as package:
            for info in package.infolist():
                if info.is_dir() or info.file_size > 1_000_000:
                    continue
                if not info.filename.lower().endswith(
                    (".md", ".txt", ".json", ".yaml", ".yml", ".py", ".ps1", ".bat", ".jsonl")
                ):
                    continue
                generated_payloads.append(_text_from_zip_member(package, info.filename))
    forbidden_fake_secret_hits = scan_forbidden_strings(generated_payloads, list(fake_seed_values.values()))

    summary = {
        "schema_name": "novali_v7rc00_workspace_topology_summary",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "proof_id": proof_id,
        "proof_kind": "v7rc00_workspace_topology_fix",
        "physical_source_root": str(ROOT),
        "physical_source_root_basename": ROOT.name,
        "active_line": ACTIVE_BRANCH,
        "active_milestone": ACTIVE_MILESTONE,
        "active_package_root": str(v7_package_root),
        "active_package_zip": str(v7_zip),
        "frozen_reference_root": str(source_root_path),
        "old_wrong_location_v7_package": str(source_root_path / "dist" / WRONG_LOCATION_PACKAGE_NAME),
        "preflight_result": preflight["safe_to_continue"],
        "path_audit_result": path_audit["result"],
        "physical_root_result": physical_root_summary["result"],
        "package_location_result": package_location_summary["result"],
        "v6_reference_result": v6_reference_summary["result"],
        "proof_chain_result": proof_chain["result"],
        "suspicious_behavior_expansion_paths": behavior_scan["suspicious_paths"],
        "forbidden_fake_secret_hits": forbidden_fake_secret_hits,
        "result": "success",
    }
    summary["result"] = (
        "success"
        if all(
            (
                bool(summary["preflight_result"]),
                summary["path_audit_result"] == "success",
                summary["physical_root_result"] == "success",
                summary["package_location_result"] == "success",
                summary["v6_reference_result"] == "success",
                summary["proof_chain_result"] == "success",
                not summary["suspicious_behavior_expansion_paths"],
                not summary["forbidden_fake_secret_hits"],
            )
        )
        else "failure"
    )
    write_summary_artifacts(
        artifact_root=ARTIFACT_ROOT,
        json_name="workspace_topology_summary.json",
        markdown_name="workspace_topology_summary.md",
        summary=summary,
        markdown=_markdown(
            "# v7rc00 Workspace Topology Summary",
            [
                f"- Result: {summary['result']}",
                f"- Physical source root: {summary['physical_source_root']}",
                f"- Active package zip: {summary['active_package_zip']}",
                f"- Path audit result: {summary['path_audit_result']}",
                f"- Package location result: {summary['package_location_result']}",
                f"- v6 reference result: {summary['v6_reference_result']}",
                f"- Proof chain result: {summary['proof_chain_result']}",
                f"- Forbidden fake secret hits: {len(summary['forbidden_fake_secret_hits'])}",
            ],
        ),
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", default=str(ROOT))
    parser.add_argument("--source-root", default=str(ROOT.parent / "novali-v6"))
    args = parser.parse_args()
    summary = run_workspace_topology_proof(
        package_root=Path(args.package_root).resolve(),
        source_root=Path(args.source_root).resolve(),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if str(summary.get("result", "")).strip() == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
