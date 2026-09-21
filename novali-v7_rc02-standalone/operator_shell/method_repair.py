"""Evidence-driven requests to reuse unused continuation allowance after repair.

The research lease owns writes. Proposal assembly is automatic; review and
reauthorization are operator ingress. Historical outcomes are never rewritten.
"""
from __future__ import annotations

import copy
import time
from pathlib import Path
from typing import Any

from . import research_procedures as records
from .research_tools import digest, read_json

UNDISPATCHED_FAILURES = {'theory_context_size_limit', 'theory_context_size_limit_inspect_targeted_records'}


def _rows(root: Path, kind: str) -> list[dict[str, Any]]:
    return [records.read(root, kind, p.stem) for p in sorted((root/'research_methods'/kind).glob('*.json'))]


def authorization(root: Path, grant_id: str) -> dict[str, Any] | None:
    rows = [r for r in _rows(root, 'repair_authorizations') if r['grant_id'] == grant_id]
    if len(rows) > 1: raise ValueError('ambiguous_repair_authorization')
    return rows[0] if rows else None


def finished(root: Path, auth: dict[str, Any]) -> bool:
    return any(r['authorization_id'] == auth['id'] for r in _rows(root, 'repair_results'))


def _basis(root: Path, grant_id: str, policy: Any, repo_root: Path | None) -> tuple[dict[str, Any], dict[str, Any]]:
    from .theory_workspace import TheoryWorkspace
    from .theory_runtime import _planner_context
    from .theory_allowance import _controls_allow
    from .theory_methods import dependency_choices
    grant = records.read(root, 'continuation_grants', grant_id)
    if authorization(root, grant_id): raise ValueError('repair_authorization_already_used')
    state = read_json(root/grant['parent_path']); work = state['work']
    ws = TheoryWorkspace(root, work['subject_id'], repo_root=repo_root)
    ws.assert_current_sources()
    if (digest(work) != grant['work_sha256'] or ws._snapshot()['snapshot_id'] != grant['snapshot_id']
            or state.get('inflight') or not state['state'].startswith('waiting_') or not _controls_allow(ws, policy)):
        raise ValueError('settled_current_authorized_repair_required')
    if any(state['usage'][k] < v for k, v in grant['usage_before'].items()):
        raise ValueError('repair_usage_rollback')
    if state['usage']['model_calls'] >= grant['maximum_model_calls']:
        raise ValueError('original_unused_continuation_allowance_required')
    if (state['usage']['tool_calls'] >= work['limits']['tool_calls']
            or work['limits']['compute_seconds']-state['usage']['compute_seconds'] < 30):
        raise ValueError('remaining_research_resources_required')
    outcomes = [r for r in _rows(root, 'continuation_results') if r['grant_id'] == grant_id]
    if len(outcomes) != 1 or outcomes[0]['state'] != 'failed' or outcomes[0]['usage'] != state['usage']:
        raise ValueError('exact_failed_continuation_outcome_required')
    call = state['usage']['model_calls']
    model = read_json(ws._path('model_turns', work['run_id']+'-'+str(call)))
    meta = model.get('provider_metadata', {})
    # Legacy size failures were raised before HTTP and retained empty metadata.
    # Never infer non-dispatch from a timeout, blank response, or missing receipt.
    if (model.get('provider_error') not in UNDISPATCHED_FAILURES
            or model.get('response') or model.get('raw_response')
            or meta and meta.get('provider_outcome') != 'not_dispatched'
            or read_json(ws._path('turns', work['run_id']+'-'+str(call)))):
        raise ValueError('verified_undispatched_failure_required')
    adopted = next((r for r in records.context(root) if r['id'] == grant['candidate_id']), None)
    if not adopted: raise ValueError('current_independently_adopted_method_required')
    context = _planner_context(ws, state)
    choices = dependency_choices(context)
    command = records.run(adopted['procedure'], {'dependency_choices': choices}).get('command')
    expected = grant['first_command']
    if (not command or command['command'] != expected['command']
            or any(command['arguments'].get(k) != v for k,v in expected['arguments'].items() if k != 'question')):
        raise ValueError('repair_first_action_changed')
    context.update(task=copy.deepcopy(work), usage={**state['usage'], 'model_calls':call+1}, feedback=state['feedback'],
        remaining_compute_seconds=work['limits']['compute_seconds']-state['usage']['compute_seconds'])
    context['call_allowance'] = {**state.get('call_allowance', {}), 'required_first_action':expected,
        'effective_model_call_limit':grant['maximum_model_calls'],
        'calls_including_current':grant['maximum_model_calls']-call,
        'remaining_model_calls':grant['maximum_model_calls']-call-1}
    basis = {'grant_id':grant_id, 'parent_id':work['run_id'], 'parent_path':grant['parent_path'],
        'snapshot_id':grant['snapshot_id'], 'work_sha256':digest(work), 'usage_before':state['usage'],
        'failed_result_id':outcomes[0]['id'], 'failed_model_sha256':digest(model), 'review_id':adopted['review_id'],
        'candidate_id':grant['candidate_id'], 'implementation':records.implementation(),
        'first_command':expected, 'maximum_model_calls':grant['maximum_model_calls'],
        'context_sha256':digest(context)}
    return basis, context


def propose(root: Path, grant_id: str, *, policy: Any, repo_root: Path | None = None) -> dict[str, Any]:
    """Novali's controller assembles evidence, without a model call or authority."""
    from .research_runtime import local_planner
    basis, context = _basis(root, grant_id, policy, repo_root)
    previous = [r for r in _rows(root, 'repair_proposals') if r['basis']['grant_id'] == grant_id]
    existing = next((r for r in previous if r['basis'] == basis), None)
    if existing: return existing
    if len(previous) >= 8: raise ValueError('repair_inspection_limit_requires_review')
    started = time.monotonic()
    payload = local_planner(policy).preflight('plan', context)
    return records.store(root, 'repair_proposals', {'kind':'unused_continuation_repair', 'basis':basis,
        'authored_by':'Novali recovery controller', 'requires_independent_review':True,
        'proof':{'payload_sha256':digest(payload), 'provider_dispatched':False,
                 'context_bytes':len(payload['messages'][1]['content'].encode()),
                 'compute_seconds':time.monotonic()-started, 'model_calls':0},
        'requested_calls':basis['maximum_model_calls']-basis['usage_before']['model_calls'],
        'new_allowance_requested':0})


def review(root: Path, proposal_id: str, *, decision: str, reviewer: str, authority_reference: str,
           policy: Any, repo_root: Path | None = None) -> dict[str, Any]:
    if decision not in {'approve','reject'} or not reviewer.strip() or not authority_reference.strip():
        raise ValueError('explicit_independent_repair_review_required')
    proposal = records.read(root, 'repair_proposals', proposal_id)
    basis, context = _basis(root, proposal['basis']['grant_id'], policy, repo_root)
    if basis != proposal['basis']: raise ValueError('repair_proposal_changed_reassess')
    from .research_runtime import local_planner
    if digest(local_planner(policy).preflight('plan', context)) != proposal['proof']['payload_sha256']:
        raise ValueError('repair_preflight_changed_reassess')
    existing = [r for r in _rows(root,'repair_reviews') if r['proposal_id'] == proposal_id]
    if existing:
        if existing[0]['decision'] == decision: return existing[0]
        raise ValueError('repair_review_already_decided')
    return records.store(root, 'repair_reviews', {'proposal_id':proposal_id, 'proposal_sha256':digest(proposal),
        'decision':decision, 'reviewer':reviewer, 'authority_reference':authority_reference})


def reauthorize(root: Path, review_id: str, *, authority_reference: str, policy: Any,
                repo_root: Path | None = None) -> dict[str, Any]:
    if not authority_reference.strip(): raise ValueError('explicit_repair_reauthorization_required')
    decision = records.read(root, 'repair_reviews', review_id)
    proposal = records.read(root, 'repair_proposals', decision['proposal_id'])
    if decision['decision'] != 'approve' or digest(proposal) != decision['proposal_sha256']:
        raise ValueError('independent_repair_approval_required')
    existing = authorization(root, proposal['basis']['grant_id'])
    if existing:
        if existing['repair_review_id'] == review_id: return existing
        raise ValueError('repair_authorization_already_used')
    basis, context = _basis(root, proposal['basis']['grant_id'], policy, repo_root)
    if basis != proposal['basis']: raise ValueError('repair_proposal_changed_reassess')
    from .research_runtime import local_planner
    if digest(local_planner(policy).preflight('plan',context)) != proposal['proof']['payload_sha256']:
        raise ValueError('repair_preflight_changed_reassess')
    return records.store(root, 'repair_authorizations', {**basis, 'repair_review_id':review_id,
        'authority_reference':authority_reference, 'model_calls_added':0, 'all_other_limits_unchanged':True})


def record_outcome(workspace: Any, state: dict[str, Any], *, preflight_failed: bool = False) -> bool:
    """Return True when this is a repaired continuation, including terminal use."""
    from .method_continuation import _grant
    grant = _grant(workspace.root, state['id'])
    auth = authorization(workspace.root, grant['id']) if grant else None
    if not auth: return False
    if finished(workspace.root, auth): return True
    call = state['usage']['model_calls']
    if call <= auth['usage_before']['model_calls'] and not preflight_failed: return True
    turn = read_json(workspace._path('turns', state['id']+'-'+str(call)))
    model = read_json(workspace._path('model_turns', state['id']+'-'+str(call)))
    verified = bool(not preflight_failed and turn and digest(turn.get('result')) == turn.get('result_sha256')
        and model.get('response') == turn.get('command'))
    records.store(workspace.root, 'repair_results', {'authorization_id':auth['id'], 'grant_id':grant['id'],
        'usage':state['usage'], 'state':'executed' if verified else 'failed', 'verified_execution':verified,
        'command':turn.get('command') if verified else None, 'feedback':state.get('feedback',''),
        'requires_independent_outcome_review':True, 'live_research_growth_demonstrated':False})
    return True


def tick(root: Path, policy: Any, *, repo_root: Path | None = None) -> list[dict[str, Any]]:
    proposals = []
    for grant in _rows(root, 'continuation_grants'):
        if authorization(root, grant['id']): continue
        try: proposals.append(propose(root, grant['id'], policy=policy, repo_root=repo_root))
        except (ValueError, KeyError, OSError): continue
    return [{'id':r['id'], 'state':'awaiting_independent_repair_review', 'requested_calls':r['requested_calls']}
            for r in proposals]
