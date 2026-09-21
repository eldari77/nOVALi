"""Independent review of failed child attempts, with one changed-method follow-up."""
from __future__ import annotations
import copy
from pathlib import Path
from typing import Any
from . import research_procedures as records
from .research_tools import digest, read_json


def effective_state(root: Path, task: dict[str, Any]) -> str:
    state = task['state']
    if state == 'awaiting_review' and not task.get('candidate_id'):
        episode = records.read(root, 'learning_episodes', task['learning_episode_id'])
        if episode.get('family') == 'child_artifact' and task['model_calls'] >= episode['reserved']['model_calls']:
            return 'exhausted_no_candidate'
        if task.get('feedback', {}).get('reason') == 'deferred_without_completion_credit': return 'deferred_without_candidate'
    return state


def basis(root: Path, episode_id: str, *, growth: bool | None = None) -> dict[str, Any]:
    from .directive_obligations import assert_current
    from .child_directive_learning import policy
    if growth is None: growth = bool(policy(root).get('growth_enabled'))
    episode = records.read(root, 'learning_episodes', episode_id)
    task = read_json(root/'research_methods/episode_tasks'/(episode_id+'.json'))
    account = read_json(root/'research_methods/episode_accounts'/(episode_id+'.json'))
    if (episode.get('family') != 'child_artifact' or task.get('candidate_id') or account.get('inflight')
            or effective_state(root, task) not in ({'exhausted_no_candidate','deferred_without_candidate'} if growth else {'exhausted_no_candidate'})
            or task['model_calls'] != account['usage']['model_calls']
            or not (0 < task['model_calls'] <= episode['reserved']['model_calls'] if growth else task['model_calls'] == episode['reserved']['model_calls'])):
        raise ValueError('settled_exhausted_child_attempts_without_candidate_required')
    attempts = [records.read(root, 'attempts', aid) for aid in task['attempt_ids']]
    if (len(attempts) != task['model_calls'] or attempts[-1]['usage_after'] != account['usage']
            or any(a['learning_episode_id'] != episode_id for a in attempts)):
        raise ValueError('owned_complete_child_attempt_lineage_required')
    try: assert_current(root, episode['frozen_child_inputs'])
    except ValueError:
        if not growth: raise
        from .child_delivery import assert_reviewed_source_transition
        assert_reviewed_source_transition(root, episode['frozen_child_inputs'])
    last = next((a for a in reversed(attempts) if isinstance(a.get('response'), dict)
                 and (not growth or a['response'].get('intent') == 'revise')), None)
    if growth:
        frozen=episode['frozen_child_inputs']; seed=frozen.get('repair_baseline') or frozen.get('revision_candidate',{}).get('response')
        authored=last['response'] if last else seed
        return {'version':'reviewed_child_failure_v2','episode_id':episode_id,'episode_sha256':digest(episode),
            'task_sha256':digest(task),'account_sha256':digest(account),'attempt_hashes':{a['id']:digest(a) for a in attempts},
            'terminal_state':effective_state(root,task),'baseline_attempt_id':last['id'] if last else None,
            'baseline_kind':'authored_attempt' if last else 'reviewed_seed' if seed else 'no_authored_baseline',
            'baseline_sha256':digest(authored) if authored else None,
            'baseline_candidate_id':frozen.get('revision_candidate',{}).get('id') if not last and seed else None,
            'lineage':episode.get('failure_learning_lineage') or episode.get('revision_root') or episode_id,
            'previous_mode':'route_then_author' if frozen.get('growth_contract') else 'legacy_full_context',
            'previous_implementation':episode.get('implementation'),
            'previous_profile':(last or attempts[-1]).get('context_choice',{}).get('used_profile','full'),
            'retained_usage':account['usage']}
    if not last: raise ValueError('authored_baseline_required_for_field_patch_followup')
    return {'episode_id': episode_id, 'episode_sha256': digest(episode), 'task_sha256': digest(task),
        'account_sha256': digest(account), 'attempt_hashes': {a['id']: digest(a) for a in attempts},
        'baseline_attempt_id': last['id'], 'lineage': episode.get('failure_learning_lineage') or episode.get('revision_root') or episode_id,
        'previous_mode': 'patch' if last.get('submitted_response', {}).get('intent') == 'patch' else 'full_response',
        'previous_profile': last.get('context_choice', {}).get('used_profile', 'full'),
        'retained_usage': account['usage']}


def review(root: Path, episode_id: str, *, reviewer: str, authority_reference: str,
           evidence_reference: str, findings: list[dict[str, Any]], context_profile: str = 'focused') -> dict[str, Any]:
    from .child_directive_learning import policy
    from .child_repairs import VERSION
    if not policy(root).get('repair_interface_enabled') or policy(root).get('max_failure_followups_per_lineage') != 1:
        raise ValueError('explicit_bounded_child_failure_learning_policy_required')
    if not all(isinstance(s, str) and 8 <= len(s.strip()) <= 800 for s in (reviewer, authority_reference, evidence_reference)):
        raise ValueError('independent_repair_evidence_review_required')
    if context_profile not in ('full', 'focused'): raise ValueError('registered_context_profile_required')
    if not isinstance(findings, list) or not 1 <= len(findings) <= 8: raise ValueError('bounded_failure_findings_required')
    for finding in findings:
        from .child_review_findings import validate
        validate(finding)
    proof = basis(root, episode_id)
    if (proof['previous_mode']=='route_then_author' and proof.get('previous_implementation')==records.implementation()
            and proof['previous_profile']==context_profile or proof['previous_mode']=='patch' and proof['previous_profile']==context_profile):
        raise ValueError('substantively_changed_authoring_approach_required')
    from .learning_episodes import _episodes
    if any(e.get('failure_learning_lineage') == proof['lineage'] for e in _episodes(root)):
        raise ValueError('child_failure_followup_lineage_already_spent')
    return records.store(root, 'child_failure_reviews', {'basis': proof, 'reviewer': reviewer,
        'authority_reference': authority_reference, 'evidence_reference': evidence_reference, 'findings': findings,
        'approach': ({'response_mode':'route_then_author','context_profile':context_profile,'contract':'child_growth_v1'}
                     if proof.get('version') else {'response_mode': 'patch', 'context_profile': context_profile, 'contract': VERSION}),
        'implementation': records.implementation(), 'decision': 'allow_one_bounded_learning_followup',
        'scientific_allowance_added': 0, 'candidate_approval_authorized': False})


def pending(root: Path, *, review_id: str | None = None) -> list[dict[str, Any]]:
    from .child_directive_learning import policy
    from .directive_obligations import build
    from .child_contracts import coverage
    from .learning_episodes import _episodes
    from .learning_evidence import context as reviewed_evidence
    if not policy(root).get('repair_interface_enabled'): return []
    spent = {e.get('failure_learning_lineage') for e in _episodes(root)}
    result = []
    for path in sorted((root/'research_methods/child_failure_reviews').glob('*.json')):
        if review_id and path.stem != review_id: continue
        reviewed = records.read(root, 'child_failure_reviews', path.stem); proof = reviewed['basis']
        if proof['lineage'] in spent or reviewed['implementation'] != records.implementation(): continue
        try:
            if basis(root, proof['episode_id'],growth=bool(proof.get('version'))) != proof: continue
            source = records.read(root, 'learning_episodes', proof['episode_id'])
            authored = (records.read(root, 'attempts', proof['baseline_attempt_id'])['response'] if proof['baseline_attempt_id'] else
                source['frozen_child_inputs'].get('repair_baseline') or source['frozen_child_inputs'].get('revision_candidate',{}).get('response'))
            if proof.get('version') and (digest(authored) if authored else None)!=proof['baseline_sha256']: continue
            frozen = build(root, source['frozen_child_inputs']['parent_episode_id'])
        except (ValueError, KeyError, OSError): continue
        for unit in frozen['obligations']:
            offered={o['id'] for o in source['frozen_child_inputs']['obligations'] if o['eligible']}
            unit['eligible'] = bool(unit['eligible'] and (coverage({'response': authored}, unit) if authored else unit['id'] in offered))
        if not any(unit['eligible'] for unit in frozen['obligations']): continue
        for key in ('revision_root', 'revision_review', 'revision_candidate'):
            if source['frozen_child_inputs'].get(key): frozen[key] = copy.deepcopy(source['frozen_child_inputs'][key])
        frozen.update(failure_review=reviewed, failure_learning_lineage=proof['lineage'],
            failure_learning_parent=proof['episode_id'], repair_baseline=authored,
            initial_context_profile=reviewed['approach']['context_profile'], reviewed_failure_patterns=reviewed_evidence(root))
        if proof.get('previous_mode')=='route_then_author':
            profile=reviewed['approach']['context_profile']
            if profile not in frozen.get('permitted_context_profiles',[]):continue
            frozen['permitted_context_profiles']=[profile]
        result.append(frozen)
    return result


def status(root: Path) -> list[dict[str, Any]]:
    from .learning_episodes import _episodes
    episodes = _episodes(root); rows = []
    reviews = [records.read(root, 'child_failure_reviews', p.stem) for p in (root/'research_methods/child_failure_reviews').glob('*.json')]
    spent = {e.get('failure_learning_lineage') for e in episodes}
    for episode in episodes:
        if episode.get('family') != 'child_artifact': continue
        task = read_json(root/'research_methods/episode_tasks'/(episode['id']+'.json'))
        state = effective_state(root, task)
        if state not in {'exhausted_no_candidate','deferred_without_candidate'}: continue
        linked = [r for r in reviews if r['basis']['episode_id'] == episode['id']]
        lineage = episode.get('failure_learning_lineage') or episode.get('revision_root') or episode['id']
        try: basis(root,episode['id']); eligibility='reviewable'
        except (ValueError,KeyError,OSError) as exc: eligibility=str(exc)
        rows.append({'episode_id': episode['id'], 'state': state, 'recorded_state': task['state'],'review_eligibility':eligibility,
            'review_state': 'followup_spent' if lineage in spent else 'reviewed_followup_queued' if linked else 'independent_failure_review_required',
            'review_ids': [r['id'] for r in linked], 'calls_retained': task['model_calls'], 'candidate_available': False})
    return rows
