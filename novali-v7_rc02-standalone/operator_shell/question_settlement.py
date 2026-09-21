"""Operator-only settlement of a durable rejected-question receipt after a crash.

No new calls or reservation. A narrowly checked repair can resume the original
remaining call, with immutable provenance and independently remeasured failure.
"""
from __future__ import annotations
import copy
from pathlib import Path
from typing import Any, Mapping
from . import research_procedures as records, learning_episodes as episodes, planner_resources
from .research_tools import digest,read_json,write_json
from .authoring_contract import prediction_issue
from .lesson_review_budget import charge


def validate(root: Path, episode: Mapping[str, Any], task: Mapping[str, Any]) -> bool:
    if not task.get('settlement_repair_id'):return False
    repair=records.read(root,'question_settlement_repairs',task['settlement_repair_id'])
    if (repair['episode_id']!=episode['id'] or repair['episode_sha256']!=digest(episode)
            or repair['implementation']!=records.implementation() or repair['attempt_id'] not in task['attempt_ids']):
        raise ValueError('question_settlement_repair_changed')
    attempt=records.read(root,'attempts',repair['attempt_id'])
    if digest(attempt)!=repair['attempt_sha256']:raise ValueError('question_settlement_attempt_changed')
    account=read_json(root/'research_methods/episode_accounts'/(episode['id']+'.json'))
    if any(account['usage'][k]<v for k,v in repair['usage_after'].items()):
        raise ValueError('question_settlement_usage_rollback')
    return True


def reconcile(root: Path, episode_id: str, attempt_id: str, *, reviewer: str,
              authority_reference: str, repo_root: Path | None = None) -> dict[str, Any]:
    if not reviewer.strip() or not authority_reference.strip():raise ValueError('explicit_settlement_review_required')
    episode=records.read(root,'learning_episodes',episode_id)
    path=root/'research_methods/episode_tasks'/(episode_id+'.json');task=read_json(path)
    if task.get('settlement_repair_id'):
        validate(root,episode,task)
        return records.read(root,'question_settlement_repairs',task['settlement_repair_id'])
    policy=episodes.policy(root);controls=read_json(root/'autonomy/status.json')
    if (not policy or not policy['enabled'] or policy['id']!=episode['policy_id']
            or controls.get('active') is not True or controls.get('emergency_stop')):
        raise ValueError('question_settlement_controls_blocked')
    current=records.implementation();old=episode['implementation']
    changed={name for name in current.keys()|old.keys() if current.get(name)!=old.get(name)}
    if changed-{'research_maintenance.py','research_procedures.py','learning_episodes.py','question_settlement.py'}:
        raise ValueError('question_settlement_requires_narrow_reviewed_implementation_repair')
    attempt=records.read(root,'attempts',attempt_id)
    account_path=root/'research_methods/episode_accounts'/(episode_id+'.json');account=read_json(account_path)
    inflight=account.get('inflight') or {};after=attempt['usage_after']
    if (episode.get('lesson_stage')!='question_authoring' or attempt.get('learning_episode_id')!=episode_id
            or attempt.get('failure_id')!=episode['failure_id'] or attempt.get('synthetic_setup')
            or attempt.get('authored_response',{}).get('intent')!='propose_question'
            or attempt.get('outcome',{}).get('error')!='strategy_preflight_prediction_not_met'
            or attempt.get('candidate_id') or attempt.get('evaluation_id')
            or attempt.get('provider_metadata',{}).get('provider_outcome')!='response_received'
            or attempt['call']!=task['model_calls'] or inflight.get('call')!=task['model_calls']
            or after['model_calls']!=account['usage']['model_calls'] or after['tool_calls']!=account['usage']['tool_calls']
            or any(not account['usage'][k]<=after[k]<=episode['reserved'][k] for k in after)
            or abs(after['compute_seconds']-account['usage']['compute_seconds']-attempt['compute_seconds'])>.001
            or attempt['compute_seconds']>inflight.get('reserved_seconds',0)+20):
        raise ValueError('durable_owned_completed_question_receipt_required')
    inputs=episodes.frozen_planning_inputs(root,episode_id,repo_root=repo_root)
    if attempt['planning_input_sha256']!=digest(inputs['planning_context']):raise ValueError('question_settlement_input_changed')
    proposal=records.store(root,'question_settlement_proposals',{'episode_id':episode_id,'attempt_id':attempt_id,
        'account_before':account,'task_before_sha256':digest(task),'usage_after_completed_call':after,
        'authority_reference':authority_reference,'scientific_allowance_added':0})
    # Settle verified completed work before independent review; failure leaves it parked.
    account.update(usage=copy.deepcopy(after),inflight=None);write_json(account_path,account)
    if attempt_id not in task['attempt_ids']:task['attempt_ids'].append(attempt_id)
    task.update(state='awaiting_review',feedback=copy.deepcopy(attempt['diagnostics']))
    task.pop('pending_prediction',None)
    task.pop('measurement_id',None)  # Old catalogs bind the old implementation; preserve their records.
    write_json(path,task)
    question=attempt['authored_response']['question']
    with charge(root,episode) as charged:
        measured=planner_resources.preflight_check(inputs['planning_context'],question['strategy'])
        hypothesis={**question['hypothesis'],'changed_fields':[k for k,v in
            {'instruction_mode':'full','excerpt_chars':4000,'command_scope':'all_executable'}.items() if question['strategy'][k]!=v]}
        if measured!=attempt['diagnostics']['assessment'] or not prediction_issue(hypothesis,measured):
            raise ValueError('question_settlement_independent_counterexample_mismatch')
    account=read_json(account_path)
    repair=records.store(root,'question_settlement_repairs',{'episode_id':episode_id,'episode_sha256':digest(episode),
        'attempt_id':attempt_id,'attempt_sha256':digest(attempt),'proposal_id':proposal['id'],
        'implementation':current,'reviewer':reviewer,'authority_reference':authority_reference,'charge':charged,
        'usage_after':account['usage'],'calls_added':0,'scientific_allowance_added':0,
        'scope':'settle_saved_question_rejection_and_resume_original_remainder_only'})
    task['settlement_repair_id']=repair['id']
    if (account['usage']['model_calls']<episode['reserved']['model_calls']
            and account['usage']['tool_calls']+2<=episode['reserved']['tool_calls']
            and account['usage']['compute_seconds']+21<episode['reserved']['compute_seconds']):task['state']='ready'
    write_json(path,task)
    return repair

def review_retry(root: Path, episode_id: str, *, reviewer: str, authority_reference: str,
                 repo_root: Path | None = None) -> dict[str, Any]:
    """Review one later, normally scheduled call after a proven nondispatch fault."""
    if not reviewer.strip() or not authority_reference.strip():raise ValueError('explicit_settlement_review_required')
    for path in (root/'research_methods/question_retry_reviews').glob('*.json'):
        row=records.read(root,'question_retry_reviews',path.stem)
        if row['source_episode_id']==episode_id:
            validate_retry(root,row['id'],repo_root=repo_root);return row
    episode=records.read(root,'learning_episodes',episode_id)
    task=read_json(root/'research_methods/episode_tasks'/(episode_id+'.json'))
    account=read_json(root/'research_methods/episode_accounts'/(episode_id+'.json'))
    policy=episodes.policy(root)
    if (not policy or not policy['enabled'] or policy['id']!=episode['policy_id']
            or episode.get('lesson_stage')!='question_authoring' or task.get('state')!='awaiting_review'
            or not task.get('settlement_repair_id') or account.get('inflight')
            or task['model_calls']!=episode['reserved']['model_calls'] or len(task['attempt_ids'])!=2):
        raise ValueError('exhausted_settled_question_repair_required')
    repair=records.read(root,'question_settlement_repairs',task['settlement_repair_id'])
    original=records.read(root,'attempts',repair['attempt_id'])
    failure=records.read(root,'attempts',task['attempt_ids'][-1])
    if (repair['episode_sha256']!=digest(episode) or repair['attempt_sha256']!=digest(original)
            or failure['learning_episode_id']!=episode_id or failure['call']!=task['model_calls']
            or failure['outcome'].get('error')!='frozen_planning_measurements_changed'
            or failure.get('authored_response') is not None or failure.get('response') is not None
            or failure.get('provider_metadata') or failure.get('raw_response')
            or failure.get('candidate_id') or failure.get('evaluation_id')
            or original.get('authored_response',{}).get('intent')!='propose_question'
            or any(account['usage'][k]<v for k,v in failure['usage_after'].items())):
        raise ValueError('verified_nondispatched_cache_fault_required')
    inputs=episodes.frozen_planning_inputs(root,episode_id,repo_root=repo_root)
    question=original['authored_response']['question']
    with charge(root,episode) as charged:
        measured=planner_resources.preflight_check(inputs['planning_context'],question['strategy'])
        if measured!=original['diagnostics']['assessment']:
            raise ValueError('retry_source_measurement_changed')
    return records.store(root,'question_retry_reviews',{'source_episode_id':episode_id,'source_episode_sha256':digest(episode),
        'source_attempt_ids':task['attempt_ids'],'lesson_review_id':episode['lesson_review_id'],
        'failed_attempt_id':failure['id'],'failed_attempt_sha256':digest(failure),
        'original_attempt_id':original['id'],'original_attempt_sha256':digest(original),
        'policy_id':policy['id'],'implementation':records.implementation(),'reviewer':reviewer,
        'authority_reference':authority_reference,'charge':charged,'source_usage_after':charged['usage_after'],
        'reserved':{'model_calls':1,'tool_calls':4,'compute_seconds':140},
        'admission':'next_existing_episode_window_and_rolling_caps','historical_charges_refunded':False,
        'scientific_allowance_added':0,'scope':'one_question_authoring_retry_after_verified_nondispatch_cache_fault'})


def _retry_source(root: Path, review_id: str, *, repo_root: Path | None = None) -> dict[str, Any]:
    review=records.read(root,'question_retry_reviews',review_id)
    episode=records.read(root,'learning_episodes',review['source_episode_id'])
    policy=episodes.policy(root)
    if (not policy or not policy['enabled']
            or policy['id']!=review['policy_id'] or digest(episode)!=review['source_episode_sha256']):
        raise ValueError('question_retry_review_changed')
    task=read_json(root/'research_methods/episode_tasks'/(episode['id']+'.json'))
    account=read_json(root/'research_methods/episode_accounts'/(episode['id']+'.json'))
    if (task['attempt_ids']!=review['source_attempt_ids'] or task['state']!='awaiting_review' or account.get('inflight')
            or any(account['usage'][k]<v for k,v in review['source_usage_after'].items())):
        raise ValueError('question_retry_source_changed')
    for prefix in ('original','failed'):
        if digest(records.read(root,'attempts',review[prefix+'_attempt_id']))!=review[prefix+'_attempt_sha256']:
            raise ValueError('question_retry_attempt_changed')
    episodes.frozen_planning_inputs(root,episode['id'],repo_root=repo_root)
    return review


def validate_retry(root: Path, review_id: str, *, repo_root: Path | None = None) -> dict[str, Any]:
    review=_retry_source(root,review_id,repo_root=repo_root)
    if review['implementation']==records.implementation():return review
    for path in (root/'research_methods/question_retry_revalidations').glob('*.json'):
        row=records.read(root,'question_retry_revalidations',path.stem)
        if (row['review_id']==review_id and row['review_sha256']==digest(review)
                and row['implementation']==records.implementation()):
            account=read_json(root/'research_methods/episode_accounts'/(review['source_episode_id']+'.json'))
            if any(account['usage'][k]<v for k,v in row['charge']['usage_after'].items()):
                raise ValueError('question_retry_revalidation_costs_missing')
            return review
    raise ValueError('question_retry_review_changed')


def revalidate_retry(root: Path, review_id: str, *, reviewer: str, authority_reference: str,
                     repo_root: Path | None = None) -> dict[str, Any]:
    if not reviewer.strip() or not authority_reference.strip():raise ValueError('explicit_settlement_review_required')
    review=_retry_source(root,review_id,repo_root=repo_root)
    if any(e.get('question_retry_review_id')==review_id for e in episodes._episodes(root)):
        raise ValueError('question_retry_already_admitted')
    for path in (root/'research_methods/question_retry_revalidations').glob('*.json'):
        row=records.read(root,'question_retry_revalidations',path.stem)
        if row['review_id']==review_id and row['implementation']==records.implementation():
            validate_retry(root,review_id,repo_root=repo_root);return row
    episode=records.read(root,'learning_episodes',review['source_episode_id'])
    original=records.read(root,'attempts',review['original_attempt_id'])
    inputs=episodes.frozen_planning_inputs(root,episode['id'],repo_root=repo_root)
    with charge(root,episode) as charged:
        measured=planner_resources.preflight_check(inputs['planning_context'],original['authored_response']['question']['strategy'])
        if measured!=original['diagnostics']['assessment']:raise ValueError('retry_source_measurement_changed')
    return records.store(root,'question_retry_revalidations',{'review_id':review_id,'review_sha256':digest(review),
        'implementation':records.implementation(),'charge':charged,'reviewer':reviewer,
        'authority_reference':authority_reference,'reserved_unchanged':review['reserved'],
        'admission_unchanged':review['admission'],'scientific_allowance_added':0,'calls_added':0})
