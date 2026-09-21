"""Versioned bounded execution previews; never a source of review or learning credit."""
from __future__ import annotations

import copy
from typing import Any
from . import child_procedure_programs as programs
from .child_repairs import baseline
from .research_tools import digest

VERSION = 'child_procedure_execution_v1'


def active(context: dict[str, Any]) -> bool:
    return context.get('procedure_execution_contract') == VERSION


def methods(context: dict[str, Any], adapter: str) -> dict[str, dict[str, Any]]:
    from .child_repairs import BINDINGS
    from .directive_candidates import STOPS
    result = {}
    if adapter in programs.STAGES:
        result['builtin:' + adapter] = {'representation': programs.VERSION, 'name': adapter,
            'adapter': adapter, 'bindings': BINDINGS[adapter], 'steps': programs.STAGES[adapter], 'stop_conditions': STOPS}
    previous = (baseline(context) or {}).get('method')
    if previous and previous.get('adapter') == adapter and not programs.issues(previous):
        result['previous:' + digest(previous)[:16]] = previous
    for row in context.get('methods', []):
        method = {k: row[k] for k in ('representation','name','adapter','bindings','steps','stop_conditions') if k in row}
        if method.get('adapter') == adapter and not programs.issues(method): result[row['id']] = method
    return result


def contract(context: dict[str, Any], original: tuple[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    if not active(context): return original
    from .planner_authoring import _object, _enum, _string
    instructions, schema = original
    schema = copy.deepcopy(schema)
    previous = baseline(context)
    preview = context.get('execution_preview')
    for variant in schema['oneOf']:
        props = variant['properties']
        oid = props.get('obligation_id', {}).get('const')
        obligation = next((o for o in context['obligations'] if o['id'] == oid), None)
        if not obligation: continue
        available = methods(context, obligation['adapter'])
        for key in ('method_plan', 'method'):
            if key in props and available:
                props[key] = {'anyOf': [props[key], _object({'method_ref': _enum(list(available))})]}
        if 'rationale' in props: props['rationale']['maxLength'] = 160
        # Failed fields are the repair surface; complete valid payload stays in the hashed baseline.
        if props['intent']['const'] == 'patch':
            paths = failed_paths(context)
            if paths: props['edits']['items']['properties']['path'] = _enum(paths)
    for obligation in context['obligations']:
        if not obligation['eligible'] or obligation['adapter'] != 'record_extraction': continue
        common = {'obligation_id': {'const': obligation['id']}, 'rationale': {**_string(8,160), 'pattern': r'^.*[.!?]["\u2019\u201d`)]?$'},
            'lesson_id': _enum(['none', *[m['id'] for m in context.get('methods',[])]]),
            'lesson_use': _enum(['new','apply','adapt','disregard'])}
        template = next((v['properties'] for v in schema['oneOf'] if v['properties'].get('obligation_id',{}).get('const')==obligation['id']),{})
        if 'change_assessment' in template: common['change_assessment']=copy.deepcopy(template['change_assessment'])
        if preview and previous and preview.get('response_sha256') == digest(previous):
            schema['oneOf'].append(_object({**common, 'intent': {'const':'submit_execution'},
                'preview_sha256': {'const':digest(preview)}}))
        elif context.get('remaining_model_calls', 2) >= 2:
            schema['oneOf'].append(_object({**common, 'intent': {'const':'execute_procedure'},
                'method_ref': _enum(list(methods(context, 'record_extraction'))),
                'baseline_sha256': {'const':digest(previous) if previous else None},
                'bindings': _object({'row_id':{'const':obligation['unit']['row_id']},
                    'fields':{'const':obligation['unit']['fields']}})}))
    fields=submission_fields(context)
    if fields:
        source=context['previous_submission']
        edit_options=[]
        for path in fields:
            value={'type':['string','number','boolean','null'],'maxLength':160}
            if path=='/rationale' or path in {'/evidence_use/contribution','/evidence_use/remaining_unknown','/change_assessment/explanation'}:
                value={**_string(8,160),'pattern':r'^.*[.!?]["\u2019\u201d`)]?$'}
            edit_options.append(_object({'path':{'const':path},'value':value}))
        schema['oneOf'].insert(0,_object({'intent':{'const':'correct_submission'},
            'obligation_id':{'const':source['obligation_id']},'submission_sha256':{'const':digest(source)},
            'edits':{'type':'array','minItems':1,'maxItems':min(8,len(fields)),
                'items':{'oneOf':edit_options}}}))
    return instructions + (' Use correct_submission to replace only the listed failed fields; the runtime retains all other submitted fields and rechecks the complete response. '
        ' Execute a selected bounded procedure to inspect its output before submit_execution. '
        'Select current bindings and justify applicability yourself. A preview is not approval. '
        'method_ref resolves the exact offered method; builtin procedures are fixed tools, not acquired learning. '
        'Prefer compact references and edit only failed fields. Keep each explanation within 160 characters.'), schema



def submission_fields(context: dict[str, Any]) -> dict[str, Any]:
    source=context.get('previous_submission'); result={}
    if not isinstance(source,dict):return result
    for finding in context.get('feedback',{}).get('field_issues',[]):
        path=finding.get('path','')
        if not isinstance(path,str) or not path.startswith('/'):continue
        value=source
        try:
            for token in path.split('/')[1:]:
                token=token.replace('~1','/').replace('~0','~')
                value=value[int(token)] if isinstance(value,list) else value[token]
        except (KeyError,IndexError,TypeError,ValueError):continue
        if value is None or type(value) in (str,int,float,bool):result[path]=value
    return result


def failed_paths(context: dict[str, Any]) -> list[str]:
    from .child_repairs import editable, finding_rows
    allowed = editable(context)
    findings = [*context.get('feedback',{}).get('field_issues',[]), *finding_rows(context)]
    return [p for p in allowed if any(f.get('path') == p or p.startswith(str(f.get('path','!')) + '/') for f in findings)]


def prepare(context: dict[str, Any], submitted: Any) -> tuple[Any, dict[str, Any]]:
    if not active(context) or not isinstance(submitted, dict): return submitted, {}
    from .directive_candidates import CandidateError
    def fail(code: str, path: str = '/') -> None:
        raise CandidateError([{'path':path,'code':code}])
    response = copy.deepcopy(submitted)
    if response.get('intent')=='correct_submission':
        source=context.get('previous_submission');allowed=submission_fields(context)
        if (set(response)!={'intent','obligation_id','submission_sha256','edits'} or not isinstance(source,dict)
                or response['submission_sha256']!=digest(source) or response['obligation_id']!=source.get('obligation_id')):
            fail('current_failed_submission_required')
        edits=response['edits'];seen=set();changes=[];revised=copy.deepcopy(source)
        if not isinstance(edits,list) or not 1<=len(edits)<=8:fail('bounded_failed_field_edits_required')
        for edit in edits:
            if not isinstance(edit,dict) or set(edit)!={'path','value'}:fail('typed_failed_field_edit_required')
            path=edit['path'];value=edit['value']
            if not isinstance(path,str) or path not in allowed or path in seen:fail('unique_failed_submission_path_required')
            if value is not None and type(value) not in (str,int,float,bool):fail('scalar_patch_value_required',path)
            if isinstance(value,str) and len(value)>160:fail('bounded_text_required',path)
            if digest(value)==digest(allowed[path]):fail('unchanged_field_edit',path)
            seen.add(path);tokens=[t.replace('~1','/').replace('~0','~') for t in path.split('/')[1:]];cursor=revised
            for token in tokens[:-1]:cursor=cursor[int(token)] if isinstance(cursor,list) else cursor[token]
            if isinstance(cursor,list):cursor[int(tokens[-1])]=value
            else:cursor[tokens[-1]]=value
            changes.append({'path':path,'before_sha256':digest(allowed[path]),'after':value})
        normalized,choice=prepare(context,revised)
        return normalized,{**choice,'submission_edits':changes,'submission_baseline_sha256':digest(source)}
    selected = next((o for o in context['obligations'] if o['id']==response.get('obligation_id') and o['eligible']),None)
    if not selected: fail('currently_eligible_obligation_required')
    available = methods(context, selected['adapter'])
    for key in ('method','method_plan'):
        value = response.get(key)
        if isinstance(value,dict) and 'method_ref' in value:
            if set(value) != {'method_ref'} or value['method_ref'] not in available: fail('offered_method_reference_required', '/'+key)
            response[key] = copy.deepcopy(available[value['method_ref']])
    if response.get('intent') == 'patch':
        paths = failed_paths(context)
        if paths and any(e.get('path') not in paths for e in response.get('edits',[])):
            fail('edit_only_unresolved_fields', '/edits')
    intent = response.get('intent')
    if intent not in {'execute_procedure','submit_execution'}: return response, {}
    common = {'intent','obligation_id','rationale','lesson_id','lesson_use'}
    if context.get('relevant_change'): common.add('change_assessment')
    expected = common | ({'method_ref','baseline_sha256','bindings'} if intent=='execute_procedure' else {'preview_sha256'})
    if set(response) != expected or selected['adapter'] != 'record_extraction': fail('exact_execution_action_required')
    if not isinstance(response['rationale'],str) or not 8 <= len(response['rationale']) <= 160: fail('bounded_text_required','/rationale')
    previous = baseline(context)
    if intent == 'execute_procedure':
        if context.get('remaining_model_calls',0) < 2: fail('reserve_inspection_call_before_execution')
        if response['baseline_sha256'] != (digest(previous) if previous else None): fail('current_repair_baseline_required')
        bindings = {'row_id':selected['unit']['row_id'],'fields':selected['unit']['fields']}
        if response['bindings'] != bindings or response['method_ref'] not in available: fail('current_execution_bindings_required')
        if response['lesson_use'] in {'apply','adapt'} and response['method_ref'] != response['lesson_id']:
            fail('selected_lesson_must_be_executed', '/method_ref')
        method = available[response['method_ref']]
        payload = programs.extract(method, context['records'], bindings['row_id'], bindings['fields'])
        normalized = {k:response[k] for k in ('obligation_id','rationale','lesson_id','lesson_use')}
        normalized.update(intent='revise',method=method,payload=payload)
        if 'change_assessment' in response: normalized['change_assessment']=response['change_assessment']
        preview = {'version':VERSION,'response_sha256':digest(normalized), 'source_sha256':digest(context['records']),
            'obligation_id':selected['id'],'method_ref':response['method_ref'], 'payload':payload,
            'method_sha256':digest(method),'completion_credit':False,'requires_independent_review':True}
        return normalized, {'execution_preview':preview,'context_profile':context['context_profile']}
    preview = context.get('execution_preview',{})
    if (not previous or response['preview_sha256'] != digest(preview) or preview.get('response_sha256') != digest(previous)
            or preview.get('source_sha256') != digest(context['records']) or preview.get('obligation_id') != selected['id']):
        fail('current_unchanged_execution_preview_required')
    if any(response[k] != previous[k] for k in ('lesson_id','lesson_use')):
        fail('preserve_inspected_method_attribution')
    # Re-execution checks the frozen bindings; no trust in cached result bytes.
    if programs.execute(previous['method'], context, previous['payload']) != previous['payload']: fail('execution_preview_output_changed')
    previous.update({k:response[k] for k in ('rationale','lesson_id','lesson_use')})
    if 'change_assessment' in response: previous['change_assessment']=response['change_assessment']
    return previous, {'execution_inspected':True,'preview_sha256':response['preview_sha256'],'context_profile':context['context_profile']}


def compact_view(context: dict[str, Any], visible: dict[str, Any]) -> dict[str, Any]:
    if not active(context): return visible
    selected = context['obligations'][0]
    definitions = {}; references = []
    for key,value in methods(context,selected['adapter']).items():
        body={k:v for k,v in value.items() if k!='name'}
        identity='p'+digest(body)[:10];definitions[identity]=body
        references.append({'id':key,'name':value['name'],'definition':identity,'fixed_runtime_tool':key.startswith('builtin:')})
    visible.pop('methods',None)
    visible['method_references']=references
    visible['procedure_definitions']=definitions
    if context.get('execution_preview'):
        visible['execution_preview'] = context['execution_preview']
        visible['preview_sha256'] = digest(context['execution_preview'])
        visible['baseline'] = {'response_sha256':context['execution_preview']['response_sha256']}
    else:
        previous = baseline(context)
        if previous and 'rationale' in visible.get('baseline',{}) and len(previous.get('rationale','')) > 160:
            visible['baseline']['rationale'] = {'sha256':digest(previous['rationale']), 'characters':len(previous['rationale']),
                'finding':'Explanation exceeded the bound; author a complete replacement within 160 characters.'}
    def bounded(value):
        if isinstance(value,str) and len(value)>240:
            return {'excerpt':value[:160],'characters':len(value),'sha256':digest(value),'full_value_retained_in_attempt':True}
        if isinstance(value,dict):return {k:bounded(v) for k,v in value.items()}
        if isinstance(value,list):return [bounded(v) for v in value]
        return value
    visible['feedback'] = bounded(visible.get('feedback',{}))
    fields=submission_fields(context)
    if fields:
        visible['failed_submission']={'sha256':digest(context['previous_submission']),
            'obligation_id':context['previous_submission']['obligation_id'],'fields':bounded(fields),
            'other_fields':'Retained unchanged by correct_submission and revalidated before review.'}
    visible['failed_edit_paths'] = failed_paths(context)
    visible['response_contract'] = VERSION
    return visible
