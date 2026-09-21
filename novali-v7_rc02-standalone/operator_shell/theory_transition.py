"""Explicit evaluator migration funded once by the shared practice reservation.

Administrative approval is not a scientific result. Historical runs remain
immutable; continuation usage is cumulative and also settles its shared account.
Callers hold the research lease, including review and admission.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from . import learning_episodes as episodes, research_procedures as records
from .research_tools import digest, read_json, write_json


def basis(workspace, proposed: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    originals = {r['snapshot_id']: r['sources'] for r in workspace._records('revisions')
                 if r.get('status') == 'original_source_snapshot'}
    predecessors = []
    for path in sorted((workspace.base / 'runs').glob('*.json')):
        state = read_json(path)
        if not any(state.get('usage', {}).values()):
            continue
        if state.get('transition_review_id'):
            raise ValueError('transition_lineage_already_funded')
        if originals.get(state['work']['snapshot_id']) != snapshot['sources']:
            raise ValueError('transition_requires_identical_scientific_sources')
        if state.get('inflight'):
            raise ValueError('settle_predecessor_before_transition')
        predecessors.append({'id': state['id'], 'sha256': digest(state), 'usage': state['usage']})
    if not predecessors or all(read_json(workspace._path('runs', p['id']))['work']['snapshot_id'] == snapshot['snapshot_id'] for p in predecessors):
        raise ValueError('changed_evaluator_snapshot_with_retained_history_required')
    active_snapshot = workspace._snapshot()['snapshot_id']
    active = [read_json(workspace._path('runs', p['id'])) for p in predecessors
              if read_json(workspace._path('runs', p['id']))['work']['snapshot_id'] == active_snapshot]
    if not active: raise ValueError('explicit_active_predecessor_required')
    primary = max(active, key=lambda r: (r['usage']['model_calls'], r['usage']['compute_seconds']))
    remaining = {k: max(0, primary['work']['limits'][k] - primary['usage'][k])
                 for k in ('tool_calls', 'compute_seconds', 'evaluations')}
    return {'proposed_work': proposed, 'snapshot': snapshot, 'predecessors': predecessors,
            'active_predecessor_id': primary['id'], 'remaining_execution_capacity': remaining,
            'retained_usage': {k: sum(p['usage'][k] for p in predecessors) for k in proposed['limits']}}


def review(workspace, proposed: dict[str, Any], snapshot: dict[str, Any], *, reviewer: str,
           authority_reference: str, evidence_reference: str) -> dict[str, Any]:
    if any(not isinstance(v, str) or not 8 <= len(v) <= 1600 for v in (reviewer, authority_reference, evidence_reference)):
        raise ValueError('explicit_independent_transition_review_required')
    packet = basis(workspace, proposed, snapshot)
    from .nine_d_testing import fidelity_check
    fidelity = fidelity_check()
    if not fidelity['passed']:
        raise ValueError('complete_transition_reference_failed')
    reviewed = records.store(workspace.root, 'theory_transition_reviews', {
        'subject_id': workspace.subject_id, 'basis': packet, 'reviewer': reviewer,
        'authority_reference': authority_reference, 'evidence_reference': evidence_reference,
        'fidelity': fidelity, 'decision': 'approve_bounded_migration', 'max_continuation_calls': 2,
        'funding': 'one_existing_shared_practice_reservation', 'active_predecessor_remaining_execution_capacity_retained': True,
        'scientific_acceptance': False, 'novali_owns_next_hypothesis': True})
    pointer = workspace.base / 'transition_review.json'
    old = read_json(pointer)
    if old and old.get('review_id') != reviewed['id']:
        raise ValueError('transition_review_already_selected')
    write_json(pointer, {'review_id': reviewed['id']})
    return reviewed


def resolve(workspace, proposed: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any] | None:
    pointer = read_json(workspace.base / 'transition_review.json')
    if not pointer:
        return None
    reviewed = records.read(workspace.root, 'theory_transition_reviews', pointer['review_id'])
    packet = reviewed['basis']
    if packet['proposed_work'] != proposed or packet['snapshot'] != snapshot:
        raise ValueError('reviewed_transition_target_changed')
    for prior in packet['predecessors']:
        if digest(read_json(workspace._path('runs', prior['id']))) != prior['sha256']:
            raise ValueError('reviewed_transition_predecessor_changed')
    existing = read_json(workspace.base / 'transition_admission.json')
    if existing:
        state = read_json(workspace._path('runs', existing['run_id']))
        validate(workspace, state)
        return state['work']
    if any(e.get('transition_review_id') == reviewed['id'] for e in episodes._episodes(workspace.root)):
        raise ValueError('partial_transition_admission_requires_reconciliation_no_new_reservation')
    shared = episodes.policy(workspace.root)
    autonomy = read_json(workspace.root / 'autonomy/status.json')
    if not shared.get('enabled') or not autonomy.get('active') or autonomy.get('emergency_stop'):
        raise ValueError('transition_shared_controls_blocked')
    now, earliest = episodes.admission_window(workspace.root, shared)
    if now < earliest:
        raise ValueError('transition_waiting_for_shared_window:' + str(earliest))
    retained = packet['retained_usage']
    if any(packet['remaining_execution_capacity'][k] <= 0 for k in ('tool_calls', 'compute_seconds', 'evaluations')):
        raise ValueError('transition_has_no_retained_execution_capacity')
    episode = records.store(workspace.root, 'learning_episodes', {
        'family': 'theory_transition', 'failure_id': reviewed['id'], 'failure_key': digest(packet),
        'transition_review_id': reviewed['id'], 'policy_id': shared['id'], 'admitted_at': now,
        'implementation': records.implementation(), 'reserved': {k: shared['limits']['episode_' + k]
            for k in ('model_calls', 'tool_calls', 'compute_seconds')},
        'validation_reserved_before_provider': True, 'scientific_allowance_added': 0,
        'funding': 'shared_calls_transferred_to_existing_scientific_cost_lineage'})
    work = {**proposed, 'run_id': 'theory-run-' + digest([reviewed['id'], episode['id']])[:24],
            'limits': continuation_limits(packet, episode),
            'transition_review_id': reviewed['id'], 'learning_episode_id': episode['id']}
    state = {'id': work['run_id'], 'work': work, 'state': 'ready', 'usage': copy.deepcopy(retained),
             'transition_review_id': reviewed['id'], 'observations': [], 'commands_seen': prior_commands(workspace, reviewed),
             'feedback': 'Evaluator migration approved. Prior failures and all costs remain. Choose your own next falsifiable hypothesis/test using the installed instruments and verified historical evidence.',
             'grants_execution_authority': False}
    # Persist the reservation before the executable pointer. Partial admission
    # never dispatches and cannot be retried for free on a fresh window.
    write_json(workspace._path('runs', work['run_id']), state)
    write_json(workspace.base / 'transition_admission.json', {'run_id': work['run_id'], 'episode_id': episode['id'], 'review_id': reviewed['id']})
    settle(workspace, state)
    return work



def continuation_limits(packet: dict[str, Any], episode: dict[str, Any]) -> dict[str, Any]:
    retained = packet['retained_usage']; available = packet['remaining_execution_capacity']
    return {'model_calls': retained['model_calls'] + min(2, episode['reserved']['model_calls']),
            **{k: retained[k] + min(available[k], episode['reserved'].get(k, available[k]))
               for k in ('tool_calls', 'compute_seconds', 'evaluations')}}


def validate(workspace, state: dict[str, Any]) -> dict[str, Any]:
    reviewed = records.read(workspace.root, 'theory_transition_reviews', state['transition_review_id'])
    packet = reviewed['basis']; work = state['work']
    episode = records.read(workspace.root, 'learning_episodes', work['learning_episode_id'])
    if episode.get('transition_review_id') != reviewed['id'] or work['snapshot_id'] != packet['snapshot']['snapshot_id']:
        raise ValueError('transition_reservation_binding_changed')
    expected = {**packet['proposed_work'], 'run_id': 'theory-run-' + digest([reviewed['id'], episode['id']])[:24],
                'limits': continuation_limits(packet, episode),
                'transition_review_id': reviewed['id'], 'learning_episode_id': episode['id']}
    if work != expected or any(state['usage'][k] < v for k, v in packet['retained_usage'].items()):
        raise ValueError('transition_cost_or_contract_changed')
    for prior in packet['predecessors']:
        if digest(read_json(workspace._path('runs', prior['id']))) != prior['sha256']:
            raise ValueError('transition_historical_state_changed')
    return reviewed


def historical_states(workspace, state: dict[str, Any]) -> list[dict[str, Any]]:
    if not state.get('transition_review_id'):
        return []
    reviewed = validate(workspace, state)
    return [read_json(workspace._path('runs', p['id'])) for p in reviewed['basis']['predecessors']]


def prior_commands(workspace, reviewed: dict[str, Any]) -> list[str]:
    return list(dict.fromkeys(signature for p in reviewed['basis']['predecessors']
        for signature in read_json(workspace._path('runs', p['id'])).get('commands_seen', [])))


def restore_read_history(workspace, state: dict[str, Any]) -> dict[str, Any]:
    """Restore replay guards once, without refunding previously charged reads."""
    reviewed = validate(workspace, state)
    merged = list(dict.fromkeys([*prior_commands(workspace, reviewed), *state['commands_seen']]))
    if merged != state['commands_seen']:
        audit = records.store(workspace.root, 'theory_transition_audits', {
            'run_id': state['id'], 'review_id': reviewed['id'], 'operation': 'restore_verified_predecessor_command_history',
            'before_sha256': digest(state['commands_seen']), 'after_sha256': digest(merged),
            'retained_usage': state['usage'], 'refunds': 0, 'new_calls': 0,
            'scope': 'prior_reads_are_cached_not_new_acquisitions'})
        state.update(commands_seen=merged, history_restoration_id=audit['id'])
        write_json(workspace._path('runs', state['id']), state)
    return state


def settle(workspace, state: dict[str, Any]) -> None:
    reviewed = validate(workspace, state)
    work = state['work']; eid = work['learning_episode_id']
    episode = records.read(workspace.root, 'learning_episodes', eid)
    before = reviewed['basis']['retained_usage']
    usage = {k: round(state['usage'][k] - before[k], 4) if k == 'compute_seconds' else state['usage'][k] - before[k]
             for k in episode['reserved']}
    path = workspace.root / 'research_methods/episode_accounts' / (eid + '.json')
    previous = read_json(path)
    if any(usage[k] < v for k, v in previous.get('usage', {}).items()):
        raise ValueError('transition_shared_account_rollback')
    account = {'usage': usage, 'inflight': copy.deepcopy(state.get('inflight')), 'limits': episode['reserved'],
               'accounting_scope': 'subset_of_cumulative_theory_usage_do_not_add_twice', 'run_id': work['run_id']}
    write_json(path, account)
    write_json(workspace.root / 'research_methods/episode_tasks' / (eid + '.json'), {
        'learning_episode_id': eid, 'failure_id': reviewed['id'], 'state': 'owned_by_theory_scheduler',
        'model_calls': usage['model_calls'], 'attempt_ids': [], 'feedback': {'theory_state': state['state'], 'reason': state.get('feedback', '')}})


def advance(workspace, state: dict[str, Any], policy, execute, *, action_budget=None):
    reviewed = validate(workspace, state)
    shared = episodes.policy(workspace.root)
    episode = records.read(workspace.root, 'learning_episodes', state['work']['learning_episode_id'])
    autonomy = read_json(workspace.root / 'autonomy/status.json')
    if not policy.enabled or not shared.get('enabled') or shared['id'] != episode['policy_id'] or not autonomy.get('active') or autonomy.get('emergency_stop'):
        raise ValueError('transition_execution_controls_blocked')
    state = restore_read_history(workspace, state)
    from .action_budget import ActionBudget
    remaining = min(state['work']['limits']['compute_seconds'] - state['usage']['compute_seconds'],
                    episode['reserved']['compute_seconds'] - (state['usage']['compute_seconds'] - reviewed['basis']['retained_usage']['compute_seconds']))
    if remaining <= 1:
        state.update(state='waiting_for_changed_input', feedback='transition_compute_budget_exhausted')
        write_json(workspace._path('runs', state['id']), state); settle(workspace, state)
        return state
    budget = ActionBudget(min(remaining, action_budget.remaining() if action_budget else policy.model_timeout_seconds))
    try:
        return execute(budget)
    finally:
        settle(workspace, read_json(workspace._path('runs', state['id'])))
