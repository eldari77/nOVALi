"""Versioned correction affordances; fixed mechanics never earn learning credit."""
from __future__ import annotations

import copy
import re
from typing import Any
from .research_tools import digest

VERSION = 'child_correction_v1'


def active(context: dict[str, Any]) -> bool:
    return context.get('correction_contract') == VERSION


def complete_sentence(value: Any) -> bool:
    return isinstance(value, str) and bool(re.search(r'[.!?][\"\'\u2019\u201d`)]?$', value.strip()))


def method_issues(method: Any) -> list[dict[str, Any]]:
    from . import child_procedure_programs as programs
    if not isinstance(method, dict) or method.get('representation') != programs.VERSION:
        return []
    expected = programs.STAGES.get(method.get('adapter'), [])
    steps = method.get('steps', [])
    if not isinstance(steps, list):
        return [{'scope': 'method', 'path': '/method/steps', 'code': 'ordered_stage_list_required', 'expected': expected, 'actual': steps}]
    issues = []
    for stage in expected:
        count = steps.count(stage)
        if count != 1:
            issues.append({'scope': 'method', 'path': '/method/steps', 'code': 'missing_stage' if count == 0 else 'repeated_stage',
                           'stage': stage, 'expected_count': 1, 'actual_count': count})
    for index, stage in enumerate(steps):
        if index >= len(expected) or stage != expected[index]:
            issues.append({'scope': 'method', 'path': '/method/steps/' + str(index), 'code': 'stage_order_mismatch',
                           'expected': expected[index] if index < len(expected) else None, 'actual': stage})
    return issues


def contract(context: dict[str, Any], original: tuple[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    if not active(context):
        return original
    from . import child_procedure_programs as programs
    from .child_repairs import finding_rows
    from .planner_authoring import _object, _enum, _string
    instructions, schema = original
    schema = copy.deepcopy(schema)
    def fixed(node: Any) -> None:
        if isinstance(node, dict):
            props = node.get('properties', {})
            if props.get('representation', {}).get('const') == programs.VERSION:
                adapter = props['adapter']['const']
                props['steps'] = {'const': list(programs.STAGES[adapter])}
            for value in node.values():
                fixed(value)
        elif isinstance(node, list):
            for value in node:
                fixed(value)
    fixed(schema)
    for variant in schema['oneOf']:
        props = variant['properties']
        if 'rationale' in props:
            props['rationale']['pattern'] = r'^.*[.!?]["\u2019\u201d`)]?$'
        if context.get('relevant_change'):
            props['change_assessment']=_object({'change_sha256':{'const':context['relevant_change']['sha256']},
                'scope':_enum(['artifact_structure','method_refinement','domain_evidence']),
                'relevance':_enum(['relevant','irrelevant','unknown']),'explanation':_string(12,160)})
            variant['required'].append('change_assessment')
        if props['intent']['const'] != 'bind_evidence':
            continue
        props['evidence_use'] = _object({'addresses': _enum(['current_obligation', *[f['id'] for f in finding_rows(context)]]),
            'contribution': _string(8, 160), 'remaining_unknown': _string(8, 160)})
        variant['required'].append('evidence_use')
        # Distractors remain visible. Known incompatible literal/subject pairs
        # are not executable bindings; semantic relevance is still Novali's job.
        if not context.get('repair_targets'):
            pairs = []
            for span in context.get('evidence_selections', []):
                for subject in context.get('evidence_subjects', []):
                    if subject['evidence_handle'] == span['source_id'] and span['literal'] in subject['literal']:
                        pairs.append(_object({'source_id': {'const': span['source_id']}, 'span_id': {'const': span['span_id']},
                                              'subject_ref': {'const': subject['subject_ref']}}))
            if not pairs:
                raise ValueError('no_literal_subject_binding_available')
            props['selections']['items'] = {'oneOf': pairs}
    from .child_relevance import contract as relevance_contract
    return relevance_contract(context, (instructions + ' Fixed program stages are runtime mechanics, not a learned result. Select their applicability and bindings. '
        'Use one short complete sentence for each explanation. For evidence_use, identify the finding or current obligation, '
        'explain what the passage contributes, and state what remains unknown. A literal title is not evidence that a design gap is solved. '
        'Compare the selected subject, exact passage and your rationale before submitting. Use remaining calls to correct specific feedback. '
        'When change_assessment is required, explain which kind of work the change helps; reviewed addenda supply no new domain evidence.', schema))


def prepare_response(context: dict[str, Any], submitted: Any) -> tuple[Any, dict[str, Any]]:
    if not active(context) or not isinstance(submitted, dict):
        return submitted, {}
    from .directive_candidates import CandidateError
    from .child_repairs import finding_rows
    from .child_relevance import prepare as prepare_relevance
    response, relevance_metadata = prepare_relevance(context, submitted)
    issues = []
    if not complete_sentence(response.get('rationale')):
        issues.append({'scope': 'artifact', 'path': '/rationale', 'code': 'complete_short_explanation_required',
                       'actual': response.get('rationale'), 'expected': 'A complete sentence ending in punctuation.'})
    use = response.pop('evidence_use', None)
    assessment=response.pop('change_assessment',None)
    if context.get('relevant_change'):
        keys={'change_sha256','scope','relevance','explanation'}
        if (not isinstance(assessment,dict) or set(assessment)!=keys
                or assessment.get('change_sha256')!=context['relevant_change']['sha256']
                or assessment.get('scope') not in {'artifact_structure','method_refinement','domain_evidence'}
                or assessment.get('relevance') not in {'relevant','irrelevant','unknown'}
                or not isinstance(assessment.get('explanation'),str) or not 12<=len(assessment['explanation'])<=160
                or not complete_sentence(assessment['explanation'])):
            issues.append({'scope':'artifact','path':'/change_assessment','code':'explicit_current_change_relevance_required'})
        elif assessment['scope']=='domain_evidence' and assessment['relevance']=='relevant':
            issues.append({'scope':'artifact','path':'/change_assessment','code':'reviewed_addenda_are_not_new_domain_evidence'})
    elif assessment is not None:
        issues.append({'scope':'artifact','path':'/change_assessment','code':'unoffered_change_reference'})
    if use is not None and response.get('intent') != 'bind_evidence':
        issues.append({'scope':'artifact','path':'/evidence_use','code':'evidence_use_requires_binding_action'})
    if response.get('intent') == 'bind_evidence':
        allowed = {'current_obligation', *[f['id'] for f in finding_rows(context)]}
        if not isinstance(use, dict) or set(use) != {'addresses', 'contribution', 'remaining_unknown'}:
            issues.append({'scope': 'artifact', 'path': '/evidence_use', 'code': 'explicit_evidence_contribution_required'})
        else:
            if use['addresses'] not in allowed:
                issues.append({'scope': 'artifact', 'path': '/evidence_use/addresses', 'code': 'current_finding_reference_required'})
            for key in ('contribution', 'remaining_unknown'):
                value = use[key]
                if not isinstance(value, str) or not 8 <= len(value) <= 160 or not complete_sentence(value):
                    issues.append({'scope': 'artifact', 'path': '/evidence_use/' + key, 'code': 'complete_short_explanation_required', 'actual': value})
    method = response.get('method_plan', response.get('method'))
    if issues:
        raise CandidateError([*issues, *method_issues(method)])
    return response, {**({'evidence_use':use} if use else {}),**({'change_assessment':assessment} if assessment else {}),
        **({'relevance_assessment':relevance_metadata} if relevance_metadata else {})}


def inspect_binding(context: dict[str, Any], response: Any) -> list[dict[str, Any]]:
    if not isinstance(response, dict) or response.get('intent') != 'bind_evidence':
        return []
    rows = []
    for choice in response.get('selections', [])[:8]:
        span = next((s for s in context.get('evidence_selections', []) if s['source_id'] == choice.get('source_id') and s['span_id'] == choice.get('span_id')), {})
        subjects = [s for s in context.get('evidence_subjects', []) if s['subject_ref'] == choice.get('subject_ref')]
        rows.append({'selection': choice, 'selected_passage': span.get('literal'), 'subject_values': subjects,
                     'relevance_requires_independent_review': True})
    return rows


def forced_route(context: dict[str, Any], routes: dict[str, Any]) -> dict[str, Any] | None:
    if not active(context) or len(routes['route_options']) != 1:
        return None
    return {**routes['route_options'][0], 'rationale': 'Only one current route fits the frozen constraints.',
            'selection': 'deterministic_single_option', 'route_set_sha256': digest(routes['route_options']),
            'provider_calls': 0, 'completion_credit': False}


def combined(context: dict[str, Any], routes: dict[str, Any]) -> dict[str, Any] | None:
    """Offer bounded joint selection/authoring only when every complete branch fits."""
    if not active(context) or not 2 <= len(routes['route_options']) <= 3:
        return None
    from . import child_planning, directive_candidates
    from .planner_authoring import _object
    import json
    visible=[]; variants=[]; contexts={}; instructions=''
    for route in routes['route_options']:
        branch=child_planning.project(context,route['obligation_id'],route['profile'],route.get('evidence_source_id'))
        instructions,schema=directive_candidates.planner_contract(branch)
        prompt,schema=child_planning.wire(branch,schema)
        visible.append({'route_id':route['id'],'task_input':prompt})
        variants.append(_object({'route_id':{'const':route['id']},'response':schema}))
        contexts[route['id']]=branch
    instructions+=' Choose one suitable route and author its response in this call. Each route has its own local source/span aliases. Prefer useful evidence over a smaller irrelevant input.'
    prompt={'choices':visible,'calls_remaining':context.get('remaining_model_calls',2)}
    schema={'oneOf':variants}
    try:
        child_planning.reserve(instructions,prompt,child_planning.OUTPUT_TOKENS)
        if len(json.dumps(schema).encode())>16000:
            return None
    except ValueError:
        return None
    return {'correction_contract':VERSION,'growth_contract':child_planning.VERSION,'bundle_visible':prompt,'bundle_schema':schema,'bundle_instructions':instructions,
            'bundle_contexts':contexts,'bundle_routes':routes['route_options']}
