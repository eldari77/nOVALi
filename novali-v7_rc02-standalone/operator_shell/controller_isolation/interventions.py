from __future__ import annotations

import json
from pathlib import Path

from operator_shell.observability.redaction import redact_value

from .namespaces import ensure_lane_namespace
from .schemas import ControllerLaneIdentity, LaneInterventionHistory, LaneReplayReviewBinding


def append_lane_intervention_entry(
    package_root: str | Path,
    lane: ControllerLaneIdentity,
    *,
    event_type: str,
    review_status: str,
    summary: str,
) -> Path:
    namespace = ensure_lane_namespace(package_root, lane)
    path = Path(package_root).resolve() / namespace.intervention_path
    entry = LaneInterventionHistory(
        lane_id=lane.lane_id,
        event_type=event_type,
        review_status=review_status,
        summary_redacted=str(redact_value(summary, key="summary") or ""),
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry.to_dict(), sort_keys=True) + "\n")
    return path


def append_lane_replay_review_binding(
    package_root: str | Path,
    lane: ControllerLaneIdentity,
    *,
    binding_kind: str,
    artifact_id: str,
    artifact_path_hint: str,
    summary: str,
    review_binding: bool = False,
) -> Path:
    namespace = ensure_lane_namespace(package_root, lane)
    relative_path = namespace.review_path if review_binding else namespace.replay_review_path
    path = Path(package_root).resolve() / relative_path
    entry = LaneReplayReviewBinding(
        lane_id=lane.lane_id,
        binding_kind=binding_kind,
        artifact_id=artifact_id,
        artifact_path_hint=artifact_path_hint,
        summary_redacted=str(redact_value(summary, key="summary") or ""),
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry.to_dict(), sort_keys=True) + "\n")
    return path
