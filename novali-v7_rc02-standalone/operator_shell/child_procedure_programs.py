"""Bounded current-input programs; artifact validity and adoption stay separate."""
from __future__ import annotations
import copy
from typing import Any

VERSION = 'child_artifact_program_v1'
STAGES = {
    'record_extraction': ['select_current_record', 'visit_requested_fields', 'distinguish_missing_unknown', 'retain_exact_values'],
    'evidence_binding': ['select_current_subject', 'bind_selected_passage', 'retain_original_claims', 'verify_literal_provenance'],
}


def schema(adapter: str) -> dict[str, Any]:
    from .child_repairs import BINDINGS
    from .directive_candidates import STOPS
    from .planner_authoring import _object, _string, _enum
    return _object({'representation': {'const': VERSION}, 'name': _string(5, 80), 'adapter': {'const': adapter},
        'bindings': {'const': BINDINGS[adapter]}, 'steps': {'type': 'array', 'minItems': 4, 'maxItems': 4,
            'uniqueItems': True, 'items': _enum(STAGES[adapter])}, 'stop_conditions': {'const': STOPS}})


def issues(method: Any) -> list[dict[str, str]]:
    from .child_repairs import BINDINGS
    from .directive_candidates import STOPS
    valid = (isinstance(method, dict) and set(method) == {'representation','name','adapter','bindings','steps','stop_conditions'}
        and isinstance(method.get('adapter'), str) and method['adapter'] in STAGES
        and method.get('representation') == VERSION and method.get('bindings') == BINDINGS[method['adapter']]
        and method.get('steps') == STAGES[method['adapter']] and method.get('stop_conditions') == STOPS
        and isinstance(method.get('name'), str) and 5 <= len(method['name']) <= 80)
    return [] if valid else [{'path':'/method','code':'ordered_current_input_program_required'}]


def extract(method: dict[str, Any], records: list[dict[str, Any]], row_id: str, fields: list[str]) -> dict[str, Any]:
    if issues(method) or method['adapter'] != 'record_extraction': raise ValueError('executable_extraction_program_required')
    if len(records) > 32 or not 1 <= len(fields) <= 12 or len(fields) != len(set(fields)):
        raise ValueError('bounded_unique_extraction_inputs_required')
    selected = None; values = []
    for stage in method['steps']:
        if stage == 'select_current_record':
            matches = [r['record'] for r in records if r['row_id'] == row_id]
            if len(matches) != 1: raise ValueError('unique_current_record_required')
            selected = matches[0]
        elif stage == 'visit_requested_fields': values = [{'field': f} for f in fields]
        elif stage == 'distinguish_missing_unknown':
            for row in values:
                f = row['field']; value = selected.get(f)
                row['state'] = ('missing' if f not in selected else 'unknown' if value is None or
                    isinstance(value,str) and value.strip().lower() in {'','unknown','unresolved','tbd'} else 'present')
        elif stage == 'retain_exact_values':
            for row in values: row['value'] = copy.deepcopy(selected.get(row['field']))
    return {'row_id': row_id, 'fields': values}


def execute(method: dict[str, Any], context: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    if issues(method): raise ValueError('ordered_current_input_program_required')
    if method['adapter'] == 'record_extraction':
        return extract(method, context['records'], payload['row_id'], [r['field'] for r in payload['fields']])
    from .child_evidence_selection import attest, resolve
    from .child_contracts import check_repairs
    selected = []; reconstructed = None
    for stage in method['steps']:
        if stage == 'select_current_subject':
            selected = [{k:r[k] for k in ('source_id','span_id', 'claim_index' if context.get('repair_targets') else 'subject_ref')}
                        for r in attest(context,payload)]
        elif stage == 'bind_selected_passage': reconstructed, _ = resolve(context, selected)
        elif stage == 'retain_original_claims':
            if context.get('repair_targets'):
                failures = []
                check_repairs(context, reconstructed, lambda p,c,*_:failures.append(c))
                if failures: raise ValueError('original_claim_binding_program_failed')
            elif not any(s['subject_ref'] == reconstructed['subject_ref'] and s['evidence_handle'] == reconstructed['evidence_handle']
                         and reconstructed['quote'] in s['literal'] for s in context['evidence_subjects']):
                raise ValueError('current_subject_program_failed')
        elif stage == 'verify_literal_provenance': attest(context, reconstructed)
    return reconstructed


def evaluate(method: dict[str, Any], context: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Execute actual bindings, then independent changed-input and rejection cases."""
    actual = execute(method, context, payload)
    if actual != payload: raise ValueError('procedure_output_disagrees_with_artifact')
    checks = []
    if method['adapter'] == 'record_extraction':
        records = [{'row_id':'/other/7','record':{'fresh':False,'uncertain':'unknown'}},
                   {'row_id':'/other/2','record':{'fresh':0,'uncertain':None}}]
        for source in (records, list(reversed(records))):
            for row_id, present, unknown in (('/other/7',False,'unknown'),('/other/2',0,None)):
                expected = {'row_id':row_id,'fields':[{'field':'uncertain','state':'unknown','value':unknown},
                    {'field':'absent','state':'missing','value':None},{'field':'fresh','state':'present','value':present}]}
                if extract(method,source,row_id,['uncertain','absent','fresh']) != expected:
                    raise ValueError('changed_record_or_field_program_counterexample')
                checks.append({'case':'reordered_current_record_and_fields','passed':True})
        for source in ([],[records[0],records[0]]):
            try: extract(method,source,'/other/7',['fresh'])
            except ValueError: checks.append({'case':'missing_or_ambiguous_record','passed':True})
            else: raise ValueError('missing_or_ambiguous_record_must_fail')
    else:
        from .research_tools import digest
        text = 'Fresh archive states that calibration remains unresolved.'
        source = {'handle':'evidence-'+digest(['fresh','observation','text','0'])[:24], 'action_id':'fresh',
            'result_sha256':'observation','kind':'text','text':text,'scope':'artifact_content_only'}
        fresh = {'evidence_options':[source],'evidence_subjects':[{'subject_ref':'/changed/item','literal':text,'evidence_handle':source['handle']}],
                 'repair_targets':[]}
        good = {'subject_ref':'/changed/item','evidence_handle':source['handle'],'quote':text}
        if execute(method,fresh,good) != good: raise ValueError('changed_evidence_program_counterexample')
        checks.append({'case':'fresh_source_subject_and_literal','passed':True})
        for key,value in (('quote','A fabricated conclusion.'),('subject_ref','/wrong/item'),('evidence_handle','evidence-stale')):
            try: execute(method,fresh,{**good,key:value})
            except ValueError: checks.append({'case':'invalid_'+key,'passed':True})
            else: raise ValueError('invalid_evidence_binding_must_fail')
    return {'current_output_verified':True,'independent_cases':checks,'scope':'bounded_program_execution_not_research_success'}
