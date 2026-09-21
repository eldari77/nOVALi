"""Precommitted longitudinal controls and actual-planner restart probes.

Instrument transfer, planner reuse and 9D scientific evidence remain separate.
This module never admits live work or promotes a candidate.
"""
from __future__ import annotations
import copy
import hashlib
import os
import time
from pathlib import Path
from typing import Any
from . import recursive_growth as growth, recursive_evaluator as evaluator
from . import research_procedures as records
from .research_tools import digest, read_json, write_json

ARMS=('with_memory','without_memory','frozen_version')


def fingerprint() -> dict:
    return {**records.implementation(),'recursive_capability_eval.py':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def save(path: Path, value: dict) -> dict:
    body={k:v for k,v in value.items() if k!='sha256'}
    result={**body,'sha256':digest(body)};write_json(path,result);return result


def checked(path: Path) -> dict:
    value=read_json(path)
    if not value or value.get('sha256')!=digest({k:v for k,v in value.items() if k!='sha256'}):
        raise ValueError('frozen_capability_evaluation_integrity_failure')
    return value


def prepare(root: Path, output: Path, *, model: str, seeds: list[int], provider_seconds: int = 90) -> dict:
    if output.exists() or not model or not 1<=len(seeds)<=8 or len(set(seeds))!=len(seeds) or any(type(s) is not int or s<0 for s in seeds):
        raise ValueError('fresh_bounded_precommitted_comparison_required')
    if not 30<=provider_seconds<=120:raise ValueError('bounded_provider_deadline_required')
    return save(output/'plan.json',{'model':model,'seeds':seeds,'provider_seconds':provider_seconds,
        'output_tokens':900,'calls_per_case':1,'arms':list(ARMS),'prepared_process_id':os.getpid(),
        'implementation':fingerprint(),'evaluator_sha256':evaluator.fingerprint(),
        'frozen_version':growth.active(root),'frozen_method_ids':[m['id'] for m in growth.methods(root)],
        'acceptance':{'complete_fields':True,'zero_regressions':True,'same_tasks_all_arms':True,
            'research_success_requires_separate_downstream_receipt':True},
        'scope':'frozen_learning_strategy_generation_in_same_runtime_not_whole_system_9D_advantage'})


def generation(root: Path, output: Path) -> dict:
    plan=checked(output/'plan.json')
    if fingerprint()!=plan['implementation']:raise ValueError('frozen_evaluation_implementation_changed')
    version=growth.active(root);name=version['version_id'] or 'initial'
    path=output/'generations'/(name+'.json')
    if path.exists():return checked(path)
    methods=growth.methods(root)
    suites=[case for seed in plan['seeds'] for case in evaluator.cases(seed,2,count=4)]
    instrument=evaluator.assess(version['strategy'],plan['frozen_version']['strategy'],suites)
    accounts=[read_json(root/'research_methods/episode_accounts'/(e['id']+'.json')) for e in growth.rows(root,'learning_episodes') if e['family'] in ('recursive_practice','recursive_question')]
    cumulative={k:sum(a.get('usage',{}).get(k,0) for a in accounts) for k in ('model_calls','tool_calls','compute_seconds')}
    return save(path,{'name':name,'version':version,'methods':methods[-8:], 'instrument':instrument,
        'cumulative_learning_cost':cumulative,'frozen_plan_sha256':plan['sha256'],
        'created_process_id':os.getpid(),'planner_reuse':'not_measured','research_improvement':'not_established'})


def probe(output: Path, generation_name: str, arm: str, seed: int, *, planner) -> dict:
    """One call in a fresh process; the planner must choose/apply a method itself."""
    plan=checked(output/'plan.json');gen=checked(output/'generations'/(generation_name+'.json'))
    if (arm not in ARMS or seed not in plan['seeds'] or fingerprint()!=plan['implementation']
            or gen['frozen_plan_sha256']!=plan['sha256']):raise ValueError('frozen_probe_binding_required')
    if os.getpid() in {plan['prepared_process_id'],gen['created_process_id']}:
        raise ValueError('fresh_process_required_for_planner_reuse')
    path=output/'probes'/generation_name/arm/(str(seed)+'.json')
    if path.exists():return checked(path)  # A failure cannot be rerun for free.
    methods=gen['methods'] if arm=='with_memory' else ([m for m in gen['methods'] if m['id'] in plan['frozen_method_ids']] if arm=='frozen_version' else [])
    case=evaluator.cases(seed^0x185D,2,count=1)[0]
    from .planner_authoring import _object,_enum
    schema=_object({'method_id':_enum(['new',*[m['id'] for m in methods]]),
        'strategy':evaluator.strategy_schema(),'applicability':{'type':'string','minLength':12,'maxLength':200}})
    visible={'task':'Preserve every selected source state with bounded evidence and complete execution.',
        'case':case,'methods':methods,'current_contract':'absent differs from null, zero, false and unknown; all fields required',
        'controls':{'projection':['whole_input','selected_slots','present_slots'],'batch_size':'fields per batch',
                    'rules':'first matching count threshold chooses projection','stopping':'all_batches or first_batch'}}
    context={'bundle_visible':visible,'bundle_schema':schema,'task':{'planner_model':plan['model']},
        'bundle_instructions':'Choose an applicable stored method or author your own strategy. Explain applicability to current input and execute complete work. Do not assume a historical result applies.',
        'provider_time_budget_seconds':plan['provider_seconds']}
    # Persist reservation before dispatch; crash recovery treats it as consumed.
    receipt={'arm':arm,'seed':seed,'generation':generation_name,'plan_sha256':plan['sha256'],
        'input_sha256':digest(case),'process_id':os.getpid(),'state':'reserved','call_reserved':1,
        'model':plan['model'],'provider_seconds':plan['provider_seconds'],'output_tokens':plan['output_tokens']}
    save(path,receipt);started=time.monotonic()
    try:
        if callable(getattr(planner,'preflight',None)):
            prepared=planner.preflight('child_bundle',context)
            if prepared['model']!=plan['model'] or prepared['options']['num_predict']!=plan['output_tokens']:
                raise ValueError('frozen_model_and_output_budget_required')
        response=planner('child_bundle',context)
        from operator_shell import recursive_contract as jsonschema
        jsonschema.validate(response,schema)
        result=evaluator.execute(response['strategy'],case);errors=evaluator.oracle(case,result)
        selected=next((m for m in methods if m['id']==response['method_id']),None)
        receipt.update(state='completed',response=response,successful=not errors,errors=errors,
            selected_reviewed_method=bool(selected),adapted=bool(selected and selected['strategy']!=response['strategy']),
            successful_reviewed_reuse=bool(selected) and selected['strategy']==response['strategy'] and not errors,
            successful_adaptation_requires_review=bool(selected) and selected['strategy']!=response['strategy'] and not errors,
            context_bytes=result['context_bytes'],
            provider_metadata=getattr(planner,'last_metadata',{}))
    except Exception as exc:receipt.update(state='failed',successful=False,error=str(exc)[:400])
    receipt['elapsed_seconds']=time.monotonic()-started
    return save(path,receipt)


def summarize(output: Path, generation_name: str) -> dict:
    plan=checked(output/'plan.json');gen=checked(output/'generations'/(generation_name+'.json'))
    arms={};complete=True
    for arm in ARMS:
        receipts=[checked(p) for p in sorted((output/'probes'/generation_name/arm).glob('*.json'))]
        complete=complete and {r['seed'] for r in receipts}==set(plan['seeds']) and all(r['state']!='reserved' for r in receipts)
        arms[arm]={'completed':len(receipts),'successes':sum(r.get('successful',False) for r in receipts),
            'reviewed_method_reuses':sum(r.get('successful_reviewed_reuse',False) for r in receipts),
            'reserved_calls':sum(r['call_reserved'] for r in receipts),
            'elapsed_seconds':sum(r.get('elapsed_seconds',0) for r in receipts)}
    return {'generation':generation_name,'complete':complete,'arms':arms,'instrument':gen['instrument'],
        'cumulative_learning_cost':gen['cumulative_learning_cost'],
        'observed_success_difference':({a:arms['with_memory']['successes']-arms[a]['successes'] for a in ARMS[1:]} if complete else None),
        'sustained_learning_advantage':'not_established','research_improvement':'not_established',
        'nine_d_contribution':'not_measured_by_projection_curriculum'}


def nine_d_comparison(spec: dict[str, Any], *, seed: int) -> dict:
    """Route an independently budgeted Novali-authored theory spec to real 9D arms.

    Caller must use the existing scientific runtime admission. This offline
    evaluator adds no research allowance and does not author a hypothesis.
    """
    from . import nine_d_testing
    if spec.get('evaluator_id')!=nine_d_testing.COMPARISON:
        raise ValueError('registered_9D_comparison_required')
    result=nine_d_testing.evaluate(copy.deepcopy(spec),seed)
    return {'spec_sha256':digest(spec),'result':result,'allowance_added':0,
        'scope':'synthetic_transition_mechanisms_not_recursive_learning_causality',
        'recursive_learning_contribution':'not_established'}
