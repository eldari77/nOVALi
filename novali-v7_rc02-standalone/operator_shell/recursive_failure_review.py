"""Independent failed-attempt review and finite, cost-retaining follow-ups."""
from __future__ import annotations
import copy
import secrets
import time
from pathlib import Path
from . import recursive_growth as growth, recursive_practice_checks as checks
from . import recursive_evaluator as evaluator, research_procedures as records
from .research_tools import digest, read_json, write_json

MAX_FOLLOWUPS = 2


def owned(root: Path, episode_id: str) -> tuple[dict, dict, dict, dict]:
    episode = records.read(root, 'learning_episodes', episode_id)
    task = read_json(root/'research_methods/episode_tasks'/(episode_id+'.json'))
    account = read_json(root/'research_methods/episode_accounts'/(episode_id+'.json'))
    if (episode.get('family') != 'recursive_practice' or task.get('learning_episode_id') != episode_id
            or task.get('state') != 'exhausted_requires_review' or task.get('candidate_id')
            or account.get('inflight') or not task.get('attempt_ids')):
        raise ValueError('settled_owned_failed_recursive_episode_required')
    attempts=[records.read(root,'attempts',a) for a in task['attempt_ids']]
    latest=attempts[-1]
    if latest.get('provider_metadata',{}).get('provider_outcome')=='unknown':raise ValueError('uncertain_dispatch_requires_reconciliation')
    attempt=latest if latest.get('provider_metadata',{}).get('provider_outcome')=='response_received' else next((a for a in reversed(attempts) if a.get('report') and isinstance(a.get('response'),dict)),latest)
    if (attempt['learning_episode_id'] != episode_id or not attempt.get('provider_dispatched')
            or not isinstance(attempt.get('response'), dict)
            or any(account['usage'][k] < v for k,v in attempt['usage_after'].items())
            or account['usage']['model_calls'] != task['model_calls']):
        raise ValueError('owned_replayable_attempt_and_retained_usage_required')
    if not attempt.get('report'):
        from .recursive_rejections import replay
        replay(root,attempt)
    return episode, task, account, attempt


def review(root: Path, episode_id: str, *, decision: str, reviewer: str, evidence_reference: str) -> dict:
    if decision not in ('followup', 'close') or min(len(reviewer), len(evidence_reference)) < 16:
        raise ValueError('explicit_independent_failure_review_required')
    existing = next((r for r in growth.rows(root,'recursive_failure_reviews') if r['episode_id']==episode_id), None)
    if existing:
        if existing['decision'] != decision: raise ValueError('immutable_failure_review_decision')
        return existing
    episode, task, account, attempt = owned(root, episode_id)
    if decision == 'followup' and episode.get('followup_depth', 0) >= MAX_FOLLOWUPS:
        raise ValueError('recursive_followup_lineage_limit')
    if episode['evaluator_sha256'] != evaluator.fingerprint():
        raise ValueError('original_evaluator_replay_required')
    structural=None
    prior=attempt['response']
    if not attempt.get('report'):
        from .recursive_rejections import replay as replay_rejection
        structural=replay_rejection(root,attempt);prior=structural['prior']
    growth.check(prior)
    from .lesson_review_budget import charge
    with charge(root, episode):
        replay = evaluator.evaluate(prior,episode['baseline']['strategy'],episode['seed'],episode['stage'])
        if not structural and replay != attempt['report']: raise ValueError('original_failure_report_not_reproduced')
        quality = checks.assess(prior, replay, episode['stage'])
        if not structural and replay['method_review_eligible'] and quality['practice_eligible']:
            raise ValueError('failed_instrument_or_coverage_required')
        protected=_protected(root,task,episode)
        if structural:
            packet=structural['packet']
            lost=sorted(set(protected)-set(packet['observed_discovery_states']))
            packet['lost_discovery_states']=lost
            if lost:
                packet['findings'].append({'path':'/practice_cases','code':'lost_discovery_coverage',
                                           'detail':','.join(lost)})
        return records.store(root,'recursive_failure_reviews',{
            'episode_id':episode_id,'attempt_id':attempt['id'],'attempt_sha256':digest(attempt),
            'task_sha256':digest(task),'usage_floor':copy.deepcopy(account['usage']),
            'decision':decision,'reviewer':reviewer,'evidence_reference':evidence_reference,
            'reviewed_at':time.time(),'implementation':records.implementation(),
            'checks_sha256':checks.fingerprint(),'replayed_report_sha256':digest(replay),
            'findings':quality,'original_prediction':prior['prediction'],
            'prior_proposal':prior,'prior_instrument_report':replay,'structural_evidence':structural,
            'protected_discovery_states':protected,
            'root_episode_id':episode.get('root_episode_id',episode_id),
            'followup_depth':episode.get('followup_depth',0)+1,
            'max_followups':MAX_FOLLOWUPS,'scientific_allowance_added':0,
            'admission':'existing_shared_limits_and_cadence_changed_effective_strategy_required',
            'allowance_added':0})


def eligible(root: Path, review: dict, previous: list[dict], baseline: dict) -> bool:
    if review['decision'] != 'followup' or review['implementation'] != records.implementation(): return False
    if review['checks_sha256'] != checks.fingerprint(): return False
    if any(e.get('failure_review_id') == review['id'] for e in previous): return False
    episode, task, account, attempt = owned(root, review['episode_id'])
    if (digest(task)!=review['task_sha256'] or digest(attempt)!=review['attempt_sha256']
            or any(account['usage'][k]<v for k,v in review['usage_floor'].items())):
        raise ValueError('reviewed_parent_state_or_costs_changed')
    if episode['baseline'] != baseline or episode['stage'] != growth.progress(root, episode['source_id']): return False
    if sum(e.get('root_episode_id')==review['root_episode_id'] for e in previous) >= MAX_FOLLOWUPS: return False
    return True


def admit(root: Path, previous: list[dict], baseline: dict, stamp: float, shared: dict, configured: dict, *, acceptance_seed: int | None = None) -> dict | None:
    if acceptance_seed is not None and (type(acceptance_seed) is not int or not 0<=acceptance_seed<2**31):raise ValueError('bounded_seed_required')
    for review in sorted(growth.rows(root,'recursive_failure_reviews'),key=lambda r:r['reviewed_at']):
        if not eligible(root,review,previous,baseline): continue
        parent, old_task, _, attempt = owned(root,review['episode_id'])
        body={'family':'recursive_practice','failure_id':parent['failure_id'],
              'failure_key':digest(['recursive_followup',review['id']]),'source_id':parent['source_id'],
              'input_sha256':review['attempt_sha256'],'stage':parent['stage'],'baseline':baseline,
              'seed':secrets.randbits(31) if acceptance_seed is None else acceptance_seed,'evaluator_sha256':evaluator.fingerprint(),
              'implementation':records.implementation(),'policy_id':shared['id'],
              'recursive_policy_id':configured['id'],'admitted_at':stamp,
              'reserved':{k:shared['limits']['episode_'+k] for k in ('model_calls','tool_calls','compute_seconds')},
              'validation_reserved_before_provider':True,'scientific_allowance_added':0,
              'practice_contract':checks.VERSION,'failure_review_id':review['id'],
              'parent_episode_id':parent['id'],'root_episode_id':review['root_episode_id'],
              'followup_depth':review['followup_depth'],'prior_attempt_id':attempt['id'],'correction_format':configured.get('correction_format','causal_v3')}
        task={'state':'ready','model_calls':0,'attempt_ids':[],'failure_id':parent['failure_id'],
              'last_proposal':review.get('prior_proposal',attempt['response']),
              'protected_discovery_states':review.get('protected_discovery_states',[]),
              'feedback':checks.feedback(review.get('prior_proposal',attempt['response']),review.get('prior_instrument_report',attempt.get('report')),review['findings']),
              'grants_execution_authority':False}
        if review.get('structural_evidence'):
            task['last_rejected_patch']=review['structural_evidence']['packet']
        prepared=growth.context(root,body,task)
        growth.reserve_context(prepared,first=True)
        episode=records.store(root,'learning_episodes',body)
        task['learning_episode_id']=episode['id']
        write_json(root/'research_methods/episode_tasks'/(episode['id']+'.json'),task)
        return task
    return None


def status(root: Path) -> list[dict]:
    reviews={r['episode_id']:r for r in growth.rows(root,'recursive_failure_reviews')}
    episodes=growth.rows(root,'learning_episodes')
    result=[]
    for episode in episodes:
        if episode.get('family')!='recursive_practice': continue
        task=read_json(root/'research_methods/episode_tasks'/(episode['id']+'.json'))
        if task.get('state')!='exhausted_requires_review': continue
        review=reviews.get(episode['id'])
        state='awaiting_failed_attempt_review'
        if review:
            state=('closed' if review['decision']=='close' else
                   'followup_admitted' if any(e.get('failure_review_id')==review['id'] for e in episodes) else
                   'review_requires_revalidation' if review['implementation']!=records.implementation() else 'reviewed_followup_awaiting_admission')
        blocker=None
        try: owned(root,episode['id']); replayable=True
        except ValueError as exc: replayable=False;blocker=str(exc)
        if not replayable and not review:state='blocked_missing_review_evidence'
        result.append({'episode_id':episode['id'],'state':state,'replayable':replayable,'review_blocker':blocker,
                       'followup_depth':episode.get('followup_depth',0),'max_followups':MAX_FOLLOWUPS})
    return result


def _protected(root: Path, task: dict, episode: dict) -> list[str]:
    """Preserve independently observable coverage, without accepting rejected work."""
    from .recursive_rejections import replay
    states=set(task.get('protected_discovery_states',[]))
    for aid in task['attempt_ids']:
        attempt=records.read(root,'attempts',aid)
        if attempt.get('report'):
            states.update(checks.coverage(attempt['response'],episode['stage'])['covered_states'])
        else:
            try:states.update(replay(root,attempt)['packet']['observed_discovery_states'])
            except ValueError:continue
    return sorted(states)
