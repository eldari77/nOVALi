"""Frozen, actionable child research obligations and bounded evidence projections.

These are preparation inputs, not new research observations or completion credit.
The original support gaps and scientific episode are never rewritten.
"""
from __future__ import annotations

import hashlib
import json
import re
import copy
from pathlib import Path
from typing import Any

from . import research_learning as learning
from .research_tools import artifact_inventory, artifact_path, digest, identifier, read_json

VERSION = 'child_obligations_v1'
ADAPTERS = ('evidence_binding', 'record_extraction', 'interface_contract')


def content(root: Path, directive_id: str, reference: str) -> bytes:
    path = artifact_path(root, directive_id, reference)
    if not path.is_file() or path.stat().st_size > 64000:
        raise ValueError('bounded_existing_artifact_required')
    return path.read_bytes()


def _records(data: Any) -> list[dict[str, Any]]:
    """Expose a bounded supplied table, with stable JSON locations, not guessed entities."""
    rows = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key == 'novali_research_addenda':
                continue
            if isinstance(value, list):
                for index, item in enumerate(value[:4]):
                    if isinstance(item, dict):
                        rows.append({'row_id': '/' + key.replace('~', '~0').replace('/', '~1') + '/' + str(index),
                                     'record': item})
                if rows:
                    break
    return rows[:4]


def build(root: Path, episode_id: str) -> dict[str, Any]:
    directory = root / 'conveyor/research/episodes' / identifier(episode_id)
    contract = read_json(directory / 'contract.json'); state = read_json(directory / 'state.json')
    task = contract.get('task', {})
    if not state or digest(contract) != state.get('contract_sha256'):
        raise ValueError('child_parent_contract_integrity_failure')
    if not task.get('directive_id') or not state.get('state', '').startswith('waiting_'):
        raise ValueError('settled_child_research_parent_required')
    did = identifier(task['directive_id']); inventory = artifact_inventory(root, did)
    target = 'drafts/' + str(task['target_artifact'])
    raw = content(root, did, target); revision = hashlib.sha256(raw).hexdigest()
    if target.endswith('.json'):
        substantive = json.loads(raw)
        if isinstance(substantive, dict): substantive.pop('novali_research_addenda', None)
    else:
        substantive = re.sub(r'\n*<!-- novali-research:([A-Za-z0-9_-]+) -->.*?<!-- /novali-research:\1 -->\n*',
                             '', raw.decode('utf-8'), flags=re.S).strip()
    observations = list(state.get('observations', []))
    for older, old_task in learning.experiences(root):
        if old_task.get('directive_id') == did:
            observations.extend(older.get('observations', []))
    # Only current local artifact observations can be rebound without acquiring
    # evidence. External source freshness still belongs to the research runtime.
    cached = {}; dependencies = {target: revision}; source_transitions=[]
    for row in observations:
        result = row.get('result', {}); ref = result.get('artifact_ref')
        current_sha=inventory.get(ref,{}).get('sha256'); source_current=current_sha==result.get('sha256')
        if row.get('ok') and ref and current_sha and not source_current:
            from .child_directive_learning import policy
            if policy(root).get('growth_enabled'):
                from .child_delivery import assert_reviewed_source_transition
                try:
                    assert_reviewed_source_transition(root,{'parent_episode_id':episode_id,'parent_contract_sha256':digest(contract),
                        'directive_id':did,'dependencies':{ref:result.get('sha256')}})
                    source_current=True
                    transition={'artifact_ref':ref,'observation_sha256':result['sha256'],'current_artifact_sha256':current_sha,
                        'scope':'historical_observation_before_verified_addenda_not_a_new_measurement'}
                    if transition not in source_transitions:source_transitions.append(transition)
                except (ValueError,KeyError,OSError):pass
        if row.get('ok') and ref and source_current:
            learning.evidence_options([row])
            cached[digest(row)] = row; dependencies[ref] = current_sha
    evidence = learning.evidence_options(list(cached.values())[:12])[:12]
    rejected = state.get('last_rejected_response', {})
    repair_feedback = {'reason': state.get('feedback', ''), 'field_issues': [], 'rejected_claims': []}
    if isinstance(rejected, dict) and isinstance(rejected.get('claims'), list):
        repair_feedback['rejected_claims'] = [{k: v for k, v in claim.items()
            if k in ('kind', 'text', 'quote', 'evidence_refs', 'evidence_handle')}
            for claim in rejected['claims'][:2] if isinstance(claim, dict)]
        if state.get('plan'):
            from .research_episodes import verify_result
            try: verify_result(state['plan'], state.get('observations', []), copy.deepcopy(rejected))
            except (ValueError, KeyError, TypeError) as exc:
                repair_feedback['field_issues'] = getattr(exc, 'field_issues', [])[:8]
    if len(json.dumps(repair_feedback).encode()) > 6000:
        repair_feedback = {'reason': state.get('feedback', '')[:600], 'field_issues': repair_feedback['field_issues'][:4],
                           'rejected_claims_omitted': 'bounded_context_use_precise_field_feedback_and_cached_handles'}
    all_required = list(dict.fromkeys(str(f) for r in task.get('requested_rows', [])
                                     for f in r.get('required_fields', []) if isinstance(f, str)))
    required = all_required[:12]
    try:
        table = _records(json.loads(raw)) if target.endswith('.json') else []
    except (ValueError, TypeError):
        table = []
    # Actual supplied values stay bounded. Oversize records cannot masquerade as
    # missing values after prompt compression.
    if len(json.dumps(table).encode()) > 10000:
        table = []
    obligations = []

    def add(adapter: str, objective: str, required_evidence: list[str], eligible: bool) -> None:
        body = {'directive_id': did, 'adapter': adapter, 'target_artifact': target,
                'target_slot': 'novali_research_addenda', 'objective': objective,
                'required_evidence': required_evidence, 'dependencies': sorted(dependencies),
                'completion_check': adapter + '_v1_then_independent_review_and_downstream_consumption',
                'completion_scope': 'artifact_structure_only', 'eligible': eligible,
                'blocked_reason': '' if eligible else 'matching_supplied_evidence_unavailable',
                'parent_gaps': task.get('gaps', []), 'source_revision': revision}
        obligations.append({'id': 'obligation-' + digest({k: v for k, v in body.items()
            if k not in ('source_revision', 'eligible', 'blocked_reason')})[:24], **body})

    if table and required:
        add('record_extraction', 'Extract the requested supplied-record fields and retain absent or unresolved values.',
            ['current_target_records', 'requested_field_names'], True)
    if target.endswith('.md'):
        add('interface_contract', 'Propose one named module handoff with a measurable check and explicit unresolved assumptions.',
            ['current_artifact_excerpt', 'existing_artifact_references'], True)
    add('evidence_binding', 'Repair one traceable observation using a cached literal evidence handle.',
        ['current_cached_artifact_observation'], bool(evidence))
    # These dependencies deliberately have no executable adapter: structural
    # practice cannot close sourcing, causal claims, or operator approval.
    for gap in task.get('gaps', []):
        obligations.append({'id': 'gap-' + digest([did, gap])[:24], 'adapter': None,
            'target_artifact': target, 'target_slot': None, 'objective': gap.get('action', ''),
            'required_evidence': gap.get('fields', []), 'dependencies': [], 'eligible': False,
            'blocked_reason': 'existing_support_or_scientific_evaluator_required',
            'completion_check': 'existing_support_acceptance_and_operator_review', 'parent_gap': gap})
    frozen = {'version': VERSION, 'directive_id': did, 'parent_episode_id': episode_id,
        'parent_contract_sha256': digest(contract), 'original_research_usage': state.get('usage', {}),
        'directive_scope': task.get('directive_text', '')[:6500], 'target_artifact': target,
        'base_sha256': revision, 'dependencies': dependencies, 'obligations': obligations,
        'substantive_source_sha256': digest(substantive),
        'evidence_options': evidence, 'cached_retrieval': True, 'new_acquisitions': 0,
        'prior_research_feedback': repair_feedback,
        'records': table, 'required_fields': required, 'unprojected_required_fields': all_required[12:],
        'artifact_excerpt': raw.decode('utf-8')[:7000],
        'artifact_refs': sorted(inventory), 'scientific_allowance_added': 0}
    if source_transitions:frozen['verified_addendum_source_transitions']=source_transitions
    from .child_contracts import refine
    return refine(root, frozen)


def assert_current(root: Path, frozen: dict[str, Any]) -> None:
    directory = root / 'conveyor/research/episodes' / identifier(frozen['parent_episode_id'])
    if digest(read_json(directory / 'contract.json')) != frozen['parent_contract_sha256']:
        raise ValueError('child_parent_contract_changed')
    for ref, sha in frozen['dependencies'].items():
        if hashlib.sha256(content(root, frozen['directive_id'], ref)).hexdigest() != sha:
            raise ValueError('child_dependency_changed:' + ref)


def projection(frozen: dict[str, Any], *, feedback=None, methods=None) -> dict[str, Any]:
    """The same projection supplies both grammar and prompt; no evidence rebinding."""
    selected = {k: frozen[k] for k in ('directive_id', 'target_artifact', 'base_sha256',
                'evidence_options', 'records', 'required_fields', 'unprojected_required_fields', 'artifact_refs', 'prior_research_feedback')}
    selected['directive_scope'] = frozen['directive_scope'][:3000]
    selected['artifact_excerpt'] = frozen['artifact_excerpt'][:3000]
    selected['obligations'] = [{k: v for k, v in o.items() if k not in ('parent_gaps', 'parent_gap')}
                               for o in frozen['obligations']]
    selected.update(feedback=feedback or {}, methods=methods or [], remaining_model_calls=2,
                    authority='propose_bounded_draft_addendum_only')
    if frozen.get('work_contract'):
        from .child_contracts import project
        selected = project(frozen, selected)
    from .child_repairs import attach
    selected = attach(selected, frozen)
    from .child_research_actions import attach as research_attach
    selected = research_attach(selected, frozen)
    if frozen.get('growth_contract'):selected['growth_contract']=frozen['growth_contract']
    if frozen.get('procedure_execution_contract'):selected['procedure_execution_contract']=frozen['procedure_execution_contract']
    if frozen.get('relevance_contract'):selected['relevance_contract']=frozen['relevance_contract']
    if frozen.get('correction_contract'):
        selected['correction_contract']=frozen['correction_contract']
        selected['permitted_context_profiles']=list(frozen.get('permitted_context_profiles',['focused']))
        if frozen.get('relevant_change'):selected['relevant_change']=frozen['relevant_change']
    if frozen.get('verified_addendum_source_transitions'):selected['verified_addendum_source_transitions']=frozen['verified_addendum_source_transitions']
    if len(json.dumps(selected).encode()) > 36000:
        raise ValueError('child_preparation_context_limit_preserve_evidence')
    return selected
