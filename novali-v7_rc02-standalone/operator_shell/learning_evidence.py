"""Operator-reviewed, answer-free failure patterns for bounded planner practice."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

from . import research_procedures as records
from .research_tools import digest,read_json


def _inside(base: Path, relative: str) -> Path:
    candidate=(base/relative).resolve()
    if Path(relative).is_absolute() or not candidate.is_relative_to(base.resolve()):
        raise ValueError('evaluation_path_must_stay_within_archive')
    return candidate


def inspect(directory: Path) -> dict[str, Any]:
    """Verify a settled archive without requiring its historical code to be current."""
    directory=directory.resolve(); manifest=read_json(directory/'manifest.json'); state=read_json(directory/'evaluation.json')
    if manifest.get('retention_contract') == 'child_retention_v1':
        from .child_retention_eval import inspect as inspect_retention
        return inspect_retention(directory)
    if manifest.get('version') == 'successor_learning_cycle_v1':
        from .successor_cycle_eval import inspect_archive
        return inspect_archive(directory)
    if manifest.get('version') in {'child_learning_cycle_v1','child_learning_cycle_v2','child_learning_cycle_v3','child_learning_cycle_v4','child_learning_cycle_v5','child_learning_cycle_v6','child_learning_cycle_v7','child_learning_cycle_v8'}:
        from .child_learning_evidence import inspect as inspect_child
        return inspect_child(directory)
    if manifest.get('version')=='learning_cycle_v1':
        from .learning_cycle_evidence import inspect as inspect_cycle
        return inspect_cycle(directory)
    live = manifest.get('version') == 'live_lesson_transfer_v1'
    if (manifest.get('version') not in {'hypothesis_decisions_v2','decision_transfer_v3','live_lesson_transfer_v1'}
            or manifest.get('sha256')!=digest({k:v for k,v in manifest.items() if k!='sha256'})):
        raise ValueError('intact_versioned_decision_evaluation_required')
    if live and (digest(manifest.get('live_lesson')) != manifest.get('live_lesson_sha256')
            or manifest.get('lesson_provenance',{}).get('decision_id') != manifest.get('live_lesson',{}).get('id')):
        raise ValueError('intact_live_lesson_provenance_required')
    if (state.get('inflight') or type(state.get('calls')) is not int or not 0<state['calls']<=(18 if live else 16)
            or len(state.get('receipts',[]))!=state['calls'] or len(set(state['receipts']))!=state['calls']
            or not 1<=len(manifest['cases'])<=(9 if live else 8)):raise ValueError('settled_bounded_evaluation_required')
    if live:
        expected={(kind,arm) for kind in ('supported','refuted','unknown')
                  for arm in ('without_memory','with_memory','with_memory_focused')}
        if {(c['kind'],c['arm']) for c in manifest['cases']} != expected or len(manifest['cases'])!=9:
            raise ValueError('complete_paired_live_lesson_cases_required')
        for kind in ('supported','refuted','unknown'):
            if len({c['frozen_context_sha256'] for c in manifest['cases'] if c['kind']==kind})!=1:
                raise ValueError('matched_live_lesson_inputs_required')
    receipts=[]; evidence=[]; patterns={'measured_outcome_used_as_improvement_prediction':0,
        'explanatory_edit_misclassified_as_control_change':0,'actual_control_changes_omitted':0,'other_rejected_actions':0}
    for key in state['receipts']:
        receipt=read_json(_inside(directory,'receipts/'+key+'.json'))
        if receipt.get('sha256')!=digest({k:v for k,v in receipt.items() if k!='sha256'}):
            raise ValueError('evaluation_receipt_integrity_failure')
        receipts.append(receipt)
    case_keys=[c['key'] for c in manifest['cases']]
    if len(set(case_keys))!=len(case_keys) or any(r['case'] not in case_keys for r in receipts):
        raise ValueError('owned_evaluation_cases_required')
    for case in manifest['cases']:
        base=_inside(directory,case['directory']); root=base/'state'
        if (digest(read_json(_inside(root,case['parent_path'])))!=case['parent_sha256']
                or hashlib.sha256((base/'repo/notes.py').read_bytes()).hexdigest()!=case['source_sha256']):
            raise ValueError('evaluation_source_or_parent_changed')
        for name,sha in case.get('source_files',{}).items():
            if hashlib.sha256(_inside(base/'repo',name).read_bytes()).hexdigest()!=sha:
                raise ValueError('evaluation_source_or_parent_changed')
        task=read_json(_inside(root,'research_methods/episode_tasks/'+case['episode_id']+'.json'))
        account=read_json(_inside(root,'research_methods/episode_accounts/'+case['episode_id']+'.json'))
        rows=[r for r in receipts if r['case']==case['key']]
        if (task.get('state')=='ready' or not rows or len(rows)>2 or task['model_calls']!=len(rows)
                or [r['call'] for r in rows]!=list(range(1,len(rows)+1))
                or digest(task)!=rows[-1]['task_sha256'] or account.get('inflight')
                or account.get('usage')!=rows[-1]['usage']):raise ValueError('settled_owned_case_accounts_required')
        previous={'model_calls':0,'tool_calls':0,'compute_seconds':0}
        for receipt in rows:
            attempt=records.read(root,'attempts',receipt['attempt_id'])
            usage=attempt['usage_after']
            if (attempt.get('learning_episode_id')!=case['episode_id'] or attempt['id'] not in task['attempt_ids']
                    or usage!=receipt['usage'] or attempt['outcome']!=receipt['outcome']
                    or any(usage[k]<previous[k] for k in previous)):
                raise ValueError('owned_monotonic_attempt_evidence_required')
            previous=usage; error=attempt['outcome'].get('error',''); response=attempt.get('response') or {}
            if live:
                from .decision_learning_eval import _score
                if receipt.get('passed')!=_score(root,case,attempt):
                    raise ValueError('independent_live_lesson_verdict_mismatch')
            if (manifest['version'] in {'decision_transfer_v3','live_lesson_transfer_v1'} and receipt is rows[-1]
                    and receipt.get('passed') is False and not error):
                patterns['accepted_action_did_not_complete_task']=patterns.get('accepted_action_did_not_complete_task',0)+1
            hyp=response.get('strategy_hypothesis',response.get('hypothesis',{})); percent=hyp.get('predicted_reduction_percent') if isinstance(hyp,dict) else None
            if (live and receipt.get('passed') is False and case['kind']=='supported'
                    and hyp.get('metric') == manifest['live_lesson']['hypothesis']['metric']
                    and hyp.get('metric') != case['metric']):
                name='prior_quantity_submitted_for_different_current_question'
                patterns[name]=patterns.get(name,0)+1
            if error and type(percent) in (int,float) and percent<=0:
                patterns['measured_outcome_used_as_improvement_prediction']+=1
            elif 'changed_fields' in error:patterns['actual_control_changes_omitted']+=1
            elif error=='hypothesis_revision_preserves_untested_strategy' and response.get('hypothesis_revision'):
                prior=records.read(root,'attempts',response['hypothesis_revision']['attempt_id'])
                old=prior['response']['planning_strategy']; new=response['planning_strategy']
                if all(old[k]==new[k] for k in ('excerpt_chars','instruction_mode','command_scope')):
                    patterns['explanatory_edit_misclassified_as_control_change']+=1
                else:patterns['other_rejected_actions']+=1
            elif error:patterns['other_rejected_actions']+=1
            evidence.append(digest(attempt))
        evidence.extend([digest(task),digest(account)])
    return {'manifest_sha256':manifest['sha256'],'archive_state_sha256':digest(state),
        'evidence_sha256':digest(evidence),'historical_implementation':manifest['implementation'],
        'calls':state['calls'],'patterns':{k:v for k,v in patterns.items() if v},
        'scope':'observed_failure_patterns_only_no_answers_or_withheld_cases'}


def propose(root: Path, directory: Path, *, repo_root: Path) -> dict[str, Any]:
    archive=directory.resolve(); repo_root=repo_root.resolve()
    if not archive.is_relative_to(repo_root/'runtime_data/generated'):
        raise ValueError('owned_development_archive_required')
    proof=inspect(archive)
    if not proof['patterns']:raise ValueError('observed_failure_pattern_required')
    return records.store(root,'learning_evidence_proposals',{'archive_path':archive.relative_to(repo_root).as_posix(),
        'proof':proof,'requires_independent_review':True,'scientific_allowance_added':0})


def review(root: Path, proposal_id: str, *, decision: str, reviewer: str,
           authority_reference: str, repo_root: Path) -> dict[str, Any]:
    if decision not in {'approve','reject'} or not reviewer.strip() or not authority_reference.strip():
        raise ValueError('explicit_independent_learning_evidence_review_required')
    proposal=records.read(root,'learning_evidence_proposals',proposal_id)
    if inspect(_inside(repo_root,proposal['archive_path']))!=proposal['proof']:
        raise ValueError('learning_evidence_changed_before_review')
    existing=[records.read(root,'learning_evidence_reviews',p.stem) for p in (root/'research_methods/learning_evidence_reviews').glob('*.json')
        if read_json(p).get('proposal_id')==proposal_id]
    if existing:
        if existing[0]['decision']!=decision:raise ValueError('learning_evidence_already_reviewed')
        return existing[0]
    return records.store(root,'learning_evidence_reviews',{'proposal_id':proposal_id,'proposal_sha256':digest(proposal),
        'decision':decision,'reviewer':reviewer,'authority_reference':authority_reference,
        'reviewed_at':time.time(),
        'scientific_allowance_added':0,'method_adoption_authorized':False})


def context(root: Path) -> list[dict[str, Any]]:
    rows=[]
    reviewed_rows=[(records.read(root,'learning_evidence_reviews',path.stem),path.stat().st_mtime)
                   for path in (root/'research_methods/learning_evidence_reviews').glob('*.json')]
    # Hash order has no relation to review recency. Legacy file times affect
    # presentation only; evidence integrity and approval remain content checked.
    for reviewed,_ in sorted(reviewed_rows,key=lambda pair:(pair[0].get('reviewed_at',pair[1]),pair[0]['id'])):
        proposal=records.read(root,'learning_evidence_proposals',reviewed['proposal_id'])
        if reviewed['proposal_sha256']!=digest(proposal):raise ValueError('reviewed_learning_evidence_integrity_failure')
        if reviewed['decision']!='approve':continue
        rows.append({'review_id':reviewed['id'],'observed_failure_patterns':proposal['proof']['patterns'],
            'scope':proposal['proof']['scope'],'learning_objective':'Formulate and test your own approach to these observed failure patterns. Recheck current measurements and choose a justified action.',
            'authored_by':'independent review of historical evaluation','scientific_allowance_added':0,
            'method_adoption_authorized':False,'does_not_establish_planner_learning':True})
    return rows[-4:]
