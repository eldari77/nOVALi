"""Frozen, paired decision tests with changed effects and a no-memory control."""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import time
import uuid
from pathlib import Path
from typing import Any,Callable

from . import authoring_planner_eval as previous, research_procedures as records
from . import research_maintenance as maintenance, research_runtime as runtime, theory_runtime
from . import learning_episodes as episodes, hypothesis_decisions, planner_resources as resources
from .authoring_contract import prediction_issue
from .research_tools import digest,read_json,write_json
from .theory_workspace import TheoryWorkspace
from .learning_evidence import _inside

PROCESS_ID=uuid.uuid4().hex


def fingerprint() -> dict[str, str]:
    return {**previous.fingerprint(), **{name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        for name in ('decision_learning_eval.py','lesson_learning_eval.py')}}


def _case(directory: Path, seed: str, kind: str, source_count: int, metric: str, percent: int) -> dict[str, Any]:
    root=directory/'state';repo=directory/'repo';repo.mkdir(parents=True)
    source_paths=[]
    for index in range(source_count):
        path='notes.py' if index==0 else 'dependency_'+str(index)+'.py'
        (repo/path).write_text('# Frozen decision input '+seed+'\n'+'# Unresolved boundary evidence.\n'*(30+index*17)+
            'def observe(value):\n    return value if value >= 0 else None\n')
        source_paths.append(path)
    write_json(repo/'theory/subjects/study.json',{'title':'Independent method study '+seed[:8],
        'sources':source_paths,'evaluator_ids':['finite_domain_v1'],
        'research_question':'Inspect boundaries and retain unknown evidence.'})
    write_json(root/'autonomy/status.json',{'active':True,'emergency_stop':False})
    policy=runtime.ResearchPolicy(enabled=True,theory_subject_ids=('study',))
    work=theory_runtime.prepare_theory_work(root,'study',policy,repo_root=repo)
    ws=TheoryWorkspace(root,'study',repo_root=repo)
    ws.register_claim({'kind':'interpretive','statement':'The source boundaries require inspection before a definite claim.',
        'definitions':{'boundary':'A supplied input limit requiring inspection.'},'assumptions':['Navigation does not establish an outcome.'],
        'scope':'Only this supplied input.','dependencies':[],'source_ids':list(ws._snapshot()['sources']),
        'operationalization':'Inspect the source and request a matching independent check.',
        'falsification':'Unresolved or inconsistent boundaries prevent a definite conclusion.'})
    state={'id':work['run_id'],'work':work,'observations':[],'state':'waiting_for_changed_input',
        'feedback':'theory_context_size_limit_inspect_targeted_records','inflight':None,
        'usage':{'model_calls':work['limits']['model_calls'],'tool_calls':work['limits']['tool_calls'],'compute_seconds':10,'evaluations':0},
        'call_allowance':{'remaining_model_calls':0,'allowed_commands':['inspect_source','inspect_dependency','register_claim','request_capability']}}
    parent=ws._path('runs',work['run_id']);write_json(parent,state)
    write_json(root/'research_methods/policy.json',{**maintenance.DEFAULT_POLICY,'enabled':True})
    episodes.configure(root,limits=dict(episodes.DEFAULT_LIMITS),enabled=True,authority_reference='Frozen isolated decision evaluation')
    task=maintenance.capture(root,{'episode_id':work['run_id'],'theory_subject_id':'study'},repo_root=repo)
    episode=episodes.admit(root,task,repo_root=repo)
    path=root/'research_methods/episode_tasks'/(episode['id']+'.json');task=read_json(path)
    profile={'name':'compact_current_stage','rationale':'Assess whether narrower instructions and command scope change the specified measured quantity.',
        'instruction_mode':'compact_catalog','excerpt_chars':4000,'command_scope':'current_stage'}
    hypothesis={'metric':metric,'predicted_reduction_percent':percent,'changed_fields':['instruction_mode','command_scope'],
        'mechanism':'Removing redundant instructions and command choices may reduce the specified resource cost.',
        'falsifier':'Reject the stated numerical reduction if independent matching measurement does not reach its threshold.'}
    context=episodes.frozen_planning_inputs(root,episode['id'],repo_root=repo)['planning_context']
    started=time.monotonic();assessment=resources.preflight_check(context,profile)
    issue=prediction_issue(hypothesis,assessment)
    observed='unknown' if metric not in (assessment['baseline_components'] or {}) else 'refuted' if issue else 'supported'
    if observed!=kind:raise ValueError('fixture_measurement_does_not_match_frozen_kind')
    _,account,account_path,_=episodes.practice_budget(root,task)
    account['usage']['tool_calls']=2;account['usage']['compute_seconds']=time.monotonic()-started
    write_json(account_path,account)
    task['requires_strategy_hypothesis']=True
    task['feedback']={'reason':'assess_supplied_hypothesis_using_current_measurements',
        'supplied_hypothesis':hypothesis,'supplied_strategy':profile,'assessment':assessment,
        'instruction':'Choose a justified action. A supported static hypothesis can become a separately evaluated proposal; a contradiction permits refutation or revision; absent observables require measurement. No scientific result is established by this exercise.',
        'setup_origin':'benchmark_supplied_hypothesis_not_new_model_authorship'}
    setup=records.store(root,'attempts',{'failure_id':task['failure_id'],'learning_episode_id':episode['id'],
        'call':0,'synthetic_setup':True,'setup_provider_calls':0,'response':{'planning_strategy':profile,'strategy_hypothesis':hypothesis},
        'outcome':{'error':'strategy_preflight_prediction_not_met'} if issue else {'setup_observation':observed},
        'diagnostics':{'assessment':assessment},'planning_input_sha256':digest(context),'implementation':records.implementation(),
        'candidate_id':'','evaluation_id':'','usage_after':dict(account['usage'])})
    task['attempt_ids'].append(setup['id'])
    if issue:
        task['candidate_signatures'].append(resources.signature(profile))
        task['pending_prediction']={'attempt_id':setup['id'],'strategy_signature':resources.signature(profile),'maximum_revisions':1}
    write_json(path,task)
    sources={p:hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in source_paths}
    return {'episode_id':episode['id'],'parent_path':parent.relative_to(root).as_posix(),'parent_sha256':digest(state),
        'source_sha256':sources['notes.py'],'source_files':sources,'initial_task_sha256':digest(task),'setup_attempt_id':setup['id'],
        'kind':kind,'metric':metric,'supplied_hypothesis':hypothesis,'supplied_profile':profile,
        'frozen_context_sha256':digest(context),'measurement':assessment}


def prepare(output: Path, *, provider_identity: dict[str, Any]) -> dict[str, Any]:
    output=output.resolve()
    if (output/'manifest.json').exists():raise ValueError('fresh_decision_evaluation_required')
    seed=uuid.uuid4().hex;cases=[]
    specifications=[('initial/context','initial','training','refuted',1,'context_bytes',15),
        ('initial/magnitude','initial','training','refuted',2,'instruction_chars',90)]
    for index,(kind,count,metric,percent) in enumerate([('supported',3,'instruction_chars',1),('refuted',5,'context_bytes',15),('unknown',4,'action_seconds',20)]):
        for arm in (('with_memory','without_memory') if index%2==0 else ('without_memory','with_memory')):
            specifications.append(('transfer/'+kind+'/'+arm,'transfer',arm,kind,count,metric,percent))
    for key,phase,arm,kind,count,metric,percent in specifications:
        case=_case(output/key,seed+kind+str(count),kind,count,metric,percent)
        cases.append({'key':key,'directory':key,'phase':phase,'arm':arm,**case})
    for kind in ('supported','refuted','unknown'):
        pair=[c for c in cases if c['phase']=='transfer' and c['kind']==kind]
        if pair[0]['frozen_context_sha256']!=pair[1]['frozen_context_sha256']:
            raise ValueError('paired_comparison_inputs_must_match')
    initial=cases[0]['measurement'];transfer=next(c for c in cases if c['phase']=='transfer' and c['kind']=='refuted')['measurement']
    if initial['baseline_components']==transfer['baseline_components']:raise ValueError('transfer_effect_must_change')
    manifest={'version':'decision_transfer_v3','seed':seed,'implementation':fingerprint(),'provider_identity':provider_identity,
        'cases':cases,'limits':{'model_calls':16,'per_trajectory_calls':2,'per_trajectory_checks':26,'per_trajectory_seconds':280},
        'setup':'Benchmark-supplied hypotheses and real local preflight measurements; zero setup provider calls, two charged checks per case.',
        'acceptance':'Supported: a locally supported candidate for the supplied metric. Refuted: a verified refutation or withdrawal, or a distinct independently checked correction/hypothesis. Unknown: a bounded request for the missing metric. Restart reuse additionally requires citing a retained Novali-authored decision, correct current handling, and a new process. Compare paired equal-input, equal-budget arms with and without that memory.',
        'research_performance':'not_evaluated','scientific_progress_credited':False,'grants_execution_authority':False}
    manifest['sha256']=digest(manifest);write_json(output/'manifest.json',manifest)
    write_json(output/'evaluation.json',{'calls':0,'inflight':None,'receipts':[]})
    return manifest


def load(output: Path) -> tuple[dict[str, Any],dict[str, Any],list[dict[str, Any]]]:
    manifest=read_json(output/'manifest.json');state=read_json(output/'evaluation.json')
    if manifest.get('sha256')!=digest({k:v for k,v in manifest.items() if k!='sha256'}) or manifest['implementation']!=fingerprint():
        raise ValueError('frozen_decision_evaluation_changed')
    rows=[read_json(_inside(output,'receipts/'+key+'.json')) for key in state['receipts']]
    if state['inflight'] or len(rows)!=state['calls'] or len(set(state['receipts']))!=len(rows):
        raise ValueError('interrupted_decision_evaluation_requires_review')
    if any(r.get('sha256')!=digest({k:v for k,v in r.items() if k!='sha256'}) for r in rows):raise ValueError('decision_receipt_changed')
    for case in manifest['cases']:
        base=_inside(output,case['directory']);root=base/'state'
        if digest(read_json(_inside(root,case['parent_path'])))!=case['parent_sha256']:raise ValueError('evaluation_parent_changed')
        for name,sha in case['source_files'].items():
            if hashlib.sha256(_inside(base/'repo',name).read_bytes()).hexdigest()!=sha:raise ValueError('evaluation_source_changed')
        task=read_json(root/'research_methods/episode_tasks'/(case['episode_id']+'.json'))
        receipts=[r for r in rows if r['case']==case['key']]
        if task['model_calls']!=len(receipts) or digest(task)!=(receipts[-1]['task_sha256'] if receipts else case['initial_task_sha256']):
            raise ValueError('evaluation_task_changed')
        episodes.practice_budget(root,task)
        for receipt in receipts:
            attempt=records.read(root,'attempts',receipt['attempt_id'])
            if attempt['outcome']!=receipt['outcome'] or attempt['usage_after']!=receipt['usage']:raise ValueError('evaluation_attempt_changed')
    return manifest,state,rows


def _score(root: Path, case: dict[str, Any], attempt: dict[str, Any]) -> bool:
    if attempt['outcome'].get('error'):return False
    candidate=records.read(root,'planning_candidates',attempt['candidate_id']) if attempt.get('candidate_id') else None
    if case['kind']=='supported':
        return bool(candidate and candidate['strategy_hypothesis']['metric']==case['metric'] and
            not prediction_issue(candidate['strategy_hypothesis'],candidate['assessment']))
    if case['kind']=='unknown':
        request=attempt.get('response',{}).get('measurement_request',{})
        return bool(attempt['outcome'].get('measurement_state')=='unknown' and request.get('metric')==case['metric'])
    decision_id=attempt['outcome'].get('hypothesis_decision_id')
    if not decision_id:return False
    decision=records.read(root,'hypothesis_decisions',decision_id)
    return bool(decision['decision'] in {'refute','withdraw'} or candidate and
        candidate['strategy_hypothesis']['metric'] in {'instruction_chars','context_bytes','schema_bytes'} and
        not prediction_issue(candidate['strategy_hypothesis'],candidate['assessment']))


def step(output: Path, *, planner: Callable | None = None) -> dict[str, Any]:
    output=output.resolve()
    with runtime.research_lease(output) as owned:
        if not owned:raise ValueError('decision_evaluation_busy')
        manifest,state,_=load(output)
        if state['calls']>=manifest['limits']['model_calls']:return summary(output)
        selected=None
        for case in manifest['cases']:
            root=output/case['directory']/'state';task=read_json(root/'research_methods/episode_tasks'/(case['episode_id']+'.json'))
            if task['state']=='ready':selected=(case,root,task);break
        if not selected:return summary(output)
        case,root,task=selected;memory=[]
        if manifest.get('live_lesson') and case['arm']!='without_memory':
            memory=[manifest['live_lesson']]
        elif case['arm']=='with_memory':
            for source in manifest['cases']:
                if source['phase']=='initial':memory+=hypothesis_decisions.memory(output/source['directory']/'state')
        if planner is None:
            from .provider_recovery import current_provider_identity
            if current_provider_identity()!=manifest['provider_identity']:raise ValueError('evaluation_provider_changed')
            planner=runtime.local_planner(dataclasses.replace(runtime.ResearchPolicy(),model_timeout_seconds=120,max_output_tokens=1400))
        def invoke(phase,context):
            context=copy.deepcopy(context)
            context['inputs']['hypothesis_memory']=memory
            if case.get('context_projection'):
                context['method_context_projection']=case['context_projection']
            context['inputs']['practice_observation']={'hypothesis':case['supplied_hypothesis'],'profile':case['supplied_profile'],
                'measurement':case['measurement'],'scope':'benchmark_supplied_hypothesis_recheck_current_evidence'}
            context['inputs']['reuse_instruction']='If applying a prior lesson, cite its decision id in your reason or rationale. A prior verdict does not settle this new hypothesis.'
            try:return planner(phase,context)
            finally:
                invoke.last_metadata=getattr(planner,'last_metadata',{});invoke.last_raw_response=getattr(planner,'last_raw_response','')
        limits,_,_,_=episodes.practice_budget(root,task)
        state['calls']+=1;state['inflight']={'case':case['key'],'reserved_seconds':120};write_json(output/'evaluation.json',state)
        before=task['model_calls'];task=maintenance.advance(root,task,limits,planner=invoke,repo_root=output/case['directory']/'repo')
        if task['model_calls']!=before+1:raise ValueError('evaluation_call_not_settled')
        attempt=records.read(root,'attempts',task['attempt_ids'][-1]);passed=_score(root,case,attempt)
        authored=attempt.get('authored_response') or attempt.get('response') or {}
        from json import dumps
        cited=[r['id'] for r in memory if r['id'] in dumps(authored)]
        receipt={'case':case['key'],'call':task['model_calls'],'process_id':PROCESS_ID,'attempt_id':attempt['id'],
            'task_sha256':digest(task),'outcome':attempt['outcome'],'usage':attempt['usage_after'],
            'passed':passed,'memory_ids_offered':[r['id'] for r in memory],'memory_ids_cited':cited,
            'authored_intent':authored.get('intent'),'candidate_id':attempt.get('candidate_id',''),
            'provider_metadata':attempt.get('provider_metadata',{}),'action_seconds':attempt['compute_seconds']}
        receipt['sha256']=digest(receipt);write_json(output/'receipts'/(receipt['sha256']+'.json'),receipt)
        state['receipts'].append(receipt['sha256']);state['inflight']=None;write_json(output/'evaluation.json',state)
        return summary(output)


def summary(output: Path) -> dict[str, Any]:
    output=output.resolve();manifest,state,receipts=load(output);rows=[]
    initial_processes={r['process_id'] for r in receipts if r['case'].startswith('initial/')}
    if manifest.get('prepared_process_id'):initial_processes.add(manifest['prepared_process_id'])
    for case in manifest['cases']:
        root=output/case['directory']/'state';task=read_json(root/'research_methods/episode_tasks'/(case['episode_id']+'.json'))
        matching=[r for r in receipts if r['case']==case['key']];last=matching[-1] if matching else {}
        eligible=case['arm']!='without_memory' and case['phase']=='transfer' and bool(last.get('memory_ids_offered'))
        rows.append({'case':case['key'],'kind':case['kind'],'phase':case['phase'],'arm':case['arm'],
            'state':task['state'],'calls':task['model_calls'],'passed':bool(last.get('passed')),'usage':last.get('usage',{}),
            'feedback':task['feedback'],'restart_reuse_eligible':eligible,
            'first_action_passed':bool(matching and matching[0]['passed']),
            'recovered_after_failure':bool(len(matching)>1 and not matching[0]['passed'] and last.get('passed')),
            'restart_reuse_passed':bool(eligible and last.get('passed') and last.get('memory_ids_cited') and last['process_id'] not in initial_processes)})
    arms={arm:{'passes':sum(r['passed'] for r in rows if r['arm']==arm),'cases':3} for arm in ('with_memory','without_memory')}
    if manifest.get('live_lesson'):
        arms['with_memory_focused']={'passes':sum(r['passed'] for r in rows if r['arm']=='with_memory_focused'),'cases':3}
    eligible=sum(r['restart_reuse_eligible'] for r in rows)
    complete=all(r['state']!='ready' for r in rows)
    return {'complete':complete,'calls':state['calls'],'trajectories':rows,'comparison':arms,
        'initial_passes':sum(r['passed'] for r in rows if r['phase']=='initial'),
        'restart_reuse_eligible_cases':eligible,'restart_reuse_passes':sum(r['restart_reuse_passed'] for r in rows),
        'restart_assessment':'not_assessable_without_retained_initial_decision' if not eligible else 'measured_on_fresh_tasks',
        'paired_pass_difference':arms['with_memory']['passes']-arms['without_memory']['passes'] if complete else None,
        'general_advantage_established':False,'research_performance':'not_evaluated',
        'method_adoption_authorized':False,'scientific_progress_credited':False,'setup_provider_calls':0,'setup_checks':16}


if __name__=='__main__':
    import argparse,json
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','step','summary']);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.action=='prepare':
        from .provider_recovery import current_provider_identity
        result=prepare(args.output,provider_identity=current_provider_identity())
        print(json.dumps({'manifest_sha256':result['sha256'],'limits':result['limits']}))
    else:
        result=step(args.output) if args.action=='step' else summary(args.output)
        write_json(args.output/'summary.json',result);print(json.dumps(result))
