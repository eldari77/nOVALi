"""Selectable method payloads: remove navigation, retain decision evidence."""
from __future__ import annotations
import copy
import json
from typing import Any, Mapping
from .research_tools import digest
MODES = ('full', 'evidence_focus_v1')
OPTIONAL = ('planning_context_outline', 'hypothesis_history')

def canonical(context: Mapping[str, Any]) -> dict[str, Any]:
    from .planner_resources import authoring_inputs
    result = copy.deepcopy(dict(context))
    result['inputs'] = authoring_inputs(result.get('inputs', {}))
    return result

def critical(context: Mapping[str, Any]) -> dict[str, Any]:
    result = canonical(context)
    inputs = result['inputs']
    outline = inputs.pop('planning_context_outline', None)
    if outline: inputs['frozen_context_sha256'] = outline['frozen_context_sha256']
    inputs.pop('hypothesis_history', None)
    inputs.pop('context_projection_options', None)
    result.pop('method_context_projection', None)
    result.pop('context_projection_receipt', None)
    return result

def project(context: Mapping[str, Any], mode: str) -> dict[str, Any]:
    if mode not in MODES: raise ValueError('known_method_context_projection_required')
    result = canonical(context)
    if mode != 'full':
        if result.get('failure', {}).get('family') != 'planning':
            raise ValueError('focused_planning_method_context_required')
        inputs = result['inputs']
        outline = inputs.pop('planning_context_outline', None)
        if outline: inputs['frozen_context_sha256'] = outline['frozen_context_sha256']
        inputs.pop('hypothesis_history', None)
    if critical(result) != critical(context): raise ValueError('method_projection_changed_required_evidence')
    result['method_context_projection'] = mode
    result['context_projection_receipt'] = {'mode': mode, 'critical_sha256': digest(critical(context)),
        'omitted_fields': list(OPTIONAL) if mode != 'full' else [],
        'scope': 'method_authoring_only', 'latency_improvement': 'unmeasured'}
    return result

def measure(context: Mapping[str, Any]) -> dict[str, Any]:
    """Measure production preflight, without a provider call or inferred speedup."""
    from .research_runtime import ResearchPolicy, local_planner
    planner = local_planner(ResearchPolicy())
    rows = []
    clean = copy.deepcopy(dict(context))
    clean.get('inputs', {}).pop('context_projection_options', None)
    for mode in MODES:
        payload = planner.preflight('method', {**clean, 'method_context_projection': mode})
        encoded = payload['messages'][1]['content']
        rows.append({'mode': mode, 'authoring_context_bytes': len(encoded.encode()),
            'instruction_chars': len(payload['messages'][0]['content']),
            'schema_bytes': len(json.dumps(payload['format'], separators=(',', ':')).encode()),
            'critical_sha256': digest(critical(json.loads(encoded)))})
    return {'scope': 'method_authoring_payload_only_not_research_context_bytes', 'profiles': rows,
        'measurement_basis':'exact_preflight_before_adding_this_diagnostic_catalog',
        'checks': 2, 'provider_dispatched': False, 'task_success_and_latency': 'require_paired_evaluation'}
