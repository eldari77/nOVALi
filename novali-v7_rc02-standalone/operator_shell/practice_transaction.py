"""Durable, idempotent settlement across the task/account write boundary."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from .research_tools import digest, read_json, write_json
from . import research_procedures as records


def preparation_key(root: Path, task: dict[str, Any]) -> str:
    return digest({"implementation":records.implementation(),
        "measurement_id":task.get("measurement_id"),
        "policy":read_json(root/"research_methods/policy.json"),
        "application_policy":read_json(root/"research_methods/lesson_applicability_policy.json"),
        "evidence":{kind:sorted(p.stem for p in (root/"research_methods"/kind).glob("*.json"))
                    for kind in ("learning_evidence_reviews","hypothesis_decisions")}})


def _path(root: Path, task_path: Path) -> Path:
    return root / "research_methods/practice_settlements" / task_path.name


def recover(root: Path, task_path: Path, account_path: Path) -> bool:
    path = _path(root, task_path); journal = read_json(path)
    if not journal or journal.get("state") == "settled":
        return False
    if journal.get("sha256") != digest({k:v for k,v in journal.items() if k not in ("sha256","state")}):
        raise ValueError("practice_settlement_integrity_failure")
    if (journal["task_path"] != task_path.relative_to(root).as_posix()
            or journal["account_path"] != account_path.relative_to(root).as_posix()):
        raise ValueError("practice_settlement_owner_mismatch")
    receipt = records.read(root, journal["record_kind"], journal["record_id"])
    if digest(receipt) != journal["record_sha256"]:
        raise ValueError("practice_settlement_receipt_changed")
    for target, name in ((task_path,"task"), (account_path,"account")):
        current = read_json(target)
        if digest(current) not in (journal[name+"_before_sha256"], digest(journal[name])):
            raise ValueError("practice_settlement_state_changed")
    # The same receipt and monotonic final values are replayed after either write.
    write_json(task_path, journal["task"]); write_json(account_path, journal["account"])
    write_json(path, {**journal, "state":"settled"})
    return True


def commit(root: Path, task_path: Path, account_path: Path,
           task: dict[str, Any], account: dict[str, Any], record: dict[str, Any], *, kind: str) -> None:
    before_account = read_json(account_path)
    if any(account["usage"][k] < v for k,v in before_account["usage"].items()):
        raise ValueError("practice_settlement_usage_rollback")
    body = {"task_path":task_path.relative_to(root).as_posix(),
            "account_path":account_path.relative_to(root).as_posix(),
            "task_before_sha256":digest(read_json(task_path)), "account_before_sha256":digest(before_account),
            "task":task, "account":account, "record_kind":kind,
            "record_id":record["id"], "record_sha256":digest(record)}
    write_json(_path(root,task_path), {**body,"sha256":digest(body),"state":"pending"})
    recover(root,task_path,account_path)
