from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from operator_shell.observability.rc83 import load_json_file, write_summary_artifacts
from operator_shell.observability.redaction import redact_value

from .observation_replay import resolve_rc87_artifact_root
from .schemas import ObservationRollbackAnalysis

ROLLBACK_ANALYSES_DIRNAME = "rollback_analyses"
ROLLBACK_ANALYSIS_SUMMARY_FILENAME = "rollback_analysis_summary.json"
ROLLBACK_ANALYSIS_SUMMARY_MARKDOWN = "rollback_analysis_summary.md"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _redact_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): redact_value(value, key=str(key)) for key, value in payload.items()}


def resolve_rollback_analyses_root(
    package_root: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    return resolve_rc87_artifact_root(package_root, env=env) / ROLLBACK_ANALYSES_DIRNAME


def write_rollback_analysis(
    analysis: ObservationRollbackAnalysis,
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    root = resolve_rollback_analyses_root(package_root, env=env)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{analysis.rollback_analysis_id}.json"
    path.write_text(
        json.dumps(_redact_payload(analysis.to_dict()), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return str(path)


def summarize_rollback_analyses(
    *,
    package_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    artifact_root = resolve_rc87_artifact_root(package_root, env=env)
    analyses_root = resolve_rollback_analyses_root(package_root, env=env)
    analyses = []
    if analyses_root.exists():
        for path in sorted(analyses_root.glob("*.json")):
            payload = load_json_file(path)
            if payload:
                analyses.append(payload)
    latest = max(analyses, key=lambda item: str(item.get("created_at", "")), default={})
    ambiguity_count = sum(1 for item in analyses if bool(item.get("ambiguity_detected", False)))
    recovery_performed_count = sum(1 for item in analyses if bool(item.get("recovery_performed", False)))
    summary = {
        "schema_name": "novali_rc87_rollback_analysis_summary_v1",
        "generated_at": _now_iso(),
        "result": "success",
        "rollback_analysis_count": len(analyses),
        "ambiguity_count": ambiguity_count,
        "recovery_performed_count": recovery_performed_count,
        "latest_rollback_analysis_id": str(latest.get("rollback_analysis_id", "")).strip() or None,
        "latest_replay_packet_id": str(latest.get("replay_packet_id", "")).strip() or None,
        "latest_prior_good_snapshot_ref": str(latest.get("prior_good_snapshot_ref", "")).strip() or None,
        "latest_checkpoint_ref": str(latest.get("checkpoint_ref", "")).strip() or None,
        "analyses_root": str(analyses_root),
    }
    markdown = "\n".join(
        [
            "# rc87 Rollback Analysis Summary",
            "",
            f"- Rollback analysis count: {summary['rollback_analysis_count']}",
            f"- Ambiguity count: {summary['ambiguity_count']}",
            f"- Recovery-performed count: {summary['recovery_performed_count']}",
            f"- Latest rollback analysis id: {summary['latest_rollback_analysis_id'] or '<none>'}",
        ]
    )
    write_summary_artifacts(
        artifact_root=artifact_root,
        json_name=ROLLBACK_ANALYSIS_SUMMARY_FILENAME,
        markdown_name=ROLLBACK_ANALYSIS_SUMMARY_MARKDOWN,
        summary=summary,
        markdown=markdown,
    )
    return summary
