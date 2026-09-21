"""Charge automatic lesson review to its source episode's retained reservation."""
from __future__ import annotations
import math
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping
from .research_tools import read_json, write_json
from . import research_procedures as records


def retained_charges(root: Path, episode_id: str) -> list[dict[str, Any]]:
    return [row for p in (root/'research_methods/lesson_review_charges').glob('*.json')
            if (row:=records.read(root,'lesson_review_charges',p.stem))['source_episode_id']==episode_id]


@contextmanager
def charge(root: Path, episode: Mapping[str, Any]) -> Iterator[dict[str, Any]]:
    path=root/'research_methods/episode_accounts'/(episode['id']+'.json')
    account=read_json(path);caps=episode['reserved'];usage=account.get('usage',{})
    if (account.get('inflight') or set(usage)!=set(caps)
            or any(type(usage[k]) not in (int,float) or not math.isfinite(usage[k]) or usage[k]<0 for k in caps)
            or usage['tool_calls']+2>caps['tool_calls'] or usage['compute_seconds']+20>caps['compute_seconds']):
        raise ValueError('lesson_review_requires_unused_source_validation_reservation')
    usage['tool_calls']+=2
    account['inflight']={'kind':'lesson_numerical_review','failure_id':episode['failure_id'],
        'call':usage['model_calls'],'reserved_seconds':20}
    write_json(path,account);started=time.monotonic()
    receipt={'source_episode_id':episode['id'],'checks':2,'scientific_allowance_added':0}
    try:yield receipt
    finally:
        elapsed=time.monotonic()-started
        usage['compute_seconds']=round(usage['compute_seconds']+elapsed,4)
        account['inflight']=None;write_json(path,account)
        receipt.update(compute_seconds=elapsed,usage_after=dict(usage))
        receipt['charge_id']=records.store(root,'lesson_review_charges',dict(receipt))['id']
