"""Operational descriptions and conservative, answer-free draft diagnostics.

These checks detect specific contradictions; passing is not semantic approval.
"""
from __future__ import annotations

import copy
import re
from typing import Any

VERSION = 'operational_question_v1'


def method_schema() -> dict[str, Any]:
    from .planner_authoring import _object
    operation = {'type':'string','minLength':8,'maxLength':96,
        'pattern':r'^[^"\\\r\n\t]{8,96}$',
        'description':'One complete operation in plain words. Evaluator identifiers and field lists are supplied separately.'}
    return _object({'baseline_operation':operation,'changed_operation':operation})


def derive(response: dict[str, Any]) -> dict[str, Any]:
    result=copy.deepcopy(response)
    if isinstance(result.get('method'),dict):
        for source,target in [('baseline_operation','method_before'),('changed_operation','method_after')]:
            value=result['method'].get(source)
            if isinstance(value,dict) and all(isinstance(value.get(k),str) for k in ('action','check')):
                value=value['action'].rstrip('.!?')+'. '+value['check']
            if isinstance(value,str): result[target]=value if value.endswith(('.', '!', '?')) else value+'.'
    return result


def source_states(source: dict[str, Any]) -> dict[str,int]:
    unit=source['obligation'].get('unit',{})
    rows=source.get('frozen',{}).get('records',[])
    record=next((r.get('record') for r in rows if r.get('row_id')==unit.get('row_id')),None)
    if not isinstance(record,dict) or not unit.get('fields'):return {}
    counts=dict(absent=0,null=0,zero=0,false=0,other=0)
    for key in unit['fields']:
        if key not in record: state='absent'
        elif record[key] is None: state='null'
        elif record[key] is False: state='false'
        elif type(record[key]) in (int,float) and record[key]==0: state='zero'
        else: state='other'
        counts[state]+=1
    return counts


def cosmetic_only(before: Any, after: Any) -> bool:
    """Ignore only terminal prose punctuation, never quoted or executable bytes."""
    if before==after:return True
    if isinstance(before,dict) and isinstance(after,dict):
        return set(before)==set(after) and all(cosmetic_only(v,after[k]) for k,v in before.items())
    if not isinstance(before,str) or not isinstance(after,str):return False
    if any(c in before+after for c in "'\"`=<>[]{}\\") or '\n' in before+after:return False
    return before.rstrip(' .!?\t\r\n')==after.rstrip(' .!?\t\r\n')


def findings(source: dict[str, Any], response: dict[str, Any], *, compact: bool=False, structured: bool=False) -> list[dict[str, Any]]:
    issues=[]
    def issue(path,code,guidance,**kw):issues.append(dict(path=path,code=code,guidance=guidance,**kw))
    method=response.get('method')
    if structured and not response.get('measurement'):
        from .question_repair import method_findings
        issues.extend(method_findings(method))
    if compact and not structured and (not isinstance(method,dict) or set(method)!={'baseline_operation','changed_operation'} or
            any(not isinstance(v,str) or not 8<=len(v)<=96 for v in method.values())):
        issue('/method','bounded_operational_method_required','Describe the baseline and changed operations in short plain language.')
    evaluator=source['obligation']['completion_check']
    for key in ('method_before','method_after','observable','failure_condition'):
        value=response.get(key)
        if not isinstance(value,str):continue
        path='/method' if compact and key.startswith('method_') else '/'+key
        if (value.count('(')!=value.count(')') or re.search(r'[,;:]\s*[.!?]*$',value)):
            issue(path,'unfinished_operational_definition','Finish the operation or comparison; a final punctuation mark does not complete a fragment.')
        if not response.get('measurement') and key.startswith('method_') and (evaluator in value or re.search(r'\b[a-z][a-z0-9_]*_v[0-9]+\b',value)):
            issue(path,'evaluator_is_not_a_method','The evaluator is already bound by runtime. Describe the actual operation instead of an evaluator or version name.',counterexample={'field':key,'text':value})
    observable=response.get('observable','')
    states=source_states(source)
    if isinstance(observable,str):
        lower=observable.lower()
        if ((states.get('absent',0) or states.get('null',0)) and re.search(r'\bresolved\b',lower) and
            not re.search(r'\b(?:absent|unknown|missing|unresolved)\b',lower)):
            issue('/observable','source_state_preservation_required',
                'The selected source includes absent or null fields. Preserve these states instead of requiring all fields to resolve.',
                counterexample={'input_state':'absent','required_outcome':'preserve_absence'})
        hypothesis=response.get('hypothesis',{})
        metric=hypothesis.get('metric') if isinstance(hypothesis,dict) else None
        if metric in {'complete_response','extraction_correctness'} and re.search(r'non[- ]null|truthy',lower):
            issue('/observable','value_presence_is_not_correctness',
                'Counting populated or truthy fields does not measure correct completion. Missing, null, zero and false may be valid.',
                counterexample={'input_state':'false','required_outcome':'preserve_false'})
        if metric in {'context_bytes','response_tokens'} and not re.search('bytes?' if metric=='context_bytes' else 'tokens?',lower):
            issue('/observable','hypothesis_observable_mismatch','Define an observable in the units of the selected metric.')
    if compact and isinstance(method,dict) and cosmetic_only(method.get('baseline_operation'),method.get('changed_operation')):
        issue('/method','substantive_operation_change_required','Define an operational difference; punctuation or a name change alone is not a changed method.')
    return issues


def repair_findings(previous: Any, response: dict[str, Any], issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(previous,dict):return []
    result=[]
    syntax={'terminal_punctuation_required','bounded_complete_sentence_required'}
    for f in issues:
        key=f.get('path','')[1:]
        if f.get('code') in syntax or f.get('code')=='linked_measurement_review':continue
        from .question_focus import value_at
        before,after=value_at(previous,f['path']),value_at(response,f['path'])
        same=cosmetic_only(before,after)
        if response.get('measurement') and key in {'measurement','observable','failure_condition'}:
            # Runtime projections can remain textually identical after a valid
            # hypothesis repair. The instrument independently rechecks consistency.
            group=('hypothesis','method','measurement')
            same=cosmetic_only({k:previous.get(k) for k in group},{k:response.get(k) for k in group})
        if key=='method' and isinstance(before,dict) and isinstance(after,dict):
            same=set(before)==set(after) and all(cosmetic_only(v,after[k]) for k,v in before.items())
        if same:
            from .question_feedback import retain_requirement
            result.append(retain_requirement(f, 'requirement_not_repaired'))
    return result


def requirement_findings(source: dict[str, Any], response: dict[str, Any],
                         requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rerun registered original checks; unknown prose still needs semantic review.

    This deliberately narrow falsifier check rejects validity-only replacements.
    Passing establishes an expressed comparison, not its truth or usefulness.
    """
    from .question_feedback import retain_requirement
    result = []
    for requirement in requirements:
        code = requirement.get('original_code', requirement.get('code'))
        if code != 'prediction_falsifier_missing':
            continue
        if response.get('measurement'):
            from .question_measurements import findings as measurement_findings
            failed = any(f['path'] in {'/hypothesis', '/measurement'} for f in measurement_findings(source, response))
        else:
            text = response.get('failure_condition', '').lower()
            effect = response.get('hypothesis', {}).get('predicted_effect')
            opposites = {
                'increase': r'(?:fails? to exceed|does not exceed|not exceed|no (?:greater|higher|better)|less than or equal|<=|does not increase)',
                'decrease': r'(?:fails? to (?:decrease|fall)|does not decrease|not (?:less|lower)|no (?:less|lower)|greater than or equal|>=)',
                'unchanged': r'(?:differs?|not equal|unequal|!=)',
            }
            failed = not ('baseline' in text and effect in opposites and re.search(opposites[effect], text))
        if failed:
            result.append(retain_requirement(requirement, 'requirement_not_repaired'))
    return result
