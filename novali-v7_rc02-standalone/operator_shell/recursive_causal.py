"""Failure-bound edits and public before/after measurements, without solutions."""
from __future__ import annotations
import copy
from . import recursive_corrections as typed, recursive_practice_checks as checks, recursive_evaluator as evaluator
from .recursive_contract import validate
from .research_tools import digest

VERSION='causal_corrections_v3'
SEMANTICS={'projection':{'whole_input':'retain the input record; runtime marks selected absent fields',
    'selected_slots':'emit every selected field with present/absent state',
    'present_slots':'emit only selected keys present in the input'},
    'rules':'first matching feature >= threshold overrides projection; otherwise use default projection',
    'batch':'fields per batch; ordering reorders them; first_batch stops early; all_batches completes them'}


def get(value: dict, path: str):
    for part in path.strip('/').split('/'):value=value[int(part)] if isinstance(value,list) else value[part]
    return value


def put(value: dict, path: str, replacement, *, remove: bool=False):
    parts=path.strip('/').split('/');target=value
    for part in parts[:-1]:target=target[int(part)] if isinstance(target,list) else target[part]
    key=int(parts[-1]) if isinstance(target,list) else parts[-1]
    if remove:del target[key]
    else:target[key]=copy.deepcopy(replacement)


def offered(proposal_schema: dict, prior: dict, paths: list[str], *, diagnostic: dict | None=None) -> tuple[dict,dict,dict]:
    fields,_=typed.offered(proposal_schema,prior,paths)
    diagnostic=diagnostic or checks.diagnostic(prior['strategy'])
    matches=[r['rule'] for r in diagnostic['rule_trace'] if r['matched']]
    if diagnostic['errors'] and matches:
        index=matches[0]
        # Bind edits to the executed branch; changing an overridden default cannot fix it.
        for name in ('rules','projection','order','batch'):fields.pop(name,None)
        if prior['strategy']['stopping']=='all_batches':fields.pop('stop',None)
        item=evaluator.strategy_schema()['properties']['rules']['items']['properties']
        for name in ('feature','at_least','projection'):
            shape=copy.deepcopy(item[name]);old=prior['strategy']['rules'][index][name]
            if 'enum' in shape:shape['enum']=[v for v in shape['enum'] if v!=old]
            fields['rule_'+name]={'path':f'/strategy/rules/{index}/{name}','value_contract':shape}
        fields['remove_rule']={'path':f'/strategy/rules/{index}','remove':True,'value_contract':{'type':'boolean','const':True}}
    branches=[{'type':'object','properties':{'field':{'type':'string','const':key},'value':value['value_contract']},
        'required':['field','value'],'additionalProperties':False} for key,value in fields.items()]
    schema={'type':'object','properties':{'edits':{'type':'array','minItems':1,'maxItems':6,'items':{'anyOf':branches}}},
            'required':['edits'],'additionalProperties':False}
    binding={'diagnostic_sha256':digest(diagnostic),'matched_rule':matches[0] if matches else None}
    return fields,schema,binding


def resolve(submitted: dict, prior: dict, schema: dict, fields: dict) -> tuple[dict,list[dict]]:
    validate(submitted,schema);result=copy.deepcopy(prior);changes=[];paths=[]
    for edit in submitted['edits']:
        binding=fields[edit['field']];path=binding['path']
        if any(path==p or path.startswith(p+'/') or p.startswith(path+'/') for p in paths):
            raise ValueError('overlapping_causal_edits')
        paths.append(path);before=get(prior,path);after=edit['value']
        from .question_quality import cosmetic_only
        if not binding.get('remove') and cosmetic_only(before,after):raise ValueError('unchanged_targeted_edit:'+path)
        put(result,path,after,remove=binding.get('remove',False))
        changes.append({'path':path,'before':before,'after':None if binding.get('remove') else after})
    return result,changes


def comparison(before: dict, after: dict) -> dict:
    """A public diagnostic grid, separate from withheld acceptance partitions."""
    result={'cases':0,'repaired':0,'partly_repaired':0,'unchanged_failures':0,'regressions':0,
            'preserved_correct':0,'representation_only_changes':0,'acceptance_credit':False}
    for count in range(1,13):
        fields=[str(i) for i in range(count)]
        for absent in range(count+1):
            case={'record':{k:None for k in fields[absent:]},'fields':fields}
            a=evaluator.execute(before,case);b=evaluator.execute(after,case)
            ae=evaluator.oracle(case,a);be=evaluator.oracle(case,b);result['cases']+=1
            if ae and not be:result['repaired']+=1
            elif ae and len(be)<len(ae):result['partly_repaired']+=1
            elif ae and be:result['unchanged_failures']+=1
            if len(be)>len(ae):result['regressions']+=1
            if not ae and not be:result['preserved_correct']+=1
            if a!=b and a['slots']==b['slots']:result['representation_only_changes']+=1
    result['failure_repair_demonstrated']=bool(result['repaired'] and not result['regressions'])
    return result


def rejection(prior: dict, submitted: dict, schema: dict, fields: dict, *, protected_states: list[str]) -> dict:
    packet=typed.packet(prior,{'corrections':{}},{'type':'object'},typed=False,protected_states=protected_states)
    packet['submitted_sha256']=digest(submitted);packet['schema_sha256']=digest(schema)
    packet['findings']=typed.errors(submitted,schema)
    fragment=copy.deepcopy(prior)
    for edit in submitted.get('edits',[]) if isinstance(submitted,dict) and isinstance(submitted.get('edits'),list) else []:
        if not isinstance(edit,dict) or not isinstance(edit.get('field'),str) or edit['field'] not in fields or 'value' not in edit:continue
        binding=fields[edit['field']];path=binding['path'];value=edit['value']
        packet['rejected_patch'][path]=copy.deepcopy(value)
        try:validate(value,binding['value_contract']);put(fragment,path,value,remove=binding.get('remove',False))
        except (ValueError,TypeError,IndexError,KeyError):continue
    try:
        evaluator.validate(fragment['strategy']);packet['diagnostic']=checks.diagnostic(fragment['strategy'])
        packet['repair_comparison']=comparison(prior['strategy'],fragment['strategy'])
    except (ValueError,TypeError,KeyError):pass
    from .recursive_growth import schema as proposal_schema
    cases=[]
    for case in fragment.get('practice_cases',[])[:3]:
        try:validate(case,proposal_schema()['properties']['practice_cases']['items']);cases.append(case)
        except (ValueError,TypeError):pass
    packet['observed_discovery_states']=checks.coverage({**prior,'practice_cases':cases},0)['covered_states']
    packet['lost_discovery_states']=sorted(set(protected_states)-set(packet['observed_discovery_states']))
    return packet
