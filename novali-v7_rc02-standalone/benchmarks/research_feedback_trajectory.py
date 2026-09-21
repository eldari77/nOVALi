"""Frozen, opt-in real-planner feedback and transfer trials in isolated state.

Prepare once, run each step in a new process, independently review the training
revision against the frozen rubric, then run the withheld subjects. No fixture
request or review counts as a learned scientific result. No live state is used.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import shutil
from pathlib import Path

from operator_shell import theory_runtime as runtime
from operator_shell.research_episodes import ResearchPolicy
from operator_shell.research_feedback import publish_review, feedback_context
from operator_shell.research_runtime import local_planner
from operator_shell.research_tools import digest, read_json, write_json
from operator_shell.theory_workspace import TheoryWorkspace

CASES = [
    {"id":"sensor_correction", "role":"training", "domain":"instrumentation",
     "source":"Specify a missing acquisition capability to test maximum absolute error max(abs(x-5)) strictly below 0.2 V for exactly two detector readings against a 5 V reference. No detector runner is available. Verify that the calibration record matches the detector identity and covers the capture time. Missing or invalid readings or calibration make the result indeterminate. Bound acquisition to two samples, five seconds and one attempt. Provide independently checkable below, exact-boundary, above and invalid fixtures in the proposal. Do not execute acquisition or substitute a finite arithmetic claim for measurements.",
     "rubric":["max absolute error in V against 5 V, strict <0.2", "two acquired readings, calibrated matching identity/time", "missing or invalid evidence yields indeterminate", "at most 2 samples,5 seconds,1 attempt", "numerically correct below,boundary,above fixtures and invalid fixture", "every review finding linked; no execution or scientific credit"]},
    {"id":"ledger_transfer", "role":"withheld", "domain":"accounting",
     "source":"Specify a missing read-only reconciliation capability. Compare one ledger total and one signed invoice total, both integer currency minor units. Acceptance requires absolute difference strictly below 3 minor units. Validate invoice signature, matching account and currency, and integer input schema. Missing signatures or mismatched currency make the result indeterminate. No ledger or invoice reader exists here. Bound the read to two totals, seven seconds and one attempt. Supply below,boundary,above and invalid fixtures. Do not fabricate financial observations or execute a payment.",
     "rubric":["absolute difference in integer minor units, strict <3", "acquire two totals and validate signature/account/currency/schema", "correct boundary semantics and invalid indeterminate", "at most 2 samples,7 seconds,1 attempt", "procedural lesson available after process restart; no detector facts transferred"]},
    {"id":"queue_ambiguity", "role":"withheld", "domain":"distributed_systems",
     "source":"Investigate whether a queue service has p95 latency below 20 milliseconds at 100 requests per second. No request timing samples, service runner, or queue evaluator is available. The source does not define a percentile convention, observation window, warm-up, or timing calibration. Request the missing measurement capability and explicitly retain these unresolved choices. Do not choose missing source requirements or claim success from synthetic arithmetic. Propose a bounded trial scope while keeping its acceptance pending clarification.",
     "rubric":["p95 latency in ms at 100 requests/second", "acquisition distinguished from arithmetic", "percentile convention,window,warm-up,timing calibration remain unresolved", "bounded cost and no false specification readiness", "retained lesson applied without importing other domain facts"]},
]


def policy():
    return dataclasses.replace(ResearchPolicy(), enabled=True, theory_subject_ids=tuple(c['id'] for c in CASES),
        max_theory_model_calls=4,max_theory_tool_calls=6,max_theory_compute_seconds=720,
        max_theory_evaluations=1,max_output_tokens=1400,model_timeout_seconds=180)


def fingerprint():
    base = Path(__file__).resolve().parents[1]
    names = ["operator_shell/"+n+".py" for n in ("research_feedback","research_semantics","provider_recovery",
        "theory_runtime","theory_methods","theory_allowance","planner_authoring","research_context","research_runtime",
        "theory_workspace","theory_evaluators")]+["benchmarks/research_feedback_trajectory.py"]
    return {n:hashlib.sha256((base/n).read_bytes()).hexdigest() for n in names}


def prepare(output, retained_root=None):
    if (output/'manifest.json').exists(): raise ValueError('fresh_evaluation_directory_required')
    cases=[c for c in CASES if not retained_root or c['role']=='withheld']
    retained={}
    if retained_root:
        feedback_context(retained_root,retained_root/'theory/subjects/transfer_integrity_check')
        for folder in ('research_feedback','theory/subjects/sensor_correction'):
            for path in (retained_root/folder).rglob('*.json'):
                relative=path.relative_to(retained_root);retained[relative.as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
                destination=output/'state'/relative;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,destination)
    manifest = {"version":"research_feedback_trajectory_v1","cases":cases,"policy":dataclasses.asdict(policy()),
        "implementation_sha256":fingerprint(),"restart":"fresh process for each step",
        "acceptance":"Independent semantic review of complete trajectories against frozen per-case rubrics; structural validity alone is insufficient.",
        "comparative_growth_demonstrated":False,"setup_charges":"training source inspection and defective proposal each charge one fixture model call; transfer starts fresh",
        "maximum_real_provider_calls":8 if retained_root else 10,"live_research":False,
        "retained_evidence_sha256":retained,"retained_training_root":str(retained_root) if retained_root else None}
    manifest['sha256']=digest(manifest);write_json(output/'manifest.json',manifest)
    root,repo=output/'state',output/'repo'
    for case in cases:
        source=repo/(case['id']+'.md');source.parent.mkdir(parents=True,exist_ok=True);source.write_text(case['source'],encoding='utf-8')
        write_json(repo/'theory/subjects'/(case['id']+'.json'),{"title":"Synthetic semantic method evaluation",
            "research_question":"Read the source and resolve its capability specification. Preserve every unresolved source choice.",
            "sources":[source.name],"evaluator_ids":["finite_domain_v1"]})
        work=runtime.prepare_theory_work(root,case['id'],policy(),repo_root=repo)
        write_json(output/'work'/(case['id']+'.json'),work)
        if case['role']!='training':continue
        ws=TheoryWorkspace(root,case['id'],repo_root=repo);sid=next(iter(ws._snapshot()['sources']))
        runtime.advance_theory(root,work,policy(),repo_root=repo,planner=lambda *a:{'command':'inspect_source',
            'arguments':{'source_id':sid,'offset_chars':0},'why':'Controlled fixture acquisition of the training task source.'})
        contract={"quantity":"Detector readings","unit":"V","statistic":"unresolved","reference":"Reference requires inspection",
            "threshold_unit":"V","procedure":"Acquire a pair of detector readings.","calibration":"Use calibrated equipment.",
            "uncertainty":"Uncertainty requires an explicit method.","invalid_outcome":"indeterminate",
            "unresolved":["The exact metric remains to be defined from the source."],"cases":[],"limits":{"samples":2,"seconds":5,"attempts":1}}
        state=runtime.advance_theory(root,work,policy(),repo_root=repo,planner=lambda *a:{'command':'request_capability',
            'arguments':{'capability':'A bounded detector acquisition interface','why_needed':'No acquisition interface is currently available.',
                'acceptance_test':'Verify detector errors using a known input.','bounded_scope':'Two readings within five seconds in one attempt.',
                'measurement_contract':contract},'why':'Controlled defective proposal for the semantic correction challenge.'})
        target=state['observations'][-1]['result']['id']
        publish_review(root,ws._path('capability_requests',target),reviewer='Frozen independent fixture reviewer',
            authority_reference='Synthetic evaluation fixture; no live research authority',findings=[
                {'code':'metric_undefined','requirement':'Use the source-defined quantity, units, statistic, reference and strict threshold; do not substitute variance.'},
                {'code':'calibration_unverified','requirement':'Specify the source-required calibration verification and invalid-evidence outcome.'},
                {'code':'acceptance_incomplete','requirement':'Supply numerically checkable below, exact-boundary, above and invalid fixtures matching the comparison.'}])
    print(json.dumps({'manifest_sha256':manifest['sha256'],'prepared':True}),flush=True)


def step(output,subject):
    manifest=read_json(output/'manifest.json')
    if manifest['implementation_sha256']!=fingerprint():raise ValueError('implementation_changed_after_freeze')
    for name,sha in manifest.get('retained_evidence_sha256',{}).items():
        if hashlib.sha256((output/'state'/name).read_bytes()).hexdigest()!=sha:raise ValueError('retained_training_evidence_changed')
    if subject not in {c['id'] for c in manifest['cases']}:raise ValueError('unknown_frozen_case')
    root,repo=output/'state',output/'repo';work=read_json(output/'work'/(subject+'.json'))
    ws=TheoryWorkspace(root,subject,repo_root=repo)
    context=feedback_context(root,ws.base)
    state=runtime.advance_theory(root,work,policy(),repo_root=repo,planner=local_planner(policy()))
    row={'subject':subject,'state':state['state'],'usage':state['usage'],'feedback':state.get('feedback'),
        'review_ids_delivered':[r['id'] for r in context['pending_reviews']],
        'lesson_codes_delivered':[r['code'] for r in context['procedural_lessons']],
        'capabilities':[read_json(p) for p in (ws.base/'capability_requests').glob('*.json')],
        'semantic_review_required':True,'growth_demonstrated':False}
    write_json(output/'results'/(subject+'.json'),row)
    print(json.dumps({k:v for k,v in row.items() if k!='capabilities'}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--prepare',action='store_true');parser.add_argument('--step')
    parser.add_argument('--retained-root',type=Path)
    args=parser.parse_args()
    if args.prepare:prepare(args.output,args.retained_root)
    elif args.step:step(args.output,args.step)
    else:parser.error('--prepare or --step required')
