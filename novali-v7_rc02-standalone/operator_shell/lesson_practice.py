"""Reviewed lessons seed bounded, Novali-authored questions and later practice.

Every stage reserves an ordinary episode. A review is a numerical provenance
check, not endorsement of the planner's explanation or research permission.
"""
from __future__ import annotations
import copy
from pathlib import Path
from typing import Any, Mapping
from . import research_procedures as records, learning_episodes as episodes, planner_resources as resources
from .research_tools import digest, read_json, write_json
from .observable_scope import STATIC_METRICS, contract, falsifier_issues, observations
from .authoring_contract import AuthoringError, field_issues, prediction_issue


def configure(root: Path, *, enabled: bool, authority_reference: str) -> dict[str, Any]:
    if type(enabled) is not bool or not authority_reference.strip():
        raise ValueError('explicit_lesson_practice_policy_required')
    row = records.store(root, 'lesson_policies', {'enabled':enabled, 'authority_reference':authority_reference,
        'max_successor_depth':2, 'max_question_episodes_per_decision':1,
        'admission':'existing_episode_reservations_and_cadence', 'scientific_allowance_added':0})
    write_json(root/'research_methods/lesson_policy_latest.json', {'policy_id':row['id']})
    return row


def policy(root: Path) -> dict[str, Any] | None:
    pointer = read_json(root/'research_methods/lesson_policy_latest.json')
    return records.read(root, 'lesson_policies', pointer['policy_id']) if pointer else None


def source(root: Path, decision_id: str, *, repo_root: Path | None = None) -> dict[str, Any]:
    """Validate historical proof without requiring its old interface fingerprint."""
    from .hypothesis_decisions import memory
    from .theory_workspace import TheoryWorkspace
    decision = records.read(root, 'hypothesis_decisions', decision_id)
    finding = records.read(root, 'hypothesis_findings', decision['finding_id'])
    attempt = records.read(root, 'attempts', finding['attempt_id'])
    episode = records.read(root, 'learning_episodes', decision['learning_episode_id'])
    task = read_json(root/'research_methods/episode_tasks'/(episode['id']+'.json'))
    account = read_json(root/'research_methods/episode_accounts'/(episode['id']+'.json'))
    inputs = episode['frozen_planning_inputs']
    if (task.get('state') != 'completed_method_learning' or account.get('inflight') or not account.get('usage')
            or decision.get('decision') not in ('refute','withdraw') or not decision.get('learning_outcome_verified')
            or attempt.get('synthetic_setup') or digest(finding) != decision['finding_sha256']
            or digest(attempt) != finding['attempt_sha256'] or digest(inputs) != episode['input_sha256']
            or digest(inputs['planning_context']) != finding['input_sha256']
            or attempt['id'] not in task.get('attempt_ids', [])
            or decision['failure_id'] != episode['failure_id'] or finding['learning_episode_id'] != episode['id']
            or episode.get('lesson_depth',0) >= 2):
        raise ValueError('settled_owned_verified_lesson_required')
    actual = [records.read(root,'attempts',key) for key in task['attempt_ids']]
    resolving = [a for a in actual if a.get('outcome',{}).get('hypothesis_decision_id') == decision_id
                 and not a.get('outcome',{}).get('error') and a.get('authored_response',{}).get('intent') in ('refute','withdraw')]
    if not resolving or any(account['usage'][k] < a['usage_after'][k] for a in actual for k in account['usage']):
        raise ValueError('settled_planner_authorship_and_retained_costs_required')
    from .lesson_review_budget import retained_charges
    for charged in retained_charges(root,episode['id']):
        if any(account['usage'][k]<v for k,v in charged['usage_after'].items()):
            raise ValueError('lesson_review_usage_rollback')
    failure = records.read(root, 'failures', episode['failure_id'])
    ws = TheoryWorkspace(root, failure['theory_subject_id'], repo_root=repo_root)
    ws.assert_current_sources()
    if ws._snapshot()['snapshot_id'] != failure['source_snapshot_id']:
        raise ValueError('lesson_source_snapshot_changed')
    # memory() verifies original measurement hashes; select by identity, never mtime.
    lesson = next((r for r in memory(root, decision_id=decision_id) if r['id'] == decision_id), None)
    if lesson is None: raise ValueError('lesson_not_in_bounded_memory')
    return {'decision':decision, 'finding':finding, 'episode':episode, 'inputs':inputs, 'lesson':lesson}


def review(root: Path, decision_id: str, *, authority_reference: str, repo_root: Path | None = None) -> dict[str, Any]:
    configured = policy(root)
    if not configured or not configured['enabled'] or not authority_reference.strip():
        raise ValueError('enabled_lesson_policy_and_review_authority_required')
    basis = source(root, decision_id, repo_root=repo_root)
    for path in (root/'research_methods/lesson_reviews').glob('*.json'):
        existing=records.read(root,'lesson_reviews',path.stem)
        if existing['decision_id']==decision_id and existing['policy_id']==configured['id']:return existing
    from .lesson_review_budget import charge
    with charge(root,basis['episode']) as charged:
        assessment = resources.preflight_check(basis['inputs']['planning_context'], basis['finding']['profile'])
        if not assessment.get('structural_preflight_passed') or not prediction_issue(basis['finding']['hypothesis'], assessment):
            raise ValueError('current_independent_refutation_required')
    return records.store(root, 'lesson_reviews', {'decision_id':decision_id, 'decision_sha256':digest(basis['decision']),
        'source_episode_id':basis['episode']['id'], 'policy_id':configured['id'], 'authority_reference':authority_reference,
        'assessment':assessment, 'observations':observations(assessment), 'independent_checks':2, 'charge':charged,
        'review_scope':'numerical_refutation_and_owned_provenance_only', 'approves':'question_authoring_opportunity',
        'rationale_semantics_verified':False, 'scientific_allowance_added':0, 'method_adoption_authorized':False})


def validate_review(root: Path, review_id: str, *, repo_root: Path | None = None) -> dict[str, Any]:
    row = records.read(root,'lesson_reviews',review_id)
    configured = policy(root)
    if not configured or not configured['enabled'] or configured['id'] != row['policy_id']:
        raise ValueError('lesson_practice_policy_changed')
    basis = source(root,row['decision_id'],repo_root=repo_root)
    if digest(basis['decision']) != row['decision_sha256']:raise ValueError('lesson_review_source_changed')
    return basis


def question_schema() -> dict[str, Any]:
    from .authoring_intents import hypothesis_schema
    from .planner_authoring import _object, _string
    from .method_context import MODES
    hypothesis = hypothesis_schema()
    hypothesis['properties']['metric']['enum'] = list(STATIC_METRICS)
    return _object({'objective':_string(12,200), 'changed_approach':_string(12,300),
        'evaluator':{'type':'string','const':'static_component_comparison_v1'},
        'strategy':resources.schema(), 'hypothesis':hypothesis,
        'context_projection':{'type':'string','enum':list(MODES)}})


def signature(question: Mapping[str, Any]) -> str:
    return digest({'metric':question['hypothesis']['metric'], 'controls':resources.signature(question['strategy'])})


def check_question(root: Path, task: Mapping[str, Any], question: dict[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
    issues = field_issues(question,question_schema(),'question')
    if issues:raise AuthoringError(issues,{})
    issues = falsifier_issues(question['hypothesis'])
    opportunity = inputs['question_opportunity']
    original = opportunity['lesson']
    key = signature(question)
    if key == signature({'hypothesis':original['hypothesis'],'strategy':original['profile']}):
        issues.append({'field':'question','reason':'distinct_metric_or_executable_controls_required'})
    for path in (root/'research_methods/practice_questions').glob('*.json'):
        prior = records.read(root,'practice_questions',path.stem)
        if prior['signature'] == key and prior['source_input_sha256'] == original['input_sha256']:
            issues.append({'field':'question','reason':'question_already_independently_accepted'})
    hypothesis = {**question['hypothesis'], 'changed_fields':[k for k,v in
        {'instruction_mode':'full','excerpt_chars':4000,'command_scope':'all_executable'}.items() if question['strategy'][k]!=v]}
    if not hypothesis['changed_fields']:
        issues.append({'field':'question.strategy','reason':'changed_executable_approach_required'})
    assessment = resources.preflight_check(inputs['planning_context'],question['strategy'])
    contradiction = prediction_issue(hypothesis,assessment)
    if contradiction:issues.append(contradiction)
    if not assessment.get('structural_preflight_passed'):
        issues.append({'field':'question.strategy','reason':'structural_preflight_required'})
    if issues:raise AuthoringError(issues,assessment)
    return records.store(root,'practice_questions',{'learning_episode_id':task['learning_episode_id'],
        'lesson_review_id':opportunity['review_id'], 'source_input_sha256':original['input_sha256'],
        'question':question, 'signature':key, 'authored_by':'Novali planner', 'hypothesis':hypothesis,
        'assessment':assessment, 'measurement_contract':contract(hypothesis),
        'acceptance':'distinct_executable_objective_and_static_prediction_checked',
        'semantic_objective_novelty_proven':False, 'practice_requires_separate_episode':True,
        'scientific_allowance_added':0,'method_adoption_authorized':False})


def pending(root: Path) -> list[dict[str, str]]:
    admitted = episodes._episodes(root)
    rows = []
    for path in sorted((root/'research_methods/question_retry_reviews').glob('*.json')):
        review=records.read(root,'question_retry_reviews',path.stem)
        if not any(e.get('question_retry_review_id')==review['id'] for e in admitted):
            rows.append({'stage':'question_authoring','review_id':review['lesson_review_id'],'retry_review_id':review['id']})
    for path in sorted((root/'research_methods/practice_questions').glob('*.json')):
        question = records.read(root,'practice_questions',path.stem)
        state = read_json(root/'research_methods/episode_tasks'/(question['learning_episode_id']+'.json'))
        if state.get('state') == 'completed_question_authoring' and not any(e.get('practice_question_id') == question['id'] for e in admitted):
            rows.append({'stage':'practice','review_id':question['lesson_review_id'],'question_id':question['id']})
    for path in sorted((root/'research_methods/lesson_reviews').glob('*.json')):
        review = records.read(root,'lesson_reviews',path.stem)
        if not any(e.get('lesson_decision_id') == review['decision_id'] and e.get('lesson_stage') == 'question_authoring' for e in admitted):
            rows.append({'stage':'question_authoring','review_id':review['id']})
    return rows


def admit(root: Path, item: Mapping[str, str], *, repo_root: Path | None = None, now: float | None = None) -> dict[str, Any]:
    configured = episodes.policy(root)
    controls = read_json(root/'autonomy/status.json')
    if not configured or not configured['enabled'] or controls.get('active') is not True or controls.get('emergency_stop'):
        raise ValueError('learning_episode_controls_blocked')
    if dict(item) not in pending(root):raise ValueError('lesson_stage_already_admitted_or_unavailable')
    basis = validate_review(root,item['review_id'],repo_root=repo_root)
    retry=None
    if item.get('retry_review_id'):
        from .question_settlement import validate_retry
        retry=validate_retry(root,item['retry_review_id'],repo_root=repo_root)
    stamp,not_before = episodes.admission_window(root,configured,now=now)
    if stamp < not_before:raise ValueError('learning_daily_or_rolling_admission_limit')
    inputs = copy.deepcopy(basis['inputs'])
    inputs['previous_strategy'] = {'instruction_mode':'full','excerpt_chars':4000,'command_scope':'all_executable'}
    inputs['previous_strategy_scope'] = 'measurement_baseline_for_distinct_question_original_refutation_retained'
    episode = records.store(root,'learning_episodes',{'failure_id':basis['episode']['failure_id'],
        'failure_key':digest({'lesson_decision':basis['decision']['id'],'stage':item['stage'],'question':item.get('question_id'),
            **({'retry_review_id':retry['id']} if retry else {})}),
        'family':'planning','input_sha256':digest(inputs),'frozen_planning_inputs':inputs,
        'implementation':records.implementation(),'policy_id':configured['id'],'admitted_at':stamp,
        'lesson_stage':item['stage'],'lesson_review_id':item['review_id'],'lesson_decision_id':basis['decision']['id'],
        'source_episode_id':basis['episode']['id'],'lesson_depth':basis['episode'].get('lesson_depth',0)+1,
        'practice_question_id':item.get('question_id'),
        **({'question_retry_review_id':retry['id']} if retry else {}),
        'reserved':retry['reserved'] if retry else {k:configured['limits']['episode_'+k] for k in ('model_calls','tool_calls','compute_seconds')},
        'validation_reserved_before_provider':True,'scientific_allowance_added':0})
    task = {'learning_episode_id':episode['id'],'failure_id':episode['failure_id'],'suite_id':'',
        'state':'ready','model_calls':0,'attempt_ids':[],'candidate_signatures':[],'feedback':{},
        'lesson_stage':item['stage'],'requires_strategy_hypothesis':True,'grants_execution_authority':False}
    if retry:
        original=records.read(root,'attempts',retry['original_attempt_id'])
        task['feedback']=copy.deepcopy(original['diagnostics'])
        task['feedback']['recovery_scope']='One scheduled call after a verified preparation fault. Prior charges remain spent; revise your own question using its counterexample.'
    if item.get('question_id'):
        question = records.read(root,'practice_questions',item['question_id'])
        task['method_context_projection'] = question['question']['context_projection']
    write_json(root/'research_methods/episode_tasks'/(episode['id']+'.json'),task)
    return episode


def enrich(root: Path, task: Mapping[str, Any], inputs: dict[str, Any]) -> None:
    if not task.get('learning_episode_id'):return
    episode = records.read(root,'learning_episodes',task['learning_episode_id'])
    if not episode.get('lesson_review_id'):return
    review = records.read(root,'lesson_reviews',episode['lesson_review_id'])
    from .hypothesis_decisions import memory
    lesson = next(r for r in memory(root, decision_id=review['decision_id']) if r['id'] == review['decision_id'])
    if episode['lesson_stage'] == 'question_authoring':
        inputs['question_opportunity'] = {'review_id':review['id'],'lesson':lesson,
            'admission':'Author a distinct measurable question; independent checks precede a later funded practice episode.',
            'evaluator_scope':'static payload components only; successful research and speed are not inferred'}
        inputs['hypothesis_memory']=[row for row in inputs.get('hypothesis_memory',[]) if row['id']!=lesson['id']]
    else:
        inputs['accepted_practice_question'] = records.read(root,'practice_questions',episode['practice_question_id'])


def status(root: Path) -> dict[str, Any]:
    configured = policy(root)
    rows = pending(root) if configured and configured['enabled'] else []
    gate = episodes.policy(root)
    try:
        stamp,boundary = episodes.admission_window(root,gate) if gate else (0,0)
        reason = 'eligible' if stamp >= boundary else 'waiting_for_existing_episode_window'
    except ValueError as exc:boundary=None;reason=str(exc)
    return {'policy':configured,'pending':rows,'queue_reason':reason if rows else 'no_reviewed_successor',
        'last_dispatch':read_json(root/'research_methods/lesson_queue_latest.json'),
        'review_checks':[records.read(root,'lesson_review_checks',p.stem)
            for p in sorted((root/'research_methods/lesson_review_checks').glob('*.json'))[-6:]],
        'not_before':boundary if rows else None,'scientific_allowance_added':0}


def tick(root: Path, *, repo_root: Path | None = None) -> None:
    configured = policy(root)
    if not configured or not configured['enabled']:return
    # Standing policy permits one provenance/measurement review per new decision.
    # Rejections are durable; unchanged findings never earn repeated checks.
    reviewed={records.read(root,'lesson_reviews',p.stem)['decision_id']
        for p in (root/'research_methods/lesson_reviews').glob('*.json')}
    checked={records.read(root,'lesson_review_checks',p.stem)['decision_id']
        for p in (root/'research_methods/lesson_review_checks').glob('*.json')}
    for path in sorted((root/'research_methods/hypothesis_decisions').glob('*.json')):
        if path.stem in reviewed or path.stem in checked:continue
        try:
            basis=source(root,path.stem,repo_root=repo_root)
        except (ValueError,KeyError,OSError):continue  # Not a settled eligible lesson.
        prior_checks=read_json(root/'research_methods/episode_accounts'/(basis['episode']['id']+'.json'))['usage']['tool_calls']
        try:
            result=review(root,path.stem,authority_reference=configured['authority_reference'],repo_root=repo_root)
            outcome={'review_id':result['id'],'state':'verified'}
        except (ValueError,KeyError,OSError) as exc:
            outcome={'state':'rejected','reason':str(exc)}
        records.store(root,'lesson_review_checks',{'decision_id':path.stem,'policy_id':configured['id'],
            'independent_checks':read_json(root/'research_methods/episode_accounts'/(basis['episode']['id']+'.json'))['usage']['tool_calls']-prior_checks,
            'outcome':outcome,'scientific_allowance_added':0})
        break
    for item in pending(root):
        try:
            admitted=admit(root,item,repo_root=repo_root)
            queue={'state':'admitted','episode_id':admitted['id'],'stage':item['stage']}
        except (ValueError,KeyError,OSError) as exc:
            queue={'state':'parked','item':dict(item),'reason':str(exc)}
        path=root/'research_methods/lesson_queue_latest.json'
        if read_json(path)!=queue:write_json(path,queue)
        if queue['state']=='admitted':break
