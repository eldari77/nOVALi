"""Novali-authored complete partitions, funded and reviewed one batch at a time."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from . import research_procedures as records
from .research_tools import digest, read_json


def schema(choices: list[dict[str, Any]]) -> dict[str, Any]:
    fields = sorted({f for r in choices for f in r['obligation'].get('unit', {}).get('fields', [])})
    return {'type': 'array', 'minItems': 0, 'maxItems': 12 if fields else 0,
            'items': {'type': 'array', 'minItems': 1, 'maxItems': 12,
                      'items': {'type': 'string', **({'enum': fields} if fields else {})}}}


def validate(source: dict[str, Any], batches: Any) -> list[dict[str, Any]]:
    expected = source['obligation'].get('unit', {}).get('fields', [])
    issue = lambda code, **kw: [{'path': '/field_batches', 'code': code, **kw}]
    if not isinstance(batches, list) or len(batches) > 12:
        return issue('bounded_partition_required')
    if not batches: return []
    if source['obligation']['adapter'] != 'record_extraction' or not expected:
        return issue('partition_adapter_not_supported')
    if any(not isinstance(b, list) or not 1 <= len(b) <= 12 or
           any(not isinstance(f, str) for f in b) for b in batches):
        return issue('bounded_nonempty_field_batches_required')
    flat = [f for b in batches for f in b]
    if len(set(flat)) != len(flat) or set(flat) != set(expected):
        return issue('partition_must_cover_each_required_field_once',
                     missing=sorted(set(expected)-set(flat)), unexpected=sorted(set(flat)-set(expected)),
                     repeated=sorted({f for f in flat if flat.count(f)>1}))
    return []


def units(question: dict[str, Any]) -> list[dict[str, Any]]:
    source = question['source']; batches = question['response'].get('field_batches', [])
    findings = validate(source, batches)
    if findings: raise ValueError('invalid_reviewed_partition')
    if not batches: return []
    original = source['obligation']
    return [{**copy.deepcopy(original), 'id': 'obligation-' + digest(
                 ['question_partition_v1', question['id'], original['unit']['row_id'], sorted(batch)])[:24],
             'unit': {**original['unit'], 'fields': list(batch)}, 'eligible': True, 'blocked_reason': None,
             'partition_parent_obligation_id': original['id']} for batch in batches]


def progress(root: Path, question: dict[str, Any]) -> dict[str, Any]:
    from . import learning_episodes as episodes
    from .child_review import latest
    from .child_contracts import coverage
    uses = [records.read(root, 'child_consumption', p.stem)
            for p in (root/'research_methods/child_consumption').glob('*.json')]
    owned = [e for e in episodes._episodes(root) if e.get('successor_question_id') == question['id']]
    rows = []
    for unit in units(question):
        tried = [e for e in owned if e.get('question_partition_id') == unit['id']]
        consumed = False
        for episode in tried:
            task = read_json(root/'research_methods/episode_tasks'/(episode['id']+'.json'))
            if not task.get('candidate_id'): continue
            candidate = records.read(root, 'child_candidates', task['candidate_id'])
            reviewed = latest(root, candidate['id'])
            consumed |= bool(reviewed.get('decision') == 'approve' and coverage(candidate, unit) and
                any(u['candidate_id'] == candidate['id'] and u['review_id'] == reviewed['id'] and
                    u.get('use') == 'verified_resident_artifact_write' for u in uses))
        rows.append({'id': unit['id'], 'fields': unit['unit']['fields'],
                     'state': 'verified_consumed' if consumed else 'attempt_retained' if tried else 'eligible'})
    complete = [f for r in rows if r['state']=='verified_consumed' for f in r['fields']]
    expected = question['source']['obligation'].get('unit', {}).get('fields', [])
    return {'question_id': question['id'], 'batches': rows, 'completed_fields': complete,
            'remaining_fields': [f for f in expected if f not in complete],
            'original_obligation_complete': bool(rows and set(complete)==set(expected)),
            'scientific_progress_credited': False}


def pending(root: Path, question: dict[str, Any], reviewed: dict[str, Any]) -> list[dict[str, Any]]:
    from . import child_directive_learning as child
    original = question['source']['frozen']
    # Rebuild from real artifact bytes; prior reviewed addenda may have changed its hash.
    current = child.current(root, original['parent_episode_id'])
    if current['substantive_source_sha256'] != original['substantive_source_sha256']:
        return []
    if not any(o['id']==question['source']['obligation']['id'] for o in current['obligations']):
        return []
    state = progress(root, question)
    result = []
    for unit, row in zip(units(question), state['batches']):
        if row['state'] != 'eligible': continue
        frozen = copy.deepcopy(current)
        frozen.update(obligations=[unit], successor_review=reviewed,
                      accepted_practice_question=question['response'],
                      question_partition_id=unit['id'], partition_progress=state)
        result.append(frozen)
    return result


def annotate(root: Path, frozen: dict[str, Any]) -> None:
    for p in (root/'research_methods/successor_review_latest').glob('*.json'):
        reviewed = records.read(root, 'successor_reviews', read_json(p)['review_id'])
        if reviewed['decision'] != 'approve': continue
        question = records.read(root, 'successor_questions', reviewed['question_id'])
        source = question['source']
        if (not question['response'].get('field_batches') or
                source['frozen']['directive_id'] != frozen['directive_id'] or
                source['frozen']['substantive_source_sha256'] != frozen['substantive_source_sha256']): continue
        state = progress(root, question)
        for obligation in frozen['obligations']:
            if obligation['id'] != source['obligation']['id']: continue
            obligation.update(eligible=False, partition_progress=state,
                blocked_reason='partition_verified_consumed' if state['original_obligation_complete'] else 'partition_practice_in_progress')
