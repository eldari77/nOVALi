"""Measured child context choices; evidence bindings and costs remain explicit."""
from __future__ import annotations
import copy
import json
from typing import Any
from .research_tools import digest

PROFILES = ('full', 'focused')


def project(context: dict[str, Any], profile: str) -> dict[str, Any]:
    if profile not in PROFILES: raise ValueError('registered_child_context_profile_required')
    result = copy.deepcopy(context)
    if profile == 'focused':
        adapters = {o['adapter'] for o in result['obligations'] if o['eligible']}
        # These are task summaries, not source bindings or proposed repair fields.
        result.pop('directive_scope', None)
        if adapters == {'record_extraction'}:
            result['artifact_excerpt'] = ''  # Exact selected source values remain in records.
            result['evidence_options'] = []
            result['evidence_subjects'] = []
        elif adapters == {'interface_contract'}:
            result['evidence_options'] = []
            result['evidence_subjects'] = []  # Interface grammar references artifact refs, not handles.
        patterns = result.get('reviewed_failure_patterns', [])
        result['reviewed_failure_patterns'] = [{k: v for k, v in row.items()
            if k in {'review_id', 'observed_failure_patterns', 'scope'}} for row in patterns]
        result['method_parameters'] = {k:v for k,v in result.get('method_parameters', {}).items() if k in adapters}
        if result.get('failure_review'):
            result['failure_review'] = {k:v for k,v in result['failure_review'].items()
                if k in {'id','findings','approach','evidence_reference'}}
    return result


def diagnostics(attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{'attempt_id': a['id'], 'call': a['call'], 'outcome': a.get('outcome', {}).get('reason'),
        'charged_seconds': a.get('compute_seconds_charged'),
        'provider_outcome_uncertain': a.get('provider_outcome_uncertain', False),
        'context_bytes': a.get('provider_metadata', {}).get('context_utf8_bytes'),
        'schema_bytes': a.get('provider_metadata', {}).get('schema_utf8_bytes'),
        'timing': a.get('provider_metadata', {}).get('timing', {}),
        'context_choice': a.get('context_choice', {}),
        'interpretation': 'Observed costs for these inputs; no causal speedup or learning claim.'} for a in attempts[-2:]]


def prepare(context: dict[str, Any], *, profile: str, attempts: list[dict[str, Any]],
            permitted: tuple[str, ...] = PROFILES) -> dict[str, Any]:
    if not permitted or any(p not in PROFILES for p in permitted) or profile not in permitted:
        raise ValueError('currently_permitted_child_context_profile_required')
    options = []
    for choice in permitted:
        projected = project(context, choice)
        options.append({'profile': choice, 'core_bytes': len(json.dumps(projected, ensure_ascii=False, separators=(',', ':')).encode()),
            'core_sha256': digest(projected), 'scope': 'core_projection_before_diagnostic_envelope_and_provider_schema',
            'success_or_latency_improvement': 'unproven'})
    result = project(context, profile)
    result.update(context_profile=profile, context_options=options, permitted_context_profiles=list(permitted),
                  phase_diagnostics=diagnostics(attempts))
    # Exact prompt costs are also recorded by the provider after dispatch.
    result['projection_measurement'] = next(row for row in options if row['profile'] == profile)
    if len(json.dumps(result).encode()) > 36000:
        raise ValueError('child_context_with_diagnostics_exceeds_limit')
    return result
