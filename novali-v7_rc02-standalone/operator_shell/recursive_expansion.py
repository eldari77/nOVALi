"""Novali requests bounded measurement adapters; independent review versions them.

Adapters select installed pure instruments, never execute proposed code or grant
network, filesystem, scientific or spending authority. Unknown capabilities park.
"""
from __future__ import annotations
import copy
from pathlib import Path
from . import research_procedures as records, recursive_evaluator as evaluator
from .research_tools import read_json,write_json,digest
from .recursive_questions import BASE

CATALOG = {
    'emitted_slots': {'unit':'count','meaning':'number of keys in emitted selected-field slots'},
    'absent_slots': {'unit':'count','meaning':'number of emitted slots explicitly marked absent'},
    'evidence_bytes': {'unit':'UTF-8 bytes','meaning':'serialized evidence bytes summed over executed batches'},
    'batch_count': {'unit':'count','meaning':'number of batches actually executed'},
}


def versions(root: Path) -> list[dict]:
    return [records.read(root,'recursive_adapter_versions',p.stem) for p in (root/'research_methods/recursive_adapter_versions').glob('*.json')]


def active(root: Path) -> dict:
    pointer=read_json(root/'research_methods/recursive_adapter_latest.json')
    if not pointer:return {'version_id':None,'observables':{}}
    version=records.read(root,'recursive_adapter_versions',pointer['version_id'])
    if version['implementation']!=records.implementation():return {'version_id':version['id'],'observables':{},'blocked':'adapter_revalidation_required'}
    return {'version_id':version['id'],'observables':version['observables']}


def definitions(root: Path) -> dict:
    return {**BASE,**active(root)['observables']}


def measure(name: str, case: dict, output: dict) -> int | str:
    if name=='effective_operation':return output['operation']
    if name=='state_errors':return len(evaluator.oracle(case,output))
    if name=='emitted_slots':return len(output['slots'])
    if name=='absent_slots':return sum(s.get('state')=='absent' for s in output['slots'].values())
    if name=='evidence_bytes':return output['context_bytes']
    if name=='batch_count':return output['batches']
    raise ValueError('uninstalled_measurement_primitive')


def request_schema() -> dict:
    from .planner_authoring import _object,_enum
    return _object({'intent':_enum(['request_capability']),'primitive':_enum([*CATALOG,'unavailable']),
        'needed_observation':{'type':'string','minLength':16,'maxLength':160},
        'why_current_tools_insufficient':{'type':'string','minLength':16,'maxLength':160}})


def submit(root: Path, episode: dict, proposal: dict) -> dict:
    from .recursive_contract import validate
    validate(proposal,request_schema())
    if proposal['primitive'] in definitions(root):raise ValueError('requested_observable_already_available')
    return records.store(root,'recursive_expansion_requests',{'episode_id':episode['id'],
        'root_episode_id':episode['root_episode_id'],'proposal':proposal,'authored_by':'Novali',
        'implementation':records.implementation(),'registry_parent':active(root)['version_id'],
        'limits':{'selected_fields':12,'input_bytes':32768,'provider_calls':0},'allowance_added':0})


def verify(primitive: str) -> dict:
    """Independent formulas over fresh valid, reordered and invalid inputs."""
    import json,math
    if primitive not in CATALOG:raise ValueError('installed_independently_testable_adapter_required')
    count=0
    for seed in (18437,57191):
        for case in evaluator.cases(seed,2,count=8):
            for projection in ('whole_input','selected_slots','present_slots'):
                for batch in (1,4,12):
                    strategy={**evaluator.BASELINE,'projection':projection,'batch_size':batch}
                    output=evaluator.execute(strategy,case)
                    n=len(case['fields']);present=sum(k in case['record'] for k in case['fields'])
                    if primitive=='emitted_slots':expected=present if projection=='present_slots' else n
                    elif primitive=='absent_slots':expected=0 if projection=='present_slots' else n-present
                    elif primitive=='batch_count':expected=math.ceil(n/batch)
                    else:expected=sum(len(json.dumps(e,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()) for e in output['evidence'])
                    if measure(primitive,case,output)!=expected:raise ValueError('adapter_independent_counterexample')
                    count+=1
    invalid=({'record':{},'fields':[]},{'record':{},'fields':['x','x']},{'record':{},'fields':[str(i) for i in range(13)]})
    for case in invalid:
        try:evaluator.execute(evaluator.BASELINE,case)
        except ValueError:continue
        raise ValueError('adapter_resource_or_input_guard_failed')
    return {'valid_checks':count,'invalid_checks':len(invalid),'passed':True,'primitive':primitive,
        'definition':CATALOG[primitive],'unknown_preserved_as_input_state':True,'new_execution_authority':False}


def review(root: Path, request_id: str, *, decision: str, reviewer: str, evidence_reference: str) -> dict:
    from .lesson_review_budget import charge
    if decision not in ('approve','reject') or min(len(reviewer),len(evidence_reference))<16:raise ValueError('independent_expansion_review_required')
    request=records.read(root,'recursive_expansion_requests',request_id)
    prior=next((records.read(root,'recursive_expansion_reviews',p.stem) for p in (root/'research_methods/recursive_expansion_reviews').glob('*.json') if read_json(p).get('request_id')==request_id),None)
    if prior:
        if prior['decision']!=decision:raise ValueError('immutable_expansion_review')
        return apply(root,prior)
    episode=records.read(root,'learning_episodes',request['episode_id']);task=read_json(root/'research_methods/episode_tasks'/(episode['id']+'.json'))
    if task.get('expansion_request_id')!=request_id or task['state']!='awaiting_recursive_expansion_review':raise ValueError('owned_pending_expansion_required')
    if not any(records.read(root,'attempts',a).get('response')==request['proposal'] for a in task['attempt_ids']):raise ValueError('novali_authored_expansion_required')
    if request['implementation']!=records.implementation():raise ValueError('expansion_request_revalidation_required')
    with charge(root,episode):
        report=verify(request['proposal']['primitive']) if decision=='approve' else None
        if decision=='approve' and active(root)['version_id']!=request['registry_parent']:raise ValueError('preserve_changed_adapter_registry')
        result=records.store(root,'recursive_expansion_reviews',{'request_id':request_id,'decision':decision,
            'reviewer':reviewer,'evidence_reference':evidence_reference,'report':report,'implementation':records.implementation()})
        return apply(root,result)


def apply(root: Path, review: dict) -> dict:
    request=records.read(root,'recursive_expansion_requests',review['request_id']);tp=root/'research_methods/episode_tasks'/(request['episode_id']+'.json');task=read_json(tp)
    if task.get('expansion_review_id')==review['id']:return review
    if review['decision']=='approve':
        current=active(root);primitive=request['proposal']['primitive']
        result=records.store(root,'recursive_adapter_versions',{'parent_version_id':request['registry_parent'],
            'review_id':review['id'],'implementation':records.implementation(),
            'observables':{**current['observables'],primitive:CATALOG[primitive]}})
        if current['version_id'] not in (request['registry_parent'],result['id']):raise ValueError('preserve_newer_adapter_version')
        write_json(root/'research_methods/recursive_adapter_latest.json',{'version_id':result['id']})
    task.update(state='recursive_expansion_reviewed',expansion_review_id=review['id']);write_json(tp,task)
    return review


def rollback(root: Path, *, expected_version: str, reviewer: str, reason: str) -> dict:
    if min(len(reviewer),len(reason))<16 or active(root)['version_id']!=expected_version:raise ValueError('owned_adapter_rollback_required')
    version=records.read(root,'recursive_adapter_versions',expected_version)
    receipt=records.store(root,'recursive_adapter_rollbacks',{'version_id':expected_version,'parent_version_id':version['parent_version_id'],'reviewer':reviewer,'reason':reason})
    write_json(root/'research_methods/recursive_adapter_latest.json',{'version_id':version['parent_version_id']} if version['parent_version_id'] else {})
    return receipt
