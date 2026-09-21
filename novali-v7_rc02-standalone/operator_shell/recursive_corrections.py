"""Typed edits, complete bounded diagnostics, and rejected-patch preservation.

Diagnostic fragments never authorize acceptance or silently repair an envelope.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
from typing import Any
from . import recursive_practice_checks as checks, recursive_evaluator as evaluator
from .recursive_contract import validate
from .research_tools import digest

VERSION='typed_recursive_corrections_v2'
HANDLES={'batch':'/strategy/batch_size','order':'/strategy/ordering','projection':'/strategy/projection',
         'rules':'/strategy/rules','stop':'/strategy/stopping','cases':'/practice_cases',
         'quantity':'/prediction/quantity','direction':'/prediction/direction',
         'falsifier':'/falsifier','relevance':'/relevance'}


def fingerprint() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def errors(value: Any, schema: dict, path: str='$') -> list[dict]:
    """Walk all bounded fields instead of stopping at the first failing field."""
    result=[]
    def add(code, detail):result.append({'path':path,'code':code,'detail':detail})
    if 'anyOf' in schema:
        alternatives=schema['anyOf'];matched=False
        for branch in alternatives:
            try:validate(value,branch);matched=True;break
            except ValueError:pass
        if not matched:
            tagged=[b for b in alternatives if isinstance(value,dict) and
                    b.get('properties',{}).get('field',{}).get('const')==value.get('field')]
            if tagged:result.extend(errors(value,tagged[0],path))
            else:add('no_offered_alternative','Use a listed field and its declared value type.')
    shallow={k:v for k,v in schema.items() if k not in ('anyOf','properties','required','additionalProperties','items')}
    if shallow.get('type')=='array':shallow['items']={}
    try:validate(value,shallow,path)
    except (ValueError,TypeError) as exc:add('value_constraint',str(exc))
    if schema.get('type')=='object' and isinstance(value,dict):
        props=schema.get('properties',{});extra=schema.get('additionalProperties',True)
        for k in schema.get('required',[]):
            if k not in value:add('missing_field',k)
        for k,v in list(value.items())[:32]:
            if k in props:result.extend(errors(v,props[k],path+'/'+k))
            elif extra is False:result.append({'path':path+'/'+str(k),'code':'unoffered_field','detail':'Use a listed field.'})
            elif isinstance(extra,dict):result.extend(errors(v,extra,path+'/'+str(k)))
    if schema.get('type')=='array' and isinstance(value,list):
        for i,v in enumerate(value[:12]):result.extend(errors(v,schema.get('items',{}),path+'/'+str(i)))
    # Schema/value bounds already constrain legitimate data; report overflow explicitly.
    return result[:32]+([{'path':path,'code':'more_findings','detail':str(len(result)-32)}] if len(result)>32 else [])


def offered(proposal_schema: dict, prior: dict, paths: list[str]) -> tuple[dict,dict]:
    fields={};branches=[]
    for name,path in HANDLES.items():
        if not any(path==p or path.startswith(p+'/') for p in paths):continue
        shape=proposal_schema
        for part in path.strip('/').split('/'):shape=shape['properties'][part]
        shape=copy.deepcopy(shape)
        if 'enum' in shape:shape['enum']=[v for v in shape['enum'] if v!=checks.get(prior,path)]
        fields[name]={'path':path,'value_contract':shape}
        branches.append({'type':'object','properties':{'field':{'type':'string','const':name},'value':shape},
                         'required':['field','value'],'additionalProperties':False})
    grammar={'type':'object','properties':{'edits':{'type':'array','minItems':1,'maxItems':6,'items':{'anyOf':branches}}},
             'required':['edits'],'additionalProperties':False}
    return fields,grammar


def bindings(submitted: Any, *, typed: bool) -> list[tuple[str,Any]]:
    if not isinstance(submitted,dict):return []
    if typed:
        edits=submitted.get('edits',[])
        if not isinstance(edits,list):return []
        return [(HANDLES[e['field']],e['value']) for e in edits[:12] if isinstance(e,dict)
                and isinstance(e.get('field'),str) and e['field'] in HANDLES and 'value' in e]
    values=submitted.get('corrections',{})
    if not isinstance(values,dict):return []
    # Legacy aliases are recognized for diagnosis only, never accepted by resolve.
    result=[]
    for k,v in list(values.items())[:16]:
        if k=='strategy' and isinstance(v,dict):result.extend(('/strategy/'+a,b) for a,b in v.items())
        else:result.append((k if k.startswith('/') else '/'+k,v))
    return result


def packet(prior: dict, submitted: Any, schema: dict, *, typed: bool, stage: int=0,
           protected_states: list[str] | None=None) -> dict:
    findings=errors(submitted,schema)
    attempted=bindings(submitted,typed=typed);fragment=copy.deepcopy(prior);seen=set();preview={}
    for path,value in attempted:
        try:before=checks.get(prior,path)
        except (KeyError,TypeError):continue
        if path in seen:findings.append({'path':path,'code':'duplicate_edit','detail':'Select each field once.'})
        seen.add(path)
        preview[path]=({'same_as_baseline':True} if before==value else copy.deepcopy(value))
        if before==value:findings.append({'path':path,'code':'unchanged_edit','detail':'Omit supporting fields that do not need change.'})
        target=fragment;parts=path.strip('/').split('/')
        try:
            for part in parts[:-1]:target=target[part]
            target[parts[-1]]=copy.deepcopy(value)
        except (KeyError,TypeError):pass
    diagnostic=None;states=[]
    try:
        evaluator.validate(fragment['strategy'])
        diagnostic=checks.diagnostic(fragment['strategy'])
        if checks.behavior_signature(fragment['strategy'])==checks.behavior_signature(prior['strategy']):
            findings.append({'path':'/strategy','code':'effective_behavior_unchanged','detail':'The executable fragment retains the previous effective behavior.'})
    except (ValueError,TypeError,KeyError):pass
    from .recursive_growth import schema as proposal_schema
    valid_cases=[]
    raw=fragment.get('practice_cases',[])
    if isinstance(raw,list):
        for case in raw[:3]:
            try:validate(case,proposal_schema()['properties']['practice_cases']['items']);valid_cases.append(case)
            except (ValueError,TypeError):pass
    if valid_cases:
        states=checks.coverage({**prior,'practice_cases':valid_cases},stage)['covered_states']
    lost=sorted(set(protected_states or [])-set(states))
    if lost:findings.append({'path':'/practice_cases','code':'lost_discovery_coverage','detail':','.join(lost)})
    result={'version':VERSION,'validator_sha256':fingerprint(),'submitted_sha256':digest(submitted),
        'schema_sha256':digest(schema),'findings':findings,'rejected_patch':preview,
        'diagnostic':diagnostic,'observed_discovery_states':states,'lost_discovery_states':lost,
        'partial_results_only':True,'acceptance_credit':False}
    return result


def resolve(submitted: dict, prior: dict, schema: dict, fields: dict) -> tuple[dict,list[dict]]:
    validate(submitted,schema)
    paths={item['path']:item['value_contract'] for item in fields.values()}
    pairs=bindings(submitted,typed=True)
    if len({p for p,_ in pairs})!=len(pairs):raise ValueError('duplicate_targeted_edit')
    legacy={'type':'object','properties':{'corrections':{'type':'object','properties':paths,'additionalProperties':False}},
            'required':['corrections'],'additionalProperties':False}
    return checks.resolve({'corrections':dict(pairs)},prior,legacy)


def compact_packet(value: dict) -> dict:
    """Full receipt stays immutable; compact previews identify omitted large values."""
    preview={};unchanged=[];findings={}
    reverse={path:handle for handle,path in HANDLES.items()}
    def label(path):
        if path.startswith('$/corrections/'):path=path[len('$/corrections/'):]
        return reverse.get(path,path)
    for path,item in value.get('rejected_patch',{}).items():
        if item=={'same_as_baseline':True}:unchanged.append(label(path));continue
        encoded=json.dumps(item,ensure_ascii=False,separators=(',',':'))
        preview[label(path)]=item if len(encoded.encode())<=750 else {'value_sha256':digest(item),'status':'large_rejected_value_retained_in_receipt'}
    for f in value['findings'][:20]:
        if f['code']=='unchanged_edit':continue  # Explicit list below carries the same finding.
        detail=f['detail'].removeprefix(f['path']+': ')
        findings.setdefault(label(f['path']),[]).append({'code':f['code'],'detail':detail[:160]})
    return {'submitted_sha256':value['submitted_sha256'],
        'findings':findings,'unchanged_fields':unchanged,
        'additional_finding_count':max(0,len(value['findings'])-20),'rejected_patch':preview,
        'observed_discovery_states':value['observed_discovery_states'],'lost_discovery_states':value['lost_discovery_states']}


def describe(shape: dict) -> dict:
    result={k:shape[k] for k in ('type','enum','minLength','maxLength','minItems','maxItems','maxProperties','minimum','maximum') if k in shape}
    if 'properties' in shape:result['fields']={k:describe(v) for k,v in shape['properties'].items()}
    if 'items' in shape:result['items']=describe(shape['items'])
    if isinstance(shape.get('additionalProperties'),dict):result['values']=describe(shape['additionalProperties'])
    if 'anyOf' in shape:result['types']=[s.get('type') for s in shape['anyOf']]
    return result
