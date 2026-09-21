"""Opt-in research tools over frozen inputs; no acquisition or execution grants."""
from __future__ import annotations
import copy
from typing import Any
from .research_tools import digest
from . import child_measurements as measurements, child_evidence_selection as evidence

VERSION='child_research_tools_v2'
SUPPORTED={'child_research_tools_v1',VERSION}
INTENTS={'bind_evidence','measure_interface','request_measurement'}


def attach(context: dict[str, Any], frozen: dict[str, Any]) -> dict[str, Any]:
    if frozen.get('research_tools_contract') not in SUPPORTED:return context
    context['research_tools_contract']=frozen['research_tools_contract']
    adapters={o['adapter'] for o in context['obligations'] if o['eligible']}
    context['measurement_inputs']=frozen.get('measurement_inputs',[]) if 'interface_contract' in adapters else []
    context['evidence_selections']=evidence.options(context) if 'evidence_binding' in adapters else []
    return context


def contract(context: dict[str, Any], original: tuple[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    if context.get('research_tools_contract') not in SUPPORTED:return original
    from .planner_authoring import _object,_enum,_string
    from .child_repairs import baseline,method_schema
    instructions,schema=original; variants=[]; previous=baseline(context)
    eligible={o['id']:o for o in context['obligations'] if o['eligible']}
    for variant in schema['oneOf']:
        props=variant['properties'];oid=props.get('obligation_id',{}).get('const')
        if oid in eligible and eligible[oid]['adapter']=='evidence_binding' and props['intent']['const'] in {'revise','patch'}:continue
        if (oid in eligible and eligible[oid]['adapter']=='interface_contract' and 'method_plan' in props
                and context['research_tools_contract']==VERSION):
            variant=copy.deepcopy(variant)
            variant['properties']['method_plan']['anyOf'].insert(0,measurements.program_schema())
        variants.append(variant)
    profiles=context.get('permitted_context_profiles',['full','focused'])
    for oid,o in eligible.items():
        adapter=o['adapter']
        common={'obligation_id':{'const':oid},'baseline_sha256':{'const':digest(previous) if previous else None},
            'context_profile':_enum(profiles),'rationale':_string(8,180),
            'lesson_id':_enum(['none',*[m['id'] for m in context.get('methods',[])]]),
            'lesson_use':_enum(['new','apply','adapt','disregard']),
            'method_plan':{'anyOf':[method_schema(adapter),{'type':'null'}]}}
        if adapter=='interface_contract' and context['research_tools_contract']==VERSION:
            common['method_plan']['anyOf'].insert(0,measurements.program_schema())
        if adapter=='evidence_binding' and context['evidence_selections']:
            pairs=[]
            for source in dict.fromkeys(s['source_id'] for s in context['evidence_selections']):
                fields={'source_id':{'const':source},'span_id':_enum([s['span_id'] for s in context['evidence_selections'] if s['source_id']==source])}
                if context.get('repair_targets'):fields['claim_index']={'type':'integer','enum':[t['claim_index'] for t in context['repair_targets']]}
                else:fields['subject_ref']=_enum(list(dict.fromkeys(s['subject_ref'] for s in context['evidence_subjects'])))
                pairs.append(_object(fields))
            count=len(context.get('repair_targets',[])) or 1
            variants.append(_object({**common,'intent':{'const':'bind_evidence'},
                'selections':{'type':'array','minItems':count,'maxItems':count,'items':{'oneOf':pairs}}}))
        if adapter=='interface_contract':
            if context['measurement_inputs']:
                fields={k:_string(3,250) for k in ('module','responsibility','input','output')}
                fields.update(artifact_ref=_enum(context['artifact_refs']),operator=_enum(['<=','>=','==']),
                    threshold={'type':'number'},invalid_input_behavior={'const':'unknown_and_stop'},
                    assumptions={'type':'array','minItems':1,'maxItems':4,'items':_string(8,250)},measurement=measurements.schema(context))
                variants.append(_object({**common,'intent':{'const':'measure_interface'},'payload':_object(fields)}))
            variants.append(_object({**common,'intent':{'const':'request_measurement'},
                'missing_capability':_string(12,180),'required_input':_string(8,180),'falsifier':_string(12,180)}))
    return (instructions+' Prefer bind_evidence to select an existing source and passage; the runtime copies exact cached bytes. '
        'Choose relevance yourself, preserve the original claim and distinguish a source fragment from its required anchor. '
        'Use measure_interface for a measurement derived from the supplied frozen records. Count missing fields as absent, '
        'but explicit unknown values remain unknown. count_records uses an empty field and count units; count_present uses a '
        'source field and count units; fraction_present uses a source field and ratio units. Predict the actual value and outcome. '
        'The runtime derives metric, unit and fixture_ref from your specification. Your falsifier and rationale still need semantic review. '
        'Use request_measurement when the required operation or evidence is unavailable; it grants no allowance or approval. '
        +('Measured methods require child_measurement_program_v1 for adoption. Author its stage order: read input before evaluating the selected definition, preserve unknown before comparing the threshold. '
          'Its declared bindings select current inputs and the current measurement. Free-text methods can accompany an artifact but are deferred for adoption. '
          if context['research_tools_contract']==VERSION else ''),{'oneOf':variants})


def normalize(context: dict[str, Any], submitted: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    from .child_repairs import baseline,absent_method
    from .directive_candidates import CandidateError,changes
    def fail(code):raise CandidateError([{'path':'/','code':code}])
    common={'intent','obligation_id','baseline_sha256','context_profile','rationale','lesson_id','lesson_use','method_plan'}
    intent=submitted['intent'];extra={'bind_evidence':{'selections'},'measure_interface':{'payload'},
        'request_measurement':{'missing_capability','required_input','falsifier'}}[intent]
    if set(submitted)!=common|extra:fail('exact_research_action_fields_required')
    previous=baseline(context)
    if submitted['baseline_sha256']!=(digest(previous) if previous else None):fail('current_repair_baseline_required')
    selected=next((o for o in context['obligations'] if o['id']==submitted['obligation_id'] and o['eligible']),None)
    if not selected or selected['adapter']!=('evidence_binding' if intent=='bind_evidence' else 'interface_contract'):
        fail('currently_eligible_research_adapter_required')
    profile=submitted['context_profile']
    if profile not in context.get('permitted_context_profiles',['full','focused']):fail('currently_permitted_child_context_profile_required')
    method=submitted['method_plan'] or (previous or {}).get('method') or absent_method(selected['adapter'])
    response={k:submitted[k] for k in ('obligation_id','rationale','lesson_id','lesson_use')}
    choice={'context_profile':profile,'research_action':intent}
    if intent=='bind_evidence':
        payload,choice['evidence_selection_receipts']=evidence.resolve(context,submitted['selections'])
    elif intent=='measure_interface':
        payload=copy.deepcopy(submitted['payload']);spec=payload.get('measurement',{})
        source=next((s for s in context.get('measurement_inputs',[]) if s['id']==spec.get('input_id')),None)
        if not source:fail('current_frozen_measurement_input_required')
        payload.update(unit=spec.get('unit'),fixture_ref=source['artifact_ref'],
            metric=f"{spec.get('operation')}({source['artifact_ref']}#{source['pointer']}, field={spec.get('field')!r}) in {spec.get('unit')}")
    else:
        request={k:submitted[k] for k in extra}
        if any(not isinstance(v,str) or not 8<=len(v)<=180 for v in request.values()):fail('bounded_measurement_capability_request_required')
        choice['measurement_capability_request']=request
        payload={'missing_dependency':request['missing_capability']+'; '+request['required_input']}
    response.update(intent='defer' if intent=='request_measurement' else 'revise',payload=payload,method=method)
    if previous and intent!='request_measurement' and previous.get('payload')==payload and previous.get('method')==method:
        fail('substantive_field_or_method_change_required')
    choice['patch_changes']=changes(previous,response)
    return response,choice
