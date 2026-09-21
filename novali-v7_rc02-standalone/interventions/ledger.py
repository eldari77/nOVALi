from __future__ import annotations

import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def intervention_data_dir() -> Path:
    state_root = str(os.environ.get("NOVALI_STATE_ROOT", "")).strip()
    path = Path(state_root) if state_root else Path(__file__).resolve().parents[1] / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def intervention_ledger_path() -> Path:
    path = intervention_data_dir() / "intervention_ledger.jsonl"
    if not path.exists():
        path.write_text("", encoding="utf-8")
    return path


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def load_ledger_entries() -> List[Dict[str, Any]]:
    path = intervention_ledger_path()
    entries: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        entries.append(json.loads(line))
    return entries


def load_latest_snapshots() -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for entry in load_ledger_entries():
        proposal_id = str(entry.get("proposal_id", ""))
        if not proposal_id:
            continue
        revision = int(entry.get("ledger_revision", 0))
        current_revision = int(latest.get(proposal_id, {}).get("ledger_revision", -1))
        if revision >= current_revision:
            latest[proposal_id] = entry
    return latest


def append_snapshot(
    proposal: Dict[str, Any],
    *,
    event_type: str,
    note: str = "",
) -> Dict[str, Any]:
    path = intervention_ledger_path()
    latest = load_latest_snapshots()
    proposal_id = str(proposal["proposal_id"])
    revision = int(latest.get(proposal_id, {}).get("ledger_revision", 0)) + 1
    snapshot = copy.deepcopy(proposal)
    snapshot["ledger_revision"] = int(revision)
    snapshot["ledger_event_type"] = str(event_type)
    snapshot["ledger_written_at"] = datetime.now(timezone.utc).isoformat()
    if note:
        snapshot["ledger_note"] = str(note)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, default=_json_default, sort_keys=True) + "\n")
    return snapshot
