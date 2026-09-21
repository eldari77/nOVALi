"""Independent semantic feedback spends only an existing unused reservation."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any
from . import research_procedures as records, question_semantics as semantics
from .research_tools import read_json, write_json, digest


def request(root: Path, question_id: str, *, reviewer: str, authority_reference: str,
            novelty_evidence: str, applicability_evidence: str,
            findings: list[dict[str, Any]]) -> dict[str, Any]:
    from .next_practice import policy
    from .learning_episodes import policy as shared_policy
    from .directive_obligations import assert_current
    from .lesson_review_budget import charge
    from .practice_experiments import FIELDS
    if any(not isinstance(v,str) or not 16 <= len(v) <= 1600 for v in
           (reviewer, authority_reference, novelty_evidence, applicability_evidence)):
        raise ValueError('independent_semantic_revision_review_required')
    allowed = (set(FIELDS) - {'input_scope'}) | semantics.KEYS | {'method','measurement'}
    from .question_focus import LEAVES
    allowed.update(p.lstrip('/') for p in LEAVES)
    if (not isinstance(findings,list) or not 1 <= len(findings) <= 10 or
        any(not isinstance(f,dict) or set(f) != {'path','code','guidance'} or
            f['path'] not in {'/'+k for k in allowed} or
            not isinstance(f['code'],str) or not 3 <= len(f['code']) <= 100 or
            not isinstance(f['guidance'],str) or not 16 <= len(f['guidance']) <= 480 for f in findings)):
        raise ValueError('bounded_field_specific_semantic_findings_required')
    q = records.read(root,'successor_questions',question_id)
    e = records.read(root,'learning_episodes',q['episode_id'])
    if e.get('authoring_contract') != 'practice_experiment_v2' or not e.get('partition_enabled'):
        raise ValueError('structured_partition_question_required')
    path = root/'research_methods/episode_tasks'/(e['id']+'.json'); task=read_json(path)
    pointer = root/'research_methods/successor_review_latest'/(question_id+'.json')
    previous = read_json(pointer)
    if previous:
        receipt=records.read(root,'successor_reviews',previous['review_id'])
        if receipt['decision']!='revise': raise ValueError('successor_review_is_terminal')
        # Recover only the original, unchanged pre-transition task after a crash.
        if digest(task)==receipt['task_before_sha256']: _apply(path,task,receipt)
        return receipt
    account=read_json(root/'research_methods/episode_accounts'/(e['id']+'.json'))
    usage=account.get('usage',{}); caps=e['reserved']
    if (task.get('state')!='awaiting_question_review' or task.get('question_id')!=question_id or
        task.get('semantic_revision_id') or account.get('inflight') or
        usage.get('model_calls',caps['model_calls'])>=caps['model_calls'] or
        usage.get('tool_calls',caps['tool_calls'])+6>caps['tool_calls'] or
        usage.get('compute_seconds',caps['compute_seconds'])+41>caps['compute_seconds']):
        raise ValueError('owned_question_with_unused_revision_reservation_required')
    if (not policy(root).get('enabled') or not shared_policy(root).get('enabled') or shared_policy(root)['id']!=e['policy_id']):
        raise ValueError('unchanged_enabled_question_and_shared_policies_required')
    assert_current(root,q['source']['frozen'])
    # The implementation transition is explicitly reviewed; old episode remains immutable.
    with charge(root,e):
        if policy(root).get('repair_contract'):
            from . import next_practice as questions, research_runtime as runtime
            from .question_repair import expand_findings,method_findings
            reviewed=copy.deepcopy(task)
            findings=expand_findings(findings,q['response'])
            if method_findings(q['response'].get('method')) and not any(f['path']=='/method' for f in findings):
                raise ValueError('method_transition_requires_explicit_review_finding')
            reviewed.update(focus_contract=policy(root).get('focus_contract'),repair_contract=policy(root)['repair_contract'],semantic_revision_id='pending-independent-review',
                feedback={'field_issues':findings})
            context=questions.project_context(questions.retry_context(root,e,reviewed,account))
            runtime.local_planner(runtime.load_policy(root)).preflight('successor_question',context)
        receipt=records.store(root,'successor_reviews',{
            'question_id':question_id,'episode_id':e['id'],'decision':'revise',
            'reviewer':reviewer,'authority_reference':authority_reference,
            'novelty_evidence':novelty_evidence,'applicability_evidence':applicability_evidence,
            'findings':copy.deepcopy(findings),'question_sha256':digest(q),
            'task_before_sha256':digest(task),'attempt_ids':task['attempt_ids'],
            'usage_before':usage,'reserved':caps,'policy_id':e['policy_id'],
            'successor_policy_id':policy(root)['id'],'original_successor_policy_id':e['successor_policy_id'],'implementation':records.implementation(),
            'semantic_contract':semantics.VERSION,'repair_contract':policy(root).get('repair_contract'),'focus_contract':policy(root).get('focus_contract'),'maximum_revisions':1,
            'scientific_allowance_added':0,'funding':'existing_unused_reservation_only'})
        write_json(pointer,{'review_id':receipt['id']})
    _apply(path,task,receipt)
    return receipt


def _apply(path: Path, task: dict[str, Any], receipt: dict[str, Any]) -> None:
    task.update(state='ready',semantic_revision_id=receipt['id'],
        repair_contract=receipt.get('repair_contract'),focus_contract=receipt.get('focus_contract'),
        semantic_contract=semantics.VERSION,revision_parent_question_id=receipt['question_id'],
        feedback={'reason':'independent_semantic_revision_required',
            'field_issues':receipt['findings'],'costs_retained':True})
    task.pop('question_id',None)
    write_json(path,task)


def compatible(root: Path, episode: dict[str, Any], task: dict[str, Any]) -> bool:
    from .next_practice import policy
    if not task.get('semantic_revision_id'): return False
    r=records.read(root,'successor_reviews',task['semantic_revision_id'])
    q=records.read(root,'successor_questions',r['question_id'])
    a=read_json(root/'research_methods/episode_accounts'/(episode['id']+'.json'))
    pointer=read_json(root/'research_methods/successor_review_latest'/(q['id']+'.json'))
    return bool(r['decision']=='revise' and r['episode_id']==episode['id'] and
        r['question_sha256']==digest(q) and r['implementation']==records.implementation() and
        r['reserved']==episode['reserved'] and r['policy_id']==episode['policy_id'] and
        r['original_successor_policy_id']==episode['successor_policy_id'] and r['successor_policy_id']==policy(root).get('id') and
        pointer.get('review_id')==r['id'] and
        set(r['attempt_ids'])<=set(task.get('attempt_ids',[])) and
        all(a.get('usage',{}).get(k,-1)>=v for k,v in r['usage_before'].items()))


def unchanged_findings(root: Path, task: dict[str, Any], response: dict[str, Any]) -> list[dict[str, Any]]:
    if not task.get('semantic_revision_id'): return []
    r=records.read(root,'successor_reviews',task['semantic_revision_id'])
    before=records.read(root,'successor_questions',r['question_id'])['response']
    from .question_quality import cosmetic_only
    from .question_focus import value_at
    from .question_feedback import retain_requirement
    return [retain_requirement(f, 'semantic_finding_unchanged')
        for f in r['findings'] if f.get('code')!='linked_measurement_review' and cosmetic_only(value_at(before,f['path']),value_at(response,f['path']))]
