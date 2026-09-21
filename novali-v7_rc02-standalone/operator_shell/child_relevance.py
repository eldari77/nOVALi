"""Explicit relevance claims; structural checks never certify their meaning."""
from __future__ import annotations

import copy
from typing import Any

VERSION = 'child_relevance_v1'
RELATIONS = ('direct_support', 'partial_support', 'context_only', 'contradiction')


def executable(method: Any) -> bool:
    from . import child_procedure_programs as programs, child_measurements as measurements
    if not isinstance(method, dict): return False
    if method.get('representation') == programs.VERSION: return not programs.issues(method)
    if method.get('representation') == measurements.PROGRAM_VERSION: return not measurements.program_issues(method)
    return False


def active(context: dict[str, Any]) -> bool:
    return context.get('relevance_contract') == VERSION


def targets(context: dict[str, Any]) -> list[str]:
    from .child_repairs import finding_rows
    from .child_review_findings import scope
    findings = [r['id'] for r in finding_rows(context) if scope(r) in {'artifact', 'both'}]
    # Existing artifact findings are the actual correction target. A generic
    # obligation or method finding cannot silently substitute for them.
    return findings or ['current_obligation']


def contract(context: dict[str, Any], original: tuple[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    from . import child_procedure_programs as programs
    from .child_measurements import PROGRAM_VERSION
    from .child_repairs import baseline
    from .planner_authoring import _enum
    instructions, original_schema = original
    schema = copy.deepcopy(original_schema)
    method_only = context.get('refinement_scope') == 'method_only'
    for variant in schema['oneOf']:
        props = variant['properties']
        if method_only:
            for key in ('method_plan', 'method'):
                choices = props.get(key, {}).get('anyOf')
                if choices is None: continue
                current = (baseline(context) or {}).get('method')
                choices[:] = [c for c in choices if
                    c.get('properties', {}).get('representation', {}).get('const') in {programs.VERSION, PROGRAM_VERSION} or
                    c.get('type') == 'null' and executable(current)]
                if not choices:
                    raise ValueError('executable_method_route_required')
        if not active(context): continue
        if 'evidence_use' in props:
            use = props['evidence_use']
            use['properties']['addresses'] = _enum(targets(context))
            use['properties']['relation'] = _enum(RELATIONS)
            use['required'].append('relation')
        if 'change_assessment' in props:
            change = props['change_assessment']
            change['properties']['assessed_object'] = {'const': 'reviewed_input_change'}
            change['required'].append('assessed_object')
    if method_only:
        instructions += ' This task requires an executable method; prose cannot satisfy adoption. Preserve the accepted payload; omit unchanged edits.'
    if active(context):
        instructions += (' Link the addressed artifact finding to the passage and limited conclusion. '
            'A contradiction is reviewable, not claim support. Assess the earlier input change separately from your proposal.')
    return instructions, schema


def prepare(context: dict[str, Any], submitted: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Normalize new fields for the unchanged historical correction checker."""
    from .directive_candidates import CandidateError
    from . import child_procedure_programs as programs
    from .child_repairs import baseline
    response = copy.deepcopy(submitted); issues = []; metadata = {}
    if context.get('refinement_scope') == 'method_only':
        method = response.get('method_plan', response.get('method'))
        if method is None: method = (baseline(context) or {}).get('method')
        if response.get('intent') != 'defer' and not executable(method):
            issues.append({'scope': 'method', 'path': '/method_plan', 'code': 'executable_method_required_by_current_task',
                'actual': method.get('representation') if isinstance(method, dict) else None,
                'expected': programs.VERSION})
    if active(context):
        if response.get('intent') == 'bind_evidence':
            use = response.get('evidence_use')
            if not isinstance(use, dict) or use.get('addresses') not in targets(context):
                issues.append({'scope': 'artifact', 'path': '/evidence_use/addresses', 'code': 'address_actual_artifact_finding', 'expected': targets(context)})
            relation = use.pop('relation', None) if isinstance(use, dict) else None
            if relation not in RELATIONS:
                issues.append({'scope': 'artifact', 'path': '/evidence_use/relation', 'code': 'explicit_evidence_relation_required'})
            elif relation == 'context_only':
                issues.append({'scope': 'artifact', 'path': '/evidence_use/relation', 'code': 'evidence_does_not_resolve_support_finding',
                    'actual': relation, 'permitted_response': 'defer_source_relevance_unresolved',
                    'explanation': 'Retain this finding and identify the missing relevant evidence; no completion credit.'})
            metadata['evidence_relation'] = relation
            metadata['independent_semantic_review_required'] = True
        if context.get('relevant_change'):
            change = response.get('change_assessment')
            assessed = change.pop('assessed_object', None) if isinstance(change, dict) else None
            if assessed != 'reviewed_input_change':
                issues.append({'scope': 'artifact', 'path': '/change_assessment/assessed_object', 'code': 'assess_reviewed_input_not_proposed_edit'})
            metadata['assessed_object'] = assessed
    if issues: raise CandidateError(issues)
    return response, metadata


def view(context: dict[str, Any]) -> dict[str, Any]:
    if not active(context): return {}
    result = {'relevance_question': {'finding_choices': targets(context),
        'judgment': 'Source -> conclusion -> unresolved question; independent meaning review.'}}
    if context.get('relevant_change'):
        result['change_to_assess'] = {**context['relevant_change'], 'assessed_object': 'reviewed_input_change',
            'origin': 'Already delivered reviewed addenda. Your new proposal is separate.'}
        result['proposed_change_reference'] = 'Your edits target baseline_sha256; change_to_assess is the earlier input change.'
    return result
