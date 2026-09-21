"""Frozen, bounded oracle for curriculum programs; never supplied to the author."""
from __future__ import annotations
import copy
import hashlib
import json
import random
from pathlib import Path
from typing import Any
from .research_tools import digest

VERSION = 'recursive_projection_v1'
BASELINE = {'batch_size':12,'projection':'whole_input','ordering':'source','stopping':'all_batches','rules':[]}
WEAKNESSES = ('state_preservation','evidence_cost','complete_execution')


def fingerprint() -> str:
    return digest({name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        for name in ('recursive_evaluator.py','recursive_contract.py','question_measurements.py','research_tools.py')})


def strategy_schema() -> dict[str, Any]:
    from .planner_authoring import _object, _enum
    return _object({'batch_size':{'type':'integer','minimum':1,'maximum':12},
        'projection':_enum(['whole_input','selected_slots','present_slots']),
        'ordering':_enum(['source','absent_first','present_first']),
        'stopping':_enum(['all_batches','first_batch']),
        'rules':{'type':'array','minItems':0,'maxItems':3,'items':_object({
            'feature':_enum(['selected_count','absent_count']), 'at_least':{'type':'integer','minimum':0,'maximum':12},
            'projection':_enum(['whole_input','selected_slots','present_slots'])})}})


def validate(strategy: Any) -> None:
    from operator_shell import recursive_contract as jsonschema
    jsonschema.validate(strategy,strategy_schema())


def execute(strategy: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    """Compose limited projection, ordering, decomposition and stopping controls."""
    validate(strategy)
    data=case['record']; keys=case['fields']
    if (not isinstance(data,dict) or not isinstance(keys,list) or not 1<=len(keys)<=12
            or any(not isinstance(k,str) or not 1<=len(k)<=80 for k in keys) or len(set(keys))!=len(keys)
            or len(json.dumps(data,allow_nan=False).encode())>32768):
        raise ValueError('bounded_cached_case_required')
    order=list(keys)
    if strategy['ordering']!='source':
        order.sort(key=lambda k: (k in data) if strategy['ordering']=='absent_first' else (k not in data))
    features={'selected_count':len(keys),'absent_count':sum(k not in data for k in keys)}
    action=strategy['projection']
    for rule in strategy['rules']:
        if features[rule['feature']]>=rule['at_least']:
            action=rule['projection'];break
    slots={}; cost=0; batches=0; evidence=[]
    # Pure primitive reused by the production cached-input instrument.
    from .question_measurements import run
    for start in range(0,len(order),strategy['batch_size']):
        selected=order[start:start+strategy['batch_size']]
        output=run(action,data,selected)
        evidence.append(output)
        cost+=len(json.dumps(output,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode())
        if 'record' in output:
            for key in selected:
                slots[key]={'state':'present','value':copy.deepcopy(output['record'][key])} if key in output['record'] else {'state':'absent'}
        else: slots.update(output['slots'])
        batches+=1
        if strategy['stopping']=='first_batch':break
    return {'slots':slots,'context_bytes':cost,'batches':batches,'operation':action,'evidence':evidence}


def oracle(case: dict[str, Any], output: dict[str, Any]) -> list[dict[str, Any]]:
    """Independent expected mapping: absence differs from null, false and zero."""
    errors=[]
    for key in case['fields']:
        expected=({'state':'present','value':case['record'][key]} if key in case['record'] else {'state':'absent'})
        actual=output['slots'].get(key)
        if digest(expected)!=digest(actual):errors.append({'field':key,'expected':expected,'actual':actual})
    extra=set(output['slots'])-set(case['fields'])
    if extra:errors.append({'unexpected_fields':sorted(extra)})
    return errors


def cases(seed: int, stage: int, *, count: int = 8) -> list[dict[str, Any]]:
    if type(seed) is not int or stage not in (0,1,2) or not 1<=count<=16:raise ValueError('bounded_suite_required')
    rng=random.Random(seed); result=[]
    for i in range(count):
        # Domain labels are deliberately irrelevant to the extraction contract.
        domain=('laboratory','inventory','survey','interface')[i%4]
        n=2 if stage==0 else rng.randint(3,12)
        fields=[f'{domain}_{rng.randrange(10**8):08d}_{j}' for j in range(n)]
        values=[None,False,0,{'state':'unknown'},'',{'value':0,'unit':'ms'}]
        record={k:copy.deepcopy(values[(i+j)%len(values)]) for j,k in enumerate(fields) if j%3!=0}
        record['unselected_payload']='x'*rng.randint(240,800)
        rng.shuffle(fields)
        result.append({'record':record,'fields':fields})
    return result


def assess(strategy: dict[str, Any], baseline: dict[str, Any], suite: list[dict[str, Any]]) -> dict[str, Any]:
    validate(strategy);validate(baseline)
    counts={'cases':len(suite),'candidate_successes':0,'baseline_successes':0,'regressions':0,
            'candidate_context_bytes':0,'baseline_context_bytes':0,'candidate_batches':0,'baseline_batches':0}
    counterexamples=[]
    for i,case in enumerate(suite):
        current=execute(strategy,case); old=execute(baseline,case)
        errors=oracle(case,current); previous=oracle(case,old)
        counts['candidate_successes']+=not errors;counts['baseline_successes']+=not previous
        counts['regressions']+=bool(errors) and not previous
        for arm,run in (('candidate',current),('baseline',old)):
            for quantity in ('context_bytes','batches'):counts[arm+'_'+quantity]+=run[quantity]
        if errors and len(counterexamples)<2:counterexamples.append({'case':case,'errors':errors[:2],'case_index':i})
    return {**counts,'counterexamples':counterexamples,'suite_sha256':digest(suite),
            'complete':counts['candidate_successes']==len(suite) and counts['regressions']==0,
            'scope':'cached_projection_only','provider_speed_improvement':'not_measured',
            'research_improvement':'not_established'}


def evaluate(proposal: dict[str, Any], baseline: dict[str, Any], seed: int, stage: int) -> dict[str, Any]:
    own=assess(proposal['strategy'],baseline,proposal['practice_cases'])
    transfer=assess(proposal['strategy'],baseline,cases(seed,stage))
    regression=assess(proposal['strategy'],baseline,cases(seed^0x71A,2,count=4))
    metric=proposal['prediction']['quantity'];direction=proposal['prediction']['direction']
    a=transfer['candidate_'+metric];b=transfer['baseline_'+metric]
    supported={'decrease':a<b,'increase':a>b,'unchanged':a==b}[direction]
    improvement=(transfer['candidate_successes']>transfer['baseline_successes'] or
                 transfer['candidate_context_bytes']<transfer['baseline_context_bytes'])
    eligible=all(r['complete'] for r in (own,transfer,regression)) and (stage<2 or improvement)
    return {'evaluator':VERSION,'evaluator_sha256':fingerprint(),'stage':stage,
            'authored_cases':own,'transfer':transfer,'regression':regression,
            'hypothesis_status':'supported' if supported else 'refuted',
            'method_review_eligible':eligible,'improvement_established_in_instrument':eligible and improvement,
            'repair_credit_separate':True,'allowance_added':0,'scientific_progress_credited':False}
