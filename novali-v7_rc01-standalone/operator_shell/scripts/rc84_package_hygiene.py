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

from operator_shell.external_adapter import resolve_rc84_artifact_root
from operator_shell.observability.rc83 import scan_forbidden_strings, write_summary_artifacts


def _fake_seed(version: str, suffix: str) -> str:
    return f"FAKE_{suffix}_{version}_SHOULD_NOT_EXPORT"


FAKE_SEEDS = (
    _fake_seed("RC83", "SECRET_TOKEN"),
    _fake_seed("RC83", "NOVALI_SECRET"),
    _fake_seed("RC83", "API_KEY"),
    _fake_seed("RC83", "COOKIE"),
    _fake_seed("RC83_1", "SECRET_TOKEN"),
    _fake_seed("RC83_1", "NOVALI_SECRET"),
    _fake_seed("RC83_1", "API_KEY"),
    _fake_seed("RC83_1", "COOKIE"),
    _fake_seed("RC83_2", "SECRET_TOKEN"),
    _fake_seed("RC83_2", "NOVALI_SECRET"),
    _fake_seed("RC83_2", "API_KEY"),
    _fake_seed("RC83_2", "COOKIE"),
    _fake_seed("RC83_2", "OTEL_HEADER"),
    _fake_seed("RC84", "SECRET_TOKEN"),
    _fake_seed("RC84", "NOVALI_SECRET"),
    _fake_seed("RC84", "API_KEY"),
    _fake_seed("RC84", "COOKIE"),
    _fake_seed("RC84", "EXTERNAL_PAYLOAD_SECRET"),
)
SUSPICIOUS_ENTRY_PATTERNS = (
    re.compile(r"(^|/)\.env($|\.)", re.IGNORECASE),
    re.compile(r"(^|/)node_modules/", re.IGNORECASE),
    re.compile(r"(^|/)\.pytest_cache/", re.IGNORECASE),
    re.compile(r"(^|/)\.mypy_cache/", re.IGNORECASE),
    re.compile(r"(^|/)\.svelte-kit/", re.IGNORECASE),
    re.compile(r"(^|/)__pycache__/", re.IGNORECASE),
    re.compile(r"(^|/)space[_-]?engineers?/", re.IGNORECASE),
    re.compile(r"(^|/)(game_server|server_bridge|bridge_mod)/", re.IGNORECASE),
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _text_from_zip_member(package: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    if info.is_dir():
        return ""
    if info.file_size > 1_000_000:
        return ""
    if not info.filename.lower().endswith((".md", ".txt", ".json", ".yaml", ".yml", ".py", ".env", ".ps1", ".bat", ".mjs", ".js", ".ts", ".svelte")):
        return ""
    return package.read(info).decode("utf-8", errors="ignore")


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# rc84 Package Hygiene Summary",
            "",
            f"- Result: {summary.get('result', '<unknown>')}",
            f"- Zip path: {summary.get('zip_path', '<none>')}",
            f"- Entry count: {summary.get('entry_count', 0)}",
            f"- Zip bytes: {summary.get('zip_bytes', 0)}",
            f"- Baseline zip bytes: {summary.get('baseline_zip_bytes', 0)}",
            f"- Delta bytes vs rc83.2: {summary.get('delta_bytes', 0)}",
            f"- Suspicious entry count: {len(summary.get('suspicious_entries', []))}",
            f"- Forbidden hit count: {len(summary.get('forbidden_hits', []))}",
        ]
    )


def run_package_hygiene(
    *,
    zip_path: Path,
    baseline_zip_path: Path | None = None,
) -> dict[str, Any]:
    suspicious_entries: list[str] = []
    forbidden_hits: list[str] = []
    with zipfile.ZipFile(zip_path) as package:
        infos = package.infolist()
        for info in infos:
            if any(pattern.search(info.filename) for pattern in SUSPICIOUS_ENTRY_PATTERNS):
                suspicious_entries.append(info.filename)
            text = _text_from_zip_member(package, info)
            if not text:
                continue
            forbidden_hits.extend(scan_forbidden_strings([text], FAKE_SEEDS))
        entry_count = len(infos)
    zip_bytes = zip_path.stat().st_size
    baseline_zip_bytes = baseline_zip_path.stat().st_size if baseline_zip_path and baseline_zip_path.exists() else 0
    delta_bytes = zip_bytes - baseline_zip_bytes if baseline_zip_bytes else 0
    result = "success" if not suspicious_entries and not forbidden_hits else "failure"
    summary = {
        "schema_name": "novali_rc84_package_hygiene_summary_v1",
        "generated_at": _now_iso(),
        "result": result,
        "zip_path": str(zip_path),
        "entry_count": entry_count,
        "zip_bytes": zip_bytes,
        "baseline_zip_bytes": baseline_zip_bytes,
        "delta_bytes": delta_bytes,
        "suspicious_entries": sorted(set(suspicious_entries)),
        "forbidden_hits": sorted(set(forbidden_hits)),
    }
    artifact_root = resolve_rc84_artifact_root(ROOT)
    write_summary_artifacts(
        artifact_root=artifact_root,
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
        default=str(ROOT / "dist" / "novali-v6_rc84-standalone.zip"),
    )
    parser.add_argument(
        "--baseline-zip-path",
        default=str(ROOT / "dist" / "novali-v6_rc83_2-standalone.zip"),
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
