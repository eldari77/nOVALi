"""Retain independently rechecked practice outcomes without method adoption."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from . import research_procedures as records, learning_episodes as episodes, planner_resources
from .research_tools import digest, read_json
from .authoring_contract import prediction_issue
from .observable_scope import observations, contract


def review(root: Path, episode_id: str, *, repo_root: Path | None = None) -> dict[str, Any]:
    episode=records.read(root,'learning_episodes',episode_id)
    if episode.get('lesson_stage')!='practice':
        raise ValueError('admitted_question_practice_required')
    for path in (root/'research_methods/practice_lessons').glob('*.json'):
        prior=records.read(root,'practice_lessons',path.stem)
        if prior['episode_id']==episode_id:return prior
    task=read_json(root/'research_methods/episode_tasks'/(episode_id+'.json'))
    episodes.practice_budget(root,task)
    account=read_json(root/'research_methods/episode_accounts'/(episode_id+'.json'))
    question=records.read(root,'practice_questions',episode['practice_question_id'])
    attempts=[records.read(root,'attempts',key) for key in task['attempt_ids']]
    if task['state']!='awaiting_review' or account.get('inflight') or not attempts:
        raise ValueError('settled_question_practice_required')
    attempt=attempts[-1]
    if attempt['outcome'].get('error') or not attempt.get('candidate_id'):
        raise ValueError('successful_owned_practice_candidate_required')
    candidate=records.read(root,'planning_candidates',attempt['candidate_id'])
    if (candidate['profile']!=question['question']['strategy']
            or candidate['strategy_hypothesis']!=question['hypothesis']
            or candidate['failure_id']!=episode['failure_id']
            or attempt['learning_episode_id']!=episode_id):
        raise ValueError('practice_candidate_question_lineage_required')
    inputs=episodes.frozen_planning_inputs(root,episode_id,repo_root=repo_root)
    from .lesson_review_budget import charge
    with charge(root,episode) as charged:
        assessment=planner_resources.preflight_check(inputs['planning_context'],candidate['profile'])
        if not assessment.get('structural_preflight_passed') or prediction_issue(candidate['strategy_hypothesis'],assessment):
            raise ValueError('independent_practice_prediction_not_supported')
    return records.store(root,'practice_lessons',{
        'episode_id':episode_id,'question_id':question['id'],'question_sha256':digest(question),
        'attempt_id':attempt['id'],'attempt_sha256':digest(attempt),
        'candidate_id':candidate['id'],'candidate_sha256':digest(candidate),
        'input_sha256':digest(inputs['planning_context']), 'hypothesis':candidate['strategy_hypothesis'],
        'profile':candidate['profile'],'assessment':assessment,'charge':charged,
        'original_verdict':'supported_on_original_input_only','authored_by':'Novali planner',
        'review_scope':'independent_static_prediction_recheck','scope':'local_method_practice_only',
        'method_adoption_authorized':False,'scientific_allowance_added':0})


def memory(root: Path) -> list[dict[str, Any]]:
    rows=[]
    for path in sorted((root/'research_methods/practice_lessons').glob('*.json')):
        row=records.read(root,'practice_lessons',path.stem)
        for kind,prefix in (('practice_questions','question'),('attempts','attempt'),('planning_candidates','candidate')):
            if digest(records.read(root,kind,row[prefix+'_id']))!=row[prefix+'_sha256']:
                raise ValueError('practice_lesson_provenance_changed')
        rows.append({'id':row['id'],'decision':'locally_supported_practice',
            'original_verdict':row['original_verdict'],'hypothesis':row['hypothesis'],
            'profile':row['profile'],'input_sha256':row['input_sha256'],
            'explanation':'The planner-authored question passed an independent static recheck on its original input.',
            'measurement_contract':contract(row['hypothesis']), 'observations':observations(row['assessment']),
            'scope':'prior_frozen_input_only_remeasure_new_tasks','method_adoption_authorized':False})
    return rows[-6:]


def tick(root: Path, *, repo_root: Path | None = None) -> None:
    from .lesson_applicability import enabled
    if not enabled(root):return
    done={records.read(root,'practice_lessons',p.stem)['episode_id']
          for p in (root/'research_methods/practice_lessons').glob('*.json')}
    checked={records.read(root,'practice_lesson_checks',p.stem)['episode_id']
             for p in (root/'research_methods/practice_lesson_checks').glob('*.json')}
    for episode in episodes._episodes(root):
        if episode.get('lesson_stage')!='practice' or episode['id'] in done|checked:continue
        task=read_json(root/'research_methods/episode_tasks'/(episode['id']+'.json'))
        if task.get('state')!='awaiting_review':continue
        try:
            lesson=review(root,episode['id'],repo_root=repo_root);result={'lesson_id':lesson['id']}
        except (ValueError,KeyError,OSError) as exc:result={'reason':str(exc)}
        records.store(root,'practice_lesson_checks',{'episode_id':episode['id'],'result':result,'scientific_allowance_added':0})
        break
