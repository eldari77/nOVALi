"""Frozen sandbox trajectories through the production theory planner and runtime.

The harness supplies fixtures, never research answers. Each CLI action starts a
fresh process. The scoring oracle and fixture manifests stay outside the prompt.
"""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import random
import time
import uuid
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

from . import research_procedures as procedures, theory_runtime as theory
from .research_episodes import ResearchPolicy
from .research_tools import digest, read_json, write_json
from .theory_workspace import TheoryWorkspace
from .theory_evaluators import rational_expression

PROCESS_ID = str(uuid.uuid4())


def fingerprint() -> dict[str, str]:
    names = ('production_planner_eval.py','theory_workspace.py','theory_evaluators.py','theory_worker.py',
             'theory_allowance.py','research_context.py')
    return {**procedures.implementation(), **{n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in names}}


def _policy() -> ResearchPolicy:
    return dataclasses.replace(ResearchPolicy(), enabled=True, max_theory_model_calls=9,
        max_theory_tool_calls=18,max_theory_compute_seconds=900,max_theory_evaluations=2,
        model_timeout_seconds=60,max_output_tokens=1400)


def prepare(output: Path, candidate: dict[str, Any], corrections: list[dict[str, Any]], *, provider_identity: dict[str, Any] | None = None,
            planning_profile: dict[str, Any] | None = None, prediction_contract: dict[str, Any] | None = None) -> dict[str, Any]:
    if (output/'manifest.json').exists() or (output/'state.json').exists():
        raise ValueError('fresh_production_evaluation_required')
    procedures.validate(candidate['procedure'])
    if planning_profile:
        from .planner_resources import validate, ADOPTION_CRITERIA
        validate(planning_profile)
    case_seed = uuid.uuid4().hex
    randomizer = random.Random(case_seed)
    cases=[]
    domains = [(name, randomizer.randint(2, 19), randomizer.randint(7, 101))
               for name in ('configuration', 'source_analysis')] + [('unresolved_latency',0,0)]
    for index,(name,scale,offset) in enumerate(domains):
        uncertain=scale==0
        spec={'quantity':'latency','unit':'ms','statistic':'unresolved','reference':0,'comparison':'<','threshold':randomizer.randint(30,80),
            'threshold_unit':'ms','sample_count':1,'validity':{'minimum':0,'maximum':100,'required_evidence':[]},
            'invalid_outcome':'indeterminate','unresolved':['calibration'], 'limits':{'samples':1,'seconds':5,'attempts':1}}
        fixture={'spec':spec,'cases':[{'kind':'below','values':[19],'unit':'ms','evidence':[],
                                     'seconds':1,'attempts':1,'expected':'pass'}]}
        question = ('Inspect the supplied latency setup and independently check its executable cases. Correct inconsistent case declarations while preserving the entire measurement specification and every unknown. Do not infer missing calibration.' if uncertain else
            'Inspect the unread normalize and expected functions. Form your own exact finite claim comparing their outputs for x in [-2, 0, 3], evaluate it with the registered finite evaluator, then record the justified decision. Keep the scope on these supplied functions.')
        arms=('with_guidance','without_guidance') if index%2==0 else ('without_guidance','with_guidance')
        for arm in arms:
            key=name+'/'+arm; directory=output/'trajectories'/name/arm
            repo=directory/'repo'; root=directory/'state'; (repo/'theory/subjects').mkdir(parents=True)
            prefix=('# Frozen case identity: '+case_seed+'\n'+
                '# Retained contextual note: navigation is not measured evidence.\n'*66)
            prefix=prefix[:4000].ljust(4000,' ')
            source=(prefix+'\n# Executable fixture follows.\nSETUP = '+repr(fixture)+'\n' if uncertain else
                prefix+f'\ndef normalize(x):\n    return ({scale}*x+{offset})-{offset}\ndef expected(x):\n    return {scale}*x\n')
            (repo/'notes.py').write_text(source,encoding='utf-8')
            write_json(repo/'theory/subjects/study.json',{'title':name,'sources':['notes.py'],
                'evaluator_ids':['finite_domain_v1'],'research_question':question})
            write_json(root/'autonomy/status.json',{'active':True,'emergency_stop':False})
            ws=TheoryWorkspace(root,'study',repo_root=repo); snapshot=ws.initialize()
            source_id=next(iter(snapshot['sources']))
            ws.register_claim({'kind':'interpretive','statement':'The supplied source contains a bounded question needing direct inspection.',
                'definitions':{'source':'A supplied sandbox fixture whose contents have not yet been established by this claim.'},
                'assumptions':['Navigation identifies text locations but does not verify any conclusion.'],
                'scope':'Only the supplied source and declared question.','source_ids':[source_id],'dependencies':[],
                'operationalization':'Inspect the source, then select the matching executable check.',
                'falsification':'Missing or contradictory source content prevents a definite conclusion.'})
            work=theory.prepare_theory_work(root,'study',_policy(),repo_root=repo)
            # A declared setup acquisition gives both arms identical retained
            # evidence and cost history. It is not a provider generation.
            seed=theory.advance_theory(root,work,_policy(),repo_root=repo,planner=lambda *a:{
                'command':'inspect_source','arguments':{'source_id':source_id,'offset_chars':0}})
            cases.append({'key':key,'domain':name,'arm':arm,'directory':directory.relative_to(output).as_posix(),
                'work':work,'source_sha256':hashlib.sha256((repo/'notes.py').read_bytes()).hexdigest(),
                'usage_before':seed['usage'],'initial_state_sha256':digest(seed),'maximum_calls':3 if uncertain else 6,
                'oracle':{'kind':'unresolved' if uncertain else 'finite','scale':scale,'spec':spec if uncertain else None,
                          'withheld_inputs':random.Random(case_seed+name).sample(list(range(-29,-3))+list(range(7,40)),3)}})
    manifest={'version':'production_planner_v2','case_seed':case_seed,
        'prediction_contract':copy.deepcopy(prediction_contract),
        'cases':cases,'candidate':candidate,'corrections':corrections,'implementation':fingerprint(),
        'planning_profile':planning_profile,
        'adoption_criteria':ADOPTION_CRITERIA if planning_profile else None,
        'provider_identity':provider_identity,
        'limits':{'model_calls':30,'compute_seconds':1800,'timeout_seconds':60},
        'acceptance':'Full production inspection, authored finite claim, independent evaluation and justified decision; unresolved measurements keep their specification and produce only indeterminate outcomes. Hidden function-output checks reject unrelated identities.',
        'arm_order':'Counterbalanced by domain; same case limits, provider and tools in both arms.',
        'evidence_scope':'isolated_production_planner_trajectories','scientific_progress_credited':False}
    manifest['sha256']=digest(manifest);write_json(output/'manifest.json',manifest)
    write_json(output/'state.json',{'usage':{'model_calls':0,'compute_seconds':0.0},'inflight':None,'trajectories':{}})
    return manifest


def _score(ws: TheoryWorkspace, case: dict[str, Any], state: dict[str, Any]) -> bool:
    rows=state.get('observations',[])
    acquired=state['usage']['tool_calls']>case['usage_before']['tool_calls'] and any(
        row['command']['command'] in {'inspect_dependency','inspect_source'} and row['command']['arguments'].get('offset_chars',0)>=4000 for row in rows)
    if not acquired:return False
    if case['oracle']['kind']=='unresolved':
        return any(r['command']['command']=='check_measurement' and r['command']['arguments'].get('spec')==case['oracle']['spec']
            and r['result'].get('passed') is True and all(v.get('actual')=='indeterminate' for v in r['result'].get('results',[]))
            for r in rows)
    for decision in ws._records('decisions'):
        if decision.get('decision')!='accept':continue
        revision=ws.read_record('revisions',decision['revision_id'])
        prop=revision.get('model_spec',{}).get('property',{})
        if prop.get('relation')!='==' or len(prop.get('domains',{}))!=1:continue
        variable=next(iter(prop['domains']))
        if set(prop['domains'][variable]) != {-2,0,3}:continue
        try:
            if all(rational_expression(prop[side],{variable:Fraction(x)})==case['oracle']['scale']*x
                for side in ('left','right') for x in case['oracle']['withheld_inputs']):return True
        except (ValueError,TypeError,ArithmeticError,SyntaxError):continue
    return False


def _load(output: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest=read_json(output/'manifest.json'); state=read_json(output/'state.json')
    if manifest.get('sha256')!=digest({k:v for k,v in manifest.items() if k!='sha256'}):
        raise ValueError('production_evaluation_manifest_integrity_failure')
    receipts=[]
    for path in (output/'attempts').glob('*.json'):
        receipt=read_json(path)
        if receipt.get('sha256')!=digest({k:v for k,v in receipt.items() if k!='sha256'}) or any(
            state['usage'][k]<v for k,v in receipt['usage_after'].items()):
            raise ValueError('production_evaluation_receipt_or_account_rollback')
        receipts.append(receipt)
    if not state.get('inflight'):
        if sum(r['calls'] for r in receipts)!=state['usage']['model_calls']:
            raise ValueError('production_evaluation_charge_history_mismatch')
        for case in manifest['cases']:
            attempts=sorted((r for r in receipts if r['trajectory']==case['key']),key=lambda r:len(r['task']['processes']))
            current=read_json(output/case['directory']/'state/theory/subjects/study/runs'/(case['work']['run_id']+'.json'))
            expected=attempts[-1]['run_sha256'] if attempts else case['initial_state_sha256']
            if digest(current)!=expected:
                raise ValueError('production_evaluation_run_projection_changed')
            if attempts and state['trajectories'].get(case['key'])!=attempts[-1]['task']:
                raise ValueError('production_evaluation_result_projection_changed')
    return manifest,state


def stage_progress(ws: TheoryWorkspace, state: dict[str, Any]) -> dict[str, Any]:
    observations = state.get('observations', [])
    return {'source_acquired':any(r['command']['command'] in {'inspect_dependency','inspect_source'}
                and r['command']['arguments'].get('offset_chars',0)>=4000 for r in observations),
        'formal_claims':sum(c.get('kind')=='mathematical' for c in ws._records('claims')),
        'evaluations':len(ws._records('evaluations')),'decisions':len(ws._records('decisions')),
        'measurement_checked':any(r['command']['command']=='check_measurement' for r in observations),
        'completed_commands':[r['command']['command'] for r in observations]}


def step(output: Path, *, planner: Callable) -> dict[str, Any]:
    manifest,account=_load(output)
    if manifest['implementation']!=fingerprint():raise ValueError('production_evaluation_implementation_changed')
    if manifest.get('provider_identity'):
        from .provider_recovery import current_provider_identity
        if current_provider_identity()!=manifest['provider_identity']:
            raise ValueError('frozen_evaluation_provider_changed')
    if account['inflight']:raise ValueError('interrupted_production_evaluation_requires_review')
    case=next((c for c in manifest['cases'] if account['trajectories'].get(c['key'],{}).get('state','ready')=='ready'),None)
    if case is None:return summary(output)
    key=case['key']; task=account['trajectories'].get(key,{'state':'ready','calls':0,'passed':False,'processes':[]})
    limits=manifest['limits']; remaining=limits['compute_seconds']-account['usage']['compute_seconds']
    if account['usage']['model_calls']>=limits['model_calls'] or remaining<1:raise ValueError('production_evaluation_budget_exhausted')
    directory=output/case['directory']; root=directory/'state';repo=directory/'repo'
    if hashlib.sha256((repo/'notes.py').read_bytes()).hexdigest()!=case['source_sha256']:raise ValueError('production_evaluation_source_changed')
    ws=TheoryWorkspace(root,'study',repo_root=repo)
    def project(context):
        result=copy.deepcopy(context)
        if case['arm']=='with_guidance' or manifest.get('planning_profile'):
            result['research_feedback']['adopted_procedures']=[manifest['candidate']]
            result['research_feedback']['reviewed_method_corrections']=manifest['corrections']
            if case['arm']=='with_guidance' and manifest.get('planning_profile'):
                result['planning_profile']=manifest['planning_profile']
        result['remaining_compute_seconds']=min(result['remaining_compute_seconds'],remaining,limits['timeout_seconds'])
        return result
    def invoke(phase,context):
        try:
            return planner(phase,project(context))
        finally:
            invoke.last_metadata=getattr(planner,'last_metadata',{})
            invoke.last_raw_response=getattr(planner,'last_raw_response','')
    if callable(getattr(planner,'preflight',None)):
        invoke.preflight=lambda phase,context:planner.preflight(phase,project(context))
    before=read_json(ws._path('runs',case['work']['run_id']))
    expected_calls=case['usage_before']['model_calls']+task['calls']
    if before['usage']['model_calls']!=expected_calls:raise ValueError('production_parent_usage_changed')
    reserved=min(remaining,limits['timeout_seconds']);account['usage']['compute_seconds']+=reserved
    account['inflight']={'trajectory':key,'reserved_seconds':reserved};write_json(output/'state.json',account)
    started=time.monotonic();error=None
    try:
        from .action_budget import ActionBudget
        state=theory.advance_theory(root,case['work'],_policy(),planner=invoke,repo_root=repo,
            action_budget=ActionBudget(reserved))
        task['passed']=_score(ws,case,state)
        if task['passed']:task['state']='completed'
        elif state['state'].startswith('waiting_'):task['state']='blocked'
    except (ValueError,OSError,KeyError,TypeError) as exc:
        error=str(exc);task['state']='blocked';state=read_json(ws._path('runs',case['work']['run_id']))
    elapsed=time.monotonic()-started
    calls=state['usage']['model_calls']-before['usage']['model_calls']
    account['usage']['model_calls']+=calls;account['usage']['compute_seconds']+=elapsed-reserved
    task['calls']+=calls;task['processes'].append(PROCESS_ID)
    if elapsed>reserved:task.update(state='budget_exceeded',passed=False)
    if task['calls']>=case['maximum_calls'] and task['state']=='ready':task['state']='exhausted'
    task['feedback']=error or state.get('feedback','');task['research_usage']=state['usage']
    if manifest.get('version') == 'production_planner_v2':
        task['stages'] = stage_progress(ws,state)
        if calls and len(task['processes'])>1 and PROCESS_ID not in task['processes'][:-1]:
            task['checkpoint_resumptions'] = task.get('checkpoint_resumptions',0)+1
        if manifest.get('planning_profile') and case['arm']=='with_guidance':
            from .planner_resources import signature
            applied = getattr(invoke,'last_metadata',{}).get('planning_profile_signature') == signature(manifest['planning_profile'])
            task['strategy_applied_every_action'] = task.get('strategy_applied_every_action',True) and applied
    receipt={'trajectory':key,'process_id':PROCESS_ID,'calls':calls,'task':copy.deepcopy(task),
        'usage_after':copy.deepcopy(account['usage']),'provider_metadata':getattr(invoke,'last_metadata',{}),
        'run_sha256':digest(state),'error':error}
    receipt['sha256']=digest(receipt)
    write_json(output/'attempts'/(key.replace('/','-')+'-'+str(len(task['processes']))+'.json'),receipt)
    account['inflight']=None;account['trajectories'][key]=task;write_json(output/'state.json',account)
    return {'trajectory':key,**task,'usage':account['usage']}


def summary(output: Path) -> dict[str, Any]:
    manifest,state=_load(output); rows=state['trajectories']
    complete=not state['inflight'] and len(rows)==len(manifest['cases']) and all(r['state']!='ready' for r in rows.values())
    counts={arm:sum(r['passed'] for k,r in rows.items() if k.endswith('/'+arm)) for arm in ('with_guidance','without_guidance')}
    result = {'complete':complete,'passes':counts,'cases_per_arm':len(manifest['cases'])//2,'usage':state['usage'],
        'trajectories':rows,'restart_retained':complete and all(len(set(r['processes']))==len(r['processes']) for r in rows.values()),
        'comparative_improvement_demonstrated':complete and counts['with_guidance']>counts['without_guidance'],
        'scientific_progress_credited':False,'evidence_scope':manifest['evidence_scope']}
    if manifest.get('version') == 'production_planner_v2':
        costs={arm:0.0 for arm in ('with_guidance','without_guidance')}; last=0.0
        for receipt in sorted((read_json(p) for p in (output/'attempts').glob('*.json')),
                              key=lambda r:(r['usage_after']['compute_seconds'],r['usage_after']['model_calls'])):
            current=receipt['usage_after']['compute_seconds']
            costs[receipt['trajectory'].split('/')[-1]]+=current-last;last=current
        result['arm_action_seconds']=costs
        result['checkpoint_integrity_retained'] = result['restart_retained']
        candidate_rows = [rows.get(c['key'],{}) for c in manifest['cases'] if c['arm']=='with_guidance']
        result['restart_retained'] = complete and all(r.get('passed') and r.get('calls',0)>=2
            and r.get('checkpoint_resumptions',0)>=1 and len(set(r['processes']))==len(r['processes'])
            and (not manifest.get('planning_profile') or r.get('strategy_applied_every_action')) for r in candidate_rows)
        result['retention_scope'] = 'successful_fresh_task_resumption_and_strategy_reuse'
    return result
