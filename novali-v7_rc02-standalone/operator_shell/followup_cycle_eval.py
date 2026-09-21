"""Frozen, reviewed Novali histories for production follow-up cycle evaluations."""
from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any
from . import question_failure_learning as failures, research_procedures as records
from .research_tools import artifact_path, read_json, write_json, digest


def capture(root: Path, review_ids: list[str]) -> dict[str, Any]:
    from .directive_obligations import assert_current
    result={}
    for review_id in review_ids:
        review=records.read(root,'question_failure_reviews',review_id)
        current=failures.basis(root,review['basis']['episode_id'])
        if any(current[k]!=review['basis'][k] for k in ('task_sha256','source','attempt_hashes')):
            raise ValueError('unchanged_reviewed_history_required')
        source=failures.followup_source(review,current);frozen=source['frozen']
        assert_current(root,frozen)
        adapter=source['obligation']['adapter']
        if adapter in result:raise ValueError('one_frozen_history_per_adapter')
        files={}
        contract=Path('conveyor/research/episodes')/frozen['parent_episode_id']/'contract.json'
        files[contract.as_posix()]=(root/contract).read_text(encoding='utf-8')
        for ref,sha in frozen['dependencies'].items():
            path=artifact_path(root,frozen['directive_id'],ref)
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('frozen_dependency_changed')
            files[path.relative_to(root).as_posix()]=raw.decode('utf-8')
        for aid in current['attempt_hashes']:
            path=Path('research_methods/attempts')/(aid+'.json')
            files[path.as_posix()]=(root/path).read_text(encoding='utf-8')
        result[adapter]={'source':source,'files':files,'review':review,
            'parent_usage':current['usage_retained'],'scope':'archived_Novali_authored_failure_no_supplied_solution'}
    if set(result)!={'record_extraction','evidence_binding'}:raise ValueError('both_followup_domains_required')
    return {'histories':result,'sha256':digest(result)}


def install(root: Path, frozen: dict[str, Any], adapter: str) -> dict[str, Any]:
    if digest(frozen['histories'])!=frozen['sha256']:raise ValueError('frozen_history_changed')
    history=frozen['histories'][adapter]
    for name,text in history['files'].items():
        path=(root/name).resolve()
        if not path.is_relative_to(root.resolve()):raise ValueError('owned_history_path_required')
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(text.encode('utf-8'))
    from .directive_obligations import assert_current
    assert_current(root,history['source']['frozen'])
    return history['source']
