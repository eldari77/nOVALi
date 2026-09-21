"""One independently reviewed refinement per lineage, under shared spending caps."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any
from . import research_procedures as records
from .research_tools import digest, read_json

VERSION = 'child_refinement_v1'


def basis(root: Path, kind: str, target_id: str) -> dict[str, Any]:
    from . import child_review, child_failure_learning, directive_obligations
    if kind == 'candidate':
        candidate = records.read(root, 'child_candidates', target_id)
        review = child_review.latest(root, target_id)
        findings = review.get('unresolved_findings') or review.get('findings')
        if review.get('decision') not in {'approve', 'revise', 'reject'} or not findings:
            raise ValueError('reviewed_unresolved_child_findings_required')
        frozen = candidate['frozen']
        baseline = candidate['response']
        lineage = candidate.get('revision_root') or candidate['id']
        source = {'candidate_sha256': digest(candidate), 'review_id': review['id'], 'review_sha256': digest(review)}
        scope = 'method_only' if review.get('decision') == 'approve' else 'artifact_and_method'
    elif kind == 'failure':
        proof = child_failure_learning.basis(root, target_id, growth=True)
        episode = records.read(root, 'learning_episodes', target_id)
        frozen = episode['frozen_child_inputs']
        baseline = (records.read(root, 'attempts', proof['baseline_attempt_id'])['response'] if proof['baseline_attempt_id'] else
                    frozen.get('repair_baseline') or frozen.get('revision_candidate', {}).get('response'))
        if not baseline:
            raise ValueError('retained_refinement_baseline_required')
        source = {'failed_attempt_basis': proof}
        lineage = proof['lineage']; scope = 'artifact_and_method'
    else:
        raise ValueError('reviewed_candidate_or_settled_failure_required')
    try:
        directive_obligations.assert_current(root, frozen)
    except ValueError:
        from .child_delivery import assert_reviewed_source_transition
        assert_reviewed_source_transition(root, frozen)
    return {'kind': kind, 'target_id': target_id, 'lineage': lineage, 'scope': scope, **source,
            'parent_episode_id': frozen['parent_episode_id'], 'directive_id': frozen['directive_id'],
            'baseline_sha256': digest(baseline), 'prior_implementation': frozen.get('correction_contract', 'legacy_correction_contract')}


def review(root: Path, kind: str, target_id: str, *, reviewer: str, authority_reference: str,
           evidence_reference: str, changed_approach: str, falsifier: str, findings: list[dict[str, Any]]) -> dict[str, Any]:
    from .child_directive_learning import policy
    from .learning_episodes import _episodes
    from .child_review_findings import validate
    from .child_correction import VERSION as CORRECTION
    configured = policy(root)
    if not configured.get('correction_enabled') or configured.get('max_refinement_episodes_per_lineage') != 1:
        raise ValueError('explicit_bounded_refinement_policy_required')
    for value in (reviewer, authority_reference, evidence_reference, changed_approach, falsifier):
        if not isinstance(value, str) or not 12 <= len(value.strip()) <= 800:
            raise ValueError('specific_independent_refinement_evidence_required')
    if not isinstance(findings, list) or not 1 <= len(findings) <= 8:
        raise ValueError('bounded_refinement_findings_required')
    for finding in findings:
        validate(finding)
    proof = basis(root, kind, target_id)
    if any(e.get('refinement_lineage') == proof['lineage'] for e in _episodes(root)):
        raise ValueError('refinement_lineage_already_spent_costs_retained')
    # Same interface plus prose edits cannot earn another episode. A current
    # correction-contract failure requires a separately reviewed implementation repair.
    if kind == 'failure':
        episode = records.read(root, 'learning_episodes', target_id)
        if proof['prior_implementation'] == CORRECTION and episode.get('implementation') == records.implementation():
            raise ValueError('verified_changed_correction_implementation_required')
    return records.store(root, 'child_refinement_reviews', {'basis': proof, 'reviewer': reviewer,
        'authority_reference': authority_reference, 'evidence_reference': evidence_reference,
        'changed_approach': changed_approach, 'falsifier': falsifier, 'findings': findings,
        'implementation': records.implementation(), 'contract': VERSION,
        'decision': 'allow_one_shared_budget_refinement', 'scientific_allowance_added': 0,
        'artifact_approval_authorized': False, 'method_adoption_authorized': False})


def pending(root: Path, *, review_id: str | None = None) -> list[dict[str, Any]]:
    from .child_directive_learning import policy
    from .learning_episodes import _episodes
    from . import directive_obligations, child_contracts
    from .learning_evidence import context as evidence_context
    configured = policy(root)
    if not configured.get('correction_enabled'):
        return []
    spent = {e.get('refinement_lineage') for e in _episodes(root)}
    result = []; emitted = set()
    for path in sorted((root / 'research_methods/child_refinement_reviews').glob('*.json')):
        if review_id and path.stem != review_id:
            continue
        reviewed = records.read(root, 'child_refinement_reviews', path.stem); proof = reviewed['basis']
        if proof['lineage'] in spent or proof['lineage'] in emitted or reviewed['implementation'] != records.implementation():
            continue
        try:
            if proof != basis(root, proof['kind'], proof['target_id']):
                continue
            if proof['kind'] == 'candidate':
                candidate = records.read(root, 'child_candidates', proof['target_id'])
                baseline = candidate['response']
            else:
                episode = records.read(root, 'learning_episodes', proof['target_id'])
                prior = proof['failed_attempt_basis']
                baseline = (records.read(root, 'attempts', prior['baseline_attempt_id'])['response'] if prior['baseline_attempt_id'] else
                            episode['frozen_child_inputs'].get('repair_baseline') or episode['frozen_child_inputs']['revision_candidate']['response'])
                candidate = episode['frozen_child_inputs'].get('revision_candidate', {})
            frozen = directive_obligations.build(root, proof['parent_episode_id'])
            for unit in frozen['obligations']:
                unit['eligible'] = bool(unit['eligible'] and child_contracts.coverage({'response': baseline}, unit))
            if not any(o['eligible'] for o in frozen['obligations']):
                continue
            frozen.update(refinement_review=reviewed, refinement_lineage=proof['lineage'], refinement_scope=proof['scope'],
                repair_baseline=copy.deepcopy(baseline), revision_root=proof['lineage'],
                permitted_context_profiles=['focused'], initial_context_profile='focused',
                reviewed_failure_patterns=evidence_context(root))
            if candidate:
                frozen['revision_candidate'] = {'id': candidate['id'], 'response': copy.deepcopy(baseline)}
            transitions=frozen.get('verified_addendum_source_transitions',[])
            if transitions:
                frozen['relevant_change']={'sha256':digest(transitions),'classification':'verified_addenda',
                    'artifact_refs':sorted({t['artifact_ref'] for t in transitions}),'domain_evidence_added':False}
            result.append(frozen); emitted.add(proof['lineage'])
        except (ValueError, KeyError, OSError, TypeError):
            continue
    return result


def status(root: Path) -> dict[str, Any]:
    from .learning_episodes import _episodes
    from .child_review import latest
    reviewed_methods = []
    for path in (root / 'research_methods/child_review_latest').glob('*.json'):
        reviewed = latest(root, path.stem)
        if reviewed.get('decision') == 'approve' and reviewed.get('unresolved_findings') and not reviewed.get('method_approved'):
            reviewed_methods.append({'candidate_id': path.stem, 'review_id': reviewed['id'], 'findings': reviewed['unresolved_findings']})
    return {'unresolved_approved_methods': reviewed_methods, 'pending': len(pending(root)),
            'spent_lineages': sorted({e['refinement_lineage'] for e in _episodes(root) if e.get('refinement_lineage')}),
            'scientific_allowance_added': 0}
