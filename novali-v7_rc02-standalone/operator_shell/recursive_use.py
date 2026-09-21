"""Persisted cached-work consumption and reviewed feedback into bounded practice."""
from __future__ import annotations
import copy
from pathlib import Path
from . import research_procedures as records,recursive_growth as growth,recursive_evaluator as evaluator
from . import recursive_practice_checks as checks
from .research_tools import digest,read_json


def consume(root: Path, candidate_id: str, case: dict, *, consumer_episode_id: str, operation_key: str) -> dict:
    """The consumer executes a reviewed method and reads the persisted artifact.

    This is cached-record work, not proof of external deployment or scientific
    improvement. Its actual consumer episode funds the checks, without new calls.
    """
    if not isinstance(operation_key,str) or not 8<=len(operation_key)<=160:raise ValueError('stable_consumer_operation_required')
    key=digest([consumer_episode_id,operation_key])
    existing=next((r for r in growth.rows(root,'recursive_use_outcomes') if r['operation_key_sha256']==key),None)
    if existing:
        if existing['candidate_id']!=candidate_id or existing['input_sha256']!=digest(case):raise ValueError('consumer_operation_binding_changed')
        return existing
    method=next((m for m in growth.methods(root) if m['id']==candidate_id),None)
    if not method:raise ValueError('independently_reviewed_current_method_required')
    candidate=records.read(root,'recursive_candidates',candidate_id)
    episode=records.read(root,'learning_episodes',consumer_episode_id)
    account=read_json(root/'research_methods/episode_accounts'/(consumer_episode_id+'.json'))
    if account.get('inflight'):raise ValueError('consumer_reservation_inflight')
    if any(r['operation_key_sha256']==key for r in growth.rows(root,'recursive_use_intents')):raise ValueError('uncertain_consumption_requires_reconciliation')
    records.store(root,'recursive_use_intents',{'operation_key_sha256':key,'candidate_id':candidate_id,
        'consumer_episode_id':consumer_episode_id,'input_sha256':digest(case)})
    from .lesson_review_budget import charge
    with charge(root,episode):
        output=evaluator.execute(method['strategy'],case)
        artifact=records.store(root,'recursive_use_artifacts',{'operation_key_sha256':key,'candidate_id':candidate_id,
            'input_sha256':digest(case),'output':output})
        persisted=records.read(root,'recursive_use_artifacts',artifact['id'])
        errors=evaluator.oracle(case,persisted['output'])
        parent=records.read(root,'learning_episodes',candidate['episode_id'])
        return records.store(root,'recursive_use_outcomes',{'operation_key_sha256':key,'candidate_id':candidate_id,
            'review_id':method['review_id'],'episode_id':consumer_episode_id,'source_episode_id':parent['id'],
            'root_episode_id':parent.get('root_episode_id',parent['id']),'case':case,'input_sha256':digest(case),
            'artifact_id':artifact['id'],'artifact_sha256':digest(persisted),'accepted':not errors,'errors':errors,
            'evaluator_sha256':evaluator.fingerprint(),'scope':'persisted_cached_record_consumer',
            'implementation':records.implementation(),'allowance_added':0})


def trace(strategy: dict, case: dict) -> dict:
    features={'selected_count':len(case['fields']),'absent_count':sum(k not in case['record'] for k in case['fields'])}
    matched=[]
    for i,rule in enumerate(strategy['rules']):
        yes=features[rule['feature']]>=rule['at_least'];matched.append({'rule':i,'matched':yes})
        if yes:break
    output=evaluator.execute(strategy,case)
    return {'scope':'observed_consumer_failure_not_acceptance','input':case,'features':features,
        'rule_trace':matched,'effective_operation':output['operation'],'output_slots':output['slots'],
        'errors':evaluator.oracle(case,output),**checks.rule_analysis(strategy)}


def compact_trace(diagnostic: dict) -> dict:
    result=copy.deepcopy(diagnostic)
    result['diagnostic_sha256']=digest(diagnostic)
    if len(result.get('errors',[]))>2:
        result['omitted_errors']=len(result['errors'])-2;result['errors']=result['errors'][:2]
    if len(result.get('output_slots',{}))>2:
        result['omitted_output_slots']=len(result['output_slots'])-2
        result['output_slots']=dict(list(result['output_slots'].items())[:2])
    return result


def verify(root: Path, outcome: dict) -> dict:
    if outcome['evaluator_sha256']!=evaluator.fingerprint():raise ValueError('consumer_evaluator_changed')
    artifact=records.read(root,'recursive_use_artifacts',outcome['artifact_id'])
    candidate=records.read(root,'recursive_candidates',outcome['candidate_id'])
    output=evaluator.execute(candidate['proposal']['strategy'],outcome['case'])
    errors=evaluator.oracle(outcome['case'],output)
    if digest(artifact)!=outcome['artifact_sha256'] or output!=artifact['output'] or errors!=outcome['errors'] or bool(errors)==outcome['accepted']:raise ValueError('consumer_evidence_replay_mismatch')
    return trace(candidate['proposal']['strategy'],outcome['case'])


def review(root: Path, outcome_id: str, *, decision: str, reviewer: str, evidence_reference: str) -> dict:
    if decision not in ('approve','reject') or min(len(reviewer),len(evidence_reference))<16:raise ValueError('independent_use_failure_review_required')
    old=next((r for r in growth.rows(root,'recursive_use_reviews') if r['outcome_id']==outcome_id),None)
    if old:
        if old['decision']!=decision:raise ValueError('immutable_use_review')
        return apply(root,old)
    outcome=records.read(root,'recursive_use_outcomes',outcome_id)
    if outcome['accepted']:raise ValueError('actual_consumer_failure_required')
    episode=records.read(root,'learning_episodes',outcome['episode_id'])
    from .lesson_review_budget import charge
    with charge(root,episode):
        diagnostic=verify(root,outcome)
        result=records.store(root,'recursive_use_reviews',{'outcome_id':outcome_id,'decision':decision,'reviewer':reviewer,
            'evidence_reference':evidence_reference,'diagnostic':diagnostic,'implementation':records.implementation(),
            'allowance_added':0})
        return apply(root,result)


def apply(root: Path, review: dict) -> dict:
    if review['decision']!='approve':return review
    outcome=records.read(root,'recursive_use_outcomes',review['outcome_id'])
    current=growth.active(root)
    if current.get('candidate_id')==outcome['candidate_id']:
        growth.rollback(root,expected_version_id=current['version_id'],reviewer=review['reviewer'],
            reason='Independently reproduced downstream failure: '+review['id'])
    old=next((r for r in growth.rows(root,'recursive_terminal_lessons') if r.get('use_review_id')==review['id']),None)
    if old:return review
    outcome=records.read(root,'recursive_use_outcomes',review['outcome_id'])
    candidate=records.read(root,'recursive_candidates',outcome['candidate_id'])
    parent=records.read(root,'learning_episodes',candidate['episode_id'])
    task=read_json(root/'research_methods/episode_tasks'/(parent['id']+'.json'))
    attempt=next(records.read(root,'attempts',a) for a in task['attempt_ids'] if records.read(root,'attempts',a).get('response')==candidate['proposal'])
    covered=checks.coverage(candidate['proposal'],parent['stage'])['covered_states']
    failure=records.store(root,'recursive_failure_reviews',{'episode_id':parent['id'],'attempt_id':attempt['id'],
        'decision':'close','origin':'independently_replayed_downstream_failure','use_review_id':review['id'],
        'original_prediction':candidate['proposal']['prediction'],'prior_proposal':candidate['proposal'],
        'root_episode_id':outcome['root_episode_id'],'followup_depth':2,'max_followups':2,
        'implementation':records.implementation(),'reviewed_at':0,'allowance_added':0})
    records.store(root,'recursive_terminal_lessons',{'episode_id':parent['id'],'review_id':failure['id'],
        'root_episode_id':outcome['root_episode_id'],'source_id':candidate['source_id'],
        'attempt_id':attempt['id'],'attempt_sha256':digest(attempt),'implementation':records.implementation(),
        'proposal':candidate['proposal'],'report':candidate['report'],'protected_states':covered,
        'unresolved':outcome['errors'],'retained_usage':read_json(root/'research_methods/episode_accounts'/(parent['id']+'.json'))['usage'],
        'available_focus':['rule_dispatch','state_encoding'],'scope':'reviewed_cached_consumer_failure',
        'use_outcome_id':outcome['id'],'use_review_id':review['id'],'allowance_added':0})
    return review


def add_findings(root: Path, episode: dict, proposal: dict, quality: dict) -> dict:
    if not episode.get('use_outcome_id'):return quality
    outcome=records.read(root,'recursive_use_outcomes',episode['use_outcome_id'])
    diagnostic=trace(proposal['strategy'],outcome['case'])
    if not diagnostic['errors']:return quality
    result=copy.deepcopy(quality);result['diagnostic']=diagnostic
    result['findings'].append({'path':'/strategy','requirement':'Repair the independently observed consumer failure and preserve previously correct work.'})
    return result


def scorecard(root: Path) -> dict:
    outcomes=growth.rows(root,'recursive_use_outcomes');methods={r['candidate_id'] for r in outcomes}
    return {'consumed_work':len(outcomes),'accepted_work':sum(r['accepted'] for r in outcomes),
        'reviewed_methods_used':len(methods),'failed_work':sum(not r['accepted'] for r in outcomes),
        'repeated_failures':len([r for r in outcomes if not r['accepted']])-len({(r['candidate_id'],digest(r['errors'])) for r in outcomes if not r['accepted']}),
        'comparative_advantage':'requires_frozen_equal_budget_longitudinal_evaluation','scope':'cached_record_consumption_only'}
