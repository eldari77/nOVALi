"""Independently reviewed authoring repairs within existing rolling reservations.

Operator entry points configure and review require the research lease. The
planner cannot issue either receipt. Admission never modifies the old episode.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from . import learning_episodes as episodes, research_procedures as records
from .authoring_contract import diagnose
from .research_tools import digest, read_json, write_json


def configure(root: Path, *, authority_reference: str) -> dict[str, Any]:
    if not authority_reference.strip(): raise ValueError('explicit_authoring_recovery_authority_required')
    policy=records.store(root,'authoring_recovery_policies',{'enabled':True,'max_repairs_per_lineage':1,
        'authority_reference':authority_reference,'uses_existing_episode_reservations':True,'scientific_allowance_added':0})
    write_json(root/'research_methods/authoring_recovery_policy.json',{'policy_id':policy['id']})
    return policy


def policy(root: Path) -> dict[str, Any] | None:
    pointer=read_json(root/'research_methods/authoring_recovery_policy.json')
    return records.read(root,'authoring_recovery_policies',pointer['policy_id']) if pointer else None


def basis(root: Path, episode_id: str, *, repo_root: Path | None = None) -> dict[str, Any]:
    source=records.read(root,'learning_episodes',episode_id)
    task=read_json(root/'research_methods/episode_tasks'/(episode_id+'.json'))
    account=read_json(root/'research_methods/episode_accounts'/(episode_id+'.json'))
    if (source['family']!='planning' or task.get('state')!='awaiting_review' or account.get('inflight')
            or source.get('authoring_repair_review_id') or task.get('model_calls')!=source['reserved']['model_calls']
            or account.get('usage',{}).get('model_calls')!=task['model_calls']):
        raise ValueError('settled_exhausted_authoring_episode_required')
    inputs=episodes.frozen_planning_inputs(root,episode_id,repo_root=repo_root)
    attempts=[records.read(root,'attempts',aid) for aid in task['attempt_ids']]
    if (len(attempts)!=task['model_calls'] or any(a.get('learning_episode_id')!=episode_id or a.get('candidate_id')
            or a.get('evaluation_id') for a in attempts) or attempts[-1]['usage_after']!=account['usage']):
        raise ValueError('owned_failed_authoring_receipts_required')
    if source['implementation']==records.implementation(): raise ValueError('verified_changed_authoring_interface_required')
    diagnostic_inputs={**inputs,'prediction_correction_available':None}
    findings=[{'attempt_id':a['id'],'issues':diagnose(a['response'],diagnostic_inputs)} for a in attempts
              if isinstance(a.get('response'),dict) and 'planning_strategy' in a['response']]
    from .research_maintenance import planner_contract
    _,schema=planner_contract({'failure':{'family':'planning'},'inputs':diagnostic_inputs})
    repaired=all('prediction_correction' not in b['properties'] for b in schema['anyOf'])
    relevant=any(a['outcome'].get('error')=='evidence_linked_prediction_correction_required' for a in attempts)
    if not relevant or not repaired or not any(f['issues'] for f in findings):
        raise ValueError('matching_independently_checkable_authoring_repair_required')
    return {'source_episode_id':episode_id,'source_sha256':digest(source),'task_sha256':digest(task),
        'account_sha256':digest(account),'attempt_ids':task['attempt_ids'],'input_sha256':digest(inputs),
        'lineage_id':source.get('lineage_id',source['id']),'implementation':records.implementation(),
        'findings':findings,'proof':{'ineligible_correction_excluded':repaired,'diagnostic_replay_checked':True},
        'research_usage_is_not_admission_authority':True}


def propose(root: Path, episode_id: str, *, repo_root: Path | None = None) -> dict[str, Any]:
    return records.store(root,'authoring_repair_proposals',{'basis':basis(root,episode_id,repo_root=repo_root),
        'requires_independent_review':True,'scientific_allowance_added':0})


def review(root: Path, proposal_id: str, *, decision: str, reviewer: str, authority_reference: str,
           repo_root: Path | None = None) -> dict[str, Any]:
    if decision not in {'approve','reject'} or not reviewer.strip() or not authority_reference.strip():
        raise ValueError('explicit_independent_authoring_review_required')
    proposal=records.read(root,'authoring_repair_proposals',proposal_id)
    if basis(root,proposal['basis']['source_episode_id'],repo_root=repo_root)!=proposal['basis']:
        raise ValueError('authoring_repair_changed_reassessment_required')
    previous=[records.read(root,'authoring_repair_reviews',p.stem) for p in
              (root/'research_methods/authoring_repair_reviews').glob('*.json') if read_json(p).get('proposal_id')==proposal_id]
    if previous:
        if previous[0]['decision']!=decision:raise ValueError('authoring_repair_already_reviewed')
        return previous[0]
    return records.store(root,'authoring_repair_reviews',{'proposal_id':proposal_id,'proposal_sha256':digest(proposal),
        'decision':decision,'reviewer':reviewer,'authority_reference':authority_reference})


def validate_review(root: Path, review_id: str, *, repo_root: Path | None = None) -> dict[str, Any]:
    reviewed=records.read(root,'authoring_repair_reviews',review_id)
    proposal=records.read(root,'authoring_repair_proposals',reviewed['proposal_id'])
    if (reviewed['decision']!='approve' or reviewed['proposal_sha256']!=digest(proposal)
            or proposal['basis']!=basis(root,proposal['basis']['source_episode_id'],repo_root=repo_root)):
        raise ValueError('current_independent_authoring_repair_approval_required')
    return proposal


def admit(root: Path, review_id: str, *, now: float | None = None, repo_root: Path | None = None) -> dict[str, Any]:
    configured=policy(root); controls=read_json(root/'autonomy/status.json'); budget=episodes.policy(root)
    if not configured or not configured['enabled'] or not budget or not budget['enabled'] or controls.get('active') is not True or controls.get('emergency_stop'):
        raise ValueError('authoring_recovery_controls_blocked')
    proposal=validate_review(root,review_id,repo_root=repo_root); binding=proposal['basis']
    old=episodes._episodes(root)
    existing=next((e for e in old if e.get('authoring_repair_review_id')==review_id),None)
    if existing:return {'state':'admitted','episode_id':existing['id'],'review_id':review_id}
    if any(e.get('authoring_repair_review_id') and e.get('lineage_id')==binding['lineage_id'] for e in old):
        raise ValueError('authoring_repair_lineage_limit')
    stamp,date=episodes.admission_window(root,budget,now=now)
    if stamp<date:return {'state':'waiting_for_policy_window','not_before':date,'review_id':review_id,
                          'reason':'existing_daily_and_weekly_reservations_retained'}
    source=records.read(root,'learning_episodes',binding['source_episode_id'])
    inputs=copy.deepcopy(source['frozen_planning_inputs']); limits=budget['limits']
    episode=records.store(root,'learning_episodes',{'failure_id':source['failure_id'],'failure_key':source['failure_key'],
        'family':'planning','input_sha256':digest(inputs),'frozen_planning_inputs':inputs,'implementation':records.implementation(),
        'policy_id':budget['id'],'admitted_at':stamp,'repair_review_id':None,'authoring_repair_review_id':review_id,
        'authoring_recovery_policy_id':configured['id'],'source_episode_id':source['id'],'lineage_id':binding['lineage_id'],
        **{k:source[k] for k in ('experiment_lesson_id','followup_policy_id') if k in source},
        'reserved':{k:limits['episode_'+k] for k in ('model_calls','tool_calls','compute_seconds')},
        'validation_reserved_before_provider':True,'scientific_allowance_added':0})
    old_task=read_json(root/'research_methods/episode_tasks'/(source['id']+'.json'))
    last=records.read(root,'attempts',binding['attempt_ids'][-1])
    task={'learning_episode_id':episode['id'],'failure_id':source['failure_id'],'suite_id':'','state':'ready',
        'model_calls':0,'attempt_ids':[],'candidate_signatures':old_task['candidate_signatures'],
        'previous_strategy':inputs['previous_strategy'],'requires_strategy_hypothesis':True,
        'feedback':{'reason':'independently_reviewed_authoring_repair','field_issues':binding['findings'][-1]['issues'],
                    'previous_rejected_proposal':last['response'],'costs_retained':True},'grants_execution_authority':False}
    write_json(root/'research_methods/episode_tasks'/(episode['id']+'.json'),task)
    return {'state':'admitted','episode_id':episode['id'],'review_id':review_id}


def tick(root: Path, *, repo_root: Path | None = None) -> list[dict[str, Any]]:
    configured=policy(root)
    if not configured or not configured['enabled']:return []
    results=[]
    for p in sorted((root/'research_methods/authoring_repair_reviews').glob('*.json')):
        if read_json(p).get('decision')!='approve':continue
        try:row=admit(root,p.stem,repo_root=repo_root)
        except (ValueError,KeyError,OSError) as exc:row={'state':'parked','review_id':p.stem,'reason':str(exc)}
        target=root/'research_methods/authoring_recovery_tasks'/(p.stem+'.json')
        if row!=read_json(target):write_json(target,row)
        results.append(row)
    return results


def status(root: Path) -> dict[str, Any]:
    return {'policy':policy(root),'tasks':[read_json(p) for p in sorted((root/'research_methods/authoring_recovery_tasks').glob('*.json'))],
            'scientific_allowance_added':0}
