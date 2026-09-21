"""Fresh decision trajectories using a frozen live lesson and paired controls."""
from __future__ import annotations
import uuid
from pathlib import Path
from typing import Any
from . import decision_learning_eval as evaluation, lesson_practice
from .research_tools import digest, read_json, write_json


def prepare(output: Path, *, live_root: Path, decision_id: str, provider_identity: dict[str,Any], repo_root: Path | None = None) -> dict[str,Any]:
    output=output.resolve()
    if (output/'manifest.json').exists():raise ValueError('fresh_live_lesson_evaluation_required')
    basis=lesson_practice.source(live_root,decision_id,repo_root=repo_root)
    seed=uuid.uuid4().hex;cases=[]
    arms=['without_memory','with_memory','with_memory_focused']
    for index,(kind,count,metric,percent) in enumerate([
        ('supported',3,'instruction_chars',1),('refuted',5,'context_bytes',15),('unknown',4,'action_seconds',20)]):
        for arm in arms[index:]+arms[:index]:
            key='transfer/'+kind+'/'+arm
            case=evaluation._case(output/key,seed+kind,kind,count,metric,percent)
            cases.append({'key':key,'directory':key,'phase':'transfer','arm':arm,
                'context_projection':'evidence_focus_v1' if arm=='with_memory_focused' else 'full',**case})
        if len({c['frozen_context_sha256'] for c in cases if c['kind']==kind})!=1:
            raise ValueError('equal_input_comparison_required')
    manifest={'version':'live_lesson_transfer_v1','seed':seed,'implementation':evaluation.fingerprint(),
        'provider_identity':provider_identity,'prepared_process_id':evaluation.PROCESS_ID,'cases':cases,
        'live_lesson':basis['lesson'],'live_lesson_sha256':digest(basis['lesson']),
        'lesson_provenance':{'decision_id':decision_id,'decision_sha256':digest(basis['decision']),
            'source_episode_id':basis['episode']['id'],'scope':'real_planner_owned_completed_live_decision'},
        'limits':{'model_calls':18,'per_trajectory_calls':2,'per_trajectory_checks':26,'per_trajectory_seconds':280},
        'acceptance':'Freeze current measurements; score justified first action, recovery within two calls, and successful use of the live lesson on fresh tasks in a different process. Citation alone is insufficient. Compare identical tasks and budgets with no memory and full versus focused memory.',
        'cost_comparison':'Rotate arm order. Report provider loading, prompt, generation and complete action time. Speed comparisons require matching loading strata; nine trajectories cannot establish a general advantage.',
        'setup':'Benchmark hypotheses and local measurements, 18 setup checks, zero setup provider calls.',
        'research_performance':'not_evaluated','scientific_progress_credited':False,'grants_execution_authority':False}
    manifest['sha256']=digest(manifest);write_json(output/'manifest.json',manifest)
    write_json(output/'evaluation.json',{'calls':0,'inflight':None,'receipts':[]})
    return manifest


def summary(output: Path) -> dict[str,Any]:
    result=evaluation.summary(output);manifest,_,receipts=evaluation.load(output)
    if digest(manifest['live_lesson'])!=manifest['live_lesson_sha256']:raise ValueError('live_lesson_memory_changed')
    result['setup_checks']=18
    result['lesson_source']=manifest['lesson_provenance']
    result['costs']=[{'case':r['case'],'call':r['call'],'action_seconds':r['action_seconds'],
        'provider':r['provider_metadata']} for r in receipts]
    pairs=[]
    for kind in ('supported','refuted','unknown'):
        pair=[next((r for r in receipts if r['case']=='transfer/'+kind+'/'+arm and r['call']==1),None)
              for arm in ('with_memory','with_memory_focused')]
        if all(pair):
            full,focused=pair
            loads=[r['provider_metadata'].get('timing',{}).get('provider_load_seconds') for r in pair]
            # Cold/warm comparisons are not speed evidence.
            matched=all(type(v) in (int,float) and v<2 for v in loads)
            pairs.append({'kind':kind,'loading_matched':matched,
                'full_context_bytes':full['provider_metadata'].get('context_utf8_bytes'),
                'focused_context_bytes':focused['provider_metadata'].get('context_utf8_bytes'),
                'full_first_action_passed':full['passed'],'focused_first_action_passed':focused['passed'],
                'action_reduction_percent':100*(1-focused['action_seconds']/full['action_seconds']) if matched else None})
    result['context_comparison']=pairs
    result['general_advantage_established']=False
    return result


if __name__=='__main__':
    import argparse,json
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','step','summary'])
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--live-root',type=Path,default=Path('operator_state'))
    parser.add_argument('--decision-id');args=parser.parse_args()
    if args.action=='prepare':
        from .provider_recovery import current_provider_identity
        m=prepare(args.output,live_root=args.live_root,decision_id=args.decision_id,provider_identity=current_provider_identity())
        print(json.dumps({'manifest_sha256':m['sha256'],'limits':m['limits']}))
    else:
        if args.action=='step':evaluation.step(args.output)
        result=summary(args.output);write_json(args.output/'summary.json',result)
        print(json.dumps({k:result[k] for k in ('complete','calls','comparison','restart_reuse_passes')}))
