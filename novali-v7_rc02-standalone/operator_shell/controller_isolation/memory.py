from __future__ import annotations

import json
from pathlib import Path

from operator_shell.observability.redaction import redact_value

from .namespaces import ensure_lane_namespace
from .schemas import ControllerLaneIdentity, LaneMemoryArtifact


def build_memory_artifact(
    lane: ControllerLaneIdentity,
    *,
    memory_summary: str,
    memory_items_count: int = 1,
) -> LaneMemoryArtifact:
    return LaneMemoryArtifact(
        lane_id=lane.lane_id,
        memory_namespace=lane.memory_namespace,
        memory_summary_redacted=str(redact_value(memory_summary, key="memory_summary") or ""),
        memory_items_count=max(0, int(memory_items_count)),
    )


def write_memory_artifact(
    package_root: str | Path,
    lane: ControllerLaneIdentity,
    artifact: LaneMemoryArtifact,
) -> Path:
    namespace = ensure_lane_namespace(package_root, lane)
    path = Path(package_root).resolve() / namespace.memory_path
    path.write_text(json.dumps(artifact.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
