from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operator_shell.observability.rc83 import scan_forbidden_strings, write_summary_artifacts

ARTIFACT_ROOT = ROOT / "artifacts" / "operator_proof" / "v7rc00"
PACKAGE_ROOT_NAME = "novali-v7_rc00-standalone"


def _fake_seed(*parts: str) -> str:
    tokens = ["FAKE", *parts, "V7RC00", "SHOULD", "NOT", "EXPORT"]
    return "_".join(str(token).strip().upper() for token in tokens if str(token).strip())


FAKE_SEEDS = (
    _fake_seed("secret", "token"),
    _fake_seed("novali", "secret"),
    _fake_seed("api", "key"),
    _fake_seed("cookie"),
    _fake_seed("otel", "header"),
    _fake_seed("migration", "secret"),
)
SUSPICIOUS_ENTRY_PATTERNS = (
    re.compile(r"(^|/)\.env($|\.)", re.IGNORECASE),
    re.compile(r"(^|/)node_modules/", re.IGNORECASE),
    re.compile(r"(^|/)\.pytest_cache/", re.IGNORECASE),
    re.compile(r"(^|/)\.mypy_cache/", re.IGNORECASE),
    re.compile(r"(^|/)\.svelte-kit/", re.IGNORECASE),
    re.compile(r"(^|/)__pycache__/", re.IGNORECASE),
    re.compile(r"(^|/)(game_server|server_bridge|bridge_mod)/", re.IGNORECASE),
    re.compile(r"(^|/)(live_external_adapter|external_adapter/connectors|external_adapter/real_)", re.IGNORECASE),
    re.compile(r"(^|/)shared_scratchpad", re.IGNORECASE),
    re.compile(r"(^|/)(season_director|sovereign_behavior)/", re.IGNORECASE),
    re.compile(r"(^|/)fixtures/read_only_world/.*(mutated|modified|backup)", re.IGNORECASE),
    re.compile(r"logicmonitor.*api.*alert", re.IGNORECASE),
)
ALLOWED_SPACE_ENGINEERS_PREFIXES = {
    f"{PACKAGE_ROOT_NAME}/planning/space_engineers/",
    f"{PACKAGE_ROOT_NAME}/artifacts/operator_proof/rc88/",
    f"{PACKAGE_ROOT_NAME}/artifacts/operator_proof/rc88_1/",
}
ACTIVE_IDENTITY_EXPECTATIONS = {
    f"{PACKAGE_ROOT_NAME}/operator_shell/observability/config.py": (
        'NOVALI_BRANCH = "novali-v7"',
        'NOVALI_PACKAGE_VERSION = "v7rc00"',
        'NOVALI_SERVICE_VERSION = "novali-v7_rc00"',
    ),
    f"{PACKAGE_ROOT_NAME}/operator_shell/handoff_package.py": (
        'DEFAULT_HANDOFF_PACKAGE_NAME = "novali-v7_rc00-standalone"',
        'CANONICAL_IMAGE_ARCHIVE_NAME = "novali-v7-standalone.tar"',
    ),
    f"{PACKAGE_ROOT_NAME}/docs/ACTIVE_VERSION_STATUS.md": (
        "`novali-v7` is the active clean baseline",
        "`novali-v6` is closed and frozen",
    ),
    f"{PACKAGE_ROOT_NAME}/docs/HANDOFF_PACKAGE_README.md": (
        "`novali-v7_rc00-standalone`",
        "`dist/novali-v6_rc88_1-standalone.zip`",
    ),
    f"{PACKAGE_ROOT_NAME}/README_FIRST.md": (
        "novali-v7_rc00-standalone",
        "novali-v7-standalone.tar",
    ),
}
ACTIVE_IDENTITY_FORBIDDEN_STRINGS = {
    f"{PACKAGE_ROOT_NAME}/operator_shell/observability/config.py": (
        'NOVALI_BRANCH = "novali-v6"',
        'NOVALI_PACKAGE_VERSION = "rc88_1"',
        'NOVALI_SERVICE_VERSION = "novali-v6_rc88_1"',
    ),
    f"{PACKAGE_ROOT_NAME}/operator_shell/handoff_package.py": (
        'DEFAULT_HANDOFF_PACKAGE_NAME = "novali-v6_rc88_1-standalone"',
        'CANONICAL_IMAGE_ARCHIVE_NAME = "novali-v6-standalone.tar"',
    ),
}


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
            "# v7rc00 Package Hygiene Summary",
            "",
            f"- Result: {summary.get('result', '<unknown>')}",
            f"- Zip path: {summary.get('zip_path', '<none>')}",
            f"- Entry count: {summary.get('entry_count', 0)}",
            f"- Zip bytes: {summary.get('zip_bytes', 0)}",
            f"- Baseline zip bytes: {summary.get('baseline_zip_bytes', 0)}",
            f"- Delta bytes vs rc88.1: {summary.get('delta_bytes', 0)}",
            f"- Suspicious entry count: {len(summary.get('suspicious_entries', []))}",
            f"- Forbidden hit count: {len(summary.get('forbidden_hits', []))}",
            f"- Active identity issue count: {len(summary.get('active_identity_issues', []))}",
        ]
    )


def run_package_hygiene(*, zip_path: Path, baseline_zip_path: Path | None = None) -> dict[str, Any]:
    suspicious_entries: list[str] = []
    forbidden_hits: list[str] = []
    active_identity_issues: list[str] = []
    with zipfile.ZipFile(zip_path) as package:
        infos = package.infolist()
        text_cache: dict[str, str] = {}
        for info in infos:
            is_allowed_space_engineers_entry = any(
                info.filename.startswith(prefix) for prefix in ALLOWED_SPACE_ENGINEERS_PREFIXES
            )
            if (
                not is_allowed_space_engineers_entry
                and "space_engineers" in info.filename.lower()
                and not info.filename.endswith("rc88_transition_decision_memo.md")
            ):
                suspicious_entries.append(info.filename)
            if (
                not is_allowed_space_engineers_entry
                and any(pattern.search(info.filename) for pattern in SUSPICIOUS_ENTRY_PATTERNS)
            ):
                suspicious_entries.append(info.filename)
            text = _text_from_zip_member(package, info)
            if text:
                text_cache[info.filename] = text
                forbidden_hits.extend(scan_forbidden_strings([text], FAKE_SEEDS))
        for path, required_strings in ACTIVE_IDENTITY_EXPECTATIONS.items():
            text = text_cache.get(path, "")
            if not text:
                active_identity_issues.append(f"missing_active_identity_file:{path}")
                continue
            for required in required_strings:
                if required not in text:
                    active_identity_issues.append(f"missing_required_identity:{path}:{required}")
        for path, forbidden_strings in ACTIVE_IDENTITY_FORBIDDEN_STRINGS.items():
            text = text_cache.get(path, "")
            for forbidden in forbidden_strings:
                if forbidden and forbidden in text:
                    active_identity_issues.append(f"unexpected_v6_identity:{path}:{forbidden}")
        entry_count = len(infos)

    zip_bytes = zip_path.stat().st_size
    baseline_zip_bytes = baseline_zip_path.stat().st_size if baseline_zip_path and baseline_zip_path.exists() else 0
    delta_bytes = zip_bytes - baseline_zip_bytes if baseline_zip_bytes else 0
    summary = {
        "schema_name": "novali_v7rc00_package_hygiene_summary",
        "schema_version": "v7rc00.v1",
        "generated_at": _now_iso(),
        "result": "success"
        if not suspicious_entries and not forbidden_hits and not active_identity_issues
        else "failure",
        "zip_path": str(zip_path),
        "entry_count": entry_count,
        "zip_bytes": zip_bytes,
        "baseline_zip_bytes": baseline_zip_bytes,
        "delta_bytes": delta_bytes,
        "suspicious_entries": sorted(set(suspicious_entries)),
        "forbidden_hits": sorted(set(forbidden_hits)),
        "active_identity_issues": sorted(set(active_identity_issues)),
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
    parser.add_argument(
        "--zip-path",
        default=str(ROOT / "dist" / "novali-v7_rc00-standalone.zip"),
    )
    parser.add_argument(
        "--baseline-zip-path",
        default=str(ROOT / "dist" / "novali-v6_rc88_1-standalone.zip"),
    )
    args = parser.parse_args()
    summary = run_package_hygiene(
        zip_path=Path(args.zip_path).resolve(),
        baseline_zip_path=Path(args.baseline_zip_path).resolve(),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if str(summary.get("result", "")).strip() == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
