from __future__ import annotations

import json
from pathlib import Path

from operator_shell.observability.redaction import redact_value

from .namespaces import ensure_lane_namespace
from .schemas import ControllerLaneIdentity, LaneDoctrineArtifact


def build_doctrine_artifact(
    lane: ControllerLaneIdentity,
    *,
    doctrine_summary: str,
    allowed_scope: list[str] | None = None,
    forbidden_scope: list[str] | None = None,
) -> LaneDoctrineArtifact:
    return LaneDoctrineArtifact(
        lane_id=lane.lane_id,
        lane_role=lane.lane_role,
        doctrine_namespace=lane.doctrine_namespace,
        doctrine_summary_redacted=str(redact_value(doctrine_summary, key="doctrine_summary") or ""),
        allowed_scope=list(allowed_scope or ["mock_lane_status", "director_mediated_cross_lane_envelopes"]),
        forbidden_scope=list(
            forbidden_scope
            or ["authority_expansion", "live_external_mutation", "space_engineers_behavior"]
        ),
    )


def write_doctrine_artifact(
    package_root: str | Path,
    lane: ControllerLaneIdentity,
    artifact: LaneDoctrineArtifact,
) -> Path:
    namespace = ensure_lane_namespace(package_root, lane)
    path = Path(package_root).resolve() / namespace.doctrine_path
    path.write_text(json.dumps(artifact.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
