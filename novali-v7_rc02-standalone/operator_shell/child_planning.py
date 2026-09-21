"""Small planning decisions and conservative input/output reservations."""
from __future__ import annotations
import copy
import json
import re
from typing import Any
from .research_tools import digest

VERSION = 'child_growth_v1'
CONTEXT_TOKENS = 8192
OUTPUT_TOKENS = 1800
WRAPPER_RESERVE = 512
INSTRUCTIONS = ('Propose a bounded internal draft using the selected current inputs. No physical operation is offered. '
    'Delivery and method adoption require independent review. Follow the schema. Preserve missing, unknown and exact source values. '
    'Select existing passages by source/span ID; do not invent citations. Patch only changed listed fields against the baseline hash. '
    'For reusable methods choose the executable program, order its declared stages and use current bindings. Free prose is deferred for adoption. '
    'Measurements must match the requested operation, field, units and threshold; unresolved values remain unknown. '
    'Select an applicable learned method using lesson_id and apply/adapt; otherwise use none/new. '
    'A deferral identifies a listed current input and a specific unresolved review question, not future execution approval. '
    'Use complete, short sentences for explanations. No result establishes scientific truth.')


def active(context: dict[str, Any]) -> bool:
    return context.get('growth_contract') == VERSION


def recent_costs(context: dict[str,Any]) -> list[dict[str,Any]]:
    return [{'charged_s':round(row['charged_seconds'],3) if isinstance(row.get('charged_seconds'),(int,float)) else None,
        'input_bytes':row.get('context_bytes'),'uncertain':row.get('provider_outcome_uncertain',False),
        'phases_s':{short:round(row['timing'][long],3) for long,short in
            (('preflight_seconds','prepare'),('provider_prompt_seconds','prompt'),('provider_load_seconds','load'),('provider_generation_seconds','generate'),('transport_seconds','transport'))
            if isinstance(row.get('timing',{}).get(long),(int,float))}} for row in context.get('phase_diagnostics',[])[-2:]]


def project(context: dict[str, Any], obligation_id: str, profile: str, evidence_source_id: str | None = None) -> dict[str, Any]:
    from .child_context import project as profile_project
    if profile not in context.get('permitted_context_profiles',['full','focused']): raise ValueError('permitted_route_profile_required')
    result = profile_project(context, profile)
    selected = next((o for o in result['obligations'] if o['id']==obligation_id and o['eligible']),None)
    if not selected: raise ValueError('eligible_route_obligation_required')
    result['obligations'] = [selected]; result['context_profile'] = profile
    result['methods']=[m for m in result.get('methods',[]) if m['adapter']==selected['adapter']]
    if selected['adapter'] in {'record_extraction','evidence_binding'}:
        result['artifact_refs']=[result['target_artifact']]
    if evidence_source_id is not None:
        if selected['adapter']!='evidence_binding' or result.get('repair_targets'):raise ValueError('original_claim_set_must_remain_complete')
        sources=[s for s in result['evidence_options'] if s['handle']==evidence_source_id]
        subjects=[s for s in result['evidence_subjects'] if s['evidence_handle']==evidence_source_id]
        if len(sources)!=1 or not subjects:raise ValueError('current_subject_source_route_required')
        result['evidence_options']=sources;result['evidence_subjects']=subjects
        result['evidence_selections']=[s for s in result['evidence_selections'] if s['source_id']==evidence_source_id]
    if selected['adapter']=='record_extraction':
        unit=selected['unit'];result['required_fields']=unit['fields'];result['unprojected_required_fields']=[]
        result['records']=[{'row_id':r['row_id'],'record':{f:v for f,v in r['record'].items() if f in unit['fields']}}
                           for r in result['records'] if r['row_id']==unit['row_id']]
    return result


def aliases(context: dict[str, Any]) -> dict[str,str]:
    result={}
    for key,prefix in (('source_id','s'),('span_id','p'),('action_id','a')):
        values=list(dict.fromkeys(s[key] for s in context.get('evidence_selections',[])))
        result.update({value:prefix+str(i) for i,value in enumerate(values)})
    return result


def wire(context: dict[str, Any], schema: dict[str, Any]) -> tuple[dict[str,Any],dict[str,Any]]:
    """Lossless interning of offered literals and opaque provenance identifiers."""
    visible=view(context);mapping=aliases(context)
    def identities(value):
        if isinstance(value,dict):return {k:mapping.get(v,v) if k in {'source_id','span_id','action_id','evidence_handle'} and isinstance(v,str)
            else identities(v) for k,v in value.items()}
        if isinstance(value,list):return [identities(v) for v in value]
        return value
    visible=identities(visible);texts={}
    for group in ('passages','subjects'):
        for row in visible.get(group,[]):
            literal=row.pop('literal')
            name=next((k for k,v in texts.items() if v==literal),None)
            if name is None:name='t'+str(len(texts));texts[name]=literal
            row['text_ref']=name
    if texts:
        visible['texts']=texts
        visible['evidence_encoding']='text_ref resolves to the exact literal in texts. Short source/span IDs are bound by the runtime to immutable provenance.'
    def grammar(value):
        if isinstance(value,dict):return {k:grammar(v) for k,v in value.items()}
        if isinstance(value,list):return [grammar(v) for v in value]
        return mapping.get(value,value) if isinstance(value,str) else value
    return visible,grammar(schema)


def decode(context: dict[str,Any], response: dict[str,Any]) -> dict[str,Any]:
    mapping={v:k for k,v in aliases(context).items()}
    def restore(value):
        if isinstance(value,dict):return {k:mapping.get(v,v) if k in {'source_id','span_id','evidence_handle'} and isinstance(v,str)
            else restore(v) for k,v in value.items()}
        if isinstance(value,list):return [restore(v) for v in value]
        return value
    return restore(response)


def view(context: dict[str, Any]) -> dict[str, Any]:
    from .child_repairs import baseline, finding_rows
    previous = baseline(context); selected=context['obligations'][0]
    result={'task':{k:selected[k] for k in ('id','adapter','objective','unit') if k in selected},
        'authority':'internal_draft_only_no_physical_operations','artifact':context['target_artifact'],
        'sources':context['artifact_refs'],'records':context['records'] if selected['adapter']=='record_extraction' else [],
        'required_fields':context['required_fields'] if selected['adapter']=='record_extraction' else [],
        'baseline':previous,'baseline_sha256':digest(previous) if previous else None,
        'findings':[{k:r[k] for k in ('id','path','scope','finding','verification') if k in r} for r in finding_rows(context)],
        'feedback':{'reason':context.get('feedback',{}).get('reason'),'field_issues':context.get('feedback',{}).get('field_issues',[])},
        'methods':[{k:m[k] for k in ('id','adapter','name','representation','bindings','steps','stop_conditions','scope') if k in m} for m in context.get('methods',[]) if m['adapter']==selected['adapter']],
        'recent_costs':recent_costs(context),
        'context_profile':context['context_profile']}
    if context.get('correction_contract'):
        if previous:
            result['baseline']={k:previous[k] for k in ('payload','method') if k in previous}
            if any(r['path'] in {'/rationale','/response'} for r in finding_rows(context)):
                result['baseline']['rationale']=previous.get('rationale')
            method=result['baseline'].get('method',{})
            for key in ('name','adapter','stop_conditions'):
                method.pop(key,None)
            from .child_repairs import BINDINGS
            if method.get('bindings')==BINDINGS.get(selected['adapter']):method.pop('bindings',None)
            result['baseline_view']='Partial view; hash binds the complete response.'
            payload=result['baseline'].get('payload',{})
            if selected['adapter']=='record_extraction' and payload.get('fields'):
                from .directive_candidates import _value
                current=next((r['record'] for r in result['records'] if r['row_id']==payload.get('row_id')),None)
                if current is not None and all(
                        _value(current,f['field'])[0]==f['state'] and digest(_value(current,f['field'])[1])==digest(f['value'])
                        for f in payload['fields']):
                    compact={k:v for k,v in payload.items() if k!='fields'}
                    compact['fields_equal_current_record']=[f['field'] for f in payload['fields']]
                    if len(json.dumps(compact))<len(json.dumps(payload)):
                        result['baseline']['payload']=compact
                        result['baseline_view']+=' Listed fields have identical current-record values and states.'
        result['feedback'].update({k:context.get('feedback',{}).get(k) for k in ('binding_comparison','unresolved_method_issues')})
        # Repeated independent findings reference their one complete displayed
        # definition. Any extra actual/expected detail stays in the issue itself.
        definitions=finding_rows(context);issues=[];references=[]
        for issue in result['feedback']['field_issues']:
            matched=next((r for r in definitions if set(issue)<={'id','scope','path','code','finding'}
                and all(r.get(k)==v for k,v in issue.items())),None)
            if matched:references.append(matched['id'])
            else:issues.append(issue)
        result['feedback']['field_issues']=issues
        if references:result['feedback']['unresolved_finding_ids']=list(dict.fromkeys(references))
        result['correction_calls_remaining']=context.get('remaining_model_calls',0)
        if context.get('relevant_change'):
            result['relevant_change']=context['relevant_change']
        result['feedback']={k:v for k,v in result['feedback'].items() if v not in (None,[],{})}
    if context['context_profile']=='full':result['directive_scope']=context.get('directive_scope','')[:800]
    from .child_relevance import view as relevance_view
    result.update(relevance_view(context))
    if 'change_to_assess' in result: result.pop('relevant_change',None)
    if context.get('reviewed_failure_patterns'):
        result['reviewed_failure_patterns']=[{k:v for k,v in row.items() if k in {'review_id','observed_failure_patterns','scope'}}
            for row in context['reviewed_failure_patterns'][-1:]]
        row=result['reviewed_failure_patterns'][0];patterns=row['observed_failure_patterns']
        row['observed_failure_patterns']=dict(list(patterns.items())[:4])
        omitted=max(0,len(patterns)-4)
        if omitted:row['additional_pattern_count']=omitted
        if len(context['reviewed_failure_patterns'])>1:result['additional_historical_review_count']=len(context['reviewed_failure_patterns'])-1
    if context.get('accepted_practice_question'):
        result['accepted_practice_question'] = context['accepted_practice_question']
    if selected['adapter']=='evidence_binding':
        if context.get('verified_addendum_source_transitions'):
            result['evidence_provenance']=context['verified_addendum_source_transitions']
        result['claims']=context.get('repair_targets',[])
        result['subjects']=context.get('evidence_subjects',[])
        result['passages']=[{k:s[k] for k in ('source_id','span_id','action_id','literal')} for s in context.get('evidence_selections',[])]
    if selected['adapter']=='interface_contract':result['measurement_inputs']=context.get('measurement_inputs',[])
    from .child_execution import compact_view
    return compact_view(context, result)


def reserve(instructions: str, body: dict[str, Any], output_tokens: int) -> dict[str, Any]:
    # This byte ceiling is deliberately more conservative than a chars/token
    # estimate. The fixed wrapper reserve covers provider chat framing. Schema
    # bytes are separately bounded because Ollama applies them as a grammar.
    size=len(instructions.encode())+len(json.dumps(body,ensure_ascii=False,separators=(',',':')).encode())
    result={'input_utf8_byte_ceiling':size,'output_tokens_reserved':output_tokens,
        'wrapper_tokens_reserved':WRAPPER_RESERVE,'context_tokens':CONTEXT_TOKENS,
        'fits':size+output_tokens+WRAPPER_RESERVE<=CONTEXT_TOKENS,
        'scope':'conservative_byte_bound_not_an_exact_token_measurement'}
    if not result['fits']:raise ValueError('child_input_plus_output_reservation_exceeded')
    return result


def route_context(context: dict[str, Any]) -> dict[str, Any]:
    from .child_repairs import finding_rows
    options=[];blocked=[]
    for o in context['obligations']:
        if not o['eligible']:continue
        profiles=context.get('permitted_context_profiles',['full','focused'])
        selections=[(profile,None) for profile in profiles]
        if o['adapter']=='evidence_binding' and not context.get('repair_targets'):
            profile='focused' if 'focused' in profiles else profiles[0]
            selections=[(profile,s['handle']) for s in context['evidence_options']
                        if any(t['evidence_handle']==s['handle'] for t in context['evidence_subjects'])]
        for profile,source_id in selections:
            try:
                author=project(context,o['id'],profile,source_id)
                from .directive_candidates import planner_contract
                instructions,grammar=planner_contract(author)
                visible,grammar=wire(author,grammar)
                # Versioned affordances must fit their actual instructions,
                # including correction and evidence-use requirements.
                budget=reserve(instructions if context.get('correction_contract') else INSTRUCTIONS,visible,OUTPUT_TOKENS)
                if len(json.dumps(grammar).encode())>16000:raise ValueError('child_authoring_grammar_budget_exceeded')
            except ValueError as exc:
                blocked.append({'obligation_id':o['id'],'profile':profile,'source_id':source_id,'reason':str(exc)});continue
            item={'obligation_id':o['id'],'profile':profile,'input_bytes':budget['input_utf8_byte_ceiling']}
            if source_id:item['evidence_source_id']=source_id
            options.append({'id':'route-'+digest(item)[:24],**item,'adapter':o['adapter'],'objective':o['objective'],
                            'unit':o.get('unit'), 'finding_count':len(context.get('revision_review',{}).get('findings',[])),
                            **({'source_preview':next(s['text'][:120] for s in context['evidence_options'] if s['handle']==source_id)} if source_id else {})})
    if not options:raise ValueError('no_current_route_fits_complete_response_reservation')
    return {'growth_contract':VERSION,'route_options':options,'blocked_routes':blocked,
        'instructions':'Choose the smallest suitable current-input route. This selects a task and prepares its authoring input; no scientific or artifact completion credit.',
        'available_methods':[{'id':m['id'],'adapter':m['adapter']} for m in context.get('methods',[])],
        'review_questions':[r['finding'] for r in finding_rows(context)],
        'recent_costs':recent_costs(context)}


def route_contract(context: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    from .planner_authoring import _object,_enum,_string
    instructions='Select one offered task/context route and explain its suitability briefly. Prefer a smaller sufficient input. Do not author a result in this planning step.'
    schema=_object({'intent':{'const':'route'},'route_id':_enum([r['id'] for r in context['route_options']]),'rationale':_string(8,120)})
    reserve(instructions,context,240)
    return instructions,schema


def accept_route(context: dict[str, Any], response: Any) -> dict[str, Any]:
    if not isinstance(response,dict) or set(response)!={'intent','route_id','rationale'} or response['intent']!='route':
        raise ValueError('typed_current_route_selection_required')
    selected=next((r for r in context['route_options'] if r['id']==response['route_id']),None)
    if not selected or not isinstance(response['rationale'],str) or not 8<=len(response['rationale'])<=120:
        raise ValueError('offered_current_route_required')
    return {**selected,'rationale':response['rationale'],'completion_credit':False}


def contract(context: dict[str, Any], original: tuple[str,dict[str,Any]]) -> tuple[str,dict[str,Any]]:
    if not active(context):return original
    from . import child_procedure_programs as programs
    from .planner_authoring import _object,_enum,_string
    variants=[]
    for old in original[1]['oneOf']:
        variant=copy.deepcopy(old);props=variant['properties'];intent=props['intent']['const']
        if intent in {'select_context','defer'}:continue
        method_key='method_plan' if 'method_plan' in props else 'method' if 'method' in props else None
        if method_key:
            oid=props.get('obligation_id',{}).get('const');o=next((o for o in context['obligations'] if o['id']==oid),None)
            if o and o['adapter'] in programs.STAGES:
                props[method_key]['anyOf'].insert(0,programs.schema(o['adapter']))
        variants.append(variant)
    for o in context['obligations']:
        if not o['eligible'] or o['adapter']=='record_extraction' and context['records']:continue
        kinds={'evidence_binding':['source_relevance_unresolved'],'interface_contract':['measurement_not_supported','input_incomplete'],
            'record_extraction':['input_incomplete']}[o['adapter']]
        variants.append(_object({'intent':{'const':'defer'},'obligation_id':{'const':o['id']},
            'context_profile':{'const':context.get('context_profile','focused')},'dependency_kind':_enum(kinds),
            'reference':_enum(context['artifact_refs']),'missing_dependency':_string(12,160),'rationale':_string(12,160)}))
    return INSTRUCTIONS,{'oneOf':variants}


def normalize_defer(context: dict[str, Any], submitted: dict[str, Any]) -> tuple[dict[str,Any],dict[str,Any]]:
    from .child_repairs import absent_method
    from .directive_candidates import CandidateError
    def fail(code):raise CandidateError([{'path':'/missing_dependency','code':code}])
    if set(submitted)!={'intent','obligation_id','context_profile','dependency_kind','reference','missing_dependency','rationale'}:
        fail('typed_task_scoped_deferral_required')
    o=next((o for o in context['obligations'] if o['eligible'] and o['id']==submitted['obligation_id']),None)
    if not o or submitted['reference'] not in context['artifact_refs']:fail('current_obligation_and_input_reference_required')
    if submitted['context_profile']!=context.get('context_profile'):fail('selected_context_profile_required')
    kinds={'evidence_binding':{'source_relevance_unresolved'},'interface_contract':{'measurement_not_supported','input_incomplete'},
           'record_extraction':{'input_incomplete'}}
    if submitted['dependency_kind'] not in kinds[o['adapter']]:fail('dependency_must_match_current_draft_action')
    if o['adapter']=='record_extraction' and context['records']:fail('missing_fields_are_extractable_not_a_missing_input')
    for value in (submitted['missing_dependency'],submitted['rationale']):
        if not isinstance(value,str) or not 12<=len(value)<=160 or not value.endswith(('.', '?', '!')):
            fail('complete_bounded_deferral_explanation_required')
        if re.search(r'actuation|real.world|stimulation|operator.approval',value,re.I):fail('future_execution_authority_does_not_block_draft_action')
    return {'intent':'defer','obligation_id':o['id'],'rationale':submitted['rationale'],'method':absent_method(o['adapter']),
        'lesson_id':'none','lesson_use':'new','payload':{'missing_dependency':submitted['missing_dependency']}}, {
        'context_profile':submitted['context_profile'],'deferral_review':{'kind':submitted['dependency_kind'],'reference':submitted['reference'],
        'claim_status':'requires_independent_review','completion_credit':False}}
