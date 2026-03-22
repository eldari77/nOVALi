from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HANDOFF_LAYOUT_SCHEMA_NAME = "NovaliStandaloneHandoffLayout"
HANDOFF_LAYOUT_SCHEMA_VERSION = "novali_standalone_handoff_layout_v1"
IMAGE_ARCHIVE_SCHEMA_NAME = "NovaliStandaloneImageArchive"
IMAGE_ARCHIVE_SCHEMA_VERSION = "novali_standalone_image_archive_v1"
DEFAULT_HANDOFF_PACKAGE_NAME = "novali-v5-standalone-handoff"
HANDOFF_PACKAGE_VERSION = "novali-v5-standalone-rc9"
HANDOFF_RELEASE_CHANNEL = "release_candidate"
HANDOFF_PRODUCT_TARGET = "zip_delivered_single_agent_docker_browser"
CANONICAL_IMAGE_TAG = "novali-v5-standalone:local"
CANONICAL_IMAGE_ARCHIVE_NAME = "novali-v5-standalone.tar"
CANONICAL_OPERATOR_LAUNCH = "python -m novali_v5.web_operator"
CANONICAL_AUTHORITY_PATH = (
    "operator shell -> launcher -> frozen session -> bootstrap -> governed execution"
)
PRIMARY_LOAD_SCRIPT_PS1 = "launch/01_load_image_archive.ps1"
PRIMARY_LOAD_SCRIPT_BAT = "launch/01_load_image_archive.bat"
PRIMARY_RUN_SCRIPT_PS1 = "launch/02_run_browser_operator.ps1"
PRIMARY_RUN_SCRIPT_BAT = "launch/02_run_browser_operator.bat"
PRIMARY_BROWSER_URL = "http://127.0.0.1:8787/"
HOST_BIND_ADDRESS = "127.0.0.1"
CONTAINER_BIND_ADDRESS = "0.0.0.0"
DEFAULT_WEB_PORT = 8787
HOST_PORT_MAPPING = f"{HOST_BIND_ADDRESS}:{DEFAULT_WEB_PORT}:{DEFAULT_WEB_PORT}"
CONTAINER_DEFAULT_COMMAND = [
    "python",
    "-m",
    "novali_v5.web_operator",
    "--host",
    CONTAINER_BIND_ADDRESS,
    "--port",
    str(DEFAULT_WEB_PORT),
]

ROOT_FILES_TO_COPY = [
    ".dockerignore",
    "Dockerfile",
    "bootstrap.py",
    "main.py",
    "operator_gui.py",
    "runtime_config.py",
    "multi_agent_env.py",
]

RUNTIME_DIRS_TO_COPY = [
    "agents",
    "benchmarks",
    "directives",
    "environment",
    "evolution",
    "experiments",
    "interventions",
    "memory",
    "novali_v5",
    "operator_shell",
    "standalone_docker",
    "theory",
    "utils",
    "world_models",
]

DOC_FILES = [
    "HANDOFF_PACKAGE_README.md",
    "STANDALONE_OPERATOR_GUIDE.md",
    "DIRECTIVE_AUTHORING_GUIDE.md",
    "LOCALHOST_WEB_OPERATOR_UI.md",
    "STANDALONE_DOCKER_QUICKSTART.md",
    "STANDALONE_HANDOFF_ACCEPTANCE.md",
    "OPERATOR_SHELL.md",
    "RUNTIME_ENVELOPE.md",
    "LAUNCH_MATRIX.md",
    "ACTIVE_VERSION_STATUS.md",
    "MANUAL_ACCEPTANCE_RESULT_TEMPLATE.md",
]

SAMPLE_FILE_MAP = {
    "manual_acceptance_samples/valid_manual_acceptance_directive.json": "samples/directives/standalone_valid_directive.example.json",
    "manual_acceptance_samples/incomplete_manual_acceptance_directive.json": "samples/directives/standalone_incomplete_directive.example.json",
    "manual_acceptance_samples/trusted_source_bindings_env_example.json": "samples/trusted_sources/trusted_source_bindings.env.example.json",
    "manual_acceptance_samples/operator_runtime_constraints_example.json": "samples/runtime/operator_runtime_constraints.example.json",
    "standalone_docker/standalone.env.template": "samples/trusted_sources/standalone.env.template",
}

LIVE_DIR_READMES = {
    "directive_inputs/README.md": (
        "# Directive Inputs\n\n"
        "Place operator-authored formal NOVALIDirectiveBootstrapFile JSON documents here.\n\n"
        "These files are operator inputs. Canonical startup authority still begins only after the selected "
        "directive is compiled through directive-first bootstrap.\n"
    ),
    "trusted_sources/README.md": (
        "# Trusted Sources\n\n"
        "Place operator-provided local trusted-source material here when needed.\n\n"
        "Credential values must stay outside directives. Use environment variables or the operator-local secret store.\n"
    ),
    "operator_state/README.md": (
        "# Operator State\n\n"
        "This folder is for operator-owned policy/session material when you choose to keep it alongside the handoff package.\n\n"
        "It is not part of NOVALI directive authority.\n"
    ),
    "runtime_data/README.md": (
        "# Runtime Data\n\n"
        "This folder groups runtime persistence, logs, and acceptance evidence for the standalone handoff path.\n"
    ),
    "runtime_data/state/README.md": (
        "# Canonical Runtime State\n\n"
        "Recommended target for persisted NOVALI canonical artifacts when launching from the standalone handoff package.\n"
    ),
    "runtime_data/logs/README.md": (
        "# Runtime Logs\n\n"
        "Recommended target for runtime logs, launch logs, and operator evidence support files.\n"
    ),
    "runtime_data/acceptance_evidence/README.md": (
        "# Acceptance Evidence\n\n"
        "Store non-authoritative operator acceptance exports here.\n"
    ),
    "novali-active_workspace/README.md": (
        "# Active Workspace\n\n"
        "This folder is the bounded governed build area for post-bootstrap mutable-shell work.\n\n"
        "Expected per-run or per-directive outputs live under `novali-active_workspace/<workspace_id>/`.\n"
        "Protected repo surfaces remain excluded by default.\n"
    ),
    "samples/README.md": (
        "# Standalone Samples\n\n"
        "These samples are non-authoritative operator aids only.\n\n"
        "Use them as references or starting points, then save real operator input under `directive_inputs/` "
        "or your chosen operator-owned paths.\n"
    ),
    "data/README.md": (
        "# Package-Local Default State Root\n\n"
        "This empty folder exists because current default trusted-source and runtime-policy defaults expect a `data/` path.\n\n"
        "For standalone handoff use, prefer pointing the GUI State Root to `runtime_data/state` instead.\n"
    ),
    "logs/README.md": (
        "# Package-Local Default Logs Root\n\n"
        "This empty folder exists because current runtime-policy defaults expect a `logs/` path.\n\n"
        "For standalone handoff use, prefer `runtime_data/logs` for long-lived operator-visible log storage.\n"
    ),
    "image/README.md": (
        "# Prebuilt Image Archive\n\n"
        "This folder is for the packaged standalone Docker image archive.\n\n"
        "Operators should prefer loading this archive instead of building the image from source.\n"
    ),
    "launch/README.md": (
        "# Launch Helpers\n\n"
        "Use `02_run_browser_operator.bat` or `02_run_browser_operator.ps1` as the primary packaged run helpers.\n\n"
        "Those helpers preserve the existing canonical authority flow; they do not create a second authority path.\n"
    ),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _copy_file(source_root: Path, target_root: Path, relative_path: str, *, target_name: str | None = None) -> None:
    source = source_root / relative_path
    target = target_root / (target_name or relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _copy_dir(source_root: Path, target_root: Path, relative_path: str) -> None:
    source = source_root / relative_path
    target = target_root / relative_path
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns(
            "__pycache__",
            "*.pyc",
            "*.pyo",
            "*.pyd",
            ".pytest_cache",
            "manual_acceptance_runs",
            "dist",
        ),
    )


def _render_root_readme(text: str) -> str:
    return (
        text
        .replace("(./STANDALONE_OPERATOR_GUIDE.md)", "(./docs/STANDALONE_OPERATOR_GUIDE.md)")
        .replace("(./DIRECTIVE_AUTHORING_GUIDE.md)", "(./docs/DIRECTIVE_AUTHORING_GUIDE.md)")
        .replace("(./LOCALHOST_WEB_OPERATOR_UI.md)", "(./docs/LOCALHOST_WEB_OPERATOR_UI.md)")
        .replace("(./OPERATOR_SHELL.md)", "(./docs/OPERATOR_SHELL.md)")
        .replace("(./RUNTIME_ENVELOPE.md)", "(./docs/RUNTIME_ENVELOPE.md)")
        .replace("(./STANDALONE_DOCKER_QUICKSTART.md)", "(./docs/STANDALONE_DOCKER_QUICKSTART.md)")
        .replace("(./STANDALONE_HANDOFF_ACCEPTANCE.md)", "(./docs/STANDALONE_HANDOFF_ACCEPTANCE.md)")
        .replace("(./LAUNCH_MATRIX.md)", "(./docs/LAUNCH_MATRIX.md)")
        .replace("(./ACTIVE_VERSION_STATUS.md)", "(./docs/ACTIVE_VERSION_STATUS.md)")
        .replace("(./MANUAL_ACCEPTANCE_RESULT_TEMPLATE.md)", "(./docs/MANUAL_ACCEPTANCE_RESULT_TEMPLATE.md)")
    )


def _docker_image_inspect(*, image_tag: str) -> tuple[dict[str, Any], str]:
    result = subprocess.run(
        ["docker", "image", "inspect", image_tag, "--format", "{{json .}}"],
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
    )
    if int(result.returncode) != 0:
        detail = str(result.stderr or result.stdout).strip()
        return {}, detail[:400] or f"docker image inspect failed for {image_tag}"
    try:
        return json.loads(str(result.stdout).strip()), ""
    except json.JSONDecodeError as exc:
        return {}, f"docker image inspect returned invalid JSON: {exc}"


def export_standalone_image_archive(
    *,
    output_path: str | Path,
    image_tag: str = CANONICAL_IMAGE_TAG,
) -> dict[str, Any]:
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    inspect_payload, inspect_error = _docker_image_inspect(image_tag=image_tag)
    if not inspect_payload:
        raise RuntimeError(inspect_error or f"docker image not available for export: {image_tag}")
    save_result = subprocess.run(
        ["docker", "save", "-o", str(output_path), image_tag],
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
    )
    if int(save_result.returncode) != 0:
        detail = str(save_result.stderr or save_result.stdout).strip()
        raise RuntimeError(detail[:400] or f"docker save failed for {image_tag}")
    return {
        "image_tag": image_tag,
        "archive_path": str(output_path),
        "docker_image_id": str(inspect_payload.get("Id", "")),
        "repo_tags": list(inspect_payload.get("RepoTags", [])),
        "container_default_command": list(dict(inspect_payload.get("Config", {})).get("Cmd", [])),
    }


def _write_packaged_launch_scripts(package_root: Path) -> None:
    load_ps1 = (
        "$ErrorActionPreference = \"Stop\"\n\n"
        "$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path\n"
        "$packageRoot = Split-Path -Parent $scriptRoot\n"
        "& (Join-Path $packageRoot \"standalone_docker\\load_image_archive.ps1\") @args\n"
    )
    run_ps1 = (
        "$ErrorActionPreference = \"Stop\"\n\n"
        "$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path\n"
        "$packageRoot = Split-Path -Parent $scriptRoot\n"
        "& (Join-Path $packageRoot \"standalone_docker\\run_web_operator_container.ps1\") @args\n"
    )
    load_bat = (
        "@echo off\r\n"
        "powershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp001_load_image_archive.ps1\" %*\r\n"
    )
    run_bat = (
        "@echo off\r\n"
        "powershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp002_run_browser_operator.ps1\" %*\r\n"
    )
    _write_text(package_root / PRIMARY_LOAD_SCRIPT_PS1, load_ps1)
    _write_text(package_root / PRIMARY_RUN_SCRIPT_PS1, run_ps1)
    _write_text(package_root / PRIMARY_LOAD_SCRIPT_BAT, load_bat)
    _write_text(package_root / PRIMARY_RUN_SCRIPT_BAT, run_bat)


def _prepare_image_archive(
    *,
    package_root: Path,
    include_image_archive: bool,
    require_image_archive: bool,
    image_archive_source: str | Path | None,
    image_tag: str,
) -> dict[str, Any]:
    image_dir = package_root / "image"
    image_dir.mkdir(parents=True, exist_ok=True)
    archive_path = image_dir / CANONICAL_IMAGE_ARCHIVE_NAME
    source_mode = "not_attempted"
    reason = ""
    export_details: dict[str, Any] = {}
    image_archive_source_path = Path(image_archive_source).resolve() if image_archive_source else None

    try:
        if image_archive_source_path is not None:
            if not image_archive_source_path.exists():
                raise RuntimeError(f"requested image archive source was not found: {image_archive_source_path}")
            shutil.copy2(image_archive_source_path, archive_path)
            source_mode = "copied_existing_archive"
        elif include_image_archive:
            export_details = export_standalone_image_archive(output_path=archive_path, image_tag=image_tag)
            source_mode = "docker_save"
        else:
            source_mode = "archive_not_included"
            reason = "image archive export was skipped by packaging configuration"
    except Exception as exc:
        source_mode = "archive_missing"
        reason = str(exc)
        if archive_path.exists():
            archive_path.unlink()
        if require_image_archive:
            raise

    archive_present = archive_path.exists()
    archive_size_bytes = int(archive_path.stat().st_size) if archive_present else 0
    archive_sha256 = _sha256_file(archive_path) if archive_present else ""
    inspect_payload: dict[str, Any] = {}
    if archive_present:
        inspect_payload, _ = _docker_image_inspect(image_tag=image_tag)
    container_default_command = list(
        export_details.get("container_default_command", list(dict(inspect_payload.get("Config", {})).get("Cmd", [])))
    ) or list(CONTAINER_DEFAULT_COMMAND)
    manifest = {
        "schema_name": IMAGE_ARCHIVE_SCHEMA_NAME,
        "schema_version": IMAGE_ARCHIVE_SCHEMA_VERSION,
        "package_version": HANDOFF_PACKAGE_VERSION,
        "release_channel": HANDOFF_RELEASE_CHANNEL,
        "product_target": HANDOFF_PRODUCT_TARGET,
        "generated_at": _now(),
        "image_tag": str(image_tag),
        "archive_present": archive_present,
        "archive_filename": CANONICAL_IMAGE_ARCHIVE_NAME,
        "archive_relative_path": f"image/{CANONICAL_IMAGE_ARCHIVE_NAME}",
        "archive_size_bytes": archive_size_bytes,
        "archive_sha256": archive_sha256,
        "source_mode": source_mode,
        "reason": reason,
        "docker_image_id": str(export_details.get("docker_image_id", inspect_payload.get("Id", ""))),
        "repo_tags": list(export_details.get("repo_tags", inspect_payload.get("RepoTags", []))),
        "container_default_command": container_default_command,
        "expected_host_bind_address": HOST_BIND_ADDRESS,
        "expected_container_bind_address": CONTAINER_BIND_ADDRESS,
        "expected_host_port_mapping": HOST_PORT_MAPPING,
        "preferred_load_script": PRIMARY_LOAD_SCRIPT_PS1,
        "preferred_run_script": PRIMARY_RUN_SCRIPT_PS1,
        "preferred_browser_url": PRIMARY_BROWSER_URL,
    }
    _write_json(image_dir / "image_archive_manifest.json", manifest)
    if archive_present:
        _write_text(
            image_dir / "README.md",
            (
                "# Prebuilt Image Archive\n\n"
                f"The packaged image archive is `{CANONICAL_IMAGE_ARCHIVE_NAME}`.\n\n"
                f"Preferred load helper: `{PRIMARY_LOAD_SCRIPT_PS1}`\n\n"
                f"Preferred run helper: `{PRIMARY_RUN_SCRIPT_PS1}`\n"
            ),
        )
    else:
        _write_text(
            image_dir / "README.md",
            (
                "# Prebuilt Image Archive\n\n"
                "The packaged standalone image archive is not present in this handoff build.\n\n"
                "A packager should rebuild the handoff package with an exported Docker image archive before end-user delivery.\n\n"
                f"Recorded reason: {reason or 'not provided'}\n"
            ),
        )
    return manifest


def build_handoff_layout_manifest(*, package_name: str) -> dict[str, Any]:
    return {
        "schema_name": HANDOFF_LAYOUT_SCHEMA_NAME,
        "schema_version": HANDOFF_LAYOUT_SCHEMA_VERSION,
        "package_version": HANDOFF_PACKAGE_VERSION,
        "release_channel": HANDOFF_RELEASE_CHANNEL,
        "product_target": HANDOFF_PRODUCT_TARGET,
        "generated_at": _now(),
        "non_authoritative_layout_only": True,
        "package_name": str(package_name),
        "canonical_operator_launch": CANONICAL_OPERATOR_LAUNCH,
        "canonical_authority_path": CANONICAL_AUTHORITY_PATH,
        "canonical_image_tag": CANONICAL_IMAGE_TAG,
        "default_container_command": list(CONTAINER_DEFAULT_COMMAND),
        "expected_host_bind_address": HOST_BIND_ADDRESS,
        "expected_container_bind_address": CONTAINER_BIND_ADDRESS,
        "expected_host_port_mapping": HOST_PORT_MAPPING,
        "image_directory": "image",
        "launch_directory": "launch",
        "primary_image_archive": f"image/{CANONICAL_IMAGE_ARCHIVE_NAME}",
        "primary_load_script": PRIMARY_LOAD_SCRIPT_PS1,
        "primary_run_script": PRIMARY_RUN_SCRIPT_PS1,
        "primary_browser_url": PRIMARY_BROWSER_URL,
        "primary_readme": "README_FIRST.md",
        "layout_manifest_path": "handoff_layout_manifest.json",
        "image_archive_manifest_path": "image/image_archive_manifest.json",
        "docs_directory": "docs",
        "samples_directory": "samples",
        "operator_input_directories": {
            "directive_inputs": "directive_inputs",
            "trusted_sources": "trusted_sources",
            "operator_state": "operator_state",
        },
        "runtime_directories": {
            "recommended_state_root": "runtime_data/state",
            "recommended_logs_root": "runtime_data/logs",
            "acceptance_evidence_root": "runtime_data/acceptance_evidence",
            "package_local_default_state_root": "data",
            "package_local_default_logs_root": "logs",
        },
        "standalone_docker_directory": "standalone_docker",
        "deferred_runtime_track": "kubernetes remains deferred and unimplemented in this standalone package slice",
    }


def assemble_standalone_handoff_package(
    *,
    source_root: str | Path,
    output_root: str | Path,
    package_name: str = DEFAULT_HANDOFF_PACKAGE_NAME,
    create_zip: bool = False,
    include_image_archive: bool = True,
    require_image_archive: bool = False,
    image_archive_source: str | Path | None = None,
) -> dict[str, Any]:
    source_root_path = Path(source_root).resolve()
    output_root_path = Path(output_root).resolve()
    package_root = output_root_path / package_name

    if package_root.exists():
        shutil.rmtree(package_root)
    package_root.mkdir(parents=True, exist_ok=True)

    for relative_file in ROOT_FILES_TO_COPY:
        _copy_file(source_root_path, package_root, relative_file)

    for relative_dir in RUNTIME_DIRS_TO_COPY:
        _copy_dir(source_root_path, package_root, relative_dir)

    _write_packaged_launch_scripts(package_root)

    docs_root = package_root / "docs"
    for relative_file in DOC_FILES:
        _copy_file(source_root_path, docs_root, relative_file, target_name=Path(relative_file).name)

    for source_relative, target_relative in SAMPLE_FILE_MAP.items():
        _copy_file(source_root_path, package_root, source_relative, target_name=target_relative)

    for relative_path, content in LIVE_DIR_READMES.items():
        _write_text(package_root / relative_path, content)

    root_readme = source_root_path / "HANDOFF_PACKAGE_README.md"
    if root_readme.exists():
        _write_text(
            package_root / "README_FIRST.md",
            _render_root_readme(root_readme.read_text(encoding="utf-8")),
        )

    manifest = build_handoff_layout_manifest(package_name=package_name)
    image_archive_manifest = _prepare_image_archive(
        package_root=package_root,
        include_image_archive=include_image_archive,
        require_image_archive=require_image_archive,
        image_archive_source=image_archive_source,
        image_tag=CANONICAL_IMAGE_TAG,
    )
    manifest["image_archive_manifest"] = image_archive_manifest
    manifest_path = package_root / "handoff_layout_manifest.json"
    _write_json(manifest_path, manifest)

    zip_path = None
    if create_zip:
        zip_path = shutil.make_archive(str(package_root), "zip", root_dir=output_root_path, base_dir=package_name)

    return {
        "package_root": str(package_root),
        "manifest_path": str(manifest_path),
        "zip_path": str(zip_path) if zip_path else "",
        "package_version": HANDOFF_PACKAGE_VERSION,
        "release_channel": HANDOFF_RELEASE_CHANNEL,
        "canonical_operator_launch": CANONICAL_OPERATOR_LAUNCH,
        "canonical_image_tag": CANONICAL_IMAGE_TAG,
        "image_archive_path": str(package_root / "image" / CANONICAL_IMAGE_ARCHIVE_NAME),
        "image_archive_manifest_path": str(package_root / "image" / "image_archive_manifest.json"),
        "primary_load_script": str(package_root / PRIMARY_LOAD_SCRIPT_PS1),
        "primary_run_script": str(package_root / PRIMARY_RUN_SCRIPT_PS1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Assemble a zip-ready standalone novali-v5 handoff directory around the existing canonical "
            "operator shell and directive-first bootstrap flow."
        )
    )
    parser.add_argument(
        "--output-root",
        default="dist",
        help="Directory under which the assembled handoff package should be created. Defaults to ./dist.",
    )
    parser.add_argument(
        "--package-name",
        default=DEFAULT_HANDOFF_PACKAGE_NAME,
        help=f"Top-level handoff package directory name. Defaults to {DEFAULT_HANDOFF_PACKAGE_NAME}.",
    )
    parser.add_argument(
        "--zip",
        action="store_true",
        help="Also create a .zip archive next to the assembled handoff directory.",
    )
    parser.add_argument(
        "--skip-image-archive",
        action="store_true",
        help="Skip exporting/copying the prebuilt Docker image archive into the handoff package.",
    )
    parser.add_argument(
        "--require-image-archive",
        action="store_true",
        help="Fail packaging if the prebuilt image archive cannot be included.",
    )
    parser.add_argument(
        "--image-archive-source",
        default="",
        help="Optional existing Docker image archive to copy into image/ instead of running docker save.",
    )
    args = parser.parse_args()

    source_root = Path(__file__).resolve().parents[1]
    result = assemble_standalone_handoff_package(
        source_root=source_root,
        output_root=args.output_root,
        package_name=args.package_name,
        create_zip=bool(args.zip),
        include_image_archive=not bool(args.skip_image_archive),
        require_image_archive=bool(args.require_image_archive),
        image_archive_source=str(args.image_archive_source).strip() or None,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
