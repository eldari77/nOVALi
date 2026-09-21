"""Frozen, bounded question -> practice -> restart reuse trajectories."""
from __future__ import annotations
import copy
import dataclasses
import hashlib
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Callable
from . import lesson_practice as lessons, learning_episodes as episodes
from . import research_maintenance as maintenance, research_procedures as records
from . import decision_learning_eval as decisions, research_runtime as runtime
from . import lesson_applicability as application, practice_lessons
from .research_tools import digest, read_json, write_json

PROCESS_ID=uuid.uuid4().hex
ARMS=('with_memory','without_memory')


def fingerprint() -> dict[str,str]:
    return {**decisions.fingerprint(),'learning_cycle_eval.py':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def _tree(path: Path) -> str:
    return digest({p.relative_to(path).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(path.rglob('*.json'))})


def _save(output: Path, state: dict[str,Any]) -> None:
    state={k:v for k,v in state.items() if k!='sha256'}
    state['roots']={arm:{'runtime':_tree(output/arm/'state'),'fresh':_tree(output/arm/'fresh'),
                        'progress':digest(read_json(output/arm/'progress.json'))} for arm in ARMS}
    state['sha256']=digest(state);write_json(output/'evaluation.json',state)


def prepare(output: Path, *, live_root: Path, decision_id: str,
            repo_root: Path, provider_identity: dict[str,Any], per_arm_calls: int = 8) -> dict[str,Any]:
    if type(per_arm_calls) is not int or not 4<=per_arm_calls<=8:
        raise ValueError('bounded_equal_cycle_arm_allowances_required')
    output=output.resolve()
    if output.exists():raise ValueError('fresh_learning_cycle_directory_required')
    method_files=list((live_root/'research_methods').rglob('*.json'))
    if len(method_files)>1024 or sum(p.stat().st_size for p in method_files)>16*1024*1024:
        raise ValueError('bounded_learning_cycle_snapshot_required')
    basis=lessons.source(live_root,decision_id,repo_root=repo_root)
    reviewed=next(records.read(live_root,'lesson_reviews',p.stem)
        for p in (live_root/'research_methods/lesson_reviews').glob('*.json')
        if read_json(p).get('decision_id')==decision_id)
    source_id=basis['episode']['id']; seed=uuid.uuid4().hex;cases=[]
    failure=records.read(live_root,'failures',basis['episode']['failure_id'])
    subject=failure['theory_subject_id']
    snapshot=read_json(live_root/'theory/subjects'/subject/'snapshot.json')
    frozen_files={'theory/subjects/'+subject+'.json'}
    frozen_files.update(row['path'] for row in snapshot['sources'].values())
    for arm in ARMS:
        base=output/arm;root=base/'state';repo=base/'repo'
        shutil.copytree(live_root/'research_methods',root/'research_methods')
        shutil.copytree(live_root/'theory/subjects'/subject,root/'theory/subjects'/subject)
        # Replay begins at the reviewed source lesson. Later live episodes are not
        # replayed or refunded; their original files remain untouched.
        for kind,keep in {'learning_episodes':source_id,'episode_tasks':source_id,'episode_accounts':source_id,
                'lesson_reviews':reviewed['id'],'practice_questions':None,'question_retry_reviews':None,
                'practice_lessons':None,'practice_lesson_checks':None,'practice_settlements':None}.items():
            for p in (root/'research_methods'/kind).glob('*.json'):
                if p.stem!=keep:p.unlink()
        for name in frozen_files:
            target=repo/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo_root/name,target)
        write_json(root/'autonomy/status.json',{'active':True,'emergency_stop':False})
        application.configure(root,enabled=arm=='with_memory',authority_reference='Frozen isolated cycle comparison')
        # Existing policy governs each stage; the evaluation advances a declared
        # logical admission clock rather than bypassing the admission function.
        now=basis['episode']['admitted_at']+8*86400
        episode=lessons.admit(root,{'stage':'question_authoring','review_id':reviewed['id']},repo_root=repo,now=now)
        for kind,count,metric,percent in [('supported',6,'instruction_chars',1),('refuted',7,'context_bytes',15)]:
            case=decisions._case(base/'fresh'/kind,seed+kind,kind,count,metric,percent)
            cases.append({'arm':arm,'directory':arm+'/fresh/'+kind,**case})
        write_json(base/'progress.json',{'phase':'question','episode_id':episode['id'],'admitted_at':now,
            'question_passed':False,'practice_passed':False,'reuse':{},'preparation_blocked':False})
    for kind in ('supported','refuted'):
        if len({r['frozen_context_sha256'] for r in cases if r['kind']==kind})!=1:
            raise ValueError('paired_cycle_fresh_inputs_required')
    manifest={'version':'learning_cycle_v1','implementation':fingerprint(),'provider_identity':provider_identity,
        'prepared_process_id':PROCESS_ID,'seed':seed,'source_decision_id':decision_id,
        'source_decision_sha256':digest(basis['decision']),'source_episode_id':source_id,
        'source_usage_retained':read_json(live_root/'research_methods/episode_accounts'/(source_id+'.json'))['usage'],
        'source_files':{name:hashlib.sha256((repo_root/name).read_bytes()).hexdigest() for name in frozen_files},
        'cases':cases,'limits':{'model_calls':2*per_arm_calls,'per_arm_model_calls':per_arm_calls,
            'per_stage_model_calls':2,'per_stage_seconds':280,'per_stage_checks':26},
        'acceptance':'A planner-authored question, independent admission and static practice recheck, then successful handling on both fresh tasks after process restart. Verified reuse requires a checked applicability decision selecting the newly retained practice lesson and successful current action.',
        'control':'Equal task inputs, admission and call limits. No-memory arm receives current constraints and measurements, with historical lesson outcomes removed from its model input.',
        'scope':'local_method_learning_cycle_only','research_performance':'not_evaluated',
        'method_adoption_authorized':False,'scientific_progress_credited':False}
    manifest['sha256']=digest(manifest);write_json(output/'manifest.json',manifest)
    _save(output,{'calls':0,'inflight':None,'receipts':[]})
    return manifest


def load(output: Path, *, require_current_implementation: bool = True) -> tuple[dict[str,Any],dict[str,Any]]:
    manifest=read_json(output/'manifest.json');state=read_json(output/'evaluation.json')
    if (manifest.get('version')!='learning_cycle_v1' or manifest.get('sha256')!=digest({k:v for k,v in manifest.items() if k!='sha256'})
            or require_current_implementation and manifest['implementation']!=fingerprint()):
        raise ValueError('learning_cycle_manifest_changed')
    if state.get('sha256')!=digest({k:v for k,v in state.items() if k!='sha256'}) or state.get('inflight'):
        raise ValueError('learning_cycle_interrupted_or_changed_requires_review')
    if state['roots']!={arm:{'runtime':_tree(output/arm/'state'),'fresh':_tree(output/arm/'fresh'),
                            'progress':digest(read_json(output/arm/'progress.json'))} for arm in ARMS}:
        raise ValueError('learning_cycle_state_changed')
    for arm in ARMS:
        for name,sha in manifest['source_files'].items():
            from .learning_evidence import _inside
            if hashlib.sha256(_inside(output/arm/'repo',name).read_bytes()).hexdigest()!=sha:
                raise ValueError('learning_cycle_source_changed')
    for case in manifest['cases']:
        base=_inside(output,case['directory'])
        if digest(read_json(_inside(base/'state',case['parent_path'])))!=case['parent_sha256']:
            raise ValueError('learning_cycle_fresh_parent_changed')
        for name,sha in case['source_files'].items():
            if hashlib.sha256(_inside(base/'repo',name).read_bytes()).hexdigest()!=sha:
                raise ValueError('learning_cycle_fresh_source_changed')
    if not 0<=state['calls']<=manifest['limits']['model_calls']<=16 or len(set(state['receipts']))!=len(state['receipts']):
        raise ValueError('bounded_unique_cycle_receipts_required')
    actual_calls=0
    for key in state['receipts']:
        if not isinstance(key,str) or len(key)!=64 or any(c not in '0123456789abcdef' for c in key):
            raise ValueError('cycle_receipt_identity_required')
        receipt=read_json(output/'receipts'/(key+'.json'))
        if key!=receipt.get('sha256') or key!=digest({k:v for k,v in receipt.items() if k!='sha256'}):
            raise ValueError('cycle_receipt_integrity_failure')
        if receipt['arm'] not in ARMS or receipt['phase'] not in ('question','practice','reuse'):
            raise ValueError('owned_cycle_receipt_required')
        if receipt.get('attempt_id'):
            root=output/receipt['arm']/'state'
            if receipt['phase']=='reuse':
                if receipt['case_kind'] not in ('supported','refuted'):raise ValueError('owned_fresh_case_required')
                root=output/receipt['arm']/'fresh'/receipt['case_kind']/'state'
            attempt=records.read(root,'attempts',receipt['attempt_id'])
            if attempt['outcome']!=receipt['outcome'] or attempt['usage_after']!=receipt['usage']:
                raise ValueError('cycle_attempt_receipt_changed')
            actual_calls+=1
    if actual_calls!=state['calls']:raise ValueError('cycle_call_accounting_changed')
    return manifest,state


def _copy_method_evidence(source: Path, destination: Path) -> None:
    # Fresh tasks own new accounts; copy immutable evidence only.
    kinds=('practice_lessons','practice_questions','attempts','planning_candidates',
           'hypothesis_decisions','hypothesis_findings')
    for kind in kinds:
        for p in (source/'research_methods'/kind).glob('*.json'):
            target=destination/'research_methods'/kind/p.name;target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists() and target.read_bytes()!=p.read_bytes():raise ValueError('cycle_evidence_identity_collision')
            shutil.copy2(p,target)


def step(output: Path, *, planner: Callable | None = None) -> dict[str,Any]:
    output=output.resolve()
    with runtime.research_lease(output) as owned:
        if not owned:raise ValueError('learning_cycle_busy')
        manifest,state=load(output)
        if state['calls']>=manifest['limits']['model_calls']:
            for arm in ARMS:
                path=output/arm/'progress.json';progress=read_json(path)
                if progress['phase']!='complete':
                    write_json(path,{**progress,'phase':'complete','evaluation_budget_exhausted':True})
            _save(output,state)
            return summary(output)
        # Alternate arms; no arm receives the other's results.
        order=ARMS if len(state['receipts'])%2==0 else tuple(reversed(ARMS))
        for arm in order:
            base=output/arm;root=base/'state';repo=base/'repo';progress=read_json(base/'progress.json')
            if progress['phase']=='complete':continue
            arm_calls=sum(bool(r.get('attempt_id')) and r['arm']==arm
                for key in state['receipts'] for r in [read_json(output/'receipts'/(key+'.json'))])
            if arm_calls>=manifest['limits'].get('per_arm_model_calls',8):
                progress.update(phase='complete',evaluation_budget_exhausted=True)
                write_json(base/'progress.json',progress);continue
            if progress['phase']=='practice_admission':
                item=next(r for r in lessons.pending(root) if r.get('question_id')==progress['question_id'])
                episode=lessons.admit(root,item,repo_root=repo,
                    now=progress['admitted_at']+episodes.policy(root).get('admission_interval_seconds',86400))
                progress.update(phase='practice',episode_id=episode['id'])
            if progress['phase']=='reuse':
                case=next((c for c in manifest['cases'] if c['arm']==arm and c['kind'] not in progress['reuse']),None)
                if case is None:
                    progress['phase']='complete';write_json(base/'progress.json',progress);continue
                task_root=output/case['directory']/'state';task_repo=output/case['directory']/'repo'
                _copy_method_evidence(root,task_root)
                application.configure(task_root,enabled=arm=='with_memory',authority_reference='Frozen isolated restart reuse')
                task=read_json(task_root/'research_methods/episode_tasks'/(case['episode_id']+'.json'))
            else:
                case=None;task_root=root;task_repo=repo
                task=read_json(root/'research_methods/episode_tasks'/(progress['episode_id']+'.json'))
            if planner is None:
                from .provider_recovery import current_provider_identity
                if current_provider_identity()!=manifest['provider_identity']:raise ValueError('learning_cycle_provider_changed')
                actual=runtime.local_planner(dataclasses.replace(runtime.ResearchPolicy(),model_timeout_seconds=120,max_output_tokens=1800))
            else:actual=planner
            def invoke(phase,context):
                context=copy.deepcopy(context)
                context['resource_allowances']['cycle_calls_after_current']=manifest['limits'].get('per_arm_model_calls',8)-arm_calls-1
                if arm=='without_memory':
                    context['inputs']['hypothesis_memory']=[]
                    context['inputs']['hypothesis_history']=[]
                    if context['inputs'].get('question_opportunity'):
                        lesson=context['inputs']['question_opportunity']['lesson']
                        context['inputs']['question_opportunity']['lesson']={
                            'hypothesis':{'metric':lesson['hypothesis']['metric']},
                            'profile':{k:lesson['profile'][k] for k in ('instruction_mode','excerpt_chars','command_scope')},
                            'scope':'novelty_constraint_only_prior_outcomes_withheld'}
                if case:
                    context['inputs']['practice_observation']={'hypothesis':case['supplied_hypothesis'],
                        'profile':case['supplied_profile'],'measurement':case['measurement'],
                        'scope':'current_task_measurement_only'}
                def record_dispatch():
                    if getattr(invoke,'supports_dispatch_hook',False):invoke.dispatch_hook()
                    state['calls']+=1;state['inflight']={'arm':arm,'phase':progress['phase'],'reserved_seconds':120}
                    _save(output,state)
                old_hook=getattr(actual,'dispatch_hook',None)
                if getattr(actual,'supports_dispatch_hook',False):actual.dispatch_hook=record_dispatch
                else:record_dispatch()
                try:return actual(phase,context)
                finally:
                    if getattr(actual,'supports_dispatch_hook',False):actual.dispatch_hook=old_hook
                    invoke.last_metadata=getattr(actual,'last_metadata',{});invoke.last_raw_response=getattr(actual,'last_raw_response','')
            invoke.supports_dispatch_hook=getattr(actual,'supports_dispatch_hook',False)
            invoke.dispatch_hook=None
            before=task['model_calls'];stage=progress['phase']
            task=maintenance.advance(task_root,task,{'enabled':True},planner=invoke,repo_root=task_repo)
            attempt=records.read(task_root,'attempts',task['attempt_ids'][-1]) if task['model_calls']>before else None
            if attempt is None:
                progress.update(phase='complete',preparation_blocked=True)
            elif stage=='question':
                if task['state']=='completed_question_authoring':
                    progress.update(phase='practice_admission',question_passed=True,question_id=task['practice_question_id'],
                        question_process_id=PROCESS_ID)
                elif task['state']!='ready':progress['phase']='complete'
            elif stage=='practice':
                if task['state']!='ready':
                    try:
                        lesson=practice_lessons.review(root,progress['episode_id'],repo_root=repo)
                        progress.update(phase='reuse',practice_passed=True,practice_lesson_id=lesson['id'],practice_process_id=PROCESS_ID)
                    except (ValueError,KeyError,OSError) as exc:progress.update(phase='complete',practice_failure=str(exc))
            elif task['state']!='ready':
                passed=decisions._score(task_root,case,attempt)
                applied=attempt.get('lesson_application') or {}
                verified=bool(passed and applied.get('comparisons_verified') and
                    applied.get('authored',{}).get('lesson_id')==progress.get('practice_lesson_id') and
                    applied['authored']['decision'] in ('reuse','adapt') and PROCESS_ID!=progress.get('practice_process_id'))
                progress['reuse'][case['kind']]={'passed':passed,'verified_method_reuse':verified,'process_id':PROCESS_ID}
                if len(progress['reuse'])==2:progress['phase']='complete'
            receipt={'arm':arm,'phase':stage,'process_id':PROCESS_ID,'case_kind':case['kind'] if case else None,
                'attempt_id':attempt['id'] if attempt else None,'outcome':attempt['outcome'] if attempt else task['feedback'],
                'usage':attempt['usage_after'] if attempt else {},'provider_metadata':attempt.get('provider_metadata',{}) if attempt else {},
                'action_seconds':attempt['compute_seconds'] if attempt else 0,'progress':copy.deepcopy(progress)}
            receipt['sha256']=digest(receipt);write_json(output/'receipts'/(receipt['sha256']+'.json'),receipt)
            state['receipts'].append(receipt['sha256']);state['inflight']=None
            write_json(base/'progress.json',progress);_save(output,state)
            return summary(output)
        _save(output,state)
        return summary(output)


def summary(output: Path) -> dict[str,Any]:
    manifest,state=load(output);arms={}
    for arm in ARMS:
        row=read_json(output/arm/'progress.json')
        complete=row['phase']=='complete';reuse=list(row['reuse'].values())
        arms[arm]={**row,'complete':complete,'fresh_task_passes':sum(r['passed'] for r in reuse),
            'verified_reuse_passes':sum(r['verified_method_reuse'] for r in reuse),
            'cycle_completed_successfully':bool(row['question_passed'] and row['practice_passed'] and len(reuse)==2 and all(r['passed'] for r in reuse))}
    return {'complete':all(r['complete'] for r in arms.values()),'calls':state['calls'],'arms':arms,
        'scope':manifest['scope'],'research_performance':'not_evaluated',
        'general_advantage_established':False,'method_adoption_authorized':False,'scientific_progress_credited':False}


if __name__=='__main__':
    import argparse,json
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('prepare','step','summary'))
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--live-root',type=Path)
    parser.add_argument('--repo-root',type=Path);parser.add_argument('--decision-id')
    parser.add_argument('--per-arm-calls',type=int,default=8);args=parser.parse_args()
    if args.action=='prepare':
        from .provider_recovery import current_provider_identity
        result=prepare(args.output,live_root=args.live_root,decision_id=args.decision_id,
            repo_root=args.repo_root,provider_identity=current_provider_identity(),per_arm_calls=args.per_arm_calls)
        print(json.dumps({'manifest_sha256':result['sha256'],'limits':result['limits']}))
    else:
        result=step(args.output) if args.action=='step' else summary(args.output)
        write_json(args.output/'summary.json',result);print(json.dumps(result))
