from __future__ import annotations

import json
from pathlib import Path

from operator_shell.observability.redaction import redact_value

from .namespaces import ensure_lane_namespace
from .schemas import ControllerLaneIdentity, LaneSummaryArtifact


def build_summary_artifact(
    lane: ControllerLaneIdentity,
    *,
    summary: str,
    continuity_note: str,
) -> LaneSummaryArtifact:
    return LaneSummaryArtifact(
        lane_id=lane.lane_id,
        summary_namespace=lane.summary_namespace,
        summary_redacted=str(redact_value(summary, key="summary") or ""),
        continuity_note=str(redact_value(continuity_note, key="continuity_note") or ""),
    )


def write_summary_artifact(
    package_root: str | Path,
    lane: ControllerLaneIdentity,
    artifact: LaneSummaryArtifact,
) -> Path:
    namespace = ensure_lane_namespace(package_root, lane)
    path = Path(package_root).resolve() / namespace.summary_path
    path.write_text(json.dumps(artifact.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
