from __future__ import annotations

import argparse
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operator_shell.observability.rc83 import write_summary_artifacts  # noqa: E402
from operator_shell.scripts.v7rc00_package_hygiene import run_package_hygiene  # noqa: E402

ARTIFACT_ROOT = ROOT / "artifacts" / "operator_proof" / "v7rc00_topology_fix"
PACKAGE_ROOT_NAME = "novali-v7_rc00-standalone"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _text_from_zip_member(package: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    if info.is_dir():
        return ""
    if info.file_size > 1_000_000:
        return ""
    if not info.filename.lower().endswith(
        (
            ".md",
            ".txt",
            ".json",
            ".yaml",
            ".yml",
            ".py",
            ".env",
            ".ps1",
            ".bat",
            ".mjs",
            ".js",
            ".ts",
            ".svelte",
            ".jsonl",
        )
    ):
        return ""
    return package.read(info).decode("utf-8", errors="ignore")


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# v7rc00 Topology-Correct Package Hygiene",
            "",
            f"- Result: {summary.get('result', '<unknown>')}",
            f"- Zip path: {summary.get('zip_path', '<none>')}",
            f"- Base hygiene result: {summary.get('base_hygiene_result', '<unknown>')}",
            f"- Topology identity result: {summary.get('topology_identity_result', '<unknown>')}",
            f"- Missing required topology strings: {len(summary.get('missing_required_strings', []))}",
            f"- Forbidden active v6 hits: {len(summary.get('forbidden_active_v6_hits', []))}",
            f"- Delta bytes vs wrong-location v7 zip: {summary.get('delta_bytes_vs_wrong_location_v7', 0)}",
            f"- Delta bytes vs v6 rc88.1 zip: {summary.get('delta_bytes_vs_v6_rc88_1', 0)}",
        ]
    )


def run_topology_package_hygiene(
    *,
    zip_path: Path,
    baseline_zip_path: Path,
    wrong_location_zip_path: Path | None = None,
) -> dict[str, Any]:
    base_summary = run_package_hygiene(zip_path=zip_path, baseline_zip_path=baseline_zip_path)
    required_strings = {
        f"{PACKAGE_ROOT_NAME}/README_FIRST.md": (
            "active physical source root: `novali-v7`",
            "future v7 development must start from `novali-v7`",
        ),
        f"{PACKAGE_ROOT_NAME}/docs/ACTIVE_VERSION_STATUS.md": (
            "active physical source root: `novali-v7`",
            "frozen physical source root: sibling `../novali-v6`",
        ),
        f"{PACKAGE_ROOT_NAME}/docs/HANDOFF_PACKAGE_README.md": (
            "canonical topology: build and package from `novali-v7`, not from `novali-v6`",
            "future v7 development must start from `novali-v7`",
        ),
        f"{PACKAGE_ROOT_NAME}/planning/versioning/v7rc00_workspace_topology_fix.md": (
            "active physical source root: `novali-v7`",
            "the topology-correct canonical package is built from `novali-v7/dist/novali-v7_rc00-standalone.zip`",
        ),
    }
    forbidden_patterns = (
        "active physical source root: `novali-v6`",
        "future v7 development must start from `novali-v6`",
        "active_v7_metadata_on_existing_worktree_path",
        "canonical topology: build and package from `novali-v6`",
        "topology-correct canonical package is built from `novali-v6`",
    )

    missing_required_strings: list[str] = []
    forbidden_active_v6_hits: list[str] = []
    with zipfile.ZipFile(zip_path) as package:
        text_cache: dict[str, str] = {}
        for info in package.infolist():
            text = _text_from_zip_member(package, info)
            if text:
                text_cache[info.filename] = text

    for filename, values in required_strings.items():
        text = text_cache.get(filename, "")
        if not text:
            missing_required_strings.append(f"missing_file:{filename}")
            continue
        for value in values:
            if value not in text:
                missing_required_strings.append(f"missing_required:{filename}:{value}")
    topology_truth_files = set(required_strings.keys()) | {
        f"{PACKAGE_ROOT_NAME}/handoff_layout_manifest.json",
        f"{PACKAGE_ROOT_NAME}/image/image_archive_manifest.json",
    }
    for filename in sorted(topology_truth_files):
        text = text_cache.get(filename, "")
        if not text:
            continue
        for forbidden in forbidden_patterns:
            if forbidden in text:
                forbidden_active_v6_hits.append(f"{filename}:{forbidden}")

    wrong_location_zip_bytes = (
        wrong_location_zip_path.stat().st_size if wrong_location_zip_path and wrong_location_zip_path.exists() else 0
    )
    delta_wrong_location = zip_path.stat().st_size - wrong_location_zip_bytes if wrong_location_zip_bytes else 0
    delta_v6 = zip_path.stat().st_size - baseline_zip_path.stat().st_size if baseline_zip_path.exists() else 0
    topology_identity_result = (
        "success" if not missing_required_strings and not forbidden_active_v6_hits else "failure"
    )
    summary = {
        "schema_name": "novali_v7rc00_topology_package_hygiene_summary",
        "schema_version": "v7rc00.v1",
        "generated_at": _now_iso(),
        "zip_path": str(zip_path),
        "baseline_zip_path": str(baseline_zip_path),
        "wrong_location_zip_path": str(wrong_location_zip_path) if wrong_location_zip_path else "",
        "base_hygiene_result": str(base_summary.get("result", "failure")),
        "topology_identity_result": topology_identity_result,
        "missing_required_strings": missing_required_strings,
        "forbidden_active_v6_hits": forbidden_active_v6_hits,
        "delta_bytes_vs_wrong_location_v7": delta_wrong_location,
        "delta_bytes_vs_v6_rc88_1": delta_v6,
        "entry_count": int(base_summary.get("entry_count", 0)),
        "result": (
            "success"
            if str(base_summary.get("result", "")).strip() == "success" and topology_identity_result == "success"
            else "failure"
        ),
    }
    write_summary_artifacts(
        artifact_root=ARTIFACT_ROOT,
        json_name="package_hygiene_summary.json",
        markdown_name="package_hygiene_summary.md",
        summary=summary,
        markdown=_markdown_summary(summary),
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip-path", default=str(ROOT / "dist" / "novali-v7_rc00-standalone.zip"))
    parser.add_argument(
        "--baseline-zip-path",
        default=str(ROOT.parent / "novali-v6" / "dist" / "novali-v6_rc88_1-standalone.zip"),
    )
    parser.add_argument(
        "--wrong-location-zip-path",
        default=str(ROOT.parent / "novali-v6" / "dist" / "novali-v7_rc00-standalone.zip"),
    )
    args = parser.parse_args()
    summary = run_topology_package_hygiene(
        zip_path=Path(args.zip_path).resolve(),
        baseline_zip_path=Path(args.baseline_zip_path).resolve(),
        wrong_location_zip_path=Path(args.wrong_location_zip_path).resolve(),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if str(summary.get("result", "")).strip() == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
