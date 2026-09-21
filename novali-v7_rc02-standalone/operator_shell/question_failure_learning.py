"""Independent review of spent authoring failures; no episode reset or free calls."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from . import research_procedures as records
from .research_tools import digest, read_json


def basis(root: Path, episode_id: str) -> dict[str, Any]:
    episode = records.read(root, 'learning_episodes', episode_id)
    task = read_json(root/'research_methods/episode_tasks'/(episode_id+'.json'))
    account = read_json(root/'research_methods/episode_accounts'/(episode_id+'.json'))
    rejected_review=None
    if task.get('question_id'):
        pointer=read_json(root/'research_methods/successor_review_latest'/(task['question_id']+'.json'))
        if pointer:
            reviewed=records.read(root,'successor_reviews',pointer['review_id'])
            if reviewed['decision']=='reject' and reviewed.get('findings'):rejected_review=reviewed
    if (episode.get('family') != 'successor_question' or task.get('state') != 'exhausted_no_candidate' and not rejected_review
            or task.get('question_id') and not rejected_review or not task.get('attempt_ids') or account.get('inflight')
            or not task.get('selected_source_id')):
        raise ValueError('settled_selected_question_failure_required')
    source = next(r for r in episode['frozen_question_choices'] if r['id']==task['selected_source_id'])
    if source.get('failure_followup'): raise ValueError('question_failure_lineage_limit')
    attempts = [records.read(root, 'attempts', aid) for aid in task['attempt_ids']]
    if not rejected_review and not any(a.get('feedback', {}).get('field_issues') for a in attempts):
        raise ValueError('independent_actionable_question_findings_required')
    return {'episode_id': episode_id, 'task_sha256': digest(task), 'source': source,
            'previous_attempt_id':attempts[-1]['id'],
            'attempt_hashes': {a['id']: digest(a) for a in attempts},
            'previous_proposal': attempts[-1].get('response'),
            'findings': rejected_review['findings'] if rejected_review else task.get('feedback', {}).get('field_issues', []),
            **({'rejection_review_sha256':digest(rejected_review)} if rejected_review else {}),
            'phase_measurements': [a.get('provider_metadata', {}) for a in attempts],
            'usage_retained': account['usage']}


def review(root: Path, episode_id: str, *, reviewer: str, evidence_reference: str,
           repair_kind: str, repair_evidence: str,
           related_evidence_ids: list[str] | None = None,
           findings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    from . import next_practice as questions
    from .directive_obligations import assert_current
    from .lesson_review_budget import charge
    configured = questions.policy(root)
    if not configured.get('failure_followups_enabled'): raise ValueError('question_failure_followup_policy_required')
    if repair_kind not in {'interface_repair', 'changed_method'} or any(
            not isinstance(v, str) or not 16 <= len(v) <= 1600 for v in (reviewer, evidence_reference, repair_evidence)):
        raise ValueError('independent_question_repair_review_required')
    if any(records.read(root, 'question_failure_reviews', p.stem)['basis']['episode_id']==episode_id
           for p in (root/'research_methods/question_failure_reviews').glob('*.json')):
        raise ValueError('question_failure_already_reviewed')
    frozen = basis(root, episode_id)
    if findings is not None:
        from .question_focus import validate_review_findings
        validate_review_findings(findings)
    available = {r['id'] for r in frozen['source']['reviewed_failures']}
    selected = sorted(available) if related_evidence_ids is None else related_evidence_ids
    if (not isinstance(selected, list) or any(not isinstance(i,str) for i in selected)
            or len(set(selected)) != len(selected) or not set(selected) <= available
            or available and not selected):
        raise ValueError('existing_distinct_related_failure_evidence_required')
    assert_current(root, frozen['source']['frozen'])
    body = {
            'basis': frozen, 'reviewer': reviewer, 'evidence_reference': evidence_reference,
            **({'reviewed_findings':copy.deepcopy(findings)} if findings is not None else {}),
            'repair_kind': repair_kind, 'repair_evidence': repair_evidence,
            'related_evidence_ids': sorted(selected),
            'policy_id': configured['id'], 'implementation': records.implementation(),
            'decision': 'permit_one_changed_followup', 'scientific_allowance_added': 0,
            'funding': 'new_episode_from_existing_shared_limits', 'maximum_followups': 1}
    if configured.get('focus_contract'):
        # Actual stored IDs have this fixed width. Review prose stays in the immutable record.
        projected=followup_source({**body,'id':'question_failure_review-'+'x'*24},frozen)
        if not questions.authoring_menu([projected],configured):
            raise ValueError('reviewed_followup_requires_both_stage_capacity')
    with charge(root, records.read(root, 'learning_episodes', episode_id)):
        result=records.store(root,'question_failure_reviews',body)
    return result


def pending(root: Path) -> list[dict[str, Any]]:
    from . import next_practice as questions, learning_episodes as episodes
    from .directive_obligations import assert_current
    configured = questions.policy(root)
    if not configured.get('failure_followups_enabled'): return []
    used = set()
    for episode in episodes._episodes(root):
        for source in episode.get('frozen_question_choices', []):
            if source.get('failure_followup'):
                # A reserved follow-up owns only its specific reviewed source.
                used.add(source['failure_followup']['review_id'])
    result = []
    for p in sorted((root/'research_methods/question_failure_reviews').glob('*.json')):
        review_record = records.read(root, 'question_failure_reviews', p.stem)
        current_review=(review_record['implementation']==records.implementation() and review_record['policy_id']==configured['id'])
        if not current_review:
            current_review=any(r.get('review_id')==review_record['id'] and r.get('basis_sha256')==digest(review_record['basis']) and r.get('implementation')==records.implementation()
                and r.get('policy_id')==configured['id'] for r in
                (records.read(root,'question_failure_revalidations',p.stem)
                 for p in (root/'research_methods/question_failure_revalidations').glob('*.json')))
        if p.stem in used or not current_review: continue
        original = review_record['basis']
        try:
            current = basis(root, original['episode_id'])
            if any(current[k] != original[k] for k in ('task_sha256', 'source', 'attempt_hashes')) or current.get('rejection_review_sha256')!=original.get('rejection_review_sha256'): continue
            assert_current(root, original['source']['frozen'])
        except (ValueError, KeyError, OSError): continue
        source = followup_source(review_record,current)
        result.append(source)
    return result


def revalidate(root: Path, review_id: str, *, reviewer: str, evidence_reference: str) -> dict[str, Any]:
    """Independently recheck an unused grant after repair; never mint a second grant."""
    from . import next_practice as questions, learning_episodes as episodes
    from .directive_obligations import assert_current
    from .lesson_review_budget import charge
    if any(not isinstance(v,str) or not 16<=len(v)<=1600 for v in (reviewer,evidence_reference)):
        raise ValueError('independent_question_repair_review_required')
    reviewed=records.read(root,'question_failure_reviews',review_id);configured=questions.policy(root)
    if not configured.get('enabled') or not configured.get('failure_followups_enabled'):
        raise ValueError('question_failure_followup_policy_required')
    if any(review_id in e.get('failure_followup_review_ids',[]) for e in episodes._episodes(root)):
        raise ValueError('question_failure_followup_already_used')
    original=reviewed['basis'];current=basis(root,original['episode_id'])
    if any(current[k]!=original[k] for k in ('task_sha256','source','attempt_hashes')) or current.get('rejection_review_sha256')!=original.get('rejection_review_sha256'):
        raise ValueError('question_failure_basis_changed')
    assert_current(root,original['source']['frozen'])
    if not questions.authoring_menu([followup_source(reviewed,current)],configured):
        raise ValueError('reviewed_followup_requires_both_stage_capacity')
    implementation=records.implementation()
    for p in (root/'research_methods/question_failure_revalidations').glob('*.json'):
        old=records.read(root,'question_failure_revalidations',p.stem)
        if old['review_id']==review_id and old['implementation']==implementation and old['policy_id']==configured['id']:return old
    with charge(root,records.read(root,'learning_episodes',original['episode_id'])):
        return records.store(root,'question_failure_revalidations',{'review_id':review_id,
            'policy_id':configured['id'],'implementation':implementation,'basis_sha256':digest(original),
            'reviewer':reviewer,'evidence_reference':evidence_reference,'decision':'revalidate_unused_grant',
            'maximum_followups':1,'scientific_allowance_added':0,'new_grants':0})


def check_changed(source: dict[str, Any], response: dict[str, Any]) -> None:
    from .practice_experiments import InvalidExperiment
    reviewed = source['failure_followup']; previous = reviewed.get('previous_proposal') or {}
    keys = ['method_after', 'field_batches'] if reviewed['repair_kind']=='changed_method' else [
        f['path'].lstrip('/') for f in reviewed['field_issues']]
    from .question_focus import value_at
    from .question_quality import cosmetic_only
    changed=lambda k: (not cosmetic_only(value_at(response,'/'+k),value_at(previous,'/'+k)) if reviewed['repair_kind']=='changed_method' else value_at(response,'/'+k)!=value_at(previous,'/'+k))
    if not any(changed(k) for k in keys):
        raise InvalidExperiment([{'path': '/method_after', 'code': 'reviewed_failure_requires_changed_approach',
                                  'guidance': 'Address the independently reviewed failure; unchanged proposals cannot spend another practice window.'}])


def followup_source(review_record: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    original=review_record['basis']
    source = copy.deepcopy(original['source'])
    selected = review_record.get('related_evidence_ids')
    if selected is not None:
        source['reviewed_failures'] = [r for r in source['reviewed_failures'] if r['id'] in selected]
    source['basis_sha256'] = digest([source['basis_sha256'], review_record['id']])
    source['id'] = 'question-source-' + source['basis_sha256'][:24]
    source['failure_followup'] = {
        'review_id': review_record['id'], 'parent_episode_id': original['episode_id'],
        'repair_kind': review_record['repair_kind'], 'repair_evidence': review_record['repair_evidence'],
        'previous_proposal': original['previous_proposal'], 'field_issues': review_record.get('reviewed_findings', original['findings']),
        'retained_costs': current['usage_retained'], 'maximum_followups': 1,
        'phase_measurements': [{'context_utf8_bytes': m.get('context_utf8_bytes'),
            'output_token_limit': m.get('output_token_limit'), 'eval_count': m.get('eval_count'),
            'done_reason': m.get('done_reason'), 'timing': {k:v for k,v in m.get('timing', {}).items()
                if k in ('provider_prompt_seconds','provider_generation_seconds','provider_load_seconds')}}
            for m in original['phase_measurements']]}
    previous=original.get('previous_proposal')
    if previous and previous==current.get('previous_proposal') and current.get('previous_attempt_id') and previous.get('measurement'):
        from .question_measurements import evaluate,feedback_observation
        measured=evaluate(source,previous)
        if measured.get('status')=='refuted':
            source['failure_followup']['measurement_observation']=feedback_observation(measured)
            source['failure_followup']['refutation_origin']={'parent_episode_id':original['episode_id'],
                'review_id':review_record['id'],'original_attempt_id':current['previous_attempt_id'],
                'original_proposal':copy.deepcopy(previous)}
    return source
