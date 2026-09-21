"""Versioned experiment proposals and bounded, auditable field corrections.

These checks establish expressibility and binding, not semantic novelty or truth.
Independent review still decides whether a changed method merits practice.
"""
from __future__ import annotations

import copy
import re
from typing import Any
from .research_tools import digest

VERSION = 'practice_experiment_v2'
FIELDS = {'method_before': 120, 'method_after': 120, 'input_scope': 120,
          'observable': 120, 'failure_condition': 160,
          'applicability_reason': 120, 'applicability_limit': 120}

# Syntax is shared by generation and validation; semantic review is separate.
SENTENCE_PATTERN = r'^[^"\\\r\n\t]{7,CAP}[.!?]$'


def sentence(cap: int) -> dict[str, Any]:
    return {'type': 'string', 'minLength': 8, 'maxLength': cap,
            'pattern': SENTENCE_PATTERN.replace('CAP', str(cap - 1)),
            'description': 'One complete sentence ending in . ! or ?, including punctuation within the character limit. Use apostrophes instead of double quotes and forward slashes in paths.'}


def compact(context: dict[str, Any]) -> dict[str, Any]:
    """Intern repeated evidence bindings losslessly; never remove a choice or finding."""
    result = copy.deepcopy(context)
    if 'failure_evidence_metadata' in result: return result
    shared = {}; evidence = {}; aliases = {}
    for original, finding in result.get('failure_evidence', {}).items():
        alias = 'e' + digest(original)[:8]
        if alias in evidence and evidence[alias]['id'] != original:
            raise ValueError('ambiguous_evidence_alias')
        aliases[original] = alias
        common = {k: v for k, v in finding.items() if k in {'adapter', 'review_id', 'scope'}}
        key = 'm' + digest(common)[:8]
        if key in shared and shared[key] != common: raise ValueError('ambiguous_evidence_metadata_alias')
        shared[key] = common
        evidence[alias] = {k: v for k, v in finding.items() if k not in common}
        evidence[alias].update(id=original, metadata=key)
    for choice in result['choices']:
        choice['failure_evidence_ids'] = [aliases[key] for key in choice.get('failure_evidence_ids', [])]
    result['failure_evidence'] = evidence; result['failure_evidence_metadata'] = shared
    return result


class InvalidExperiment(ValueError):
    def __init__(self, findings: list[dict[str, Any]]):
        self.findings = findings
        super().__init__(';'.join(f['path'] + ':' + f['code'] for f in findings))


def editable(context: dict[str, Any]) -> list[str]:
    prior = context.get('previous_proposal')
    if not isinstance(prior, dict) or prior.get('source_id') != context.get('selected_source_id'):
        return []
    issues = context.get('feedback', {}).get('field_issues', [])
    allowed = ({'measurement'} if context.get('measurement_contract') else set()) | set(FIELDS) | ({'method'} if context.get('quality_contract') else set()) | ({'execution_scope', 'hypothesis'} if context.get('semantic_contract') else set())
    if context.get('focus_contract'):
        from .question_focus import LEAVES
        allowed.update(p.lstrip('/') for p in LEAVES)
    if context.get('measurement_contract'):
        derived={'/observable','/failure_condition'}
        if context['measurement_contract']=='question_measurements_v2':derived.add('/measurement')
        issues=[{**f,'path':'/hypothesis'} if f.get('path') in derived else f for f in issues]
    paths = sorted({f['path'] for f in issues if f.get('path', '').lstrip('/') in allowed})
    # Structural errors outside the leaf contract require full submission again.
    if any(f.get('path', '').lstrip('/') not in allowed for f in issues): return []
    if context.get('focus_contract'):
        from .question_focus import paths as focus_paths
        paths=focus_paths(context,paths)
    from .question_diagnosis import narrow_paths
    return narrow_paths(context,paths)


def contract(context: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    from .planner_authoring import _object, _string, _enum
    instructions = (
        'Keep the objective and evidence bindings. Define a changed method, inputs, observable, falsifier and applicability. '
        'Resolve evidence aliases and metadata. End complete sentences with . ! or ? inside field limits. '
        'Address every finding. Rewording is not method change; independent review is required. ')
    if any(r.get('failure_followup') for r in context.get('choices', [])):
        instructions += 'Use failure_followup findings and evidence to revise your previous proposal. '
    paths = editable(context)
    if context.get('quality_contract'):
        instructions += ' Describe operations in plain words; evaluator bindings are supplied separately. Preserve absent, unknown, zero and false source states. '
    if context.get('repair_contract'):
        instructions += ' Each operation has the supplied input_ref, one short action and one short check. Do not repeat paths. A changed prediction requires independent evaluation; its original is retained. '
    if context.get('semantic_contract'):
        instructions += (' Select execution_scope: full_unit or a complete partition. Scope fields and counts are derived by runtime. '
            'Separate observed evidence from your untested prediction; choose the affected phase and metric. '
            'Use observable and failure_condition to define a controlled falsifiable comparison; unknown values are valid. ')
    if context.get('repair_contract'):
        instructions = ('Keep the selected source and evidence bindings; resolve aliases and scope references. '
            'Define a controlled comparison and falsifier for your untested prediction. '
            'Each method has input_ref, a short complete action and a short complete check; omit repeated paths. '
            'Preserve absent, unknown, zero and false states. Choose full scope or a complete partition. '
            'Address all findings; measurement fields may be corrected together. Changed predictions retain their original and require independent evaluation. '
            'Finish prose sentences within their limits. Independent review is required; no added allowance.')
    if context.get('focus_contract'):
        instructions = ('Use input_bindings and finding_guidance. Use offered source_id and evidence bindings. '
            'Write short complete operations without paths. Compare the selected metric under matching inputs and budgets; define its falsifier. '
            'Preserve absent, unknown, zero and false. Fix every unresolved finding; supporting measurement fields may stay unchanged. '
            'Changed predictions retain their originals. Independent review is required; no new allowance.')
    if context.get('measurement_contract'):
        instructions += ' Select cached-input operations: whole_input returns the record; selected_slots returns every selected state; present_slots omits absent slots. Measure preparation/context_bytes or execution/extraction_correctness, with a falsifier contradicting the prediction. This tests projections only, not provider performance.'
    if context.get('measurement_contract')=='question_measurements_v2':
        instructions = ('Use offered source/evidence bindings. whole_input returns the record; selected_slots returns all selected states; '
            'present_slots omits absent slots. Choose an untested prediction; runtime derives its falsifier. '
            'Use observed_failure for matching phases, motivating_failure to motivate a different-phase test. '
            'Read measurement_observation and finding_guidance; repair every unresolved requirement. '
            'Preserve absent/null/zero/false; write short complete explanations. '
            'Measurements grant no acceptance or allowance; independent review is required.')
    if paths:
        from .question_semantics import properties as semantic_properties
        extra = semantic_properties(context) if context.get('semantic_contract') else {}
        if context.get('quality_contract'):
            if context.get('repair_contract'):
                from .question_repair import method_schema
            else:
                from .question_quality import method_schema
            extra['method'] = method_schema()
        if context.get('measurement_contract'):
            from .question_measurements import method_schema as executable_method, schema
            extra.update(method=executable_method(),measurement=schema())
        rules = {}
        for path in paths:
            if path.startswith('/method/'):
                rule=extra['method']
                for part in path.split('/')[2:]:rule=rule['properties'][part]
                if context.get('diagnosis_contract') and 'enum' in rule:
                    from .question_focus import value_at
                    rule=copy.deepcopy(rule)
                    alternatives=[v for v in rule['enum'] if v!=value_at(context['previous_proposal'],path)]
                    if alternatives:rule['enum']=alternatives
                rules[path]=rule
            else:rules[path]=extra[path[1:]] if path[1:] in extra else sentence(FIELDS[path[1:]])
        items = [_object({'path': _enum([path]), 'value': rule}) for path, rule in rules.items()]
        edit_schema = _object({'edits': {'type':'array','minItems':1,'maxItems':len(paths),
            'items': items[0] if len(items)==1 else {'anyOf':items}}})
        if context.get('diagnosis_contract'):
            from .question_diagnosis import schema
            edit_schema=schema(context,edit_schema)
            instructions += ' Submit repair with the bound requirement, target and replacement value. supporting_edits may fix other failed fields; use [] when none. Preserve the baseline. Refute only the original measured hypothesis using its report. Verified repair is distinct from invention and grants no allowance.'
        return instructions + ' Submit edits only to offered failed fields. Unchanged findings stay unresolved. In finding_table, rows follow columns; {s:N} resolves feedback.strings[N]. Null cells are absent fields.', edit_schema
    properties = {'source_id': _enum([r['id'] for r in context['choices']]),
                  **{k: sentence(n) for k, n in FIELDS.items()}}
    if context.get('partition_enabled') and not context.get('semantic_contract'):
        from .question_partitions import schema
        properties['field_batches'] = schema(context['choices'])
        instructions += (' field_batches: [] keeps the full unit; otherwise cover every required field exactly once. '
                         'Each batch spends a shared window. Prose alone cannot reduce scope.')
    if context.get('semantic_contract'):
        from .question_semantics import properties as semantic_properties
        for derived in ('input_scope','field_batches','scope_mode'): properties.pop(derived,None)
        properties.update(semantic_properties(context))
    if context.get('quality_contract'):
        if context.get('repair_contract'):
            from .question_repair import method_schema
        else:
            from .question_quality import method_schema
        properties.pop('method_before',None);properties.pop('method_after',None)
        properties['method'] = method_schema()
        if not context.get('focus_contract'):instructions += ' Use method operations in plain words; the evaluator binding is supplied separately. Preserve source states and compare the proposed metric under matching inputs and budgets.'
    if context.get('measurement_contract'):
        from .question_measurements import method_schema as executable_method, schema
        properties.update(method=executable_method(),measurement=schema())
        properties.pop('observable',None);properties.pop('failure_condition',None)
        if context['measurement_contract']=='question_measurements_v2':properties.pop('measurement',None)
    return instructions, _object(properties)


def resolve(context: dict[str, Any], submitted: Any) -> tuple[Any, list[dict[str, Any]]]:
    """Merge only permitted leaves; never let a patch replace its evidence binding."""
    paths = editable(context)
    prior = context.get('previous_proposal')
    if not paths:
        # Full retries preserve already valid leaves when an envelope error prevented patches.
        if isinstance(prior, dict) and isinstance(submitted, dict) and context.get('selected_source_id'):
            failed = {f.get('path') for f in context.get('feedback', {}).get('field_issues', [])}
            derived={'method_before','method_after','input_scope','field_batches','scope_mode'} if context.get('repair_contract') else set()
            if context.get('measurement_contract'):
                derived.update({'observable','failure_condition'})
                if context['measurement_contract']=='question_measurements_v2':derived.add('measurement')
            changed = [k for k in ('source_id', 'field_batches', 'scope_mode', 'execution_scope', 'hypothesis', 'method', 'measurement', *FIELDS) if k not in derived and k in prior and '/' + k not in failed
                       and submitted.get(k) != prior[k]]
            if changed: raise InvalidExperiment([{'path': '/' + k, 'code': 'valid_field_is_frozen'} for k in changed])
        return submitted, []
    if context.get('diagnosis_contract'):
        from .question_diagnosis import validate
        checked=validate(context,submitted)
        if checked['decision']!='repair':raise InvalidExperiment([{'path':'/hypothesis','code':'refutation_requires_independent_replay'}])
        submitted={'edits':checked['edits']}
    if not isinstance(submitted, dict) or set(submitted) != {'edits'} or not isinstance(submitted['edits'], list):
        raise InvalidExperiment([{'path': '/', 'code': 'bounded_field_edits_required'}])
    edits = submitted['edits']
    if not 1 <= len(edits) <= len(paths):
        raise InvalidExperiment([{'path': '/edits', 'code': 'bounded_distinct_edits_required'}])
    result = copy.deepcopy(prior); changes = []; seen = set()
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) != {'path', 'value'} or edit['path'] not in paths or edit['path'] in seen:
            raise InvalidExperiment([{'path': '/edits', 'code': 'only_distinct_failed_fields_editable', 'permitted': paths}])
        seen.add(edit['path']); key = edit['path'][1:]
        from .question_focus import value_at,assign
        before = value_at(result,edit['path']); assign(result,edit['path'],edit['value'])
        changes.append({'path': edit['path'], 'before': before, 'after': edit['value'], 'changed': before != edit['value']})
    return result, changes


def check(rows: list[dict[str, Any]], response: Any) -> dict[str, Any]:
    if not isinstance(response, dict):
        raise InvalidExperiment([{'path': '/', 'code': 'typed_experiment_required'}])
    findings = []
    def issue(key, code, **details): findings.append({'path': '/' + key, 'code': code, **details})
    for key in sorted(set(response) - {'source_id', 'field_batches', 'scope_mode', 'execution_scope', 'hypothesis', 'method', 'measurement', *FIELDS}): issue(key, 'unexpected_field')
    source = next((r for r in rows if r['id'] == response.get('source_id')), None)
    if source is None: issue('source_id', 'invalid_reference', permitted=[r['id'] for r in rows])
    for key, cap in FIELDS.items():
        text = response.get(key)
        if not isinstance(text, str) or not 8 <= len(text) <= cap:
            issue(key, 'bounded_complete_sentence_required', max_length=cap,
                  actual_length=len(text) if isinstance(text, str) else None); continue
        if text[-1] not in '.!?':
            issue(key, 'terminal_punctuation_required', actual_length=len(text), max_length=cap,
                  characters_remaining=cap-len(text),
                  guidance='End the sentence with . ! or ? inside the limit; shorten wording if no space remains. Semantic completeness is independently reviewed.')
        if (text != text.strip() or '\n' in text or '\r' in text or text.endswith('...')
                or re.search(r'\b(and|or|because|by|with|the|to|of|if|than)[.!?]$', text, re.I)):
            issue(key, 'incomplete_explanation', guidance='Use one short complete sentence; semantic review still applies.')
    if source and 'field_batches' in response:
        from .question_partitions import validate
        findings.extend(validate(source, response['field_batches']))
    # Only exact equality is a deterministic no-op: case, whitespace inside a
    # quoted value, operators and signs can matter. Review judges semantic novelty.
    if isinstance(response.get('method_before'), str) and response.get('method_before') == response.get('method_after'):
        issue('method_after', 'unchanged_method', before=response['method_before'])
    if findings: raise InvalidExperiment(findings)
    return source
