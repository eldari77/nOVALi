"""Matched interface comparison; correction and downstream learning stay separate."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from . import successor_cycle_eval as cycle
from .research_tools import digest


def prepare(output: Path, *, model: str, provider_seconds: int = 120, executable_measurements: bool = False, diagnosed_corrections: bool = False) -> dict[str, Any]:
    if output.exists():raise ValueError('fresh_correction_comparison_required')
    manifests={}
    for arm in ('existing','focused'):
        manifests[arm]=cycle.prepare(output/arm,model=model,provider_seconds=provider_seconds,
            structured_experiments=True,semantic_experiments=True,compact_methods=True,
            repairable_questions=True,context_pressure=True,focused_corrections=diagnosed_corrections or arm=='focused',
            executable_measurements=executable_measurements and (diagnosed_corrections or arm=='focused'),
            diagnosed_corrections=diagnosed_corrections and arm=='focused')
    cycle.save(output/'comparison.json',{'version':'question_correction_comparison_v1',
        'manifests':{arm:m['sha256'] for arm,m in manifests.items()},
        'model':model,'limits':manifests['existing']['limits'],
        'executable_measurements':executable_measurements,'diagnosed_corrections':diagnosed_corrections,
        'difference':'Focused working projection, instructions and action/check edits; optional registered cached projection instruments. No supplied research answer.',
        'acceptance':'Substantive repair of an owned failure, independent question approval, accepted consumed work and verified reuse after restart are separate requirements.',
        'scientific_progress_credited':False})
    return summary(output)


def summary(output: Path) -> dict[str, Any]:
    frozen=cycle.checked(output/'comparison.json')
    data={arm:cycle.load(output/arm) for arm in ('existing','focused')}
    for arm,(manifest,state) in data.items():
        if frozen['manifests'][arm]!=manifest['sha256']:raise ValueError('frozen_interface_comparison_changed')
        if manifest['limits']!=frozen['limits'] or manifest['model']!=frozen['model']:
            raise ValueError('equal_interface_budgets_and_provider_required')
    first,second=(data[arm][0] for arm in ('existing','focused'))
    if first['fingerprint']!=second['fingerprint']:raise ValueError('matched_interface_implementation_required')
    if frozen.get('diagnosed_corrections'):
        if first.get('diagnosed_corrections') or not second.get('diagnosed_corrections') or not first['focused_corrections']:raise ValueError('distinct_frozen_diagnosis_interfaces_required')
    elif first['focused_corrections'] or not second['focused_corrections']:raise ValueError('distinct_frozen_interfaces_required')
    inputs=lambda m:[(c['name'],digest(c['inputs']),c['question_choices_sha256']) for c in m['cases']]
    if inputs(first)!=inputs(second):raise ValueError('equal_interface_inputs_required')
    return {'version':frozen['version'],'arms':{arm:cycle.summary(output/arm) for arm in data},
        'limits_per_interface':frozen['limits'],
        'interpretation':'Question correction is not method acquisition; restart or retention cannot pass unless accepted downstream work and verified fresh reuse occur.'}
