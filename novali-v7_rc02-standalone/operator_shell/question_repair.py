"""Bounded correction contexts and immutable prediction lineage."""
from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

from .research_tools import digest, read_json, write_json

VERSION = 'question_repair_v1'
MEASUREMENT_CODES = {'hypothesis_observable_mismatch', 'evidence_phase_mismatch',
    'comparison_not_defined', 'prediction_falsifier_missing', 'measurement_definition_required', 'measurement_prediction_mismatch'}


def method_schema() -> dict[str, Any]:
    from .planner_authoring import _object
    text = {'type':'string','minLength':8,'maxLength':48,
        'pattern':r'^[^"\\\r\n\t]{8,48}$',
        'description':'One complete short operation. Omit repeated paths and evaluator names.'}
    operation = _object({'input_ref':{'const':'selected_obligation'},'action':text,'check':text})
    return _object({'baseline_operation':operation,'changed_operation':operation})


def method_findings(method: Any) -> list[dict[str, Any]]:
    errors=[]
    if not isinstance(method,dict) or set(method)!={'baseline_operation','changed_operation'}:
        return [{'path':'/method','code':'structured_operations_required','guidance':'Describe baseline and changed operations using input_ref, action and check.'}]
    for name,v in method.items():
        if (not isinstance(v,dict) or set(v)!={'input_ref','action','check'} or v.get('input_ref')!='selected_obligation'
            or any(not isinstance(v.get(k),str) or not 8<=len(v[k])<=48 for k in ('action','check'))):
            errors.append({'path':'/method','code':'structured_operations_required','guidance':name+' requires the selected input binding and complete short action/check fields.'})
            continue
        for k in ('action','check'):
            original=v[k]; text=original.replace('_',' ')
            path='/method/'+name+'/'+k
            if '_' in original and not re.search(r'\s', original):
                errors.append({'path':'/method','subject':path,'code':'operation_format_requires_prose','guidance':'Use plain words; underscores alone do not identify an evaluator.','counterexample':{'text':original}})
            if (text!=text.strip() or text.count('(')!=text.count(')') or
                re.search(r'\b(?:a|an|the)\s+(?:(?:complete|bounded|bound|valid|verified|retrieved|selected)[ ,]+)*(?:complete|bounded|bound|valid|verified|retrieved|selected)\s*[.!?]*$',text,re.I) or
                re.search(r'\b(and|or|because|by|with|the|to|of|if|than|ensure|ensuring)\s*[.!?]*$',text,re.I)):
                errors.append({'path':'/method','subject':path,'code':'unfinished_operation','guidance':'This operation is unfinished; shorten it to a complete operation.','counterexample':{'text':original}})
    return errors


def expand_findings(issues: list[dict[str, Any]], response: dict[str, Any]) -> list[dict[str, Any]]:
    result=copy.deepcopy(issues)
    if any(f.get('code') in MEASUREMENT_CODES for f in issues):
        h=response.get('hypothesis',{})
        detail=f"Selected prediction: {h.get('phase')} / {h.get('metric')} / {h.get('predicted_effect')}."
        for path in ('/hypothesis','/observable','/failure_condition'):
            if not any(f.get('path')==path for f in result):
                result.append({'path':path,'code':'linked_measurement_review',
                    'guidance':detail+' Check this field together with the other measurement fields; retain it if already consistent.'})
    return result


def project(context: dict[str, Any]) -> dict[str, Any]:
    result=copy.deepcopy(context)
    # Each choice already contains its exact evaluator binding.
    result.pop('bound_evaluators',None)
    scopes={}
    for metadata in result.get('failure_evidence_metadata',{}).values():
        if isinstance(metadata.get('scope'),str):
            scope=metadata.pop('scope');key='s'+digest(scope)[:8]
            if key in scopes and scopes[key]!=scope:raise ValueError('ambiguous_scope_alias')
            scopes[key]=scope;metadata['scope_ref']=key
    if scopes:result['failure_evidence_scopes']=scopes
    # Keep the authored fields and literal values; remove only runtime-derived duplicates.
    prior=result.get('previous_proposal')
    if isinstance(prior,dict):
        if isinstance(prior.get('method'),dict):
            for k in ('method_before','method_after'):prior.pop(k,None)
        for k in ('input_scope','field_batches','scope_mode'):prior.pop(k,None)
        aliases={v.get('id',k):k for k,v in result.get('failure_evidence',{}).items()}
        h=prior.get('hypothesis',{})
        if isinstance(h,dict):h['evidence_ids']=[aliases.get(k,k) for k in h.get('evidence_ids',[])]
    for key,evidence in result.get('failure_evidence',{}).items():
        measurements=evidence.pop('measurements',None)
        if measurements:
            evidence['measurement_reference']={'evidence_id':evidence.get('id',key),'sha256':digest(measurements),'records':len(measurements)}
            # Preserve phase/cost observations, without repeating every historical receipt.
            evidence['measured_ranges']={field:[min(vals),max(vals)] for field in
                ('context_utf8_bytes','output_token_limit','eval_count')
                if (vals:=[m[field] for m in measurements if type(m.get(field)) in (int,float)])}
        evidence.pop('evidence_receipts',None)  # Immutable evidence ID resolves the complete receipts.
    feedback=result.get('feedback',{})
    if feedback.get('field_issues'):
        feedback.pop('reason',None)
        feedback['field_issues']=expand_findings(feedback['field_issues'],prior or {})
    return result


def reserve_cycle(context: dict[str, Any]) -> dict[str, Any]:
    """Reserve a bounded retry envelope as well as the actual initial request.

    Arbitrarily large reviewer prose still undergoes exact preflight at review.
    This reservation covers the largest schema response plus 1200 bytes of concise findings.
    """
    from .next_practice import contract
    from .child_planning import reserve
    from .question_feedback import transport,FEEDBACK_BYTES
    wire=transport if context.get('focus_contract') else lambda c:c
    initial=reserve(contract(context)[0],wire(context),650)
    retry=copy.deepcopy(context)
    retry['choices']=retry['choices'][:1]
    envelope=maximum_response(contract(context)[1])
    if context.get('diagnosis_contract') and context.get('previous_proposal'):
        # A reviewed follow-up starts with a preserved proposal and bounded edits.
        # Reserve the longest permitted value at every editable leaf, not an edits
        # envelope mistakenly used as the next canonical proposal.
        from .practice_experiments import editable
        from .question_focus import assign
        from .question_semantics import properties
        from .question_measurements import method_schema as instrument_schema
        rules=properties(context)
        rules['method']=instrument_schema() if context.get('measurement_contract') else method_schema()
        from .practice_experiments import FIELDS,sentence
        envelope=copy.deepcopy(context['previous_proposal'])
        for path in editable(context):
            parts=path.lstrip('/').split('/')
            rule=rules.get(parts[0]) or sentence(FIELDS[parts[0]])
            for part in parts[1:]:rule=rule['properties'][part]
            assign(envelope,path,maximum_response(rule))
    # Legal partitions contain each selected field once; the JSON grammar's
    # independent nested array maxima otherwise imply impossible duplication.
    fields=max((r['obligation'].get('unit',{}).get('fields',[]) for r in context['choices']),key=lambda v:len(str(v)),default=[])
    envelope['execution_scope']={'mode':'partition','batches':[[k] for k in fields]} if fields else {'mode':'full_unit'}
    retry['previous_proposal']=envelope
    retry['feedback']={'reserved_findings':'x'*(FEEDBACK_BYTES if context.get('focus_contract') else 1200)}
    if context.get('focus_contract'):retry.pop('finding_guidance',None)  # Included in the total findings envelope.
    retry['selected_source_id']=retry['choices'][0]['id']
    retry['execution_preview']={'reserved_preview':'x'*180}
    instruction_context=copy.deepcopy(retry)
    instruction_context['feedback']={'field_issues':[{'path':'/method','code':'reserved'}]}
    retry_instructions=max((contract(retry)[0],contract(instruction_context)[0]),key=len)
    retry_wire=wire(retry)
    if context.get('diagnosis_contract'):
        # Project the failed-field envelope before replacing its diagnostics with
        # the total reserved byte bound. Guidance and diagnosis references share
        # that bound at transport time; do not reserve them twice.
        projected=copy.deepcopy(instruction_context)
        from .practice_experiments import editable
        possible=editable(context) or ['/method','/hypothesis','/observable','/failure_condition',
            '/applicability_reason','/applicability_limit']
        projected['feedback']={'field_issues':[{'path':p,'code':'reserved'} for p in possible]}
        projected.pop('finding_guidance',None);projected.pop('correction_requirements',None)
        retry_wire=wire(projected)
        retry_wire['feedback']={'reserved_findings':'x'*FEEDBACK_BYTES}
    retry_reservation=reserve(retry_instructions,retry_wire,650)
    if context.get('focus_contract'):
        initial['correction_reservation']=retry_reservation
        initial['feedback_bytes_reserved']=FEEDBACK_BYTES
    return initial


def maximum_response(schema: dict[str, Any]) -> Any:
    """Conservative JSON-size envelope, never an authored proposal or solution."""
    import json
    size=lambda value:len(json.dumps(value,ensure_ascii=False).encode())
    if 'const' in schema:return schema['const']
    if 'enum' in schema:return max(schema['enum'],key=size)
    if 'anyOf' in schema:return max((maximum_response(s) for s in schema['anyOf']),key=size)
    if schema.get('type')=='object':return {k:maximum_response(s) for k,s in schema.get('properties',{}).items()}
    if schema.get('type')=='array':return [maximum_response(schema['items']) for _ in range(schema.get('maxItems',1))]
    if schema.get('type')=='string':return 'x'*schema.get('maxLength',120)
    return None


def last_parsed(root: Path, task: dict[str, Any]) -> dict[str, Any] | None:
    from . import research_procedures as records
    for aid in reversed(task.get('attempt_ids',[])):
        attempt=records.read(root,'attempts',aid)
        if isinstance(attempt.get('response'),dict):return attempt
    return None


def prediction_lineage(prior: Any, response: Any) -> dict[str, Any] | None:
    if not isinstance(prior,dict) or not isinstance(response,dict):return None
    before,after=prior.get('hypothesis'),response.get('hypothesis')
    if before==after:return None
    return {'original_prediction':copy.deepcopy(before),'revised_prediction':copy.deepcopy(after),
        'original_prediction_sha256':digest(before),'revised_prediction_sha256':digest(after),
        'relationship':'new_prediction_requires_independent_evaluation',
        'original_outcome':'not_established_by_rewording','adoption_credit':False}


def recover(root: Path, episode_id: str, *, planner, reviewer: str, evidence_reference: str) -> dict[str, Any]:
    """Review one verified local retry failure; retain its existing reservation."""
    from . import research_procedures as records, next_practice as questions, learning_episodes
    from .directive_obligations import assert_current
    from .lesson_review_budget import charge
    if any(not isinstance(v,str) or not 16<=len(v)<=1600 for v in (reviewer,evidence_reference)):
        raise ValueError('independent_preparation_repair_evidence_required')
    e=records.read(root,'learning_episodes',episode_id)
    path=root/'research_methods/episode_tasks'/(episode_id+'.json');task=read_json(path)
    account=read_json(root/'research_methods/episode_accounts'/(episode_id+'.json'))
    usage=account.get('usage',{});cap=e['reserved']
    latest=records.read(root,'attempts',task['attempt_ids'][-1]) if task.get('attempt_ids') else {}
    if any(records.read(root,'successor_preparation_repairs',p.stem).get('episode_id')==episode_id
           for p in (root/'research_methods/successor_preparation_repairs').glob('*.json')):
        raise ValueError('preparation_recovery_already_reviewed')
    previous=last_parsed(root,task)
    if (e.get('family')!='successor_question' or task.get('state')!='exhausted_no_candidate' or task.get('question_id')
        or account.get('inflight') or task.get('preparation_repair_id') or not previous
        or usage.get('model_calls')!=task.get('model_calls') or not 0<usage['model_calls']<cap['model_calls']
        or usage['tool_calls']+6>cap['tool_calls'] or usage['compute_seconds']+41>cap['compute_seconds']
        or latest.get('provider_dispatched') is not False or latest.get('response') is not None
        or not any(reason in latest.get('feedback',{}).get('reason','') for reason in
            ('child_input_plus_output_reservation_exceeded','question_feedback_reservation_exceeded'))):
        raise ValueError('verified_unused_retry_preparation_reservation_required')
    if (not questions.policy(root).get('repair_contract') or not questions.policy(root).get('enabled')
        or learning_episodes.policy(root)['id']!=e['policy_id'] or not learning_episodes.policy(root)['enabled']
        or e['implementation']==records.implementation()):
        raise ValueError('changed_reviewed_preparation_implementation_required')
    for choice in e['frozen_question_choices']:assert_current(root,choice['frozen'])
    resumed=copy.deepcopy(task);resumed['repair_contract']=VERSION;resumed['state']='ready'
    resumed['feedback']=copy.deepcopy(previous['feedback'])
    if not e.get('repair_contract'):
        resumed['feedback'].setdefault('field_issues',[]).append({'path':'/method','code':'structured_operations_required',
            'guidance':'Re-express your existing operations as input_ref, action and check; do not substitute evaluator names.'})
    context=questions.retry_context(root,e,resumed,account)
    with charge(root,e):
        planner.preflight('successor_question',questions.project_context(context))
        receipt=records.store(root,'successor_preparation_repairs',{'episode_id':episode_id,
            'attempt_ids':task['attempt_ids'],'task_before_sha256':digest(task),'resumed_task':resumed,
            'implementation':records.implementation(),'successor_policy_id':questions.policy(root)['id'],
            'policy_id':e['policy_id'],'reserved':cap,'usage_before':copy.deepcopy(usage),
            'reviewer':reviewer,'evidence_reference':evidence_reference,'repair_contract':VERSION,
            'preflight_context_sha256':digest(questions.project_context(context)),
            'scientific_allowance_added':0,'funding':'existing_unused_reservation_only'})
    resumed['preparation_repair_id']=receipt['id'];write_json(path,resumed)
    return receipt
