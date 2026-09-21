"""Child research practice funded by the existing shared learning episode policy."""
from __future__ import annotations

import copy
import time
from pathlib import Path
from typing import Any

from . import directive_candidates as candidates
from . import directive_obligations as obligations
from . import learning_episodes as episodes
from . import practice_transaction as transaction
from . import research_procedures as records
from .research_tools import digest, identifier, read_json, write_json
from .research_context import sanitize_planner_context


def configure(root: Path, *, directive_ids: list[str], enabled: bool, authority_reference: str, enable_repairs: bool = False, context_profiles: tuple[str, ...] = ('full', 'focused'), enable_research_tools: bool = False, enable_growth: bool = False, enable_correction: bool = False, enable_relevance: bool = False, enable_procedure_execution: bool = False) -> dict[str, Any]:
    if type(enable_procedure_execution) is not bool or enable_procedure_execution and not enable_correction:
        raise ValueError("procedure_execution_requires_correction_policy")
    if type(enable_relevance) is not bool or enable_relevance and not enable_correction:
        raise ValueError('relevance_requires_explicit_correction_policy')
    if type(enable_correction) is not bool or enable_correction and not enable_growth:
        raise ValueError('correction_requires_explicit_growth_policy')
    if type(enable_growth) is not bool or enable_growth and not enable_research_tools:
        raise ValueError('growth_requires_reviewed_research_tools')
    if type(enable_research_tools) is not bool or enable_research_tools and not enable_repairs:
        raise ValueError('research_tools_require_explicit_repair_policy')
    if type(enable_repairs) is not bool or type(enabled) is not bool or not authority_reference.strip() or not 1 <= len(directive_ids) <= 12:
        raise ValueError('explicit_bounded_child_practice_policy_required')
    if not context_profiles or len(set(context_profiles)) != len(context_profiles) or any(p not in ('full', 'focused') for p in context_profiles):
        raise ValueError('bounded_child_context_profiles_required')
    configured = records.store(root, 'child_policies', {'enabled': enabled, 'directive_ids': sorted(set(map(identifier, directive_ids))),
        'authority_reference': authority_reference, 'adapters': list(obligations.ADAPTERS),
        'funding': 'existing_shared_learning_episode_policy', 'max_episodes_per_obligation_input': 1,
        'automatic_candidate_approval': False, 'max_revision_episodes_per_lineage': 1, 'scientific_allowance_added': 0,
        'repair_interface_enabled': enable_repairs, 'max_failure_followups_per_lineage': 1 if enable_repairs else 0,
        'context_profiles': list(context_profiles), **({'research_tools_enabled': True} if enable_research_tools else {}),
        **({'growth_enabled': True} if enable_growth else {}),
        **({'correction_enabled': True, 'max_refinement_episodes_per_lineage': 1} if enable_correction else {}),
        **({'relevance_enabled': True} if enable_relevance else {}),
        **({'procedure_execution_enabled': True} if enable_procedure_execution else {})})
    write_json(root / 'research_methods/child_policy_latest.json', {'policy_id': configured['id']})
    return configured


def policy(root: Path) -> dict[str, Any]:
    pointer = read_json(root / 'research_methods/child_policy_latest.json')
    return records.read(root, 'child_policies', pointer['policy_id']) if pointer else {}


def opportunities(root: Path) -> list[dict[str, Any]]:
    configured = policy(root)
    if not configured.get('enabled'): return []
    found = []
    latest = read_json(root / 'conveyor/research/latest.json')
    for row in latest.get('directives', [])[:12]:
        if row.get('directive_id') not in configured['directive_ids']: continue
        try:
            frozen = current(root, row['episode_id'])
            if any(o['eligible'] for o in frozen['obligations']): found.append(frozen)
        except (ValueError, KeyError, OSError, TypeError): continue
    return sorted(found, key=lambda f: f['directive_id'])


def current(root: Path, episode_id: str) -> dict[str, Any]:
    from .child_review import apply_attempts
    from .learning_evidence import context as evidence_context
    frozen = apply_attempts(root, obligations.build(root, episode_id))
    frozen['reviewed_failure_patterns'] = evidence_context(root)
    from .question_partitions import annotate
    annotate(root, frozen)
    return frozen



def key(frozen: dict[str, Any]) -> str:
    # Policy IDs, implementation hashes, rationale changes and resets of the
    # scheduler cannot mint another attempt at the same child obligation input.
    return digest({'contract': obligations.VERSION, 'directive': frozen['directive_id'],
        'target': frozen['target_artifact'], 'source': frozen['base_sha256'],
        'obligations': frozen['obligations'], 'evidence': frozen['evidence_options'],
        'revision_review_id': frozen.get('revision_review',{}).get('id'),
        **({'successor_review_id': frozen['successor_review']['id']} if frozen.get('successor_review') else {}),
        'failure_review_id': frozen.get('failure_review',{}).get('id'),
        **({'refinement_review_id': frozen['refinement_review']['id']} if frozen.get('refinement_review') else {})})


def admit(root: Path, frozen: dict[str, Any], *, now: float | None = None) -> dict[str, Any]:
    configured = policy(root); shared = episodes.policy(root); autonomy = read_json(root / 'autonomy/status.json')
    if (not configured.get('enabled') or not shared or not shared['enabled'] or not autonomy.get('active')
            or autonomy.get('emergency_stop') or frozen['directive_id'] not in configured['directive_ids']):
        raise ValueError('child_practice_controls_blocked')
    obligations.assert_current(root, frozen)
    obligation_key = key(frozen)
    if any(e.get('child_obligation_key') == obligation_key for e in episodes._episodes(root)):
        raise ValueError('unchanged_child_obligation_already_practiced')
    from .child_review import pending as pending_revisions
    if frozen.get('successor_review'):
        from .next_practice import pending as pending_successors
        if frozen not in pending_successors(root):
            raise ValueError('current_independent_successor_review_required')
    elif frozen.get('refinement_review'):
        from .child_refinement import pending as pending_refinement
        if frozen not in pending_refinement(root, review_id=frozen['refinement_review']['id']):
            raise ValueError('current_independent_refinement_review_required')
    elif frozen.get('failure_review'):
        from .child_failure_learning import pending as pending_failure
        if frozen not in pending_failure(root, review_id=frozen['failure_review']['id']): raise ValueError('current_independent_failure_review_required')
    elif frozen.get('revision_root'):
        if frozen not in pending_revisions(root, candidate_id=frozen['revision_candidate']['id']): raise ValueError('current_independent_revision_review_required')
    elif current(root, frozen['parent_episode_id']) != frozen:
        raise ValueError('current_derived_child_obligations_required')
    # Preparation validates the compact projection and grammar before reserving
    # an episode; no research episode is restarted or reimbursed.
    candidates.planner_contract(obligations.projection(frozen))
    stamp, not_before = episodes.admission_window(root, shared, now=now)
    if stamp < not_before: raise ValueError('shared_learning_window_not_open')
    failure = records.store(root, 'failures', {'failure_family': 'child_artifact', 'parent_id': frozen['parent_episode_id'],
        'parent_contract_sha256': frozen['parent_contract_sha256'], 'failure': 'child_artifact_obligation_practice',
        'failed_command': {}, 'usage_before': frozen['original_research_usage'],
        'implementation': records.implementation(), 'directive_id': frozen['directive_id']})
    episode = records.store(root, 'learning_episodes', {'failure_id': failure['id'], 'failure_key': episodes.failure_key(failure),
        'family': 'child_artifact', 'revision_root': frozen.get('revision_root'),
        **({'successor_review_id': frozen['successor_review']['id'], 'successor_question_id': frozen['successor_review']['question_id']} if frozen.get('successor_review') else {}),
        **({'question_partition_id': frozen['question_partition_id']} if frozen.get('question_partition_id') else {}),
        'failure_learning_lineage': frozen.get('failure_learning_lineage'),
        'failure_learning_parent': frozen.get('failure_learning_parent'),
        **({'refinement_lineage':frozen['refinement_lineage'], 'refinement_review_id':frozen['refinement_review']['id']} if frozen.get('refinement_review') else {}),
        'failure_review_id': frozen.get('failure_review',{}).get('id'),
        'revision_review_id': frozen.get('revision_review',{}).get('id'), 'child_obligation_key': obligation_key, 'child_policy_id': configured['id'],
        'frozen_child_inputs': frozen, 'input_sha256': digest(frozen), 'implementation': records.implementation(),
        'policy_id': shared['id'], 'admitted_at': stamp,
        'reserved': {k: shared['limits']['episode_' + k] for k in ('model_calls', 'tool_calls', 'compute_seconds')},
        'validation_reserved_before_provider': True, 'scientific_allowance_added': 0,
        'admission_basis': 'new_bounded_artifact_adapter_task_not_research_continuation'})
    write_json(root / 'research_methods/episode_tasks' / (episode['id'] + '.json'), {
        'learning_episode_id': episode['id'], 'failure_id': failure['id'], 'state': 'ready', 'model_calls': 0,
        'attempt_ids': [], 'feedback': {}, 'grants_execution_authority': False})
    return episode


def advance(root: Path, task: dict[str, Any], *, planner) -> dict[str, Any]:
    task_path = root / 'research_methods/episode_tasks' / (task['learning_episode_id'] + '.json')
    account_path = root / 'research_methods/episode_accounts' / task_path.name
    if transaction.recover(root, task_path, account_path): task = read_json(task_path)
    old = read_json(account_path)
    if old.get('inflight'):
        # Preparation did not dispatch a call, but its reserved elapsed cost is
        # retained after a crash; a dispatched/uncertain call is never refunded.
        pending = old['inflight']; old['usage']['compute_seconds'] += pending['reserved_seconds']
        task['model_calls'] = old['usage']['model_calls']
        task.update(state='awaiting_review', feedback={'reason': 'interrupted_child_practice_costs_retained'})
        old['inflight'] = None
        receipt = records.store(root, 'episode_interruptions', {'episode_id': task['learning_episode_id'],
            'usage': old['usage'], 'reason': task['feedback']['reason']})
        transaction.commit(root, task_path, account_path, task, old, receipt, kind='episode_interruptions')
        return task
    from . import child_repairs, child_context
    configured = policy(root); autonomy = read_json(root / 'autonomy/status.json')
    episode = records.read(root, 'learning_episodes', task['learning_episode_id'])
    if (not configured.get('enabled') or configured['id'] != episode['child_policy_id']
            or not autonomy.get('active') or autonomy.get('emergency_stop')):
        return {**task, 'control_blocker': 'child_practice_paused'}
    limits, account, account_path, task_path = episodes.practice_budget(root, task)
    if task['state'] == 'waiting_for_preparation_repair':
        if task.get('preparation_failure_key') == transaction.preparation_key(root, task): return task
        task['state'] = 'ready'
    if task['state'] != 'ready': return task
    modern = bool(episode['frozen_child_inputs'].get('repair_contract'))
    from . import child_planning, child_correction
    growth = child_planning.active(episode['frozen_child_inputs'])
    correcting = child_correction.active(episode['frozen_child_inputs'])
    routing = growth and not task.get('route')
    exhausted = 'exhausted_no_candidate' if modern and not task.get('candidate_id') else 'awaiting_review'
    remaining = limits['max_compute_seconds'] - account['usage']['compute_seconds']
    validation_cost = 2 if routing else 10 if episode['frozen_child_inputs'].get('research_tools_contract') else 3
    review_reserve = 2 if episode['frozen_child_inputs'].get('research_tools_contract') else 0
    if (task['model_calls'] >= limits['max_model_calls'] or account['usage']['tool_calls'] + validation_cost + review_reserve > limits['max_tool_calls']
            or remaining <= 21):
        task.update(state=exhausted, feedback={'reason': 'child_practice_budget_exhausted_costs_retained'})
        write_json(task_path, task); return task
    from .action_budget import ActionBudget
    budget = ActionBudget(min(140 if correcting else 55 if routing else 140, remaining), reserve_seconds=20 if correcting else 10 if routing else 20)
    reserved = min(45 if routing else 120, budget.provider_seconds()); dispatched = False; response = None; context = None
    account['inflight'] = {'phase': 'preparing', 'call': task['model_calls'] + 1,
                          'failure_id': task['failure_id'], 'reserved_seconds': reserved}
    write_json(account_path, account)
    submitted = None; expanded = None; choice = {}; used_profile = None; combined = False
    started = time.monotonic(); previous = task.get('previous_response'); previous_hook = getattr(planner, 'dispatch_hook', None)
    try:
        frozen = episode['frozen_child_inputs']
        if digest(frozen) != episode['input_sha256']: raise ValueError('child_frozen_input_integrity_failure')
        obligations.assert_current(root, frozen)
        context = obligations.projection(frozen, feedback=task['feedback'], methods=candidates.methods(root))
        if frozen.get('accepted_practice_question'):
            context['accepted_practice_question'] = frozen['accepted_practice_question']
        context['remaining_model_calls'] = limits['max_model_calls'] - task['model_calls']
        if task.get('correction_review_id'):
            from .child_review import latest as latest_review
            reviewed=latest_review(root,task['reviewed_candidate_id'])
            if reviewed.get('id')!=task['correction_review_id'] or reviewed.get('decision')!='revise':
                raise ValueError('current_correction_review_required')
            context['correction_review']=reviewed
            context['reviewed_candidate_id']=task['reviewed_candidate_id']
        if previous: context['previous_response'] = previous
        if task.get('execution_preview'): context['execution_preview'] = task['execution_preview']
        if task.get('last_failed_submission'): context['previous_submission'] = task['last_failed_submission']
        if modern:
            context = child_repairs.attach(context, frozen)
            retained = [records.read(root, 'attempts', aid) for aid in task['attempt_ids']]
            if not retained and frozen.get('failure_review'):
                retained = [records.read(root, 'attempts', aid) for aid in frozen['failure_review']['basis']['attempt_hashes']]
            used_profile = task.get('context_profile', frozen.get('initial_context_profile', 'full'))
            if growth:
                context['phase_diagnostics'] = child_context.diagnostics(retained)
                if routing:
                    routes = child_planning.route_context(context)
                    forced = child_correction.forced_route(context, routes)
                    bundle = None if forced else child_correction.combined(context, routes)
                    if forced or bundle:
                        if forced: task['route'] = forced
                        routing = False
                        validation_cost = 10; reserved = min(120, budget.provider_seconds())
                        if account['usage']['tool_calls'] + 2 + validation_cost + review_reserve > limits['max_tool_calls']:
                            raise ValueError('reserve_forced_route_validation_and_review')
                        account['usage']['tool_calls'] += 2
                        account['inflight']['reserved_seconds'] = reserved
                        write_json(account_path, account)
                        if forced:
                            used_profile = forced['profile']
                            context = child_planning.project(context, forced['obligation_id'], used_profile, forced.get('evidence_source_id'))
                            choice['forced_route'] = forced
                        else:
                            context = bundle; combined = True
                    else: context = routes
                else:
                    route = task['route'];used_profile=route['profile']
                    context = child_planning.project(context,route['obligation_id'],used_profile,route.get('evidence_source_id'))
            else:
                context = child_context.prepare(context, profile=used_profile, attempts=retained,
                    permitted=tuple(frozen.get('permitted_context_profiles', child_context.PROFILES)))
        context['provider_time_budget_seconds'] = min(reserved, budget.provider_seconds())
        phase = 'child_bundle' if combined else 'child_route' if routing else 'child_method'
        if routing: child_planning.route_contract(context)
        elif not combined: candidates.planner_contract(context)
        if hasattr(planner, 'preflight'): planner.preflight(phase, context)

        def dispatch():
            nonlocal dispatched
            budget.require('provider_dispatch')
            if dispatched: raise ValueError('child_provider_double_dispatch')
            account['usage']['model_calls'] += 1; task['model_calls'] += 1
            account['inflight']['phase'] = 'dispatched'; write_json(account_path, account)
            dispatched = True

        if getattr(planner, 'supports_dispatch_hook', False): planner.dispatch_hook = dispatch
        else: dispatch()
        submitted = planner(phase, context)
        if not dispatched: raise ValueError('child_provider_dispatch_not_recorded')
        budget.require('independent_validation')
        account['usage']['tool_calls'] += validation_cost; write_json(account_path, account)
        if combined:
            if not isinstance(submitted,dict) or set(submitted)!={'route_id','response'} or submitted['route_id'] not in context['bundle_contexts']:
                raise ValueError('one_current_combined_route_response_required')
            selected = submitted['route_id']
            task['route'] = {**next(r for r in context['bundle_routes'] if r['id']==selected),
                'selection':'combined_selection_and_authoring','completion_credit':False}
            choice['combined_route'] = task['route']; used_profile = task['route']['profile']
            context = context['bundle_contexts'][selected]; submitted = submitted['response']
        if routing:
            task['route'] = child_planning.accept_route(context,submitted)
            choice = {'route':task['route'],'context_profile':task['route']['profile'],'completion_credit':False}
        else:
            from . import child_execution
            expanded, execution_choice = child_execution.prepare(context, submitted)
            prepared, correction_choice = child_correction.prepare_response(context, expanded)
            choice.update(execution_choice)
            response, normalized_choice = child_repairs.normalize(context, prepared)
            choice.update(normalized_choice); choice.update(correction_choice)
            if correction_choice:
                context.update(correction_choice)
        if choice.get('measurement_capability_request'):
            request=records.store(root,'requests',{'kind':'child_measurement_capability_request','learning_episode_id':episode['id'],
                'failure_id':task['failure_id'],'proposal':choice['measurement_capability_request'],'requires_operator_review':True,
                'requested_research_calls':0,'scientific_allowance_added':0})
            task['request_id']=request['id']
        choice['used_profile'] = used_profile
        if modern: task['context_profile'] = choice['context_profile']
        if choice.get('execution_preview'):
            candidates.assess(frozen, context, response)
            choice['execution_preview']['response_sha256'] = digest(response)
            task['execution_preview'] = choice['execution_preview']
            task['feedback'] = {'reason':'procedure_output_ready_for_inspection', 'field_issues':[],
                'execution_preview':choice['execution_preview'], 'completion_credit':False}
        elif response is None:
            task['feedback'] = {'reason': 'bounded_route_selected_no_completion_credit' if routing else 'measured_context_choice_no_completion_credit', 'context_trial': choice,
                **child_repairs.feedback(context, previous, None, [])}
        else:
            result = candidates.assess(frozen, context, response)
            task['feedback'] = {'reason': 'deferred_without_completion_credit' if result['deferred'] else 'candidate_requires_independent_review',
                **child_repairs.feedback(context, previous, response, [])}
            if result.get('method_assessment'): task['feedback']['method_assessment'] = result['method_assessment']
            if choice.get('deferral_review'): task['feedback']['deferral_review'] = choice['deferral_review']
            task['state'] = 'deferred_without_candidate' if modern and result['deferred'] else 'awaiting_review'
            method_failed = bool(result.get('method_assessment', {}).get('field_issues'))
            can_correct = (correcting and method_failed and task['model_calls'] < limits['max_model_calls']
                and account['usage']['tool_calls'] + 10 + review_reserve <= limits['max_tool_calls'])
            if can_correct:
                task.update(state='ready', feedback={**task['feedback'], 'reason':'method_correction_available_artifact_preserved',
                    'field_issues':child_correction.method_issues(response.get('method')), 'artifact_check_passed':True})
            elif not result['deferred']:
                candidate = candidates.propose(root, frozen, context, response, episode_id=episode['id'])
                request = records.store(root, 'requests', {'kind': 'child_artifact_revision_review', 'candidate_id': candidate['id'],
                    'failure_id': task['failure_id'], 'learning_episode_id': episode['id'], 'requires_operator_review': True,
                    'scope': 'isolated_draft_structure_only', 'requested_research_calls': 0})
                task.update(candidate_id=candidate['id'], request_id=request['id'])
        task.pop('last_failed_submission',None)
    except (ValueError, TypeError, KeyError, OSError, TimeoutError) as exc:
        from .child_execution import active as execution_active
        if (execution_active(context or {}) and not routing and isinstance(submitted,dict)
                and submitted.get('obligation_id') and response is None):
            task['last_failed_submission'] = copy.deepcopy(expanded if isinstance(expanded,dict) else submitted)
        task['feedback'] = {'reason': str(exc)[:1000],
            **child_repairs.feedback(context or {}, previous, response, getattr(exc, 'field_issues', []))}
        if correcting and isinstance(context, dict):
            task['feedback']['binding_comparison'] = child_correction.inspect_binding(context, submitted)
            extra = child_correction.method_issues((submitted or {}).get('method_plan', (submitted or {}).get('method'))) if isinstance(submitted,dict) else []
            task['feedback']['unresolved_method_issues'] = extra
        if not dispatched:
            task.update(state='waiting_for_preparation_repair', preparation_failure_key=transaction.preparation_key(root, task))
        elif task['model_calls'] >= limits['max_model_calls']:
            task['state'] = exhausted
    finally:
        if getattr(planner, 'supports_dispatch_hook', False): planner.dispatch_hook = previous_hook
        elapsed = time.monotonic() - started
        metadata = getattr(planner, 'last_metadata', {}) if dispatched else {}
        from .child_failure_patterns import classify, measurements
        patterns = classify(task['feedback'], metadata, dispatched=dispatched)
        if patterns:
            task['feedback']['failure_mechanisms'] = patterns
            task['feedback']['cost_diagnostics'] = measurements(metadata, dispatched=dispatched)
        uncertain = dispatched and metadata.get('provider_outcome') == 'unknown'
        charged = max(elapsed, reserved) if uncertain else elapsed
        account['usage']['compute_seconds'] = round(account['usage']['compute_seconds'] + charged, 4)
        account['inflight'] = None
        if response is not None: task['previous_response'] = response
        kind = 'attempts' if dispatched else 'preparation_attempts'
        receipt = records.store(root, kind, {'failure_id': task['failure_id'], 'learning_episode_id': episode['id'],
            'call': task['model_calls'], 'response': response, 'submitted_response': submitted, 'context_choice': choice,
            'outcome': task['feedback'], 'provider_metadata': metadata,
            'compute_seconds': elapsed, 'compute_seconds_charged': charged, 'provider_outcome_uncertain': uncertain,
            'provider_dispatched': dispatched, 'usage_after': copy.deepcopy(account['usage']),
            'original_research_usage': episode['frozen_child_inputs']['original_research_usage'],
            **({'raw_response_excerpt':sanitize_planner_context(getattr(planner,'last_raw_response','')[:2000]),
                'raw_response_sha256':digest(getattr(planner,'last_raw_response','')),
                'route_phase':routing} if growth else {})})
        if dispatched: task['attempt_ids'].append(receipt['id'])
        transaction.commit(root, task_path, account_path, task, account, receipt, kind=kind)
    return task


def admit_next(root: Path) -> dict[str, Any] | None:
    # A closed shared window needs no child artifact scan or repeated evaluator
    # preparation. Admission still rechecks the reservation atomically below.
    configured = episodes.policy(root)
    if not policy(root).get('enabled') or not configured or not configured['enabled']: return None
    try:
        now, earliest = episodes.admission_window(root, configured)
        if now < earliest: return None
    except ValueError: return None
    from .child_review import pending as pending_revisions
    from .child_failure_learning import pending as pending_failure
    from .child_refinement import pending as pending_refinement
    from .next_practice import pending as pending_successors
    revised = pending_successors(root) or pending_refinement(root) or pending_failure(root) or pending_revisions(root, limit=1)
    for frozen in revised or opportunities(root):
        try:
            episode = admit(root, frozen)
            return read_json(root / 'research_methods/episode_tasks' / (episode['id'] + '.json'))
        except (ValueError, KeyError, OSError, TypeError): continue
    return None


def status(root: Path) -> dict[str, Any]:
    configured = policy(root); shared = episodes.policy(root); rows = []
    admitted = {e.get('child_obligation_key') for e in episodes._episodes(root)}
    latest = read_json(root / 'conveyor/research/latest.json')
    for source in latest.get('directives', []):
        if source.get('directive_id') not in configured.get('directive_ids', []): continue
        try: frozen = current(root, source['episode_id'])
        except (ValueError, KeyError, OSError) as exc:
            rows.append({'directive_id': source['directive_id'], 'preparation_blocker': str(exc)}); continue
        rows.append({'directive_id': frozen['directive_id'], 'parent_episode_id': frozen['parent_episode_id'],
                     'obligations': frozen['obligations'], 'already_practiced': key(frozen) in admitted,
                     'cached_evidence_handles': len(frozen['evidence_options'])})
    try:
        now, earliest = episodes.admission_window(root, shared) if shared else (0, 0)
        forecast = {'state': 'eligible' if earliest <= now else 'waiting_for_shared_window', 'not_before': earliest}
    except ValueError as exc: forecast = {'state': 'blocked', 'reason': str(exc)}
    from .child_review import queue, pending
    from .child_failure_learning import status as failure_status
    from .child_refinement import status as refinement_status
    return {'policy': configured, 'shared_admission': forecast, 'directives': rows,
            'review_queue': queue(root), 'pending_bounded_corrections': len(pending(root)),
            'failed_corrections': failure_status(root), 'refinement':refinement_status(root),
            'method_memory_count': len(candidates.methods(root)), 'scientific_allowance_added': 0}
