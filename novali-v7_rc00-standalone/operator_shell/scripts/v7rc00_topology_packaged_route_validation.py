from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operator_shell.observability.rc83 import write_summary_artifacts  # noqa: E402
from operator_shell.scripts.v7rc00_packaged_route_validation import run_packaged_route_validation  # noqa: E402

ARTIFACT_ROOT = ROOT / "artifacts" / "operator_proof" / "v7rc00_topology_fix"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# v7rc00 Topology-Correct Packaged Route Validation",
            "",
            f"- Result: {summary.get('result', '<unknown>')}",
            f"- Package root: {summary.get('package_root', '<none>')}",
            f"- Route validation result: {summary.get('route_validation_result', '<unknown>')}",
            f"- Package doc truth result: {summary.get('package_doc_truth_result', '<unknown>')}",
            f"- Active line: {summary.get('operator_state_checks', {}).get('active_line', '<unknown>')}",
            f"- Active milestone: {summary.get('operator_state_checks', {}).get('active_milestone', '<unknown>')}",
            f"- Controller-isolation mock-only: {summary.get('operator_state_checks', {}).get('controller_isolation_all_mock_only', False)}",
            f"- Missing required package doc strings: {len(summary.get('missing_required_strings', []))}",
            f"- Forbidden active v6 doc hits: {len(summary.get('forbidden_active_v6_doc_hits', []))}",
        ]
    )


def run_topology_packaged_route_validation(*, package_root: Path) -> dict[str, Any]:
    base_summary = run_packaged_route_validation(package_root=package_root)
    package_docs = {
        "README_FIRST.md": package_root / "README_FIRST.md",
        "docs/ACTIVE_VERSION_STATUS.md": package_root / "docs" / "ACTIVE_VERSION_STATUS.md",
        "docs/HANDOFF_PACKAGE_README.md": package_root / "docs" / "HANDOFF_PACKAGE_README.md",
        "planning/versioning/v7rc00_workspace_topology_fix.md": (
            package_root / "planning" / "versioning" / "v7rc00_workspace_topology_fix.md"
        ),
    }
    required_strings = {
        "README_FIRST.md": (
            "active physical source root: `novali-v7`",
            "future v7 development must start from `novali-v7`",
        ),
        "docs/ACTIVE_VERSION_STATUS.md": (
            "active physical source root: `novali-v7`",
            "topology note: the earlier `novali-v6/dist/novali-v7_rc00*` package is superseded",
        ),
        "docs/HANDOFF_PACKAGE_README.md": (
            "canonical topology: build and package from `novali-v7`, not from `novali-v6`",
            "future v7 development must start from `novali-v7`",
        ),
        "planning/versioning/v7rc00_workspace_topology_fix.md": (
            "active physical source root: `novali-v7`",
            "the topology-correct canonical package is built from `novali-v7/dist/novali-v7_rc00-standalone.zip`",
        ),
    }
    forbidden_patterns = (
        "active physical source root: `novali-v6`",
        "future v7 development must start from `novali-v6`",
        "active_v7_metadata_on_existing_worktree_path",
        "novali-v6/dist/novali-v7_rc00-standalone.zip",
        "novali-v6\\dist\\novali-v7_rc00-standalone.zip",
    )

    missing_required_strings: list[str] = []
    forbidden_active_v6_doc_hits: list[str] = []
    for label, path in package_docs.items():
        text = _safe_read(path)
        if not text:
            missing_required_strings.append(f"missing_file:{label}")
            continue
        for required in required_strings.get(label, ()):
            if required not in text:
                missing_required_strings.append(f"missing_required:{label}:{required}")
        for forbidden in forbidden_patterns:
            if forbidden in text:
                if "superseded" in text and forbidden == "novali-v6/dist/novali-v7_rc00-standalone.zip":
                    continue
                forbidden_active_v6_doc_hits.append(f"{label}:{forbidden}")

    package_doc_truth_result = (
        "success" if not missing_required_strings and not forbidden_active_v6_doc_hits else "failure"
    )
    summary = {
        "schema_name": "novali_v7rc00_topology_packaged_route_validation_summary",
        "schema_version": "v7rc00.v1",
        "generated_at": _now_iso(),
        "package_root": str(package_root),
        "route_validation_result": str(base_summary.get("result", "failure")),
        "package_doc_truth_result": package_doc_truth_result,
        "routes": list(base_summary.get("routes", [])),
        "operator_state_checks": dict(base_summary.get("operator_state_checks", {})),
        "missing_required_strings": missing_required_strings,
        "forbidden_active_v6_doc_hits": forbidden_active_v6_doc_hits,
        "result": (
            "success"
            if str(base_summary.get("result", "")).strip() == "success" and package_doc_truth_result == "success"
            else "failure"
        ),
    }
    write_summary_artifacts(
        artifact_root=ARTIFACT_ROOT,
        json_name="packaged_route_validation.json",
        markdown_name="packaged_route_validation.md",
        summary=summary,
        markdown=_markdown_summary(summary),
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--package-root",
        default=str(ROOT / "dist" / "novali-v7_rc00-standalone"),
    )
    args = parser.parse_args()
    summary = run_topology_packaged_route_validation(package_root=Path(args.package_root).resolve())
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if str(summary.get("result", "")).strip() == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
