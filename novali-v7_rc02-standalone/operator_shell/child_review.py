"""Independent findings and one governed corrective episode per candidate lineage."""
from __future__ import annotations
import copy
from pathlib import Path
from typing import Any
from . import research_procedures as records
from .research_tools import digest, read_json, write_json


def latest(root: Path, candidate_id: str) -> dict[str, Any]:
    pointer=read_json(root/'research_methods/child_review_latest'/(candidate_id+'.json'))
    if not pointer: return {}
    reviewed=records.read(root,'child_reviews',pointer['review_id'])
    if reviewed.get('candidate_id')!=candidate_id: raise ValueError('child_review_target_mismatch')
    return reviewed


def review(root: Path, candidate_id: str, *, decision: str, reviewer: str,
           authority_reference: str, findings=None, finding_resolutions=None, method_decision: str = 'defer') -> dict[str, Any]:
    from . import directive_candidates as candidates, directive_obligations as obligations
    candidate=records.read(root,'child_candidates',candidate_id)
    if decision not in {'approve','reject','revise'} or not reviewer.strip() or not authority_reference.strip():
        raise ValueError('explicit_independent_child_review_required')
    if decision!='revise':
        if findings:
            from .child_review_findings import validate,scope
            if decision!='approve' or method_decision!='defer' or not isinstance(findings,list) or not 1<=len(findings)<=8:
                raise ValueError('unresolved_findings_require_revision_decision')
            for finding in findings:
                validate(finding)
                if scope(finding)!='method':raise ValueError('artifact_findings_require_revision_decision')
        return candidates._structural_review(root,candidate_id,decision=decision,reviewer=reviewer,authority_reference=authority_reference,
            finding_resolutions=finding_resolutions, method_decision=method_decision, method_findings=findings)
    obligations.assert_current(root,candidate['frozen'])
    if not isinstance(findings,list) or not 1<=len(findings)<=8: raise ValueError('bounded_actionable_review_findings_required')
    for finding in findings:
        from .child_review_findings import validate
        validate(finding)
    result=records.store(root,'child_reviews',{'candidate_id':candidate_id,'candidate_sha256':digest(candidate),
        'decision':'revise','findings':findings,'reviewer':reviewer,'authority_reference':authority_reference,
        'revision_root':candidate.get('revision_root') or candidate_id,
        'scope':'independent_findings_require_novali_authored_correction','canonical_promotion_authorized':False})
    write_json(root/'research_methods/child_review_latest'/(candidate_id+'.json'),{'review_id':result['id']})
    return result


def pending(root: Path, *, candidate_id: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    from . import directive_obligations as obligations, learning_episodes as episodes
    from .child_contracts import coverage
    from .learning_evidence import context as evidence_context
    spent={e.get('revision_root') for e in episodes._episodes(root) if e.get('revision_root')}
    result=[]; prepared={}; reviewed_patterns=evidence_context(root)
    for pointer in sorted((root/'research_methods/child_review_latest').glob('*.json')):
        if candidate_id and pointer.stem!=candidate_id: continue
        review_record=latest(root,pointer.stem)
        if review_record.get('decision')!='revise' or review_record['revision_root'] in spent: continue
        candidate=records.read(root,'child_candidates',pointer.stem)
        if digest(candidate)!=review_record['candidate_sha256']: raise ValueError('child_review_candidate_changed')
        try:
            obligations.assert_current(root,candidate['frozen'])
            parent=candidate['frozen']['parent_episode_id']
            if parent not in prepared: prepared[parent]=obligations.build(root,parent)
            frozen=copy.deepcopy(prepared[parent])
        except (ValueError,KeyError,OSError): continue
        for o in frozen['obligations']:
            o['eligible']=bool(o['eligible'] and coverage(candidate,o))
        if not any(o['eligible'] for o in frozen['obligations']): continue
        frozen.update(revision_root=review_record['revision_root'],revision_review=review_record,
            revision_candidate=candidate, reviewed_failure_patterns=reviewed_patterns)
        result.append(frozen)
        if limit and len(result)>=limit: break
    return result


def apply_attempts(root: Path, frozen: dict[str, Any]) -> dict[str, Any]:
    from . import learning_episodes as episodes
    from .child_contracts import coverage
    all_episodes=episodes._episodes(root)
    spent_revisions={e.get('revision_root') for e in all_episodes if e.get('revision_root')}
    for episode in all_episodes:
        previous=episode.get('frozen_child_inputs',{})
        if (previous.get('directive_id')!=frozen['directive_id'] or
                previous.get('substantive_source_sha256')!=frozen['substantive_source_sha256']): continue
        task=read_json(root/'research_methods/episode_tasks'/(episode['id']+'.json'))
        if task.get('state') not in {'awaiting_review','ready','waiting_for_preparation_repair','exhausted_no_candidate','deferred_without_candidate'}: continue
        selected=[]
        available_ids={o['id'] for o in previous['obligations'] if o['eligible']}
        for key in task.get('attempt_ids',[]):
            attempt=records.read(root,'attempts',key)
            response=attempt.get('response')
            if isinstance(response,dict) and isinstance(response.get('obligation_id'),str) and response['obligation_id'] in available_ids:
                selected.append({'response':response})
        previous_available=[o for o in previous['obligations'] if o['eligible']]
        offered=previous_available[:4] if previous.get('work_contract') else previous_available
        for o in frozen['obligations']:
            if not o['eligible']: continue
            matched=any(c['response'].get('obligation_id')==o['id'] or coverage(c,o) for c in selected)
            if not selected:
                matched=any(p['id']==o['id'] or not previous.get('work_contract') and p['adapter']==o['adapter'] for p in offered)
            if matched:
                reviewed=latest(root,task['candidate_id']) if task.get('candidate_id') else {}
                decision=reviewed.get('decision')
                reason={'approve':'accepted_structure_awaiting_verified_use','revise':'reviewed_correction_queued',
                        'reject':'rejected_requires_new_evidence'}.get(decision,'pending_independent_review' if task.get('candidate_id') else 'attempt_retained_requires_review')
                if decision=='approve':
                    uses=[read_json(p) for p in (root/'research_methods/child_consumption').glob('*.json')]
                    if any(u.get('candidate_id')==task.get('candidate_id') and u.get('review_id')==reviewed.get('id') and u.get('use')=='verified_resident_artifact_write' for u in uses):
                        reason='verified_artifact_consumed_method_refinement_pending' if reviewed.get('unresolved_findings') else 'verified_artifact_consumed'
                if decision=='revise' and reviewed.get('revision_root') in spent_revisions:reason='correction_attempt_retained_requires_outcome_review'
                o.update(eligible=False,blocked_reason=reason,candidate_id=task.get('candidate_id'),review_id=reviewed.get('id'))
    return frozen


def queue(root: Path) -> list[dict[str, Any]]:
    result=[]
    for path in sorted((root/'research_methods/child_candidates').glob('*.json')):
        candidate=records.read(root,'child_candidates',path.stem); reviewed=latest(root,path.stem)
        result.append({'candidate_id':path.stem,'directive_id':candidate['frozen']['directive_id'],
            'target_artifact':candidate['frozen']['target_artifact'],'decision':reviewed.get('decision','awaiting_review'),
            'review_id':reviewed.get('id'),'findings':reviewed.get('unresolved_findings') or reviewed.get('findings',[]),
            'method_approved':reviewed.get('method_approved',False),
            'revision_root':candidate.get('revision_root') or path.stem})
    return result


def return_for_correction(root: Path, candidate_id: str) -> dict[str, Any]:
    """Return an independently reviewed proposal within its original unused cap."""
    from . import learning_episodes as episodes, practice_transaction as transaction
    from .child_correction import active
    candidate=records.read(root,'child_candidates',candidate_id)
    episode_id=candidate['learning_episode_id']; review=latest(root,candidate_id)
    task_path=root/'research_methods/episode_tasks'/(episode_id+'.json')
    task=read_json(task_path)
    episode=records.read(root,'learning_episodes',episode_id)
    if not active(episode['frozen_child_inputs']) or review.get('decision')!='revise' or review.get('candidate_sha256')!=digest(candidate):
        raise ValueError('independent_current_revision_review_required')
    if task.get('correction_review_id')==review['id']:
        return task
    limits,account,account_path,_=episodes.practice_budget(root,task)
    if (task.get('candidate_id')!=candidate_id or task['state']!='awaiting_review' or account.get('inflight')
            or task['model_calls']>=limits['max_model_calls'] or account['usage']['tool_calls']+2+10+2>limits['max_tool_calls']
            or limits['max_compute_seconds']-account['usage']['compute_seconds']<=25):
        raise ValueError('unused_original_correction_and_review_budget_required')
    account['usage']['tool_calls']+=2
    task.update(state='ready',reviewed_candidate_id=candidate_id,correction_review_id=review['id'])
    task.pop('candidate_id',None);task.pop('request_id',None)
    receipt=records.store(root,'child_correction_returns',{'episode_id':episode_id,'candidate_id':candidate_id,
        'review_id':review['id'],'usage_after':account['usage'],'scientific_allowance_added':0})
    transaction.commit(root,task_path,account_path,task,account,receipt,kind='child_correction_returns')
    return task
