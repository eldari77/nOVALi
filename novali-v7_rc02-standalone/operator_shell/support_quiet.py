"""Skip duplicate planning while retaining change-triggered and periodic routing."""
from __future__ import annotations

import time
from pathlib import Path

from .research_tools import digest, read_json, write_json

MAX_QUIET_SECONDS = 300


def input_signature(root: Path, observations: dict, charter: dict) -> str:
    try:
        return _input_signature(root, observations, charter)
    except (ValueError, OSError, TypeError, KeyError):
        return ""  # Uncertain cache inputs must run the full routing path.


def _input_signature(root: Path, observations: dict, charter: dict) -> str:
    from .conveyor import _support_tick_input_signature
    support = _support_tick_input_signature(root)
    if not support: return ""
    # Observations include health, current directive, readiness, dispatch and
    # long-run state. Only explicitly non-semantic timestamp/cadence keys drop.
    volatile = {"created_at", "updated_at", "checked_at", "observed_at", "generated_at", "loop_iteration"}
    def stable(value):
        if isinstance(value, dict): return {k:stable(v) for k,v in value.items() if k not in volatile}
        if isinstance(value, list): return [stable(v) for v in value]
        return value
    inputs = {}
    for relative in ("conveyor/research_policy.json", "conveyor/scheduler.json", "autonomy/charter.json",
                     "conveyor/research/latest.json", "autonomy/capability_registry.json"):
        path = Path(root) / relative
        inputs[relative] = digest(stable(read_json(path)))
    # New immutable capability, review, claim and evaluation records wake work.
    for directory in ("autonomy/capabilities", "autonomy/reviews", "conveyor/research/capability_requests", "theory/subjects", "research_feedback", "research_recovery", "research_methods"):
        paths = sorted((Path(root) / directory).rglob("*.json"))
        if len(paths) > 4096: return ""  # Unknown inventory falls through to normal routing.
        inputs[directory] = [(str(p.relative_to(root)), p.stat().st_size, p.stat().st_mtime_ns) for p in paths]
    return digest([support, stable(observations), charter, inputs])


def cached_wait(root: Path, signature: str) -> dict:
    if not signature: return {}
    try:
        record = read_json(Path(root) / "autonomy/support_quiet_latest.json")
    except (OSError, ValueError):
        return {}
    if type(record.get("checked_at_epoch")) not in (int, float): return {}
    age = time.time() - record.get("checked_at_epoch", 0)
    if record.get("routing_input_sha256") == signature and 0 <= age < MAX_QUIET_SECONDS:
        return record.get("wait", {})
    return {}


def remember_wait(root: Path, signature: str, waiting: dict) -> None:
    if not signature: return
    write_json(Path(root) / "autonomy/support_quiet_latest.json", {
        "routing_input_sha256": signature, "checked_at_epoch": time.time(), "wait": waiting,
        "max_quiet_seconds": MAX_QUIET_SECONDS, "grants_execution_authority": False})
