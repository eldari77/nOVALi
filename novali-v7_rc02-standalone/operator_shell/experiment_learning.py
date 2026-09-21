"""Evidence-conditioned method sequels, without reopening scientific research."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from . import learning_episodes as episodes, research_procedures as records
from .research_tools import digest, read_json, write_json


def configure(root: Path, *, enabled: bool, authority_reference: str) -> dict[str, Any]:
    if type(enabled) is not bool or not authority_reference.strip():
        raise ValueError('explicit_experiment_learning_policy_required')
    result = records.store(root,'experiment_learning_policies',{'enabled':enabled,
        'authority_reference':authority_reference,'max_followups_per_lineage':2,
        'requires_changed_strategy':True,'uses_existing_rolling_episode_limits':True,
        'scientific_allowance_added':0})
    write_json(root/'research_methods/experiment_learning_policy_latest.json',{'policy_id':result['id']})
    return result


def policy(root: Path) -> dict[str, Any] | None:
    pointer=read_json(root/'research_methods/experiment_learning_policy_latest.json')
    return records.read(root,'experiment_learning_policies',pointer['policy_id']) if pointer else None


def _evidence(root: Path, experiment_id: str) -> tuple[dict, dict, dict, Path]:
    from .production_planner_eval import _load, summary
    experiment=records.read(root,'resource_experiments',experiment_id)
    directory=root/'research_methods/strategy_evaluations'/experiment_id
    task=read_json(root/'research_methods/resource_tasks'/(experiment_id+'.json'))
    if task.get('state')!='completed' or task.get('inflight') or task.get('decision')!='reject':
        raise ValueError('completed_independently_rejected_experiment_required')
    review=records.read(root,'planning_reviews',task['review_id'])
    manifest,account=_load(directory); result=summary(directory)
    if (account.get('inflight') or not result['complete'] or review['decision']!='reject'
            or review['candidate_id']!=experiment['candidate_id'] or review['manifest_sha256']!=manifest['sha256']
            or review['implementation']!=manifest['implementation'] or review['result_sha256']!=digest(result)
            or task['result']!=result):
        raise ValueError('experiment_review_evidence_mismatch')
    candidate=records.read(root,'planning_candidates',experiment['candidate_id'])
    if manifest.get('planning_profile')!=candidate['profile']:
        raise ValueError('experiment_candidate_binding_changed')
    for case in manifest['cases']:
        source=(directory/case['directory']/'repo/notes.py').resolve()
        if not source.is_relative_to(directory.resolve()): raise ValueError('experiment_source_scope_changed')
        import hashlib
        if hashlib.sha256(source.read_bytes()).hexdigest()!=case['source_sha256']:
            raise ValueError('experiment_source_changed')
    return experiment,review,candidate,directory


def capture(root: Path, experiment_id: str) -> dict[str, Any]:
    from .planner_resources import cost_diagnostics
    experiment,review,candidate,directory=_evidence(root,experiment_id)
    old=next((records.read(root,'experiment_lessons',p.stem)
              for p in (root/'research_methods/experiment_lessons').glob('*.json')
              if read_json(p).get('experiment_id')==experiment_id),None)
    if old:
        validate_lesson(root,old['id']);return old
    attempts=[records.read(root,'attempts',p.stem) for p in (root/'research_methods/attempts').glob('*.json')]
    authored=next((a for a in attempts if a.get('candidate_id')==candidate['id'] and
        isinstance(a.get('response'),dict) and a['response'].get('planning_strategy')==candidate['profile']),None)
    if not authored or not authored.get('learning_episode_id'):
        raise ValueError('frozen_authoring_episode_required_for_experiment_learning')
    source=records.read(root,'learning_episodes',authored['learning_episode_id'])
    inputs=copy.deepcopy(source.get('frozen_planning_inputs'))
    if not inputs or digest(inputs)!=source['input_sha256']:
        raise ValueError('original_frozen_method_input_required')
    inputs['resource_feedback']=cost_diagnostics(directory)
    inputs['previous_strategy']=candidate['profile']
    inputs['constraint']='Isolated method diagnosis. Historical research inputs do not authorize parent execution. Propose a substantively changed strategy and falsifiable cost hypothesis.'
    lesson=records.store(root,'experiment_lessons',{'experiment_id':experiment_id,'review_id':review['id'],
        'review_sha256':digest(review),'source_episode_id':source['id'],
        'lineage_id':source.get('lineage_id',source['id']),'failure_id':candidate['failure_id'],
        'candidate_id':candidate['id'],'inputs':inputs,'input_sha256':digest(inputs),
        'parent_continuation_authorized':False,'scientific_allowance_added':0})
    write_json(root/'research_methods/experiment_learning_tasks'/(lesson['id']+'.json'),
        {'lesson_id':lesson['id'],'state':'pending_admission','grants_execution_authority':False})
    return lesson


def validate_lesson(root: Path, lesson_id: str) -> dict[str, Any]:
    lesson=records.read(root,'experiment_lessons',lesson_id)
    _,review,candidate,_=_evidence(root,lesson['experiment_id'])
    if (digest(review)!=lesson['review_sha256'] or candidate['id']!=lesson['candidate_id']
            or digest(lesson['inputs'])!=lesson['input_sha256']):
        raise ValueError('experiment_lesson_evidence_changed')
    return lesson


def admit(root: Path, lesson_id: str, *, now: float | None = None) -> dict[str, Any]:
    configured=policy(root); account_policy=episodes.policy(root); controls=read_json(root/'autonomy/status.json')
    if not configured or not configured['enabled'] or not account_policy or not account_policy['enabled'] or \
            controls.get('active') is not True or controls.get('emergency_stop'):
        raise ValueError('experiment_learning_controls_blocked')
    lesson=validate_lesson(root,lesson_id); previous=episodes._episodes(root)
    existing=next((e for e in previous if e.get('experiment_lesson_id')==lesson_id),None)
    if existing:return {'state':'admitted','episode_id':existing['id'],'lesson_id':lesson_id,'grants_execution_authority':False}
    family=[e for e in previous if e.get('lineage_id')==lesson['lineage_id']]
    if len(family)>=configured['max_followups_per_lineage']:
        raise ValueError('experiment_learning_lineage_limit')
    stamp,not_before=episodes.admission_window(root,account_policy,now=now)
    path=root/'research_methods/experiment_learning_tasks'/(lesson_id+'.json')
    if stamp<not_before:
        from .resource_experiments import admission_forecast
        result={'lesson_id':lesson_id,'state':'waiting_for_policy_window','not_before':not_before,
            'reason':'existing_daily_and_weekly_reservations_retained','grants_execution_authority':False,
            'production_forecast':admission_forecast(root,now=stamp)}
        if read_json(path)!=result:write_json(path,result)
        return result
    source=records.read(root,'learning_episodes',lesson['source_episode_id'])
    limits=account_policy['limits']; inputs=lesson['inputs']
    episode=records.store(root,'learning_episodes',{'failure_id':lesson['failure_id'],'failure_key':source['failure_key'],
        'family':'planning','experiment_lesson_id':lesson_id,'lineage_id':lesson['lineage_id'],
        'source_episode_id':source['id'],'input_sha256':digest(inputs),'frozen_planning_inputs':inputs,
        'implementation':records.implementation(),'policy_id':account_policy['id'],
        'followup_policy_id':configured['id'],'admitted_at':stamp,'repair_review_id':None,
        'reserved':{k:limits['episode_'+k] for k in ('model_calls','tool_calls','compute_seconds')},
        'validation_reserved_before_provider':True,'scientific_allowance_added':0})
    from .planner_resources import signature
    signatures={signature(inputs['previous_strategy'])}
    for e in [source,*family]:
        signatures.update(read_json(root/'research_methods/episode_tasks'/(e['id']+'.json')).get('candidate_signatures',[]))
    task={'learning_episode_id':episode['id'],'failure_id':lesson['failure_id'],'suite_id':'',
        'state':'ready','model_calls':0,'attempt_ids':[],'candidate_signatures':sorted(signatures),
        'previous_strategy':inputs['previous_strategy'],'requires_strategy_hypothesis':True,
        'feedback':{'reason':'independent_experiment_feedback_available','diagnostics':inputs['resource_feedback']},
        'grants_execution_authority':False}
    write_json(root/'research_methods/episode_tasks'/(episode['id']+'.json'),task)
    result={'lesson_id':lesson_id,'state':'admitted','episode_id':episode['id'],'grants_execution_authority':False}
    write_json(path,result)
    return result


def tick(root: Path) -> list[dict[str, Any]]:
    configured=policy(root)
    if not configured or not configured['enabled']:return []
    results=[]
    for path in sorted((root/'research_methods/resource_tasks').glob('*.json')):
        task=read_json(path)
        if task.get('state')!='completed' or task.get('decision')!='reject':continue
        try:
            lesson=capture(root,path.stem); results.append(admit(root,lesson['id']))
        except (ValueError,KeyError,OSError) as exc:
            result={'experiment_id':path.stem,'state':'blocked_requires_evidence_review','reason':str(exc)[:300]}
            destination=root/'research_methods/experiment_learning_blocks'/(path.stem+'.json')
            if read_json(destination)!=result:write_json(destination,result)
            results.append(result)
    return results


def status(root: Path) -> dict[str, Any]:
    tasks=[]
    for p in sorted((root/'research_methods/experiment_learning_tasks').glob('*.json')):
        row=read_json(p); episode_task=read_json(root/'research_methods/episode_tasks'/(row.get('episode_id','')+'.json'))
        tasks.append({**row,'episode_state':episode_task.get('state'),'review_request_id':episode_task.get('request_id'),
                      'executable':episode_task.get('state')=='ready'})
    from .authoring_recovery import status as recovery_status
    return {'policy':policy(root),'tasks':tasks,'authoring_recovery':recovery_status(root),
        'blocks':[read_json(p) for p in sorted((root/'research_methods/experiment_learning_blocks').glob('*.json'))],
        'scientific_allowance_added':0}
