"""Durable operator review queue, bounded leases and non-authoritative shadowing."""
from __future__ import annotations
import copy
import time
from pathlib import Path
from . import research_procedures as records
from .research_tools import read_json,write_json,digest


def rows(root: Path, kind: str) -> list[dict]:
    return [records.read(root,kind,p.stem) for p in (root/'research_methods'/kind).glob('*.json')]


def lesson_current(root: Path, lesson: dict) -> bool:
    return lesson['implementation']==records.implementation() or any(
        r['lesson_id']==lesson['id'] and r['lesson_sha256']==digest(lesson) and r['implementation']==records.implementation()
        for r in rows(root,'recursive_lesson_revalidations'))


def revalidate(root: Path, lesson: dict) -> dict:
    """Caller charges and holds the research lease; no renewal is granted."""
    from . import recursive_evaluator as evaluator
    attempt=records.read(root,'attempts',lesson['attempt_id'])
    if digest(attempt)!=lesson['attempt_sha256']:raise ValueError('original_terminal_attempt_changed')
    episode=records.read(root,'learning_episodes',lesson['episode_id'])
    if episode['evaluator_sha256']!=evaluator.fingerprint():raise ValueError('original_evaluator_required')
    report=evaluator.evaluate(lesson['proposal'],episode['baseline']['strategy'],episode['seed'],episode['stage'])
    if report!=lesson['report']:raise ValueError('terminal_report_replay_mismatch')
    return records.store(root,'recursive_lesson_revalidations',{'lesson_id':lesson['id'],'lesson_sha256':digest(lesson),
        'implementation':records.implementation(),'report_sha256':digest(report),'allowance_added':0})


def transition(root: Path, episode_id: str, *, reviewer: str, evidence_reference: str, findings: list[str]) -> dict:
    """Only the existing unused call may move to the executable question contract."""
    from . import recursive_loop as loop,recursive_questions as executable
    from .lesson_review_budget import charge
    if min(len(reviewer),len(evidence_reference))<16 or not 1<=len(findings)<=4 or any(not isinstance(f,str) or not 8<=len(f)<=240 for f in findings):raise ValueError('explicit_transition_findings_required')
    prior=next((r for r in rows(root,'recursive_question_transitions') if r['episode_id']==episode_id and r['implementation']==records.implementation()),None)
    if prior:return apply_transition(root,prior)
    episode=records.read(root,'learning_episodes',episode_id);tp=root/'research_methods/episode_tasks'/(episode_id+'.json');task=read_json(tp)
    account=read_json(root/'research_methods/episode_accounts'/(episode_id+'.json'))
    if episode['family']!='recursive_question' or task['state']!='awaiting_recursive_question_review' or account.get('inflight') or not 0<task['model_calls']<2:raise ValueError('owned_pending_question_with_unused_call_required')
    if task['model_calls']!=account['usage']['model_calls']:raise ValueError('retained_question_account_required')
    question=records.read(root,'recursive_questions',task['question_id'])
    if question['episode_id']!=episode_id or question.get('contract')==executable.VERSION:raise ValueError('legacy_question_transition_required')
    with charge(root,episode):
        lesson=records.read(root,'recursive_terminal_lessons',episode['terminal_lesson_id']);revalidate(root,lesson)
        replay=loop.measure_question(question['proposal'],lesson,episode['available_focus'])
        if replay!=question['diagnostic']:raise ValueError('original_question_measurement_changed')
        result=records.store(root,'recursive_question_transitions',{'episode_id':episode_id,'episode_sha256':digest(episode),
            'question_id':question['id'],'implementation':records.implementation(),'contract':executable.VERSION,
            'usage_floor':copy.deepcopy(account['usage']),'attempt_ids':task['attempt_ids'],
            'reviewer':reviewer,'evidence_reference':evidence_reference,'findings':findings,'allowance_added':0})
        return apply_transition(root,result)


def apply_transition(root: Path, result: dict) -> dict:
    tp=root/'research_methods/episode_tasks'/(result['episode_id']+'.json');task=read_json(tp)
    if task.get('question_transition_id')==result['id']:return result
    if task['question_id']!=result['question_id']:raise ValueError('preserve_changed_question')
    task.update(state='ready',question_transition_id=result['id'],feedback={'independent_findings':result['findings']})
    write_json(tp,task);return result


def compatible(root: Path, episode: dict, task: dict) -> bool:
    if not task.get('question_transition_id'):return False
    record=records.read(root,'recursive_question_transitions',task['question_transition_id'])
    account=read_json(root/'research_methods/episode_accounts'/(episode['id']+'.json'))
    return bool(record['episode_id']==episode['id'] and record['episode_sha256']==digest(episode)
        and record['implementation']==records.implementation() and task['attempt_ids'][:len(record['attempt_ids'])]==record['attempt_ids']
        and all(account.get('usage',{}).get(k,-1)>=v for k,v in record['usage_floor'].items()))


def question_contract(root: Path, episode: dict) -> str:
    task=read_json(root/'research_methods/episode_tasks'/(episode.get('id','')+'.json'))
    if task.get('question_transition_id'):
        if not compatible(root,episode,task):raise ValueError('question_transition_binding_changed')
        return records.read(root,'recursive_question_transitions',task['question_transition_id'])['contract']
    return episode.get('question_contract','legacy_v1')


def pending(root: Path) -> list[dict]:
    result=[]
    states={'awaiting_recursive_question_review':('question','question_id','recursive_questions'),
        'awaiting_recursive_review':('method','candidate_id','recursive_candidates'),
        'awaiting_recursive_expansion_review':('expansion','expansion_request_id','recursive_expansion_requests')}
    for episode in rows(root,'learning_episodes'):
        task=read_json(root/'research_methods/episode_tasks'/(episode['id']+'.json'))
        if task.get('state') not in states:continue
        kind,key,folder=states[task['state']];target=records.read(root,folder,task[key])
        result.append({'kind':kind,'target_id':target['id'],'target_sha256':digest(target),'episode_id':episode['id']})
    for outcome in rows(root,'recursive_use_outcomes'):
        if outcome['accepted'] or any(r['outcome_id']==outcome['id'] for r in rows(root,'recursive_use_reviews')):continue
        result.append({'kind':'use_failure','target_id':outcome['id'],'target_sha256':digest(outcome),'episode_id':outcome['episode_id']})
    return result


def sync(root: Path, *, now: float | None=None) -> list[dict]:
    stamp=time.time() if now is None else now
    existing=rows(root,'recursive_review_items');result=[]
    for target in pending(root):
        found=next((r for r in existing if all(r[k]==v for k,v in target.items())),None)
        result.append(found or records.store(root,'recursive_review_items',{**target,'created_at':stamp,
            'due_at':stamp+86400,'owner_role':'independent_operator','automatic_approval_authority':False}))
    return result


def claim(root: Path, item_id: str, *, reviewer: str, now: float | None=None, ttl: int=900) -> dict:
    stamp=time.time() if now is None else now
    if len(reviewer)<16 or type(ttl) is not int or not 60<=ttl<=3600:raise ValueError('bounded_independent_review_lease_required')
    item=records.read(root,'recursive_review_items',item_id)
    if not any(all(t[k]==item[k] for k in t) for t in pending(root)):raise ValueError('review_target_no_longer_pending')
    pointer=root/'research_methods/review_claims'/(item_id+'.json');old=read_json(pointer)
    if old and old['expires_at']>stamp:
        if old['reviewer']!=reviewer:raise ValueError('review_owned_by_another_reviewer')
        return old
    result=records.store(root,'recursive_review_claims',{'item_id':item_id,'reviewer':reviewer,'claimed_at':stamp,
        'expires_at':stamp+ttl,'implementation':records.implementation(),'prior_claim_id':old.get('id')})
    write_json(pointer,result);return result


def decide(root: Path, claim_id: str, *, decision: str, evidence_reference: str, findings=None, now: float | None=None) -> dict:
    stamp=time.time() if now is None else now;lease=records.read(root,'recursive_review_claims',claim_id)
    item=records.read(root,'recursive_review_items',lease['item_id'])
    if read_json(root/'research_methods/review_claims'/(item['id']+'.json'))!=lease or stamp>=lease['expires_at'] or lease['implementation']!=records.implementation():raise ValueError('current_review_lease_required')
    previous=next((r for r in rows(root,'recursive_queue_decisions') if r['claim_id']==claim_id),None)
    if previous:
        if previous['decision']!=decision or previous['evidence_reference']!=evidence_reference or previous['findings']!=findings:raise ValueError('immutable_queue_decision')
        return previous
    intent_body={'claim_id':claim_id,'item_id':item['id'],'decision':decision,'evidence_reference':evidence_reference,'findings':findings}
    intent=next((r for r in rows(root,'recursive_queue_intents') if r['claim_id']==claim_id),None)
    if intent:
        if any(intent[k]!=v for k,v in intent_body.items()):raise ValueError('immutable_queue_intent')
    else:
        if not any(all(t[k]==item[k] for k in t) for t in pending(root)):raise ValueError('review_target_changed')
        records.store(root,'recursive_queue_intents',intent_body)
    args={'decision':decision,'reviewer':lease['reviewer'],'evidence_reference':evidence_reference}
    if item['kind']=='question':
        from .recursive_loop import review_question
        result=review_question(root,item['target_id'],findings=findings,**args)
    elif item['kind']=='method':
        from .recursive_growth import review
        result=review(root,item['target_id'],findings=findings,**args)
    elif item['kind']=='expansion':
        from .recursive_expansion import review
        result=review(root,item['target_id'],**args)
    else:
        from .recursive_use import review
        result=review(root,item['target_id'],**args)
    return records.store(root,'recursive_queue_decisions',{'claim_id':claim_id,'item_id':item['id'],'decision':decision,
        'evidence_reference':evidence_reference,'findings':findings,'review_id':result['id']})


def shadow(root: Path, item_id: str) -> dict:
    """Cheap candidate reviewer. It cannot call decide or issue authority."""
    item=records.read(root,'recursive_review_items',item_id)
    previous=next((r for r in rows(root,'recursive_shadow_reviews') if r['item_id']==item_id and r['implementation']==records.implementation()),None)
    if previous:return previous
    if not any(all(t[k]==item[k] for k in t) for t in pending(root)):raise ValueError('shadow_requires_pending_independent_review')
    from .lesson_review_budget import charge
    episode=records.read(root,'learning_episodes',item['episode_id'])
    with charge(root,episode):
        recommendation='abstain'
        if item['kind']=='question':
            question=records.read(root,'recursive_questions',item['target_id'])
            if question.get('contract')=='executable_question_v2':recommendation='approve'
        return records.store(root,'recursive_shadow_reviews',{'item_id':item_id,'recommendation':recommendation,
            'reviewer_version':'structured_contract_only_v1','implementation':records.implementation(),
            'limitation':'semantic_relevance_not_evaluated','approval_authority':False})


def status(root: Path, *, now: float | None=None) -> dict:
    stamp=time.time() if now is None else now;targets=pending(root);items=rows(root,'recursive_review_items')
    queue=[]
    for target in targets:
        item=next((r for r in items if all(r[k]==v for k,v in target.items())),None)
        lease=read_json(root/'research_methods/review_claims'/(item['id']+'.json')) if item else {}
        queue.append({**target,'item_id':item['id'] if item else None,'overdue':bool(item and stamp>item['due_at']),
            'reviewer':lease.get('reviewer') if lease.get('expires_at',0)>stamp else None})
    graded=[]
    for decision in rows(root,'recursive_queue_decisions'):
        for shadowed in rows(root,'recursive_shadow_reviews'):
            if shadowed['implementation']==records.implementation() and shadowed['item_id']==decision['item_id'] and decision['decision'] in ('approve','reject'):
                graded.append((shadowed['recommendation'],decision['decision']))
    return {'pending':queue,'automatic_approval_authority':False,'shadow_calibration':{'adjudicated':len(graded),
        'false_approvals':sum(a=='approve' and b=='reject' for a,b in graded),
        'false_rejections':sum(a=='reject' and b=='approve' for a,b in graded),
        'abstentions':sum(a=='abstain' for a,b in graded),'validated_for_authority':False}}
