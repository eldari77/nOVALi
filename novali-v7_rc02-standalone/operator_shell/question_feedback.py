"""Canonical feedback survives persistence; transport is a reversible projection."""
from __future__ import annotations
import copy
import json
from typing import Any
from .research_tools import digest

FEEDBACK_BYTES = 3000


def retain_requirement(finding: dict[str, Any], status: str) -> dict[str, Any]:
    """A retry changes status, never the requirement's explanation or identity."""
    original = copy.deepcopy(finding)
    code = original.get('original_code', original['code'])
    identity = original.get('requirement_id') or 'r' + digest({
        'path': original['path'], 'code': code,
        'guidance': original.get('guidance'),
        'counterexample': original.get('counterexample')})[:16]
    return {**original, 'requirement_id': identity, 'code': status, 'original_code': code}


def canonical(feedback: dict[str, Any], guidance: dict[str, str] | None = None) -> dict[str, Any]:
    result = copy.deepcopy(feedback)
    lookup = {**(guidance or {}), **result.pop('finding_guidance', {})}
    issues = []; seen = set()
    for item in result.get('field_issues', []):
        ref = item.pop('guidance_ref', None)
        if ref and not item.get('guidance'):
            if ref not in lookup: raise ValueError('unresolved_question_feedback_reference')
            item['guidance'] = lookup[ref]
        key = digest(item)
        if key not in seen: issues.append(item); seen.add(key)
    if 'field_issues' in result: result['field_issues'] = issues
    return result


def restore(root, task: dict[str, Any]) -> dict[str, Any]:
    """Resolve legacy references from owned immutable attempts, never guessed text."""
    from . import research_procedures as records
    feedback = task.get('feedback', {})
    lookup = {}; historical = []
    episode = records.read(root, 'learning_episodes', task['learning_episode_id'])
    for source in episode.get('frozen_question_choices', []):
        historical.extend(source.get('failure_followup', {}).get('field_issues', []))
    for aid in task.get('attempt_ids', []):
        attempt = records.read(root, 'attempts', aid)
        if attempt.get('learning_episode_id') != task.get('learning_episode_id'):
            raise ValueError('owned_question_feedback_required')
        old = attempt.get('feedback', {})
        historical.extend(old.get('field_issues', []))
        lookup.update(old.get('finding_guidance', {}))
        for item in old.get('field_issues', []):
            if item.get('guidance'): lookup['g' + digest(item['guidance'])[:8]] = item['guidance']
    result = canonical(feedback, lookup)
    # Resolve legacy generic wrappers only when an owned original is unambiguous.
    # Never choose between competing reviewer requirements by recency.
    for item in result.get('field_issues', []):
        if item.get('code') not in {'requirement_not_repaired', 'semantic_finding_unchanged'}:
            continue
        if item.get('guidance', '').startswith('The reported requirement is unresolved.'):
            matches = {}
            for old in historical:
                code = old.get('original_code', old.get('code'))
                if (old.get('path') == item.get('path') and old.get('guidance')
                    and not old['guidance'].startswith('The reported requirement is unresolved.')
                    and code not in {'requirement_not_repaired', 'semantic_finding_unchanged', 'linked_measurement_review'}
                    and item.get('original_code') in {code, 'requirement_not_repaired', 'semantic_finding_unchanged'}):
                    key = digest([code, old['guidance'], old.get('counterexample')])
                    matches[key] = old
            if len(matches) == 1:
                old = next(iter(matches.values()))
                recovered = retain_requirement(old, item['code'])
                item.update(recovered)
    return result


def transport(context: dict[str, Any]) -> dict[str, Any]:
    """Keep canonical fields for schema/merge; send only necessary working values."""
    from .practice_experiments import editable
    from .question_focus import value_at, assign
    result = copy.deepcopy(context)
    result.pop('parent_refutation_origin',None)  # Immutable runtime provenance; observation is visible.
    result.pop('correction_requirements',None)  # IDs remain attached to findings; target bindings are in the schema.
    result.pop('provider_time_budget_seconds', None)
    for key in ('authoring_contract','quality_contract','repair_contract','focus_contract',
                'semantic_contract','measurement_contract','diagnosis_contract','partition_enabled','failure_evidence_metadata'):
        result.pop(key,None)  # Schema and instructions are generated from the canonical context.
    paths = editable(context)
    prior = result.get('previous_proposal')
    if paths and isinstance(prior, dict):
        working = {'source_id': prior.get('source_id')}
        for path in paths:
            top = path.split('/')[1]
            # Method siblings are useful operational context; bindings remain canonical.
            working[top] = copy.deepcopy(prior.get(top))
        result['previous_proposal'] = working
        result['preserved_fields'] = sorted(set(prior) - set(working))
    for choice in result.get('choices', []):
        choice.get('obligation',{}).pop('id',None)  # source_id already binds this exact obligation.
        followup = choice.get('failure_followup')
        if followup:
            # Reference resolves full retained accounting and timing, unchanged in storage.
            choice['failure_followup'] = {'reference_sha256':followup['reference_sha256']}
    if result.get('selected_source_id'):
        result.pop('selected_source_id')  # Already bound by previous_proposal.source_id and the edit schema.
    result['input_bindings']={'selected_obligation':'Source binds artifact/unit.'}
    result['evidence_scope']='Historical failures; no current result or authority.'
    # Repeated historical descriptions are interned once; every evidence ID and value survives.
    descriptions = {}
    for item in result.get('failure_evidence', {}).values():
        for key in ('id','method_adoption_authorized','scientific_allowance_added'):
            item.pop(key,None)  # Offered aliases resolve immutable evidence; no authority is granted.
        if item.get('observation'):
            text = item.pop('observation'); key = 'd' + digest(text)[:8]
            descriptions[key] = text; item['observation_ref'] = key
    if descriptions: result['evidence_descriptions'] = descriptions
    feedback = result.get('feedback', {})
    if feedback.get('field_issues'):
        feedback.pop('field_changes', None)  # Current values and canonical before/after remain in receipts.
        feedback.pop('reason', None)
        # Group identical diagnoses while preserving every affected path and counterexample.
        groups = {}
        for issue in feedback['field_issues']:
            body = {k:v for k,v in issue.items() if k != 'path'}
            requirement_id=body.pop('requirement_id',None)
            if body.get('subject')==issue['path']:body.pop('subject')
            counterexample=body.get('counterexample')
            # Exact current field text is already present. Reference only on byte
            # equality; historical or differently shaped counterexamples stay literal.
            if (isinstance(counterexample,dict) and set(counterexample)=={'text'}
                    and value_at(result.get('previous_proposal',{}),issue['path'])==counterexample['text']):
                body['counterexample']={'text_ref':'previous_proposal_at_each_path'}
            elif isinstance(counterexample,dict) and set(counterexample)=={'field','text'} and counterexample['field'] in {'method_before','method_after'}:
                from .question_quality import derive
                if derive(result.get('previous_proposal',{})).get(counterexample['field'])==counterexample['text']:
                    operation='baseline_operation' if counterexample['field']=='method_before' else 'changed_operation'
                    body['counterexample']={'operation_ref':'previous_proposal.method.'+operation}
            key = digest(body)
            grouped=groups.setdefault(key,{**body,'paths':[],'_ids':[]})
            grouped['paths'].append(issue['path']);grouped['_ids'].append(requirement_id)
        feedback['field_issues'] = []
        for grouped in groups.values():
            ids=grouped.pop('_ids')
            if len(ids)==1 and ids[0] is not None:grouped['requirement_id']=ids[0]
            elif any(i is not None for i in ids):grouped['requirement_ids']=ids
            feedback['field_issues'].append(grouped)
        if size(feedback)+size(result.get('finding_guidance',{}))+size(result.get('correction_requirements',{})) > FEEDBACK_BYTES:
            result = compact_transport(result)
            if size(result['feedback'])+size(result.get('finding_guidance',{})) > FEEDBACK_BYTES:
                raise ValueError('question_feedback_reservation_exceeded')
    return result


def compact_transport(context: dict[str, Any]) -> dict[str, Any]:
    """Tabulate repeated keys; keep all explanations and measurement evidence.

    Equality hashes are receipt provenance, not distinct counterexamples. Their
    equality can be expressed directly against the unchanged visible field.
    """
    result = copy.deepcopy(context)
    feedback = result['feedback']
    issues = feedback.pop('field_issues', [])
    for issue in issues:
        example = issue.get('counterexample', {})
        if (set(example) == {'before_sha256','after_sha256'}
                and example['before_sha256'] == example['after_sha256']):
            issue['counterexample'] = {'unchanged': True}
    columns = sorted({key for issue in issues for key in issue})
    feedback['finding_table'] = {'columns': columns,
        'rows': [[issue.get(key) for key in columns] for issue in issues]}
    # Tables preserve original/current findings separately. Repeated long strings
    # have a visible dictionary, never an opaque external lookup.
    from collections import Counter
    counts: Counter[str] = Counter()
    def visit(value):
        if isinstance(value,str): counts[value] += 1
        elif isinstance(value,list):
            for item in value: visit(item)
        elif isinstance(value,dict):
            for item in value.values(): visit(item)
    visit(feedback)
    strings = [s for s,n in counts.items() if n>1 and len(s)>20]
    indexes = {s:i for i,s in enumerate(strings)}
    def pack(value):
        if isinstance(value,str) and value in indexes: return {'s':indexes[value]}
        if isinstance(value,list): return [pack(v) for v in value]
        if isinstance(value,dict): return {k:pack(v) for k,v in value.items()}
        return value
    result['feedback'] = pack(feedback)
    if strings: result['feedback']['strings'] = strings
    return result


def size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))


def bounded_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Bound authored prose bytes. Exact Unicode source values remain runtime bindings."""
    result=copy.deepcopy(schema)
    def walk(node):
        if not isinstance(node,dict):return
        pattern=node.get('pattern')
        if node.get('type')=='string' and isinstance(pattern,str) and pattern.startswith('^[^'):
            end=pattern.index(']')+1
            node['pattern']=r'^[\x20-\x21\x23-\x5B\x5D-\x7E]'+pattern[end:]
        for value in node.values():
            if isinstance(value,dict):walk(value)
            elif isinstance(value,list):
                for item in value:walk(item)
    # Property dictionaries contain arbitrary field names, so walk every dictionary value.
    walk(result)
    return result
