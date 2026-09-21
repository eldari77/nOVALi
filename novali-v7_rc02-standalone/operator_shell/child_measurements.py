"""Bounded measurements derived from frozen artifact data, never model values."""
from __future__ import annotations
import copy
import json
import math
from pathlib import Path
from typing import Any
from .research_tools import digest

VERSION = 'child_artifact_measurements_v1'
OPERATIONS = ('count_records', 'count_present', 'fraction_present')
PROGRAM_VERSION = 'child_measurement_program_v1'
PROGRAM_STAGES = ['read_current_input', 'evaluate_current_definition', 'preserve_unknown', 'compare_threshold']
PROGRAM_BINDINGS = {'target_artifact':'selected_artifact','fixture_ref':'selected_fixture','definition':'selected_measurement'}


def program_schema() -> dict[str, Any]:
    from .planner_authoring import _object,_enum,_string
    from .directive_candidates import STOPS
    return _object({'representation':{'const':PROGRAM_VERSION},'name':_string(5,100),'adapter':{'const':'interface_contract'},
        'bindings':{'const':PROGRAM_BINDINGS},'steps':{'type':'array','minItems':4,'maxItems':4,
            'uniqueItems':True,'items':_enum(PROGRAM_STAGES)},'stop_conditions':{'const':STOPS}})


def program_issues(method: dict[str, Any]) -> list[dict[str,str]]:
    from .directive_candidates import STOPS
    valid=(set(method)=={'representation','name','adapter','bindings','steps','stop_conditions'}
        and method.get('representation')==PROGRAM_VERSION and method.get('adapter')=='interface_contract'
        and method.get('bindings')==PROGRAM_BINDINGS and method.get('steps')==PROGRAM_STAGES
        and method.get('stop_conditions')==STOPS and isinstance(method.get('name'),str) and 5<=len(method['name'])<=100)
    return [] if valid else [{'path':'/method/steps','code':'bounded_measurement_program_order_and_bindings_required'}]


def execute_program(method: dict[str, Any], spec: dict[str, Any], payload: dict[str, Any], rows: Any) -> dict[str, Any]:
    """Execute declared stages on current bindings. Free prose is not a program."""
    from .directive_candidates import check_interface
    if program_issues(method):raise ValueError('valid_measurement_program_required')
    trace=[];actual=None;reason='';source=None
    for stage in method['steps']:
        trace.append(stage)
        if stage=='read_current_input':source=rows
        elif stage=='evaluate_current_definition':actual,reason=value(spec['operation'],spec['field'],source)
        elif stage=='preserve_unknown' and actual is None:return {'value':None,'outcome':'unknown','reason':reason,'trace':trace}
        elif stage=='compare_threshold':return {'value':actual,'outcome':check_interface(payload,actual,spec['unit'],True),'reason':reason,'trace':trace}
    raise ValueError('measurement_program_did_not_settle')


def freeze(root: Path, frozen: dict[str, Any]) -> list[dict[str, Any]]:
    from .directive_obligations import content
    result = []; size = 0
    for ref in frozen['artifact_refs']:
        if not ref.endswith('.json'): continue
        try:
            raw = content(root, frozen['directive_id'], ref); data = json.loads(raw)
        except (ValueError, OSError): continue
        if not isinstance(data, dict): continue
        for field, rows in data.items():
            if field == 'novali_research_addenda' or not isinstance(rows, list) or not rows or len(rows) > 32: continue
            if any(not isinstance(row, dict) for row in rows): continue
            fields = sorted({k for row in rows for k in row if isinstance(k,str)})
            if len(fields)>24: continue
            body = {'artifact_ref':ref, 'source_sha256':__import__('hashlib').sha256(raw).hexdigest(),
                'pointer':'/'+field.replace('~','~0').replace('/','~1'), 'rows':rows, 'fields':fields}
            cost=len(json.dumps(body).encode())
            if cost>6000 or size+cost>10000: continue
            size+=cost; result.append({'id':'measurement-input-'+digest(body)[:24],**body})
            frozen['dependencies'][ref]=body['source_sha256']
            if len(result)>=4:return result
    return result


def value(operation: str, field: str, rows: Any) -> tuple[float | int | None, str]:
    if not isinstance(rows,list) or len(rows)>32 or any(not isinstance(r,dict) for r in rows):
        return None,'invalid_or_oversized_input'
    if operation=='count_records':return len(rows),''
    if not rows:return None,'empty_population'
    present=0
    for row in rows:
        if field not in row:continue
        item=row[field]
        if item is None or isinstance(item,str) and item.strip().lower() in {'unknown','unresolved','tbd',''}:
            return None,'unresolved_source_value'
        present+=1
    return (present if operation=='count_present' else present/len(rows)),''


def schema(context: dict[str, Any]) -> dict[str, Any]:
    from .planner_authoring import _object,_enum,_string
    return _object({'input_id':_enum([row['id'] for row in context['measurement_inputs']]),
        'operation':_enum(list(OPERATIONS)), 'field':_enum(['',*sorted({f for r in context['measurement_inputs'] for f in r['fields']})]),
        'unit':_enum(['count','ratio']), 'predicted_value':{'type':['number','null']},
        'predicted_outcome':_enum(['pass','fail','unknown']), 'falsifier':_string(12,180)})


def check(context: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    from .directive_candidates import check_interface
    spec=payload.get('measurement')
    required={'input_id','operation','field','unit','predicted_value','predicted_outcome','falsifier'}
    if not isinstance(spec,dict) or set(spec)!=required:raise ValueError('typed_artifact_measurement_required')
    source=next((r for r in context.get('measurement_inputs',[]) if r['id']==spec['input_id']),None)
    if not source:raise ValueError('current_frozen_measurement_input_required')
    op=spec['operation']; field=spec['field']
    if op not in OPERATIONS or (field!='' if op=='count_records' else field not in source['fields']):
        raise ValueError('registered_operation_and_source_field_required')
    unit='ratio' if op=='fraction_present' else 'count'
    if spec['unit']!=unit or payload['unit']!=unit:raise ValueError('measurement_unit_mismatch')
    if payload['fixture_ref']!=source['artifact_ref']:raise ValueError('measurement_fixture_binding_mismatch')
    if not isinstance(spec['falsifier'],str) or not 12<=len(spec['falsifier'])<=180:raise ValueError('bounded_measurement_falsifier_required')
    prediction=spec['predicted_value']
    if prediction is not None and (type(prediction) not in (int,float) or not math.isfinite(prediction)):
        raise ValueError('finite_or_unknown_measurement_prediction_required')
    if spec['predicted_outcome'] not in ('pass','fail','unknown'):raise ValueError('typed_measurement_prediction_required')
    actual,reason=value(op,field,source['rows'])
    observed=check_interface(payload,actual,unit,actual is not None)
    # The interface comparator calls its unresolved state "unknown".
    errors=[]
    if prediction!=actual or (type(prediction) is bool):errors.append({'path':'/payload/measurement/predicted_value',
        'code':'artifact_measurement_prediction_refuted','before':prediction,'actual':actual,'reason':reason})
    if spec['predicted_outcome']!=observed:errors.append({'path':'/payload/measurement/predicted_outcome',
        'code':'artifact_measurement_outcome_refuted','before':spec['predicted_outcome'],'actual':observed,'reason':reason})
    variants=[('missing_population',None),('empty_population',[]),('invalid_record',[None]),
        ('resource_limit',[{}]*33),('unknown_field',[{field:None}])]
    probes=[{'case':name,'input':rows,'value':value(op,field,rows)[0],
        'reason':value(op,field,rows)[1]} for name,rows in variants]
    return {'version':VERSION,'input_id':source['id'],'source_sha256':source['source_sha256'],
        'artifact_ref':source['artifact_ref'],'pointer':source['pointer'],'operation':op,'field':field,
        'value':actual,'unit':unit,'outcome':observed,'reason':reason,'counterexamples':errors,
        'independent_cases':probes,'definition':f"{op}({source['artifact_ref']}#{source['pointer']}, field={field!r}) in {unit}",
        'semantic_review_required':True,'scope':'frozen_artifact_content_only','scientific_claim_verified':False}
