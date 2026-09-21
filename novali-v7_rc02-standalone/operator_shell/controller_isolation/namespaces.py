from __future__ import annotations

from pathlib import Path

from .lane_registry import lane_namespace_root
from .schemas import ControllerLaneIdentity, LaneNamespace


def _relative_path(package_root: Path, target: Path) -> str:
    try:
        return target.resolve().relative_to(package_root.resolve()).as_posix()
    except ValueError:
        return target.as_posix()


def build_lane_namespace(package_root: str | Path, lane: ControllerLaneIdentity) -> LaneNamespace:
    package_root_path = Path(package_root).resolve()
    namespace_root = lane_namespace_root(package_root_path, lane.lane_id)
    return LaneNamespace(
        lane_id=lane.lane_id,
        lane_role=lane.lane_role,
        namespace_root=_relative_path(package_root_path, namespace_root),
        doctrine_path=_relative_path(package_root_path, namespace_root / "doctrine.json"),
        memory_path=_relative_path(package_root_path, namespace_root / "memory_summary.json"),
        summary_path=_relative_path(package_root_path, namespace_root / "summary.json"),
        intervention_path=_relative_path(package_root_path, namespace_root / "intervention_history.jsonl"),
        replay_review_path=_relative_path(package_root_path, namespace_root / "replay_review_ledger.jsonl"),
        review_path=_relative_path(package_root_path, namespace_root / "review_ledger.jsonl"),
    )


def ensure_lane_namespace(package_root: str | Path, lane: ControllerLaneIdentity) -> LaneNamespace:
    package_root_path = Path(package_root).resolve()
    namespace = build_lane_namespace(package_root_path, lane)
    for target in (
        package_root_path / namespace.namespace_root,
        package_root_path / namespace.doctrine_path,
        package_root_path / namespace.memory_path,
        package_root_path / namespace.summary_path,
        package_root_path / namespace.intervention_path,
        package_root_path / namespace.replay_review_path,
        package_root_path / namespace.review_path,
    ):
        target.parent.mkdir(parents=True, exist_ok=True)
    # Materialize the per-lane ledgers so proof packaging can copy lane-local
    # evidence even before a review or replay entry has been appended.
    for ledger_path in (
        package_root_path / namespace.intervention_path,
        package_root_path / namespace.replay_review_path,
        package_root_path / namespace.review_path,
    ):
        ledger_path.touch(exist_ok=True)
    return namespace
