from __future__ import annotations

import json
from pathlib import Path

from .schemas import ControllerLaneIdentity, ControllerLaneRegistry

LANE_DEFINITIONS = (
    ("lane_director", "director", "Director lane"),
    ("lane_sovereign_good", "sovereign_good", "Sovereign good lane"),
    ("lane_sovereign_dark", "sovereign_dark", "Sovereign dark lane"),
)


def _relative_path(package_root: Path, target: Path) -> str:
    try:
        return target.resolve().relative_to(package_root.resolve()).as_posix()
    except ValueError:
        return target.as_posix()


def resolve_controller_isolation_data_root(package_root: str | Path) -> Path:
    return Path(package_root).resolve() / "data" / "controller_isolation"


def lane_namespace_root(package_root: str | Path, lane_id: str) -> Path:
    return resolve_controller_isolation_data_root(package_root) / lane_id


def build_lane_identity(
    package_root: str | Path,
    *,
    lane_id: str,
    lane_role: str,
    lane_display_name: str,
) -> ControllerLaneIdentity:
    package_root_path = Path(package_root).resolve()
    namespace_root = lane_namespace_root(package_root_path, lane_id)
    return ControllerLaneIdentity(
        lane_id=lane_id,
        lane_role=lane_role,
        lane_display_name=lane_display_name,
        namespace_root=_relative_path(package_root_path, namespace_root),
        doctrine_namespace=_relative_path(package_root_path, namespace_root / "doctrine.json"),
        memory_namespace=_relative_path(package_root_path, namespace_root / "memory_summary.json"),
        summary_namespace=_relative_path(package_root_path, namespace_root / "summary.json"),
        intervention_namespace=_relative_path(package_root_path, namespace_root / "intervention_history.jsonl"),
        replay_namespace=_relative_path(package_root_path, namespace_root / "replay_review_ledger.jsonl"),
        review_namespace=_relative_path(package_root_path, namespace_root / "review_ledger.jsonl"),
        telemetry_identity=f"controller_isolation:{lane_role}",
    )


def build_default_lane_registry(package_root: str | Path) -> ControllerLaneRegistry:
    return ControllerLaneRegistry(
        lanes=[
            build_lane_identity(
                package_root,
                lane_id=lane_id,
                lane_role=lane_role,
                lane_display_name=lane_display_name,
            )
            for lane_id, lane_role, lane_display_name in LANE_DEFINITIONS
        ]
    )


def write_lane_registry(package_root: str | Path, registry: ControllerLaneRegistry) -> Path:
    path = resolve_controller_isolation_data_root(package_root) / "lane_registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_lane_registry(package_root: str | Path) -> ControllerLaneRegistry:
    path = resolve_controller_isolation_data_root(package_root) / "lane_registry.json"
    if not path.exists():
        return build_default_lane_registry(package_root)
    payload = json.loads(path.read_text(encoding="utf-8"))
    lanes = [ControllerLaneIdentity(**lane_payload) for lane_payload in payload.get("lanes", [])]
    return ControllerLaneRegistry(lanes=lanes)
