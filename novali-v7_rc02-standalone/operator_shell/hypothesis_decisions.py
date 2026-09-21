"""Evidence-bound hypothesis decisions, independent of useful-method adoption."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping

from . import planner_resources as resources, research_procedures as records
from .authoring_contract import prediction_issue
from .method_patches import _valid
from .research_tools import digest


def finding(root: Path, task: Mapping[str, Any], attempt_id: str, inputs: Mapping[str, Any]) -> dict[str, Any]:
    attempt=records.read(root,'attempts',attempt_id)
    if (attempt_id not in task['attempt_ids'] or attempt.get('failure_id')!=task['failure_id']
            or attempt.get('learning_episode_id')!=task.get('learning_episode_id')
            or attempt.get('candidate_id') or attempt.get('evaluation_id')
            or attempt.get('outcome',{}).get('error')!='strategy_preflight_prediction_not_met'):
        raise ValueError('owned_refuted_untested_hypothesis_required')
    response=attempt.get('response',{}); assessment=attempt.get('diagnostics',{}).get('assessment',{})
    hypothesis=response.get('strategy_hypothesis'); profile=response.get('planning_strategy')
    if (attempt.get('planning_input_sha256')!=digest(inputs['planning_context'])
            or attempt.get('implementation')!=records.implementation()):
        raise ValueError('current_frozen_hypothesis_measurements_required')
    if not _valid(profile,resources.schema()):raise ValueError('checked_planning_profile_required')
    counterexample=prediction_issue(hypothesis,assessment)
    if (not counterexample or assessment.get('structural_preflight_passed') is not True
            or hypothesis['metric'] not in {'context_bytes','instruction_chars','schema_bytes'}
            or counterexample['observed_reduction_percent'] is None):
        raise ValueError('independent_static_refutation_required')
    return records.store(root,'hypothesis_findings',{'attempt_id':attempt_id,'attempt_sha256':digest(attempt),
        'failure_id':task['failure_id'],'learning_episode_id':task.get('learning_episode_id'),
        'input_sha256':digest(inputs['planning_context']),'implementation':records.implementation(),
        'profile':profile,'hypothesis':hypothesis,'hypothesis_sha256':digest(hypothesis),
        'assessment_sha256':digest(assessment),'counterexample':counterexample,'verdict':'refuted',
        'scope':'frozen_transport_measurement_only','scientific_allowance_added':0,'method_adoption_authorized':False})


def available(root: Path, task: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any] | None:
    pending=task.get('pending_prediction')
    if not pending or task.get('hypothesis_response_used') or task.get('prediction_revision_used'):return None
    try:record=finding(root,task,pending['attempt_id'],inputs)
    except ValueError:return None
    return {'attempt_id':record['attempt_id'],'finding_id':record['id'],'verdict':record['verdict'],
            'hypothesis':record['hypothesis'],'profile':record['profile'],'counterexample':record['counterexample'],
            'scope':record['scope'],'allowed_decisions':['refute','withdraw','new_hypothesis']}


def link_schema(binding: Mapping[str, Any]) -> dict[str, Any]:
    from .planner_authoring import _object,_string
    return _object({'attempt_id':{'type':'string','const':binding['attempt_id']},
        'finding_id':{'type':'string','const':binding['finding_id']},'reason':_string(12,300)})


def resolution_schema(binding: Mapping[str, Any]) -> dict[str, Any]:
    from .planner_authoring import _object
    fields=link_schema(binding)['properties']
    return _object({**fields,'decision':{'type':'string','enum':['refute','withdraw']},
        'metric':{'type':'string','const':binding['hypothesis']['metric']},
        'observed_reduction_percent':{'type':'number','minimum':-1000000,'maximum':100},
        'effect':{'type':'string','enum':['increase','decrease','unchanged']}})


def validate_link(root: Path, task: Mapping[str, Any], link: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
    current=available(root,task,inputs)
    if not current or not isinstance(link,dict) or not _valid({k:link.get(k) for k in ('attempt_id','finding_id','reason')},link_schema(current)):
        raise ValueError('current_owned_hypothesis_evidence_link_required')
    for p in (root/'research_methods/hypothesis_decisions').glob('*.json'):
        if records.read(root,'hypothesis_decisions',p.stem)['finding_id']==link['finding_id']:
            raise ValueError('hypothesis_evidence_already_resolved')
    return records.read(root,'hypothesis_findings',current['finding_id'])


def validate_revision(root: Path, task: Mapping[str, Any], response: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
    link=response['hypothesis_revision']; record=validate_link(root,task,link,inputs)
    if not _valid(link,link_schema({'attempt_id':record['attempt_id'],'finding_id':record['id']})):
        raise ValueError('typed_hypothesis_revision_link_required')
    hypothesis=response['strategy_hypothesis']; old=record['hypothesis']
    if not _valid(hypothesis,resources.hypothesis_schema()):raise ValueError('typed_strategy_cost_hypothesis_required')
    if all(hypothesis[k]==old[k] for k in ('metric','mechanism','falsifier')):
        raise ValueError('numerical_change_uses_prediction_correction')
    if resources.signature(response['planning_strategy'])!=resources.signature(record['profile']):
        raise ValueError('hypothesis_revision_preserves_untested_controls')
    return record


def resolution(root: Path, task: Mapping[str, Any], response: Mapping[str, Any], inputs: Mapping[str, Any],
               assessment: Mapping[str, Any]) -> dict[str, Any]:
    record=validate_link(root,task,response,inputs)
    binding={'attempt_id':record['attempt_id'],'finding_id':record['id'],'hypothesis':record['hypothesis']}
    if not _valid(response,resolution_schema(binding)):raise ValueError('typed_hypothesis_resolution_required')
    fresh=prediction_issue(record['hypothesis'],assessment)
    if fresh!=record['counterexample']:raise ValueError('hypothesis_measurement_changed_reassess')
    expected=fresh['observed_reduction_percent']
    if expected is None:raise ValueError('measured_hypothesis_effect_required')
    effect='decrease' if expected>0 else 'increase' if expected<0 else 'unchanged'
    if (expected is None or not math.isclose(response['observed_reduction_percent'],expected,rel_tol=1e-6,abs_tol=1e-6)
            or response['effect']!=effect):
        from .authoring_contract import AuthoringError
        raise AuthoringError([{'field':'hypothesis_resolution','reason':'resolution_must_match_verified_measurement',
            'expected_effect':effect,'expected_reduction_percent':expected,'actual':dict(response)}],dict(assessment))
    result=record_decision(root,task,record,response['decision'],response)
    task.update(state='completed_method_learning',hypothesis_response_used=True,
                feedback={'reason':'verified_hypothesis_'+response['decision'],'decision_id':result['id'],
                          'method_adoption_authorized':False,'scientific_allowance_added':0})
    task.pop('pending_prediction',None)
    return result


def record_decision(root: Path, task: Mapping[str, Any], record: Mapping[str, Any], decision: str,
                    response: Mapping[str, Any], *, new_hypothesis: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return records.store(root,'hypothesis_decisions',{'finding_id':record['id'],'finding_sha256':digest(record),
        'parent_attempt_id':record['attempt_id'],'failure_id':task['failure_id'],
        'learning_episode_id':task.get('learning_episode_id'),'call':task['model_calls'],
        'decision':decision,'authored_by':'Novali planner','response':dict(response),
        'authorship_scope':'planner decision and reason; measurement facts independently verified by the controller',
        'original_hypothesis_verdict':'refuted','new_hypothesis':dict(new_hypothesis) if new_hypothesis else None,
        'new_hypothesis_sha256':digest(new_hypothesis) if new_hypothesis else None,
        'requires_separate_evaluation':new_hypothesis is not None,'learning_outcome_verified':True,
        'new_hypothesis_verdict':'unassessed' if new_hypothesis else None,
        'scope':'hypothesis_handling_only','method_adoption_authorized':False,'scientific_allowance_added':0})


def memory(root: Path, *, decision_id: str | None = None) -> list[dict[str, Any]]:
    from .observable_scope import observations, contract
    rows=[]
    for p in sorted((root/'research_methods/hypothesis_decisions').glob('*.json')):
        if decision_id is not None and p.stem != decision_id:continue
        decision=records.read(root,'hypothesis_decisions',p.stem)
        record=records.read(root,'hypothesis_findings',decision['finding_id'])
        if decision['finding_sha256']!=digest(record):raise ValueError('hypothesis_memory_integrity_failure')
        attempt = records.read(root, 'attempts', record['attempt_id'])
        assessment = attempt.get('diagnostics', {}).get('assessment', {})
        if digest(attempt) != record['attempt_sha256'] or digest(assessment) != record['assessment_sha256']:
            raise ValueError('hypothesis_memory_measurement_integrity_failure')
        rows.append({'id':decision['id'],'decision':decision['decision'],'original_verdict':'refuted',
            'hypothesis':record['hypothesis'],'profile':record['profile'],'counterexample':record['counterexample'],
            'explanation':decision['response']['reason'],'input_sha256':record['input_sha256'],
            'measurement_contract':contract(record['hypothesis']), 'observations':observations(assessment),
            'interpretation_scope':'Only the selected prediction was refuted. Other effects remain distinct; unmeasured latency is unknown. The planner rationale is not a verified general rule.',
            'scope':'prior_frozen_input_only_remeasure_new_tasks','method_adoption_authorized':False})
    if decision_id is None:
        from .practice_lessons import memory as practice_memory
        rows.extend(practice_memory(root))
    return rows[-6:]
