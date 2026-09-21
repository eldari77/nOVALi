"""Renewable method practice with immutable admissions and rolling spend caps.

No policy or receipt resets historical usage. Admission reserves the whole
episode, including validation; repeated inputs cannot earn another episode.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Mapping

from . import research_procedures as records
from .research_tools import digest, read_json, write_json

DEFAULT_LIMITS = {'episode_model_calls':2, 'episode_tool_calls':26, 'episode_compute_seconds':280,
    'max_episodes_per_day':1, 'model_calls_per_week':6, 'tool_calls_per_week':78, 'compute_seconds_per_week':840}


def configure(root: Path, *, limits: dict[str, int], enabled: bool, authority_reference: str,
              admission_interval_seconds: int | None = None) -> dict[str, Any]:
    if (not authority_reference.strip() or type(enabled) is not bool or set(limits) != set(DEFAULT_LIMITS)
            or any(type(v) is not int or v < 1 for v in limits.values())):
        raise ValueError('explicit_typed_learning_episode_policy_required')
    if admission_interval_seconds is not None and (type(admission_interval_seconds) is not int
            or not 7200 <= admission_interval_seconds <= 86400):
        raise ValueError('bounded_typed_admission_interval_required')
    maxima = dict(zip(DEFAULT_LIMITS, (2,26,300,2,12,156,1800)))
    if admission_interval_seconds is not None:
        weekly_episodes = 7*86400 // admission_interval_seconds
        maxima.update(max_episodes_per_day=86400 // admission_interval_seconds,
            model_calls_per_week=weekly_episodes*2, tool_calls_per_week=weekly_episodes*26,
            compute_seconds_per_week=weekly_episodes*300)
    if any(limits[k] > maxima[k] for k in limits): raise ValueError('learning_episode_policy_exceeds_hard_ceiling')
    if limits['episode_tool_calls'] < limits['episode_model_calls']*13 or limits['episode_compute_seconds'] < limits['episode_model_calls']*140:
        raise ValueError('reserve_independent_validation_before_admission')
    policy = records.store(root,'episode_policies',{'limits':limits,'enabled':enabled,'authority_reference':authority_reference,
        **({'admission_interval_seconds':admission_interval_seconds} if admission_interval_seconds is not None else {})})
    write_json(root/'research_methods/episode_policy_latest.json', {'policy_id':policy['id']})
    return policy


def policy(root: Path) -> dict[str, Any] | None:
    pointer = read_json(root/'research_methods/episode_policy_latest.json')
    return records.read(root,'episode_policies',pointer['policy_id']) if pointer else None


def _episodes(root: Path) -> list[dict[str, Any]]:
    return [records.read(root,'learning_episodes',p.stem) for p in sorted((root/'research_methods/learning_episodes').glob('*.json'))]


def failure_key(failure: Mapping[str, Any]) -> str:
    rejected = failure.get('failed_command', {})
    if isinstance(rejected,dict): rejected = {k:v for k,v in rejected.items() if k not in {'name','rationale','why'}}
    return digest({'parent_id':failure['parent_id'], 'contract':failure['parent_contract_sha256'],
        'failure':failure['failure'], 'rejected':rejected})


def admission_window(root: Path, configured: Mapping[str, Any], *, now: float | None = None) -> tuple[float, float]:
    """Earliest admission under all policies' retained reservations; no writes."""
    stamp = time.time() if now is None else now
    if type(stamp) not in (int,float) or not 0 < stamp < 10**12:
        raise ValueError('valid_admission_time_required')
    episodes = _episodes(root); limits = configured['limits']
    if any(e['admitted_at']>stamp for e in episodes): raise ValueError('learning_clock_rollback')
    if any(read_json(root/'research_methods/episode_accounts'/(e['id']+'.json')).get('inflight') for e in episodes):
        raise ValueError('unsettled_learning_episode_requires_review')
    interval = configured.get('admission_interval_seconds')
    if interval is not None and (type(interval) is not int or not 7200 <= interval <= 86400):
        raise ValueError('bounded_typed_admission_interval_required')
    cadence_boundary = max((e['admitted_at']+interval for e in episodes),default=stamp) if interval else stamp
    boundaries = sorted({stamp,max(stamp,cadence_boundary),*[e['admitted_at']+period for e in episodes for period in (86400,7*86400)
                                if e['admitted_at']+period>stamp]})
    for point in boundaries:
        if point<cadence_boundary: continue
        if sum(point-e['admitted_at']<86400 for e in episodes)>=limits['max_episodes_per_day']: continue
        week = [e for e in episodes if point-e['admitted_at']<7*86400]
        if all(sum(e['reserved'][field] for e in week)+limits['episode_'+field]<=limits[key]
               for field,key in [('model_calls','model_calls_per_week'),('tool_calls','tool_calls_per_week'),
                                 ('compute_seconds','compute_seconds_per_week')]): return stamp,point
    raise ValueError('learning_policy_cannot_fund_one_episode')


def admit(root: Path, task: Mapping[str, Any], *, repo_root: Path | None = None, now: float | None = None) -> dict[str, Any]:
    from .research_maintenance import _inputs
    configured = policy(root); status = read_json(root/'autonomy/status.json')
    if not configured or not configured['enabled'] or status.get('active') is not True or status.get('emergency_stop'):
        raise ValueError('learning_episode_controls_blocked')
    failure = records.read(root,'failures',task['failure_id'])
    family = failure['failure_family']
    if family not in {'dependency','measurement','planning'}: raise ValueError('matching_independent_evaluator_required')
    inputs = _inputs(root,failure,repo_root=repo_root)
    if not inputs: raise ValueError('substantive_learning_input_required')
    key = failure_key(failure); episodes = _episodes(root)
    if any(e['failure_key'] == key for e in episodes): raise ValueError('unchanged_failure_episode_already_admitted')
    # A consumed legacy attempt also counts. A reviewed repair is required to
    # revisit it; source/interface timestamps and changed names are insufficient.
    prior = []
    for p in (root/'research_methods/attempts').glob('*.json'):
        row = records.read(root,'attempts',p.stem)
        old = records.read(root,'failures',row['failure_id'])
        if failure_key(old) == key: prior.append(row)
    repair_review = None
    if prior:
        for p in (root/'research_methods/repair_reviews').glob('*.json'):
            review = records.read(root,'repair_reviews',p.stem)
            proposal = records.read(root,'repair_proposals',review['proposal_id'])
            basis = proposal['basis']
            if (review['decision']=='approve' and basis['parent_id']==failure['parent_id']
                    and basis['implementation']==records.implementation()): repair_review = review['id']
        if not repair_review: raise ValueError('changed_input_or_independently_verified_repair_required')
    stamp,not_before = admission_window(root,configured,now=now)
    if stamp<not_before: raise ValueError('learning_daily_or_rolling_admission_limit')
    limits = configured['limits']
    episode = records.store(root,'learning_episodes',{'failure_id':failure['id'],'failure_key':key,
        'family':family,'input_sha256':digest(inputs),'implementation':records.implementation(),
        'frozen_planning_inputs':inputs if family=='planning' else None,
        'policy_id':configured['id'],'admitted_at':stamp,'repair_review_id':repair_review,
        'reserved':{k:limits['episode_'+k] for k in ('model_calls','tool_calls','compute_seconds')},
        'validation_reserved_before_provider':True,'scientific_allowance_added':0})
    suite = records.freeze_suite(root,family) if family in {'dependency','measurement'} else {}
    state = {'learning_episode_id':episode['id'], 'failure_id':failure['id'],'suite_id':suite.get('id',''),
        'state':'ready','model_calls':0,'attempt_ids':[],'candidate_signatures':[], 'feedback':{},'grants_execution_authority':False}
    write_json(root/'research_methods/episode_tasks'/(episode['id']+'.json'),state)
    return episode


def frozen_planning_inputs(root: Path, episode_id: str, *, repo_root: Path | None = None) -> dict[str, Any]:
    from .theory_workspace import TheoryWorkspace
    episode=records.read(root,'learning_episodes',episode_id)
    inputs=episode.get('frozen_planning_inputs')
    if episode['family']!='planning' or not inputs or digest(inputs)!=episode['input_sha256']:
        raise ValueError('frozen_planning_input_integrity_failure')
    if episode.get('experiment_lesson_id'):
        from .experiment_learning import validate_lesson
        validate_lesson(root,episode['experiment_lesson_id'])
    if episode.get('authoring_repair_review_id'):
        from .authoring_recovery import validate_review
        validate_review(root,episode['authoring_repair_review_id'],repo_root=repo_root)
    if episode.get('lesson_review_id'):
        from .lesson_practice import validate_review as validate_lesson_review
        validate_lesson_review(root,episode['lesson_review_id'],repo_root=repo_root)
    if episode.get('question_retry_review_id'):
        from .question_settlement import validate_retry
        validate_retry(root,episode['question_retry_review_id'],repo_root=repo_root)
    failure=records.read(root,'failures',episode['failure_id'])
    ws=TheoryWorkspace(root,failure['theory_subject_id'],repo_root=repo_root)
    ws.assert_current_sources()
    if ws._snapshot()['snapshot_id']!=failure['source_snapshot_id']: raise ValueError('planning_source_snapshot_changed')
    return inputs


def practice_budget(root: Path, task: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], Path, Path]:
    episode = records.read(root,'learning_episodes',task['learning_episode_id']); configured = policy(root)
    if any(records.read(root,'episode_interruptions',p.stem)['episode_id']==episode['id']
           for p in (root/'research_methods/episode_interruptions').glob('*.json')):
        raise ValueError('interrupted_episode_requires_review')
    from .question_settlement import validate as validate_settlement
    from .question_revision import compatible as semantic_revision_compatible
    from .next_practice import preparation_compatible
    from .recursive_growth import revision_compatible as recursive_revision_compatible
    from .recursive_review_queue import compatible as recursive_question_compatible
    implementation_current=(episode['implementation']==records.implementation() or validate_settlement(root,episode,task)
                            or preparation_compatible(root,episode,task) or semantic_revision_compatible(root,episode,task)
                            or recursive_revision_compatible(root,episode,task) or recursive_question_compatible(root,episode,task))
    if task.get('semantic_revision_id'):
        implementation_current = semantic_revision_compatible(root,episode,task)
    if (not configured or not configured['enabled'] or configured['id'] != episode['policy_id']
            or not implementation_current or episode['failure_id'] != task['failure_id']):
        raise ValueError('learning_episode_policy_or_implementation_changed')
    if episode.get('experiment_lesson_id'):
        from .experiment_learning import policy as followup_policy
        followup = followup_policy(root)
        if not followup or not followup['enabled'] or followup['id']!=episode['followup_policy_id']:
            raise ValueError('experiment_learning_policy_changed')
    caps = episode['reserved']
    if episode.get('authoring_repair_review_id'):
        from .authoring_recovery import policy as recovery_policy
        repair_policy=recovery_policy(root)
        if not repair_policy or not repair_policy['enabled'] or repair_policy['id']!=episode['authoring_recovery_policy_id']:
            raise ValueError('authoring_recovery_policy_changed')
    limits = {'enabled':True,'max_model_calls':caps['model_calls'],'max_tool_calls':caps['tool_calls'],
        'max_compute_seconds':caps['compute_seconds'],'max_calls_per_task':caps['model_calls'],'model_timeout_seconds':120}
    path = root/'research_methods/episode_accounts'/(episode['id']+'.json')
    account = read_json(path)
    if not account:
        if task['model_calls'] or task['attempt_ids']: raise ValueError('missing_episode_account_with_retained_costs')
        account = {'usage':{'model_calls':0,'tool_calls':0,'compute_seconds':0.0},'inflight':None,
            'limits':{k:v for k,v in limits.items() if k!='enabled'}}
    if account.get('limits') != {k:v for k,v in limits.items() if k!='enabled'}:
        raise ValueError('learning_episode_limits_changed')
    usage = account.get('usage',{})
    if (set(usage)!=set(caps) or any(type(usage[k]) not in (int,float) or not 0<=usage[k]<10**12 for k in caps)
            or any(type(usage[k]) is not int for k in ('model_calls','tool_calls'))):
        raise ValueError('invalid_episode_usage')
    for p in (root/'research_methods/attempts').glob('*.json'):
        attempt = records.read(root,'attempts',p.stem)
        if attempt.get('learning_episode_id') == episode['id'] and any(usage[k] < v for k,v in attempt['usage_after'].items()):
            raise ValueError('learning_episode_usage_rollback')
    if usage['model_calls'] != task['model_calls']: raise ValueError('learning_episode_call_projection_changed')
    for p in (root/'research_methods/preparation_attempts').glob('*.json'):
        row=records.read(root,'preparation_attempts',p.stem)
        if row.get('learning_episode_id')==episode['id'] and any(usage[k]<v for k,v in row['usage_after'].items()):
            raise ValueError('preparation_usage_rollback')
    from .lesson_review_budget import retained_charges
    if any(usage[k]<v for row in retained_charges(root,episode['id']) for k,v in row['usage_after'].items()):
        raise ValueError('lesson_review_usage_rollback')
    return limits,account,path,root/'research_methods/episode_tasks'/(episode['id']+'.json')


def status(root: Path) -> dict[str, Any]:
    from .recursive_growth import status as recursive_status
    episodes = _episodes(root)
    cumulative = {k:0 for k in ('model_calls','tool_calls','compute_seconds')}
    reserved = dict(cumulative)
    for e in episodes:
        for k,v in e['reserved'].items(): reserved[k]+=v
        account = read_json(root/'research_methods/episode_accounts'/(e['id']+'.json'))
        usage=dict(account.get('usage',{}))
        from .lesson_review_budget import retained_charges
        for row in retained_charges(root,e['id']):
            for k,v in row['usage_after'].items():usage[k]=max(usage.get(k,0),v)
        for p in (root/'research_methods/episode_interruptions').glob('*.json'):
            interrupted=records.read(root,'episode_interruptions',p.stem)
            if interrupted['episode_id']==e['id']:
                for k,v in interrupted['usage'].items(): usage[k]=max(usage.get(k,0),v)
        for k,v in usage.items(): cumulative[k]+=v
        if account.get('inflight'): cumulative['compute_seconds']+=account['inflight']['reserved_seconds']
    legacy = read_json(root/'research_methods/account.json').get('usage',{})
    return {'policy':policy(root),'episodes':len(episodes),'reserved_lifetime':reserved,'episode_usage':cumulative,
        'recursive_growth':recursive_status(root),
        'tasks':[{k:read_json(root/'research_methods/episode_tasks'/(e['id']+'.json')).get(k)
                  for k in ('learning_episode_id','state','model_calls','request_id','feedback')} for e in episodes],
        'practice_usage_including_legacy':{k:cumulative[k]+legacy.get(k,0) for k in cumulative},
        'scientific_allowance_added':0}


def tick(root: Path, tasks: list[dict[str, Any]], research_policy: Any, *, planner=None, repo_root: Path | None = None) -> dict[str, Any] | None:
    from .research_maintenance import advance
    configured = policy(root)
    if not configured or not configured['enabled']: return None
    from .recursive_review_queue import sync as sync_reviews
    sync_reviews(root)
    from .authoring_recovery import tick as recovery_tick
    recovery_tick(root,repo_root=repo_root)
    from .lesson_practice import tick as lesson_tick
    lesson_tick(root,repo_root=repo_root)
    from .practice_lessons import tick as practice_lesson_tick
    practice_lesson_tick(root,repo_root=repo_root)
    from .resource_experiments import admission_forecast
    for path in sorted((root/'research_methods/episode_tasks').glob('*.json')):
        waiting=read_json(path)
        if waiting.get('state')!='waiting_for_validation_window':continue
        forecast=admission_forecast(root)
        original=dict(waiting)
        waiting['validation_forecast']=forecast
        if forecast['state']=='eligible':
            waiting.update(state='ready',feedback={'reason':'validation_window_open_recheck_frozen_episode'})
        elif forecast['state']=='waiting_for_policy_window' and waiting.get('resume_not_before')!=forecast['not_before']:
            waiting['resume_not_before']=forecast['not_before']
        if waiting!=original:write_json(path,waiting)
    from .practice_transaction import preparation_key
    pending = next((read_json(p) for p in sorted((root/'research_methods/episode_tasks').glob('*.json'))
                    if read_json(p).get('state')=='ready' or
                    read_json(p).get('state')=='waiting_for_preparation_repair' and
                    read_json(p).get('preparation_failure_key')!=preparation_key(root,read_json(p))), None)
    if not pending:
        for task in tasks:
            try:
                e = admit(root,task,repo_root=repo_root)
                pending = read_json(root/'research_methods/episode_tasks'/(e['id']+'.json')); break
            except (ValueError,KeyError,OSError): continue
    if not pending:
        from .child_directive_learning import admit_next
        pending = admit_next(root)
    if not pending:
        from .next_practice import admit as admit_successor
        pending = admit_successor(root)
    if not pending:
        from .recursive_growth import admit as admit_recursive
        pending = admit_recursive(root)
    if not pending: return None
    if planner is None:
        import dataclasses
        from .research_runtime import local_planner
        recursive = records.read(root,'learning_episodes',pending['learning_episode_id']).get('family') in ('recursive_practice','recursive_question')
        planner = local_planner(dataclasses.replace(research_policy,model_timeout_seconds=120,max_output_tokens=1000 if recursive else 1800))
    try:
        episode = records.read(root, 'learning_episodes', pending['learning_episode_id'])
        if episode.get('family') == 'recursive_question':
            from .recursive_loop import advance as advance_question
            return advance_question(root,pending,planner=planner)
        if episode.get('family') == 'recursive_practice':
            from .recursive_growth import advance as advance_recursive
            return advance_recursive(root,pending,planner=planner)
        if episode.get('family') == 'successor_question':
            from .next_practice import advance as advance_successor
            return advance_successor(root, pending, planner=planner)
        if episode.get('family') == 'child_artifact':
            from .child_directive_learning import advance as child_advance
            return child_advance(root, pending, planner=planner)
        return advance(root,pending,{'enabled':True},planner=planner,repo_root=repo_root)
    except (ValueError,KeyError,OSError) as exc:
        pending.update(state='awaiting_review',feedback={'reason':str(exc)[:500]})
        write_json(root/'research_methods/episode_tasks'/(pending['learning_episode_id']+'.json'),pending)
        return pending
