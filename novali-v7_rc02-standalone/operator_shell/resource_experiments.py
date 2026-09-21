"""Standing-policy production tests for Novali-authored planning strategies.

Each experiment reserves 30 calls and 1800 seconds before any provider action.
At most one is admitted per seven days, and a strategy signature is never retried
automatically. Separate processes exercise restart retention on every action.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from . import research_procedures as records, planner_resources as strategies
from .research_tools import read_json, write_json


def configure(root: Path, *, enabled: bool, authority_reference: str) -> dict[str, Any]:
    if type(enabled) is not bool or not authority_reference.strip(): raise ValueError('explicit_resource_experiment_policy_required')
    policy=records.store(root,'resource_policies',{'enabled':enabled,'authority_reference':authority_reference,
        'max_experiments_per_week':1,'model_calls_per_experiment':30,'compute_seconds_per_experiment':1800,
        'action_seconds':60,'automatic_independent_adoption':True})
    write_json(root/'research_methods/resource_policy_latest.json',{'policy_id':policy['id']})
    return policy


def policy(root: Path) -> dict[str, Any] | None:
    pointer=read_json(root/'research_methods/resource_policy_latest.json')
    return records.read(root,'resource_policies',pointer['policy_id']) if pointer else None


def experiments(root: Path) -> list[dict[str, Any]]:
    return [records.read(root,'resource_experiments',p.stem) for p in sorted((root/'research_methods/resource_experiments').glob('*.json'))]


def _directory(root: Path, experiment: dict[str, Any]) -> Path:
    return root/'research_methods/strategy_evaluations'/experiment['id']


def admission_forecast(root: Path, candidate_id: str | None = None, *, now: float | None = None) -> dict[str, Any]:
    """Read-only policy forecast; eligibility is rechecked before any reservation."""
    configured=policy(root); controls=read_json(root/'autonomy/status.json')
    result={'state':'blocked','not_before':None,'fresh_admission_checks_required':True,
        'scientific_allowance_added':0,'grants_execution_authority':False,
        'policy_id':configured['id'] if configured else None,
        'diagnostic_options':['local_preflight_measurements','prepare_candidate_for_later_validation']}
    if not configured or not configured['enabled'] or controls.get('active') is not True or controls.get('emergency_stop'):
        return {**result,'reason':'resource_experiment_controls_blocked'}
    previous=experiments(root);stamp=time.time() if now is None else now
    if type(stamp) not in (int,float) or not 0<stamp<10**12:return {**result,'reason':'valid_experiment_time_required'}
    if candidate_id:
        candidate=records.read(root,'planning_candidates',candidate_id);sig=strategies.signature(candidate['profile'])
        known=next((e for e in previous if e['strategy_signature']==sig),None)
        if known:
            task=read_json(root/'research_methods/resource_tasks'/(known['id']+'.json'))
            if task.get('state')=='blocked_requires_review':
                return {**result,'state':'blocked_requires_review','reason':task.get('feedback','resource_evaluation_requires_review'),
                    'experiment_id':known['id']}
            return {**result,'state':'already_evaluated' if task.get('state')=='completed' else 'already_reserved',
                'reason':'strategy_experiment_already_admitted','experiment_id':known['id']}
    if any(read_json(p).get('inflight') for p in (root/'research_methods/resource_tasks').glob('*.json')):
        return {**result,'reason':'unsettled_resource_experiment_requires_review'}
    if any(e['admitted_at']>stamp for e in previous):return {**result,'reason':'resource_experiment_clock_rollback'}
    if not records.context(root):return {**result,'reason':'reviewed_method_required_for_matched_comparison'}
    active=sorted(e['admitted_at']+7*86400 for e in previous if stamp-e['admitted_at']<7*86400)
    if len(active)>=configured['max_experiments_per_week']:
        return {**result,'state':'waiting_for_policy_window','reason':'resource_experiment_rolling_limit',
            'not_before':active[len(active)-configured['max_experiments_per_week']]}
    return {**result,'state':'eligible','reason':'standing_policy_window_open'}


def _queue(root: Path, candidate_id: str, forecast: dict[str, Any]) -> None:
    destination=root/'research_methods/resource_queue'/(candidate_id+'.json')
    record={'candidate_id':candidate_id,**forecast}
    if read_json(destination)!=record:write_json(destination,record)


def prepare(root: Path, candidate_id: str, *, now: float | None = None) -> dict[str, Any]:
    from . import production_planner_eval as evaluation
    from .method_learning import corrections_context
    from .provider_recovery import current_provider_identity
    configured=policy(root); status=read_json(root/'autonomy/status.json')
    if not configured or not configured['enabled'] or status.get('active') is not True or status.get('emergency_stop'):
        raise ValueError('resource_experiment_controls_blocked')
    candidate=records.read(root,'planning_candidates',candidate_id); signature=strategies.signature(candidate['profile'])
    attempts=[records.read(root,'attempts',p.stem) for p in (root/'research_methods/attempts').glob('*.json')]
    if not any(row.get('candidate_id')==candidate_id and isinstance(row.get('response'),dict)
               and row['response'].get('planning_strategy')==candidate['profile'] for row in attempts):
        raise ValueError('original_strategy_authorship_receipt_required')
    stamp=time.time() if now is None else now
    forecast=admission_forecast(root,candidate_id,now=stamp)
    if forecast['state']!='eligible':raise ValueError(forecast['reason'])
    methods=records.context(root)
    if not methods: raise ValueError('reviewed_method_required_for_matched_comparison')
    experiment=records.store(root,'resource_experiments',{'candidate_id':candidate_id,'strategy_signature':signature,
        'policy_id':configured['id'],'admitted_at':stamp,'reserved':{'model_calls':30,'compute_seconds':1800},
        'implementation':evaluation.fingerprint(),'parent_continuation_authorized':False})
    directory=_directory(root,experiment)
    evaluation.prepare(directory,methods[0],corrections_context(root),provider_identity=current_provider_identity(),
        planning_profile=candidate['profile'],prediction_contract=strategies.prediction_contract(candidate))
    write_json(root/'research_methods/resource_tasks'/(experiment['id']+'.json'),{'state':'ready','experiment_id':experiment['id'],'inflight':False})
    return experiment


def _feedback(root: Path, candidate_id: str, result: dict[str, Any], *, review: dict[str, Any] | None = None) -> None:
    """A failed experiment may inform only the remaining original authoring call."""
    experiment=next((e for e in experiments(root) if e['candidate_id']==candidate_id),None)
    diagnostics=strategies.cost_diagnostics(_directory(root,experiment)) if experiment else None
    for kind in ('tasks','episode_tasks'):
        for path in (root/'research_methods'/kind).glob('*.json'):
            task=read_json(path)
            if not task.get('request_id'): continue
            request=records.read(root,'requests',task['request_id'])
            if request.get('kind')!='planning_strategy_evaluation' or request.get('candidate_id')!=candidate_id: continue
            rejected=not review or review['decision']=='reject'
            task['feedback']={'reason':'independent_production_strategy_rejected' if rejected else 'independent_production_strategy_reviewed',
                'production_result':result,**({'hypothesis_result':review['hypothesis_result'],'method_decision':review['decision']} if review else {})}
            task['previous_strategy']=records.read(root,'planning_candidates',candidate_id)['profile']
            if diagnostics:task['feedback']['diagnostics']=diagnostics
            if rejected and task.get('model_calls',0)<2: task['state']='ready'
            write_json(path,task)


def tick(root: Path) -> dict[str, Any] | None:
    from . import production_planner_eval as evaluation
    configured=policy(root); status=read_json(root/'autonomy/status.json')
    if not configured or not configured['enabled'] or status.get('active') is not True or status.get('emergency_stop'): return None
    task=None
    for path in sorted((root/'research_methods/resource_tasks').glob('*.json')):
        row=read_json(path)
        if row['state']=='ready': task=row; break
    if task is None:
        for path in sorted((root/'research_methods/planning_candidates').glob('*.json')):
            try:
                forecast=admission_forecast(root,path.stem);_queue(root,path.stem,forecast)
                if forecast['state']!='eligible':continue
                e=prepare(root,path.stem)
                task=read_json(root/'research_methods/resource_tasks'/(e['id']+'.json'));break
            except (ValueError,KeyError,OSError) as exc:
                _queue(root,path.stem,{'state':'blocked_requires_review','reason':str(exc)[:300],
                    'not_before':None,'grants_execution_authority':False})
                continue
    if not task: return None
    path=root/'research_methods/resource_tasks'/(task['experiment_id']+'.json')
    e=records.read(root,'resource_experiments',task['experiment_id']); directory=_directory(root,e)
    try:
        if task.get('inflight'): raise ValueError('interrupted_resource_experiment_requires_review')
        if e['policy_id']!=configured['id'] or e['implementation']!=evaluation.fingerprint():
            raise ValueError('resource_experiment_inputs_changed')
        result=evaluation.summary(directory)
        if not result['complete']:
            task['inflight']=True;write_json(path,task)
            started=time.monotonic()
            try:
                subprocess.run([sys.executable,'-B','-m','scripts.evaluate_production_planner','--output',str(directory.resolve()),'--next'],
                    capture_output=True,text=True,check=True,timeout=75)
            finally:
                task['supervision_seconds']=task.get('supervision_seconds',0)+time.monotonic()-started
            task['inflight']=False
            result=evaluation.summary(directory)
        task['result']=result
        if result['complete']:
            review=strategies.review(root,e['candidate_id'],directory,reviewer='Frozen independent production evaluator',
                authority_reference=configured['authority_reference'])
            task.update(state='completed',review_id=review['id'],decision=review['decision'])
            _feedback(root,e['candidate_id'],result,review=review)
    except (ValueError,KeyError,OSError,subprocess.SubprocessError) as exc:
        task.update(state='blocked_requires_review',feedback=str(exc)[:500])
    write_json(path,task)
    _queue(root,e['candidate_id'],admission_forecast(root,e['candidate_id']))
    return task


def status(root: Path) -> dict[str, Any]:
    rows=experiments(root); calls=seconds=0
    for row in rows:
        account=read_json(_directory(root,row)/'state.json')
        calls+=account.get('usage',{}).get('model_calls',0)
        seconds+=account.get('usage',{}).get('compute_seconds',0)
    return {'policy':policy(root),'experiments':len(rows),'usage':{'model_calls':calls,'compute_seconds':seconds},
        'admission_forecast':admission_forecast(root),
        'queue':[read_json(p) for p in sorted((root/'research_methods/resource_queue').glob('*.json'))],
        'reserved_lifetime':{'model_calls':sum(r['reserved']['model_calls'] for r in rows),
            'compute_seconds':sum(r['reserved']['compute_seconds'] for r in rows)},'scientific_allowance_added':0}
