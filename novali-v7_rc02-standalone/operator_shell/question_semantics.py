"""Typed execution scope and evidence-linked, explicitly untested predictions."""
from __future__ import annotations

from typing import Any
from .research_tools import digest

VERSION = 'question_semantics_v1'
KEYS = {'execution_scope', 'hypothesis'}


def properties(context: dict[str, Any]) -> dict[str, Any]:
    from .planner_authoring import _object, _enum
    from .question_partitions import schema
    ids = list(context.get('failure_evidence', {}))
    batches = schema(context['choices'])
    partition = {**batches, 'minItems': 1}
    scope_options = [_object({'mode': _enum(['full_unit'])})]
    if batches['maxItems']:
        scope_options.append(_object({'mode': _enum(['partition']), 'batches': partition}))
    prediction = {
        'phase': _enum(['preparation', 'authoring', 'execution']),
        'metric': _enum(['context_bytes', 'response_tokens', 'complete_response', 'extraction_correctness']),
        'predicted_effect': _enum(['decrease', 'unchanged', 'increase']),
        'status': _enum(['untested'])}
    if context.get('measurement_contract'):
        prediction['metric']=_enum(['context_bytes','extraction_correctness'])
        prediction['phase']=_enum(['preparation','execution'])
        scope_options=[_object({'mode':_enum(['full_unit'])})]
    hypotheses = [_object({**prediction, 'basis':_enum(['prospective_control']),
        'evidence_ids':{'type':'array','maxItems':0,'items':{'type':'string','maxLength':0}}})]
    if ids:
        hypotheses.append(_object({**prediction,'basis':_enum(['observed_failure']),
            'evidence_ids':{'type':'array','minItems':1,'maxItems':min(2,len(ids)),'items':_enum(ids)}}))
    if context.get('measurement_contract')=='question_measurements_v2':
        from .question_measurements import METRICS
        for h in hypotheses:
            if h['properties']['basis'].get('enum') == ['observed_failure']:
                h['properties']['basis'] = _enum(['observed_failure','motivating_failure'])
        hypotheses=[_object({**h['properties'],'metric':{'const':metric},'phase':{'const':phase}})
            for h in hypotheses for metric,(phase,units) in METRICS.items()]
    return {'execution_scope': {'anyOf': scope_options}, 'hypothesis': {'anyOf': hypotheses}}



def preview(source: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    unit = source['obligation'].get('unit', {})
    fields = unit.get('fields', [])
    batches = response.get('field_batches', [])
    body = {'mode': response.get('scope_mode', 'full_unit'), 'original_unit': unit,
        'original_field_count': len(fields), 'execution_batches': batches or [fields],
        'batch_field_counts': [len(b) for b in batches] if batches else [len(fields)],
        'completion_check': source['obligation']['completion_check'],
        'missing_and_unknown_values': 'preserve', 'each_batch_requires_shared_reservation': True}
    return {**body, 'sha256': digest(body)}


def resolve(context: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    import copy
    result = copy.deepcopy(response)
    scope = result.get('execution_scope')
    if isinstance(scope,dict):
        result['scope_mode'] = scope.get('mode')
        result['field_batches'] = scope.get('batches',[])
    source = next((s for s in context['choices'] if s['id'] == result.get('source_id')), None)
    if source:
        plan = preview(source, result)
        count = plan['original_field_count']
        result['input_scope'] = (f'All {count} required fields across {len(plan["execution_batches"])} execution batches.'
                                 if count else 'The complete selected obligation and its existing completion check.')
    hypothesis = result.get('hypothesis')
    if isinstance(hypothesis, dict) and isinstance(hypothesis.get('evidence_ids'), list):
        evidence = context.get('failure_evidence', {})
        hypothesis['evidence_ids'] = [evidence.get(key, {}).get('id', key) for key in hypothesis['evidence_ids']]
    return result


def findings(source: dict[str, Any], response: dict[str, Any]) -> list[dict[str, Any]]:
    from .question_partitions import validate
    issues = []
    def issue(path, code, **kw): issues.append({'path': path, 'code': code, **kw})
    scope = response.get('execution_scope')
    if not isinstance(scope,dict) or (scope.get('mode')=='full_unit' and set(scope)!={'mode'}) or (scope.get('mode')=='partition' and set(scope)!={'mode','batches'}):
        issue('/execution_scope','typed_execution_scope_required')
    mode = response.get('scope_mode'); batches = response.get('field_batches')
    if isinstance(scope,dict) and (scope.get('mode')!=mode or scope.get('batches',[])!=batches):
        issue('/execution_scope','scope_projection_mismatch')
    if not isinstance(mode,str) or mode not in {'full_unit', 'partition'}: issue('/execution_scope', 'explicit_execution_scope_required')
    issues.extend([{**f,'path':'/execution_scope'} for f in validate(source,batches)])
    if (mode == 'full_unit' and batches != []) or (mode == 'partition' and not batches):
        issue('/execution_scope', 'scope_mode_partition_mismatch')
    h = response.get('hypothesis')
    if not isinstance(h, dict) or set(h) != {'basis','evidence_ids','phase','metric','predicted_effect','status'}:
        issue('/hypothesis', 'typed_untested_prediction_required'); return issues
    if h['status'] != 'untested': issue('/hypothesis', 'predictions_are_not_observed_results')
    if any(not isinstance(h[k],str) for k in ('basis','phase','metric','predicted_effect','status')):
        issue('/hypothesis','typed_prediction_fields_required'); return issues
    if h['phase'] not in {'preparation','authoring','execution'} or h['metric'] not in {
            'context_bytes','response_tokens','complete_response','extraction_correctness'} or h['predicted_effect'] not in {'decrease','unchanged','increase'}:
        issue('/hypothesis', 'registered_phase_metric_and_effect_required')
    ids = h['evidence_ids']; available = {f['id']: f for f in source.get('reviewed_failures', [])}
    if not isinstance(ids, list) or len(ids)>2 or any(not isinstance(i,str) for i in ids):
        issue('/hypothesis', 'bounded_evidence_ids_required'); return issues
    if len(set(ids)) != len(ids) or any(i not in available for i in ids): issue('/hypothesis', 'invalid_prediction_evidence_binding')
    bases = {'observed_failure','prospective_control'}
    if response.get('measurement',{}).get('instrument')=='question_measurements_v2': bases.add('motivating_failure')
    if h['basis'] not in bases or bool(ids) != (h['basis'] in {'observed_failure','motivating_failure'}):
        issue('/hypothesis', 'observed_basis_requires_evidence_prospective_basis_requires_control')
    for key in ids:
        # Motivation does not assert an observed effect in the proposed phase.
        if h['basis']=='motivating_failure': continue
        code = available.get(key, {}).get('code')
        if code == 'preparation_context_exceeded' and h['phase'] != 'preparation':
            issue('/hypothesis', 'evidence_phase_mismatch', evidence_id=key, observed_phase='preparation')
        if code == 'output_exhausted' and h['phase'] == 'preparation':
            issue('/hypothesis', 'evidence_phase_mismatch', evidence_id=key, observed_phase='provider_generation')
    return issues
