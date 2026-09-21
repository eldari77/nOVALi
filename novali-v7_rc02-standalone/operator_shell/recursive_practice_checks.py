"""Answer-free diagnostics and bounded corrections for cached-record practice.

These checks supplement the frozen instrument, without rewriting old reports.
Disclosed diagnostic inputs are separate from fresh acceptance partitions.
"""
from __future__ import annotations
import copy
import hashlib
from pathlib import Path
from typing import Any
from . import recursive_evaluator as evaluator
from .research_tools import digest

VERSION = 'recursive_practice_checks_v1'


def fingerprint() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def rule_analysis(strategy: dict) -> dict:
    evaluator.validate(strategy)
    reached = set()
    for selected in range(1, 13):
        for absent in range(selected + 1):
            features = {'selected_count': selected, 'absent_count': absent}
            for index, rule in enumerate(strategy['rules']):
                if features[rule['feature']] >= rule['at_least']:
                    reached.add(index)
                    break
    return {'unreachable_rules': [i for i in range(len(strategy['rules'])) if i not in reached]}


def behavior_signature(strategy: dict) -> str:
    """Compare effective behavior, so changing a shadowed rule earns no repair."""
    outputs = []
    for count in range(1, 13):
        fields = [str(i) for i in range(count)]
        for absent in range(count + 1):
            case = {'record': {k: None for k in fields[absent:]}, 'fields': fields}
            outputs.append(evaluator.execute(strategy, case))
    return digest(outputs)


def coverage(proposal: dict, stage: int) -> dict:
    states = set()
    for case in proposal['practice_cases']:
        for field in case['fields']:
            if field not in case['record']:
                states.add('absent')
                continue
            value = case['record'][field]
            if value is None: states.add('null')
            elif value is False: states.add('false')
            elif type(value) in (int, float) and value == 0: states.add('zero')
            elif value == 'unknown' or value == {'state': 'unknown'}: states.add('unknown')
    required = {'absent', 'null'} if proposal['weakness'] == 'state_preservation' else set()
    if required and stage > 0: required.update(('false', 'zero', 'unknown'))
    missing = sorted(required - states)
    if proposal['weakness'] == 'evidence_cost' and not any(set(c['record'])-set(c['fields']) for c in proposal['practice_cases']):
        missing.append('unselected_input_for_cost_comparison')
    if proposal['weakness'] == 'complete_execution' and not any(len(c['fields']) > 1 for c in proposal['practice_cases']):
        missing.append('multiple_selected_fields')
    return {'covered_states': sorted(states), 'missing': missing, 'complete': not missing}


def diagnostic(strategy: dict) -> dict:
    # A public teaching example, never one of the held-out acceptance inputs.
    case = {'record': {'present': None}, 'fields': ['absent', 'present']}
    features = {'selected_count': 2, 'absent_count': 1}
    matches = []
    for i, rule in enumerate(strategy['rules']):
        matched = features[rule['feature']] >= rule['at_least']
        matches.append({'rule': i, 'matched': matched})
        if matched: break
    output = evaluator.execute(strategy, case)
    return {'scope': 'public_diagnostic_not_acceptance', 'input': case, 'features': features,
            'rule_trace': matches, 'effective_operation': output['operation'],
            'output_slots': output['slots'], 'errors': evaluator.oracle(case, output),
            **rule_analysis(strategy)}


def assess(proposal: dict, report: dict, stage: int) -> dict:
    covered = coverage(proposal, stage)
    trace = diagnostic(proposal['strategy'])
    issues = []
    if not report['transfer']['complete'] or not report['regression']['complete']:
        issues.append({'path': '/strategy', 'requirement': 'Preserve every selected state and complete all fields on changed inputs.'})
    if trace['unreachable_rules']:
        issues.append({'path': '/strategy/rules', 'requirement': 'Explain or remove unreachable rules; edits must change effective behavior.',
                       'indices': trace['unreachable_rules']})
    if covered['missing']:
        issues.append({'path': '/practice_cases', 'requirement': 'Exercise the selected weakness in your own cases.', 'missing': covered['missing']})
    if report['hypothesis_status'] == 'refuted':
        issues.append({'path': '/prediction', 'requirement': 'Original prediction is refuted. Any revised prediction is separately evaluated; repair need not improve the baseline.'})
    return {'contract': VERSION, 'sha256': fingerprint(), 'coverage': covered, 'diagnostic': trace,
            'findings': issues, 'practice_eligible': covered['complete']}


def paths(quality: dict) -> list[str]:
    result = set()
    for finding in quality['findings']:
        path = finding['path']
        if path == '/strategy':
            result.update('/strategy/' + k for k in evaluator.strategy_schema()['properties'])
        else: result.add(path)
    if '/prediction' in result:
        result.update(('/falsifier', '/relevance'))
    return sorted(result)


def get(proposal: dict, path: str) -> Any:
    value = proposal
    for part in path.strip('/').split('/'): value = value[part]
    return value


def correction_schema(proposal_schema: dict, proposal: dict, editable: list[str]) -> dict:
    properties = {}
    for path in editable:
        entry = proposal_schema
        for part in path.strip('/').split('/'): entry = entry['properties'][part]
        entry = copy.deepcopy(entry)
        if 'enum' in entry: entry['enum'] = [v for v in entry['enum'] if v != get(proposal, path)]
        properties[path] = entry
    return {'type': 'object', 'properties': {'corrections': {'type': 'object', 'properties': properties,
            'anyOf': [{'type':'object','required':[path]} for path in properties], 'maxProperties': len(properties), 'additionalProperties': False}},
            'required': ['corrections'], 'additionalProperties': False}


def resolve(submitted: dict, prior: dict, schema: dict) -> tuple[dict, list[dict]]:
    from .recursive_contract import validate
    from .question_quality import cosmetic_only
    validate(submitted, schema)
    result = copy.deepcopy(prior)
    changes = []
    for path, value in submitted['corrections'].items():
        before = get(prior, path)
        if cosmetic_only(before, value): raise ValueError('unchanged_targeted_edit:' + path)
        target = result
        parts = path.strip('/').split('/')
        for part in parts[:-1]: target = target[part]
        target[parts[-1]] = copy.deepcopy(value)
        changes.append({'path': path, 'before': before, 'after': value})
    if result['strategy'] != prior['strategy'] and behavior_signature(result['strategy']) == behavior_signature(prior['strategy']):
        raise ValueError('strategy_edit_does_not_change_effective_behavior')
    return result, changes


def feedback(proposal: dict, report: dict, quality: dict) -> dict:
    def compact(value):
        return {**{k: value[k] for k in ('cases','candidate_successes','baseline_successes','regressions',
                                      'candidate_context_bytes','baseline_context_bytes','complete')},
                'counterexamples':[{'errors':c['errors']} for c in value['counterexamples'][:1]]}
    return {'hypothesis_status': report['hypothesis_status'], 'transfer': compact(report['transfer']),
            'regression': compact(report['regression']), 'practice_checks': quality,
            'unresolved': 'Independent review must check relevance and falsifier, including absence versus null.'}
