"""Bounded planner-authored patches, typed method bindings and review feedback."""
from __future__ import annotations

import copy
import json
import re
from typing import Any

from .research_tools import digest
from .child_contracts import PARAMETERS

VERSION = 'child_repairs_v1'
METHOD_VERSION = 'child_parameter_bindings_v1'
BINDINGS = {
    'record_extraction': {'record_id': 'selected_record', 'required_fields': 'selected_fields'},
    'evidence_binding': {'evidence_handle': 'selected_evidence', 'subject_ref': 'selected_subject'},
    'interface_contract': {'target_artifact': 'selected_artifact', 'fixture_ref': 'selected_fixture'},
}


def baseline(context: dict[str, Any]) -> dict[str, Any] | None:
    value = context.get('previous_response') or context.get('previous_candidate')
    if not isinstance(value, dict) or not isinstance(value.get('payload'), dict): return None
    result = copy.deepcopy(value)
    targets = context.get('repair_targets', [])
    if targets and 'repairs' not in result['payload']:
        # Empty repair fields describe missing work; no source answer is supplied.
        result['payload'] = {'repairs': [{'claim_index': t['claim_index'], 'evidence_handle': '', 'quote': ''} for t in targets]}
    return result


def editable(context: dict[str, Any]) -> dict[str, Any]:
    previous = baseline(context)
    if not previous: return {}
    result: dict[str, Any] = {}
    def visit(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {'claim_index', 'row_id', 'field'}: continue
                visit(child, path + '/' + key.replace('~', '~0').replace('/', '~1'))
        elif isinstance(value, list):
            for index, child in enumerate(value): visit(child, path + '/' + str(index))
        elif value is None or type(value) in (str, int, float, bool): result[path] = value
    visit(previous['payload'], '/payload')
    if len(result) > 64: raise ValueError('repair_surface_exceeds_bounded_fields')
    return result


def finding_rows(context: dict[str, Any]) -> list[dict[str, Any]]:
    reviews = [context.get('revision_review', {}), context.get('failure_review', {}), context.get('refinement_review', {}), context.get('correction_review', {})]
    return [{'id': 'finding-' + digest([review.get('id'), finding])[:24], **finding}
            for review in reviews for finding in review.get('findings', [])]


def attach(context: dict[str, Any], frozen: dict[str, Any]) -> dict[str, Any]:
    if frozen.get('repair_contract') != VERSION: return context
    context['repair_contract'] = VERSION
    if frozen.get('refinement_review'):
        context['refinement_review'] = {k:v for k,v in frozen['refinement_review'].items()
            if k in {'id','findings','changed_approach','falsifier','evidence_reference'}}
        context['refinement_scope'] = frozen['refinement_scope']
    if frozen.get('failure_review'):
        context['failure_review'] = {k:v for k,v in frozen['failure_review'].items()
            if k in {'id','findings','approach','evidence_reference'}}
    if frozen.get('repair_baseline'): context['previous_candidate'] = frozen['repair_baseline']
    previous = baseline(context)
    context['repair_options'] = {'baseline_sha256': digest(previous) if previous else None,
        'editable_fields': list(editable(context)), 'max_edits': 8,
        'method_bindings': {o['adapter']:BINDINGS[o['adapter']] for o in context['obligations'] if o['eligible']},
        'finding_ids': [row['id'] for row in finding_rows(context)],
        'scope': 'independent_artifact_review_and_separate_method_adoption_required'}
    return context


def method_schema(adapter: str) -> dict[str, Any]:
    from .planner_authoring import _object, _string, _enum
    from .directive_candidates import STOPS
    bindings = BINDINGS[adapter]
    return _object({'representation': {'const': METHOD_VERSION}, 'name': _string(5, 100),
        'adapter': {'const': adapter}, 'bindings': {'const': bindings},
        'steps': {'type': 'array', 'minItems': 1, 'maxItems': 4, 'items': _object({
            'instruction': _string(5, 160), 'uses': {'type': 'array', 'minItems': 1,
                'maxItems': len(bindings), 'uniqueItems': True, 'items': _enum(list(bindings))}})},
        'stop_conditions': {'const': STOPS}})


def contract(context: dict[str, Any], old: tuple[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    if context.get('repair_contract') != VERSION: return old
    from .planner_authoring import _object, _string, _enum
    instructions, schema = old
    instructions = instructions.replace('Write concise complete method steps using every required {parameter} literally as a placeholder; bind actual values only in the payload. ',
        'Describe complete method instructions and declare their input roles through typed uses and bindings. ')
    profiles = context.get('permitted_context_profiles', ['full', 'focused'])
    shared = {'context_profile': _enum(profiles), 'rationale': _string(8, 180),
        'lesson_id': _enum(['none', *[m['id'] for m in context.get('methods', [])]]),
        'lesson_use': _enum(['new', 'apply', 'adapt', 'disregard'])}
    previous = baseline(context)
    variants = []
    if previous:
        paths = list(editable(context))
        for o in context['obligations']:
            if not o['eligible']: continue
            variants.append(_object({**shared, 'intent': {'const': 'patch'}, 'obligation_id': {'const': o['id']},
                'baseline_sha256': {'const': digest(previous)},
                'edits': {'type': 'array', 'minItems': 0, 'maxItems': 8, 'items': _object({
                    'path': _enum(paths), 'value': {'type': ['string', 'number', 'boolean', 'null']}})},
                'method_plan': {'anyOf': [method_schema(o['adapter']), {'type': 'null'}]}}))
    else:
        for variant in schema['oneOf']:
            if variant['properties']['intent']['const'] != 'revise': continue
            revised = copy.deepcopy(variant)
            adapter = revised['properties']['method']['properties']['adapter']['const']
            revised['properties']['method'] = {'anyOf': [method_schema(adapter), {'type': 'null'}]}
            revised['properties'].update(shared)
            revised['required'] = list(revised['properties'])
            variants.append(revised)
    variants.append(_object({'intent': {'const': 'defer'}, 'context_profile': _enum(profiles),
        'obligation_id': _enum([o['id'] for o in context['obligations'] if o['eligible']]),
        'missing_dependency': _string(8, 180), 'rationale': _string(8, 180)}))
    if context.get('remaining_model_calls', 0) > 1 and len(profiles) > 1:
        variants.append(_object({'intent': {'const': 'select_context'}, 'context_profile': _enum(profiles),
            'predicted_core_bytes': {'type': 'integer', 'minimum': 1}, 'rationale': _string(8, 180)}))
    return (instructions + ' Use the repair interface. Patch only listed payload fields against the exact baseline hash; '
        'omit unchanged fields. Keep a null method_plan to preserve the old method, or author typed method steps with explicit '
        'uses and bindings; do not embed fixed paths or evidence IDs in reusable instructions. Method defects do not establish '
        'artifact defects or method adoption. Explain the change in one complete sentence under 180 characters. '
        'Review findings stay open until independently verified. A measurement label is not a measurement procedure. '
        'Choose a permitted context_profile for the next call; select_context spends a call and earns no completion credit. '
        'Its predicted_core_bytes concerns the measured core projection only, not latency or the complete request.', {'oneOf': variants})


def absent_method(adapter: str) -> dict[str, Any]:
    from .directive_candidates import STOPS
    return {'representation': METHOD_VERSION, 'name': 'Method not proposed', 'adapter': adapter,
            'bindings': {}, 'steps': [], 'stop_conditions': STOPS}


def normalize(context: dict[str, Any], submitted: Any) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    from .directive_candidates import CandidateError, changes
    def reject(code: str, path: str = '/') -> None:
        raise CandidateError([{'path': path, 'code': code}])
    if not isinstance(submitted, dict) or len(json.dumps(submitted, allow_nan=False).encode()) > 12000:
        reject('bounded_response_object_required')
    from . import child_planning
    if child_planning.active(context):
        if submitted.get('intent')=='defer':return child_planning.normalize_defer(context,submitted)
        if submitted.get('intent')=='select_context':reject('route_before_authoring_no_repeated_context_choice')
    if context.get('repair_contract') != VERSION: return submitted, {}
    from . import child_research_actions as actions
    if context.get('research_tools_contract') in actions.SUPPORTED and submitted.get('intent') in actions.INTENTS:
        return actions.normalize(context, submitted)
    response = copy.deepcopy(submitted)
    if context.get('failure_review') and not child_planning.active(context) and response.get('intent') not in {'patch', 'select_context', 'defer'}:
        reject('reviewed_followup_requires_field_patch')
    profile = response.pop('context_profile', context.get('context_profile', 'full'))
    if profile not in context.get('permitted_context_profiles', ['full', 'focused']): reject('currently_permitted_context_profile_required')
    choice = {'context_profile': profile}
    if response.get('intent') == 'select_context':
        if set(response) != {'intent', 'predicted_core_bytes', 'rationale'} or context['remaining_model_calls'] <= 1:
            reject('context_trial_requires_remaining_repair_call')
        prediction = response['predicted_core_bytes']
        if type(prediction) is not int or prediction < 1: reject('positive_context_size_prediction_required')
        measured = next(row['core_bytes'] for row in context['context_options'] if row['profile'] == profile)
        choice.update(context_trial=True, predicted_core_bytes=prediction, measured_core_bytes=measured,
                      prediction_verdict='supported' if measured == prediction else 'refuted', completion_credit=False)
        return None, choice
    if response.get('intent') == 'defer' and 'missing_dependency' in response:
        if set(response) != {'intent', 'obligation_id', 'missing_dependency', 'rationale'}: reject('typed_deferral_required')
        selected = next((o for o in context['obligations'] if o['id'] == response['obligation_id']), None)
        if not selected: reject('currently_eligible_obligation_required')
        response = {'intent': 'defer', 'obligation_id': selected['id'], 'rationale': response['rationale'],
            'method': absent_method(selected['adapter']), 'lesson_id': 'none', 'lesson_use': 'new',
            'payload': {'missing_dependency': response['missing_dependency']}}
    elif response.get('intent') == 'patch':
        if set(response) != {'intent', 'baseline_sha256', 'obligation_id', 'edits', 'rationale', 'method_plan', 'lesson_id', 'lesson_use'}:
            reject('exact_patch_fields_required')
        previous = baseline(context)
        if not previous or response['baseline_sha256'] != digest(previous): reject('current_repair_baseline_required')
        edits = response['edits']; allowed = editable(context)
        if not isinstance(edits, list) or len(edits) > 8: reject('at_most_eight_field_edits')
        revised = copy.deepcopy(previous); seen = set(); unchanged = []
        for edit in edits:
            if not isinstance(edit, dict) or set(edit) != {'path', 'value'}: reject('typed_field_edit_required')
            path = edit['path']
            if not isinstance(path, str) or path not in allowed or path in seen: reject('unique_allowed_patch_path_required')
            if edit['value'] is not None and type(edit['value']) not in (str, int, float, bool): reject('scalar_patch_value_required', path)
            seen.add(path)
            if type(allowed[path]) is type(edit['value']) and allowed[path] == edit['value']:
                unchanged.append({'path': path, 'before': allowed[path], 'after': edit['value'], 'status': 'unchanged'})
                continue
            tokens = [p.replace('~1', '/').replace('~0', '~') for p in path.split('/')[1:]]
            cursor = revised
            for token in tokens[:-1]: cursor = cursor[int(token)] if isinstance(cursor, list) else cursor[token]
            if isinstance(cursor, list): cursor[int(tokens[-1])] = edit['value']
            else: cursor[tokens[-1]] = edit['value']
        if response['method_plan'] is not None: revised['method'] = response['method_plan']
        from .child_execution import active as execution_active
        rationale_repair = (execution_active(context) and response['rationale'] != previous.get('rationale')
            and any(f.get('path') == '/rationale' for f in [*context.get('feedback',{}).get('field_issues',[]), *finding_rows(context)]))
        if digest(revised['payload']) == digest(previous['payload']) and revised.get('method') == previous.get('method') and not rationale_repair:
            if unchanged:
                raise CandidateError([{**row, 'code': 'unchanged_field_edit'} for row in unchanged])
            reject('substantive_field_or_method_change_required')
        revised.update(intent='revise', obligation_id=response['obligation_id'], rationale=response['rationale'],
                       lesson_id=response['lesson_id'], lesson_use=response['lesson_use'])
        choice['patch_changes'] = changes(previous, revised)
        choice['unchanged_patch_fields'] = unchanged
        response = revised
    if response.get('method') is None:
        selected = next((o for o in context['obligations'] if o['id'] == response.get('obligation_id')), None)
        if selected: response['method'] = absent_method(selected['adapter'])
    return response, choice


def check_method(context: dict[str, Any], method: Any) -> list[dict[str, Any]]:
    from .child_procedure_programs import VERSION as PROGRAM,issues
    if isinstance(method,dict) and method.get('representation')==PROGRAM:
        from .child_correction import active, method_issues
        return (method_issues(method) or issues(method)) if active(context) else issues(method)
    from .child_measurements import PROGRAM_VERSION,program_issues
    if isinstance(method,dict) and method.get('representation')==PROGRAM_VERSION:
        return program_issues(method)
    from .directive_candidates import STOPS
    issues = []
    def fail(path: str, code: str) -> None: issues.append({'path': path, 'code': code})
    if not isinstance(method, dict) or set(method) != {'representation', 'name', 'adapter', 'bindings', 'steps', 'stop_conditions'}:
        return [{'path': '/method', 'code': 'typed_parameter_binding_method_required'}]
    adapter = method['adapter']; expected = BINDINGS.get(adapter) if isinstance(adapter, str) else None
    if not expected or method['representation'] != METHOD_VERSION or method['bindings'] != expected:
        fail('/method/bindings', 'current_input_binding_sources_required')
    if method['stop_conditions'] != STOPS: fail('/method/stop_conditions', 'all_stop_conditions_required')
    if not isinstance(method['name'], str) or not 5 <= len(method['name']) <= 100: fail('/method/name', 'bounded_method_name_required')
    steps = method['steps']; used = set()
    if not isinstance(steps, list) or not 1 <= len(steps) <= 4: fail('/method/steps', 'one_to_four_typed_steps_required')
    else:
        for i, step in enumerate(steps):
            path = '/method/steps/' + str(i)
            if not isinstance(step, dict) or set(step) != {'instruction', 'uses'}: fail(path, 'typed_instruction_and_uses_required'); continue
            text = step['instruction']; uses = step['uses']
            if not isinstance(text, str) or not 5 <= len(text) <= 160 or text.count('`') % 2:
                fail(path + '/instruction', 'complete_bounded_instruction_required')
            elif re.search(r'(?:evidence|obligation|child_candidate)-[a-zA-Z0-9]{8,}|(?:drafts|canonical)/[a-zA-Z0-9_]', text):
                fail(path + '/instruction', 'historical_binding_in_reusable_method')
            if not isinstance(uses, list) or not uses or any(not isinstance(p, str) or p not in (expected or {}) for p in uses):
                fail(path + '/uses', 'declared_current_input_uses_required')
            else: used.update(uses)
    if expected and used != set(expected): fail('/method/steps', 'all_parameters_must_be_used')
    return issues


def feedback(context: dict[str, Any], previous: Any, response: Any, field_issues: list[dict[str, Any]]) -> dict[str, Any]:
    from .directive_candidates import changes
    original = previous or context.get('previous_candidate')
    diff = changes(original, response) if response is not None else []
    findings = []
    for finding in finding_rows(context):
        touched = any(row['path'].startswith(finding['path']) or finding['path'].startswith(row['path']) for row in diff)
        findings.append({**finding, 'change_observed': touched, 'status': 'unresolved_requires_independent_review'})
    return {'changes': diff, 'comparison_baseline_sha256': digest(original) if original else None,
            'review_findings': findings, 'field_issues': field_issues, 'cached_evidence_retained': True}


def verify_review(candidate: dict[str, Any], resolutions: Any, method_decision: str, *, decision: str = 'approve') -> dict[str, Any]:
    """An independent reviewer explicitly resolves findings; the planner cannot."""
    findings = finding_rows(candidate['context'])
    from .child_review_findings import scope
    if decision not in {'approve','reject'}: raise ValueError('explicit_artifact_review_decision_required')
    if decision == 'reject':
        if resolutions or method_decision != 'defer': raise ValueError('rejection_preserves_findings_without_method_adoption')
        return {'finding_resolutions':[], 'unresolved_findings':findings, 'method_approved':False,
                'review_scope':'rejected_with_unresolved_findings_retained'}
    supplied = resolutions or []
    if not isinstance(supplied, list): raise ValueError('typed_independent_finding_resolutions_required')
    ids = []
    for row in supplied:
        if (not isinstance(row, dict) or set(row) != {'finding_id', 'evidence_reference', 'explanation'}
                or any(not isinstance(v, str) or not 8 <= len(v) <= 800 for v in row.values())):
            raise ValueError('explicit_review_evidence_for_each_finding_required')
        ids.append(row['finding_id'])
    required = {row['id'] for row in findings if scope(row) in {'artifact','both'} or method_decision == 'approve'}
    if len(ids) != len(set(ids)) or not required <= set(ids) or not set(ids) <= {row['id'] for row in findings}:
        raise ValueError('unresolved_review_findings_block_delivery_approval')
    if method_decision not in {'approve', 'defer'}: raise ValueError('separate_method_adoption_decision_required')
    if method_decision == 'approve' and not candidate['assessment'].get('method_assessment', {}).get('eligible_for_independent_adoption'):
        raise ValueError('method_checks_required_before_adoption_review')
    return {'finding_resolutions': supplied, 'unresolved_findings':[row for row in findings if row['id'] not in ids],
            'method_approved': method_decision == 'approve',
            'review_scope': 'independent_finding_resolution_with_separate_method_decision'}
