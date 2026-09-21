"""Finite, pure paired experiments on cached JSON; no provider or execution authority.

Novali selects programs and a falsifier. These instruments measure serialized
projection bytes or exact selected-state preservation, not research usefulness.
"""
from __future__ import annotations
import copy
import json
from typing import Any
from .research_tools import digest

VERSION = 'question_measurements_v1'
COHERENT_VERSION = 'question_measurements_v2'
ACTIONS = ('whole_input', 'selected_slots', 'present_slots')
METRICS = {'context_bytes': ('preparation', 'utf8_bytes'),
           'extraction_correctness': ('execution', 'exact_state_fraction')}
FALSIFIERS = {'decrease':'not_less', 'increase':'not_greater', 'unchanged':'not_equal'}


def method_schema() -> dict[str, Any]:
    from .planner_authoring import _object, _enum
    operation = _object({'input_ref': {'const':'selected_obligation'},
        'action':_enum(list(ACTIONS)), 'check':{'const':'preserve_selected_states'}})
    return _object({k:copy.deepcopy(operation) for k in ('baseline_operation','changed_operation')})


def schema() -> dict[str, Any]:
    from .planner_authoring import _object, _enum
    return _object({'instrument':{'const':VERSION}, 'quantity':_enum(list(METRICS)),
        'baseline':{'const':'baseline_operation'}, 'changed':{'const':'changed_operation'},
        'falsifier':_enum(list(FALSIFIERS.values()))})


def inputs(source: dict[str, Any]) -> tuple[Any, list[str]]:
    """Select existing cached data using the runtime-owned obligation binding."""
    obligation=source['obligation']; unit=obligation.get('unit',{}); frozen=source.get('frozen',{})
    if obligation['adapter']=='record_extraction':
        rows=[r for r in frozen.get('records',[]) if r.get('row_id')==unit.get('row_id')]
        if len(rows)!=1: raise ValueError('measurement_input_unavailable')
        data=rows[0].get('record'); keys=unit.get('fields',[])
    else:
        # Cached input primitives are explicitly limited to registered adapters.
        raise ValueError('measurement_adapter_unavailable')
    if (not isinstance(data,dict) or not isinstance(keys,list) or not 1<=len(keys)<=12
        or any(not isinstance(k,str) or not k or len(k)>160 for k in keys) or len(set(keys))!=len(keys)):
        raise ValueError('measurement_input_unavailable')
    raw=json.dumps(data,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf-8')
    if len(raw)>65536: raise ValueError('measurement_input_budget_exceeded')
    return data,keys


def state(data: dict[str, Any], key: str) -> dict[str, Any]:
    return {'state':'present','value':copy.deepcopy(data[key])} if key in data else {'state':'absent'}


def run(action: str, data: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    if action not in ACTIONS: raise ValueError('registered_projection_required')
    selected={k:state(data,k) for k in keys}
    if action=='whole_input': return {'record':copy.deepcopy(data)}
    if action=='selected_slots': return {'slots':selected}
    return {'slots':{k:v for k,v in selected.items() if v['state']=='present'}}


def findings(source: dict[str, Any], response: dict[str, Any]) -> list[dict[str, Any]]:
    result=[]
    def issue(path,code,guidance): result.append({'path':path,'code':code,'guidance':guidance})
    m=response.get('measurement'); h=response.get('hypothesis',{})
    if (not isinstance(m,dict) or set(m)!={'instrument','quantity','baseline','changed','falsifier'}
        or m.get('instrument') not in {VERSION,COHERENT_VERSION} or not isinstance(m.get('quantity'),str) or m.get('quantity') not in METRICS
        or m.get('baseline')!='baseline_operation' or m.get('changed')!='changed_operation'
        or m.get('falsifier') not in FALSIFIERS.values()):
        issue('/measurement','executable_measurement_required','Choose the offered instrument, quantity, operation bindings and falsifier.'); return result
    quantity=m['quantity']; phase,_=METRICS[quantity]
    if response.get('execution_scope')!={'mode':'full_unit'}:
        issue('/execution_scope','measurement_scope_mismatch','This instrument compares projections of the whole selected unit; it does not measure partition execution.')
    if h.get('metric')!=quantity or h.get('phase')!=phase or FALSIFIERS.get(h.get('predicted_effect'))!=m['falsifier']:
        issue('/measurement','measurement_prediction_mismatch','Quantity, phase and falsifier must match the prediction; preserve its original when revising.')
        issue('/hypothesis','linked_measurement_review','Check the instrument quantity, phase and predicted direction together; retain an already consistent hypothesis.')
    method=response.get('method',{})
    for name in ('baseline_operation','changed_operation'):
        op=method.get(name) if isinstance(method,dict) else None
        if (not isinstance(op,dict) or set(op)!={'input_ref','action','check'}
            or op.get('input_ref')!='selected_obligation' or op.get('action') not in ACTIONS
            or op.get('check')!='preserve_selected_states'):
            issue('/method','registered_measurement_operations_required','Choose complete registered operations on the selected input; prose is not executable.')
    if not any(f['path']=='/method' for f in result) and method['baseline_operation']==method['changed_operation']:
        issue('/method','substantive_operation_change_required','Select distinct operations for this changed-method experiment.')
    try: inputs(source)
    except (ValueError,TypeError) as exc:
        issue('/measurement',str(exc),'This cached input cannot run the instrument; a reviewed capability extension is required, not an inferred result.')
    return result


def observe(source: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    """Run only validated pure programs; a rejected hypothesis cannot suppress data."""
    issues = [f for f in findings(source, response)
              if f['code'] not in {'measurement_prediction_mismatch', 'linked_measurement_review',
                                   'substantive_operation_change_required'}]
    if issues:
        return {'status':'unavailable','findings':issues,'scientific_progress_credited':False}
    data,keys=inputs(source); m=response['measurement']; values={}; runs={}
    expected={k:state(data,k) for k in keys}
    for arm,name in (('baseline',m['baseline']),('changed',m['changed'])):
        op=response['method'][name]; output=run(op['action'],data,keys)
        encoded=json.dumps(output,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf-8')
        observed=({k:state(output['record'],k) for k in keys} if 'record' in output else output['slots'])
        correct=sum(digest(observed.get(k))==digest(v) for k,v in expected.items())/len(keys)
        values[arm]=len(encoded) if m['quantity']=='context_bytes' else correct
        runs[arm]={'operation_sha256':digest(op),'output_sha256':digest(output),
            'serialized_bytes':len(encoded),'state_preservation':correct,
            'counterexamples':[{'field':k,'field_index':keys.index(k),'expected':v,'actual':observed.get(k)}
                for k,v in expected.items() if digest(observed.get(k))!=digest(v)]}
    return {'instrument':m['instrument'],'status':'measured',
        'quantity':m['quantity'],'phase':METRICS[m['quantity']][0],'units':METRICS[m['quantity']][1],
        'input_sha256':digest(data),'selection_sha256':digest(keys),'values':values,'runs':runs,
        'equal_information':True,'limits':{'input_bytes':65536,'selected_slots':12,'program_runs':2},
        'scope':'cached_projection_only_not_provider_speed_or_research_success',
        'artifact_state_preserved':runs['changed']['state_preservation']==1,
        'adoption_credit':False,'scientific_progress_credited':False}


def evaluate(source: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    observation = observe(source, response)
    issues = findings(source, response)
    if issues or observation['status'] != 'measured':
        return {'status':'inconclusive','findings':issues,'observation':observation,
                'scientific_progress_credited':False,'adoption_credit':False}
    baseline, changed = observation['values']['baseline'], observation['values']['changed']
    falsifier = response['measurement']['falsifier']
    refuted = {'not_less':changed>=baseline,'not_greater':changed<=baseline,'not_equal':changed!=baseline}[falsifier]
    return {**observation,'status':'refuted' if refuted else 'supported'}


def feedback_observation(result: dict[str, Any]) -> dict[str, Any]:
    """Bounded answer-free working view; full report is retained in the attempt."""
    observation = result.get('observation', result)
    if observation.get('status') == 'unavailable':
        return {'status':'unavailable','report_sha256':digest(result),
                'reason':'Safe instrument bindings or limits invalid; no measurement inferred.'}
    return {'report_sha256':digest(result),'quantity':observation['quantity'],
            'values':observation['values'],'units':observation['units'],
            'state_preservation':{k:v['state_preservation'] for k,v in observation['runs'].items()},
            'hypothesis_status':result['status'],'acceptance':'not_established',
            'scope':'cached_projection_only_not_provider_performance',
            'changed_counterexamples':[{'field_index':c['field_index'],'expected_state':c['expected']['state'],
                'actual_state':(c['actual'] or {}).get('state','omitted')}
                for c in observation['runs']['changed']['counterexamples'][:3]],
            'counterexample_counts':{k:len(v['counterexamples']) for k,v in observation['runs'].items()}}


def artifact_findings(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Expose an operation edit when its promised preservation check actually fails."""
    observation = result.get('observation', result)
    if observation.get('artifact_state_preserved') is not False:
        return []
    diagnostic = feedback_observation(result)
    return [{'path':'/method','code':'source_state_preservation_required',
             'guidance':'The changed operation failed its preserve_selected_states check. Revise the operation using the measured counterexamples; a prediction edit alone cannot repair it.',
             'counterexample':{'changed':diagnostic['changed_counterexamples'],
                               'report_sha256':diagnostic['report_sha256']}}]


def derive(response: dict[str, Any], *, contract: str | None = None) -> dict[str, Any]:
    result=copy.deepcopy(response)
    if contract==COHERENT_VERSION:
        h=result.get('hypothesis',{})
        result['measurement']={'instrument':COHERENT_VERSION,'quantity':h.get('metric'),
            'baseline':'baseline_operation','changed':'changed_operation','falsifier':FALSIFIERS.get(h.get('predicted_effect'))}
    m=result.get('measurement',{})
    if isinstance(m,dict) and m.get('quantity') in METRICS:
        units=METRICS[m['quantity']][1]
        result['observable']=f'Compare {units} of registered operations on the same cached input and selected slots.'
        result['failure_condition']='Refute the prediction when the registered '+str(m.get('falsifier'))+' comparison holds.'
    return result
