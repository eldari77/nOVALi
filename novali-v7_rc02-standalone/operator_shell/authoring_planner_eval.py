"""Frozen real-planner authoring trajectories; every step can run after restart.

This is an isolated development evaluation, with no live research authority or
method adoption. Correct proposals are never supplied by the harness.
"""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from . import research_procedures as records, research_maintenance as maintenance, learning_episodes as episodes
from . import research_runtime as runtime, theory_runtime
from .research_tools import digest, read_json, write_json
from .theory_workspace import TheoryWorkspace

PROCESS_ID=uuid.uuid4().hex


def fingerprint() -> dict[str, str]:
    return {**records.implementation(), 'authoring_planner_eval.py':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def prepare(output: Path, *, provider_identity: dict[str, Any], prior_proposal: dict[str, Any],
            decision_evaluation: bool = False) -> dict[str, Any]:
    output=output.resolve()
    if (output/'manifest.json').exists():raise ValueError('fresh_authoring_evaluation_required')
    seed=uuid.uuid4().hex; cases=[]
    for phase in ('initial','transfer'):
        for domain in ('configuration','measurement'):
            directory=output/phase/domain; root=directory/'state'; repo=directory/'repo'
            repo.mkdir(parents=True)
            source=('# Independent frozen fixture '+seed+phase+domain+'\n' + '# Input boundary evidence remains unresolved.\n'*130+
                    ('def scale_input(value):\n    return value * 7\n' if domain=='configuration' else
                     'def sample_latency(value):\n    return value if value >= 0 else None\n'))
            (repo/'notes.py').write_text(source)
            write_json(repo/'theory/subjects/study.json',{'title':domain+' method study '+seed[:8],
                'sources':['notes.py'],'evaluator_ids':['finite_domain_v1'],'research_question':'Inspect the supplied boundaries and retain unknown evidence.'})
            write_json(root/'autonomy/status.json',{'active':True,'emergency_stop':False})
            policy=runtime.ResearchPolicy(enabled=True,theory_subject_ids=('study',))
            work=theory_runtime.prepare_theory_work(root,'study',policy,repo_root=repo)
            ws=TheoryWorkspace(root,'study',repo_root=repo)
            ws.register_claim({'kind':'interpretive','statement':'The supplied source requires inspection before deciding its boundary behavior.',
                'definitions':{'boundary':'A supplied input limit whose meaning requires source inspection.'},
                'assumptions':['No outcome is established by the navigation index.'],'scope':'Only this supplied source.',
                'dependencies':[],'source_ids':list(ws._snapshot()['sources']),
                'operationalization':'Inspect the implementation and identify a matching independent check.',
                'falsification':'Unresolved or inconsistent boundaries prevent a definite claim.'})
            state={'id':work['run_id'],'work':work,'observations':[]}
            # Explicit synthetic setup history, not an unrecorded live call.
            state.update(state='waiting_for_changed_input',feedback='theory_context_size_limit_inspect_targeted_records',inflight=None)
            state['usage']={'model_calls':work['limits']['model_calls'],'tool_calls':work['limits']['tool_calls'],
                            'compute_seconds':10,'evaluations':0}
            state['call_allowance']={'remaining_model_calls':0,'allowed_commands':['inspect_source','inspect_dependency','register_claim','request_capability']}
            write_json(ws._path('runs',work['run_id']),state)
            write_json(root/'research_methods/policy.json',{**maintenance.DEFAULT_POLICY,'enabled':True})
            episodes.configure(root,limits=dict(episodes.DEFAULT_LIMITS),enabled=True,authority_reference='Frozen isolated authoring evaluation')
            task=maintenance.capture(root,{'episode_id':work['run_id'],'theory_subject_id':'study'},repo_root=repo)
            episode=episodes.admit(root,task,repo_root=repo)
            active=read_json(root/'research_methods/episode_tasks'/(episode['id']+'.json'))
            active['requires_strategy_hypothesis']=True
            active['feedback']={'reason':'review_previous_rejected_proposal_against_current_measurements',
                'previous_rejected_proposal':prior_proposal,'scope':'prior_model_authorship_not_a_validated_solution'}
            if decision_evaluation:
                _replay_failure(root,active,prior_proposal,repo)
            write_json(root/'research_methods/episode_tasks'/(episode['id']+'.json'),active)
            cases.append({'key':phase+'/'+domain,'directory':directory.relative_to(output).as_posix(),
                'phase':phase,'domain':domain,'episode_id':episode['id'],'parent_path':ws._path('runs',work['run_id']).relative_to(root).as_posix(),
                'initial_task_sha256':digest(active),
                'setup_attempt_id':active.get('pending_prediction',{}).get('attempt_id'),
                'parent_sha256':digest(state),'source_sha256':hashlib.sha256((repo/'notes.py').read_bytes()).hexdigest()})
    manifest={'version':'hypothesis_decisions_v2' if decision_evaluation else 'authoring_learning_v1',
        'seed':seed,'implementation':fingerprint(),'provider_identity':provider_identity,
        'cases':cases,'limits':{'model_calls':8,'per_trajectory_calls':2,'per_trajectory_seconds':280,'per_trajectory_checks':26},
        'acceptance':'Valid model-authored proposal within the frozen episode, with supported local static prediction. Transfer additionally selects and cites a retained model-authored method and succeeds on a fresh task in another process.',
        'comparative_advantage_tested':False,'scientific_progress_credited':False,'grants_execution_authority':False}
    if decision_evaluation:
        manifest.update(prior_response_sha256=digest(prior_proposal),setup='Historical model response replayed unchanged and independently remeasured; zero setup provider calls, two charged local checks per case.',
            acceptance='Diagnosis requires an evidence-bound decision on the replayed refutation. Justified response additionally requires a checked refutation or withdrawal, or a separately supported static replacement hypothesis. Restart reuse requires citing a prior verified decision and successfully handling fresh measurements in a different process. These scores do not establish research success, causal explanation, or comparative advantage.',
            scope='Four refuted static transport hypotheses on fresh configuration and measurement source fixtures; supported and unknown controls are covered separately by deterministic tests.')
    manifest['sha256']=digest(manifest);write_json(output/'manifest.json',manifest)
    write_json(output/'evaluation.json',{'calls':0,'inflight':None,'receipts':[]})
    return manifest


def _replay_failure(root: Path, task: dict[str, Any], response: dict[str, Any], repo: Path) -> None:
    """Explicit isolated setup; never grants, hides or simulates a provider call."""
    from .authoring_contract import diagnose,prediction_issue
    from .planner_resources import preflight_check,signature
    inputs=episodes.frozen_planning_inputs(root,task['learning_episode_id'],repo_root=repo)
    if set(response)!={'planning_strategy','strategy_hypothesis'} or diagnose(response,inputs):
        raise ValueError('well_formed_prior_model_proposal_required')
    started=time.monotonic();assessment=preflight_check(inputs['planning_context'],response['planning_strategy'])
    issue=prediction_issue(response['strategy_hypothesis'],assessment)
    if not issue:raise ValueError('prior_proposal_must_be_refuted_on_fresh_fixture')
    task['feedback']={'reason':issue['reason'],'field_issues':[issue],'assessment':assessment,
        'setup_origin':'unchanged_historical_model_response_remeasured_on_current_fixture'}
    _,account,account_path,_=episodes.practice_budget(root,task)
    account['usage']['tool_calls']+=2;account['usage']['compute_seconds']+=time.monotonic()-started
    write_json(account_path,account)
    attempt=records.store(root,'attempts',{'failure_id':task['failure_id'],'learning_episode_id':task['learning_episode_id'],
        'call':0,'synthetic_setup':True,'setup_provider_calls':0,'response':response,
        'outcome':{'error':issue['reason']},'diagnostics':copy.deepcopy(task['feedback']),
        'planning_input_sha256':digest(inputs['planning_context']),'implementation':records.implementation(),
        'candidate_id':'','evaluation_id':'','usage_after':account['usage']})
    task['attempt_ids'].append(attempt['id']);task['candidate_signatures'].append(signature(response['planning_strategy']))
    task['pending_prediction']={'attempt_id':attempt['id'],'strategy_signature':signature(response['planning_strategy']),
        'permitted_edit':'predicted_reduction_percent_only_with_reason','maximum_revisions':1}


def load(output: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest=read_json(output/'manifest.json'); state=read_json(output/'evaluation.json')
    if manifest.get('sha256')!=digest({k:v for k,v in manifest.items() if k!='sha256'}):raise ValueError('authoring_manifest_integrity_failure')
    if manifest['implementation']!=fingerprint():raise ValueError('authoring_evaluation_implementation_changed')
    receipts=[read_json(output/'receipts'/(rid+'.json')) for rid in state['receipts']]
    if any(r.get('sha256')!=digest({k:v for k,v in r.items() if k!='sha256'}) for r in receipts):raise ValueError('authoring_receipt_changed')
    if state['inflight'] or len(receipts)!=state['calls']:raise ValueError('interrupted_authoring_evaluation_requires_review')
    for case in manifest['cases']:
        directory=output/case['directory']; root=directory/'state'
        if (digest(read_json(root/case['parent_path']))!=case['parent_sha256'] or
                hashlib.sha256((directory/'repo/notes.py').read_bytes()).hexdigest()!=case['source_sha256']):
            raise ValueError('frozen_authoring_parent_changed')
        task=read_json(root/'research_methods/episode_tasks'/(case['episode_id']+'.json'))
        expected=[r for r in receipts if r['case']==case['key']]
        if len(expected)!=task['model_calls']:raise ValueError('authoring_case_account_mismatch')
        if not expected and case.get('initial_task_sha256')!=digest(task):raise ValueError('authoring_setup_changed')
        if case.get('setup_attempt_id'):records.read(root,'attempts',case['setup_attempt_id'])
        if expected and digest(task)!=expected[-1]['task_sha256']:raise ValueError('authoring_task_projection_changed')
    return manifest,state


def step(output: Path, *, planner: Callable | None = None) -> dict[str, Any]:
    output=output.resolve()
    from .research_runtime import research_lease
    with research_lease(output) as owned:
        if not owned:raise ValueError('authoring_evaluation_busy')
        return _step(output,planner=planner)


def _step(output: Path, *, planner: Callable | None = None) -> dict[str, Any]:
    manifest,state=load(output)
    if state['calls']>=manifest['limits']['model_calls']:return summary(output)
    if planner is None:
        from .provider_recovery import current_provider_identity
        if current_provider_identity()!=manifest['provider_identity']:raise ValueError('authoring_provider_changed')
        planner=runtime.local_planner(dataclasses.replace(runtime.ResearchPolicy(),model_timeout_seconds=120,max_output_tokens=1800))
    selected=None
    for case in manifest['cases']:
        root=output/case['directory']/'state'; task=read_json(root/'research_methods/episode_tasks'/(case['episode_id']+'.json'))
        if task['state']=='ready':selected=(case,root,task);break
    if selected is None:return summary(output)
    case,root,task=selected; retained=[]; retained_decisions=[]
    if case['phase']=='transfer':
        for earlier in manifest['cases']:
            if earlier['phase']!='initial':continue
            from .hypothesis_decisions import memory
            retained_decisions.extend(memory(output/earlier['directory']/'state'))
            for p in (output/earlier['directory']/'state/research_methods/planning_candidates').glob('*.json'):
                candidate=records.read(output/earlier['directory']/'state','planning_candidates',p.stem)
                retained.append({'id':candidate['id'],'profile':candidate['profile'],'strategy_hypothesis':candidate.get('strategy_hypothesis')})
    limits,account,_,_=episodes.practice_budget(root,task)
    state['calls']+=1;state['inflight']={'case':case['key'],'reserved_seconds':120};write_json(output/'evaluation.json',state)
    def invoke(phase,context):
        if retained_decisions:
            context=copy.deepcopy(context)
            context['inputs']['hypothesis_memory']=context['inputs'].get('hypothesis_memory',[])+retained_decisions
            context['inputs']['decision_reuse_instruction']='Decide whether a prior lesson applies to these fresh measurements. If applying one, cite its exact decision id in your reason. A previous refutation does not establish a verdict on new inputs.'
        if retained:
            context=copy.deepcopy(context); context['inputs']['retained_method_candidates']=retained
            context['inputs']['reuse_instruction']='Choose whether a retained method applies. If using one, cite its exact id in the rationale and verify your current prediction on this task. Retention is not independent adoption.'
        try:return planner(phase,context)
        finally:
            invoke.last_metadata=getattr(planner,'last_metadata',{});invoke.last_raw_response=getattr(planner,'last_raw_response','')
    before_calls=task['model_calls']; started=time.monotonic()
    task=maintenance.advance(root,task,limits,planner=invoke,repo_root=output/case['directory']/'repo')
    if task['model_calls']!=before_calls+1:raise ValueError('authoring_evaluation_call_not_settled')
    attempt=records.read(root,'attempts',task['attempt_ids'][-1]); candidate=records.read(root,'planning_candidates',attempt['candidate_id']) if attempt['candidate_id'] else None
    from .planner_resources import signature
    reused=[r['id'] for r in retained if candidate and r['id'] in candidate['profile']['rationale'] and signature(r['profile'])==signature(candidate['profile'])]
    decision_id=attempt['outcome'].get('hypothesis_decision_id')
    decision=records.read(root,'hypothesis_decisions',decision_id) if decision_id else None
    current_finding=records.read(root,'hypothesis_findings',decision['finding_id']) if decision else None
    justified=bool(decision and (decision['decision'] in {'refute','withdraw'} or candidate and
        candidate.get('strategy_hypothesis',{}).get('metric') in {'context_bytes','instruction_chars','schema_bytes'}))
    reused_decisions=[r['id'] for r in retained_decisions if justified and r['id'] in decision['response']['reason']
        and r['hypothesis']['metric']==current_finding['hypothesis']['metric']
        and signature(r['profile'])==signature(current_finding['profile'])]
    receipt={'case':case['key'],'process_id':PROCESS_ID,'call':task['model_calls'],'attempt_id':attempt['id'],
        'task_sha256':digest(task),'candidate_id':attempt['candidate_id'],'field_issues':attempt.get('diagnostics',{}).get('field_issues',[]),
        'usage':attempt['usage_after'],'wall_seconds':time.monotonic()-started,'retained_ids_offered':[r['id'] for r in retained],
        'reused_method_ids':reused,'outcome':attempt['outcome'],'diagnostic_correction':before_calls>0 and bool(candidate)}
    if manifest['version']=='hypothesis_decisions_v2':
        receipt.update(hypothesis_decision_id=decision_id,diagnosis_verified=bool(decision),response_justified=justified,
            retained_decision_ids_offered=[r['id'] for r in retained_decisions],reused_decision_ids=reused_decisions,
            repeated_refuted_proposal=bool(attempt['response']==records.read(root,'attempts',case['setup_attempt_id'])['response']))
    receipt['sha256']=digest(receipt);write_json(output/'receipts'/(receipt['sha256']+'.json'),receipt)
    state['receipts'].append(receipt['sha256']);state['inflight']=None;write_json(output/'evaluation.json',state)
    return summary(output)


def summary(output: Path) -> dict[str, Any]:
    output=output.resolve()
    manifest,state=load(output); receipts=[read_json(output/'receipts'/(rid+'.json')) for rid in state['receipts']]
    initial_processes={r['process_id'] for r in receipts if r['case'].startswith('initial/')}
    rows=[]
    for case in manifest['cases']:
        root=output/case['directory']/'state'; task=read_json(root/'research_methods/episode_tasks'/(case['episode_id']+'.json'))
        matching=[r for r in receipts if r['case']==case['key']]; last=matching[-1] if matching else {}
        candidate=records.read(root,'planning_candidates',last['candidate_id']) if last.get('candidate_id') else None
        static=bool(candidate and candidate.get('strategy_hypothesis',{}).get('metric') in {'context_bytes','instruction_chars','schema_bytes'})
        passed=bool(candidate and static)
        rows.append({'case':case['key'],'state':task['state'],'calls':task['model_calls'],'passed':passed,
            'corrected_own_attempt':bool(last.get('diagnostic_correction')),'feedback':task['feedback'],
            'restart_reuse_passed':bool(passed and case['phase']=='transfer' and last.get('reused_method_ids')
                and last['process_id'] not in initial_processes),'usage':last.get('usage',{})})
        if manifest['version']=='hypothesis_decisions_v2':
            rows[-1].update(diagnosis_verified=bool(last.get('diagnosis_verified')),response_justified=bool(last.get('response_justified')),
                hypothesis_decision_id=last.get('hypothesis_decision_id'),
                restart_decision_reuse=bool(case['phase']=='transfer' and last.get('reused_decision_ids')
                    and last['process_id'] not in initial_processes and not any(r.get('repeated_refuted_proposal') for r in matching)),
                repeated_refuted_proposal=any(r.get('repeated_refuted_proposal') for r in matching))
    result={'complete':all(r['state']!='ready' for r in rows),'calls':state['calls'],'trajectories':rows,
        'valid_authoring_passes':sum(r['passed'] for r in rows),'restart_reuse_passes':sum(r['restart_reuse_passed'] for r in rows),
        'scientific_progress_credited':False,'method_adoption_authorized':False,'comparative_advantage_tested':False}
    if manifest['version']=='hypothesis_decisions_v2':
        result.update(diagnosis_passes=sum(r['diagnosis_verified'] for r in rows),
            justified_response_passes=sum(r['response_justified'] for r in rows),
            restart_decision_reuse_passes=sum(r['restart_decision_reuse'] for r in rows),
            research_performance='not_evaluated',setup_provider_calls=0,setup_local_checks=2*len(rows))
    return result


if __name__=='__main__':
    import argparse,json
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','step','summary'])
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--prior-attempt',type=Path)
    parser.add_argument('--decision-evaluation',action='store_true')
    args=parser.parse_args()
    if args.action=='prepare':
        if not args.prior_attempt:parser.error('--prior-attempt is required for prepare')
        from .provider_recovery import current_provider_identity
        result=prepare(args.output,provider_identity=current_provider_identity(),prior_proposal=read_json(args.prior_attempt)['response'],
            decision_evaluation=args.decision_evaluation)
        print(json.dumps({'manifest_sha256':result['sha256'],'limits':result['limits']}))
    else:
        result=step(args.output) if args.action=='step' else summary(args.output)
        write_json(args.output/'summary.json',result);print(json.dumps(result))
