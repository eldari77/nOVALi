"""Reproducible structural rejection evidence, separate from program results."""
from __future__ import annotations
import copy
import hashlib
from pathlib import Path
from . import research_procedures as records, recursive_corrections as corrections
from . import recursive_contract, recursive_practice_checks as checks
from .research_tools import digest


def freeze(prepared: dict, prior: dict | None) -> dict:
    typed=prepared['bundle_visible'].get('typed_correction_contract')
    names=['recursive_contract.py','recursive_practice_checks.py']
    if typed:names.append('recursive_corrections.py')
    causal=bool(prepared['bundle_visible'].get('causal_binding'))
    if causal:names.append('recursive_causal.py')
    return {'schema':copy.deepcopy(prepared['bundle_schema']),'schema_sha256':digest(prepared['bundle_schema']),
            'prior':copy.deepcopy(prior),'prior_sha256':digest(prior),
            'fields':copy.deepcopy(prepared['correction_bindings']) if typed else {},
            'wire_format':'causal_v3' if causal else 'typed_v2' if typed else 'path_v1',
            'validator_sources':{n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in names},
            'capture_kind':'frozen_before_dispatch'}


def envelope(root: Path, attempt: dict) -> dict:
    value=attempt.get('validation_envelope')
    if value and value.get('capture_kind')!='frozen_before_dispatch':
        raise ValueError('persisted_pre_dispatch_schema_required')
    if value and value.get('capture_kind')=='frozen_before_dispatch':
        key=attempt.get('validation_request_id')
        if not key:raise ValueError('persisted_pre_dispatch_schema_required')
        request=records.read(root,'recursive_validation_requests',key)
        if request['episode_id']!=attempt['learning_episode_id'] or request['envelope']!={k:v for k,v in value.items() if k!='rejection'}:
            raise ValueError('persisted_validation_request_binding_changed')
    if not value:
        matches=[records.read(root,'recursive_rejection_evidence',p.stem)
                 for p in (root/'research_methods/recursive_rejection_evidence').glob('*.json')]
        record=next((r for r in matches if r['attempt_id']==attempt['id']),None)
        if not record or record['attempt_sha256']!=digest(attempt):raise ValueError('frozen_rejection_schema_required')
        value=record['validation_envelope']
        episode=records.read(root,'learning_episodes',attempt['learning_episode_id'])
        if value.get('capture_kind')!='reconstructed_from_original_implementation_and_owned_history' or value.get('implementation')!=episode['implementation'] or not value.get('metadata_lengths_match'):
            raise ValueError('verified_legacy_schema_reconstruction_required')
    if digest(value['schema'])!=value['schema_sha256'] or digest(value['prior'])!=value['prior_sha256']:
        raise ValueError('frozen_rejection_binding_changed')
    for name,sha in value['validator_sources'].items():
        if name not in {'recursive_contract.py','recursive_practice_checks.py','recursive_corrections.py','recursive_causal.py'}:
            raise ValueError('bounded_validator_dependency_required')
        if hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()!=sha:
            raise ValueError('rejection_validator_requires_revalidation')
    return value


def replay(root: Path, attempt: dict) -> dict:
    if (not attempt.get('provider_dispatched') or attempt.get('provider_metadata',{}).get('provider_outcome')!='response_received'
            or not isinstance(attempt.get('submitted_response'),dict)):
        raise ValueError('confirmed_response_required_for_structural_review')
    value=envelope(root,attempt)
    prior=value['prior'];submitted=attempt['submitted_response']
    if not prior:raise ValueError('known_valid_correction_baseline_required')
    from .recursive_growth import check
    check(prior)
    try:
        if value['wire_format']=='causal_v3':
            from .recursive_causal import resolve
            resolve(submitted,prior,value['schema'],value['fields'])
        elif value['wire_format']=='typed_v2':corrections.resolve(submitted,prior,value['schema'],value['fields'])
        else:checks.resolve(submitted,prior,value['schema'])
    except (ValueError,TypeError,KeyError) as exc:reason=str(exc)
    else:raise ValueError('structural_rejection_not_reproduced')
    expected=value.get('rejection',attempt.get('feedback',{}).get('reason'))
    if reason[:600]!=str(expected)[:600]:raise ValueError('recorded_rejection_reason_not_reproduced')
    if value['wire_format']=='causal_v3':
        from .recursive_causal import rejection
        packet=rejection(prior,submitted,value['schema'],value['fields'],protected_states=[])
    else:packet=corrections.packet(prior,submitted,value['schema'],typed=value['wire_format']=='typed_v2')
    return {'evidence_type':'structural_rejection','attempt_id':attempt['id'],'attempt_sha256':digest(attempt),
            'envelope_sha256':digest(value),'reproduced_reason':reason,'prior':prior,'packet':packet,
            'executable_report':None,'scientific_progress_credited':False,'acceptance_credit':False}
