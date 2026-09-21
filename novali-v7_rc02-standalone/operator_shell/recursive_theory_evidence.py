"""Attach existing governed 9D comparisons to capability generations, read-only."""
from pathlib import Path
from .research_tools import digest, read_json, identifier
from .recursive_capability_eval import checked, save
from .theory_workspace import TheoryWorkspace
from .theory_evaluators import evaluator_fingerprint
from .nine_d_testing import COMPARISON


def checkpoint(root: Path, output: Path, generation_name: str, evaluation_id: str, *, repo_root: Path | None = None) -> dict:
    generation=checked(output/'generations'/(identifier(generation_name)+'.json'))
    plan=checked(output/'plan.json')
    if generation['frozen_plan_sha256']!=plan['sha256']:raise ValueError('owned_capability_generation_required')
    workspace=TheoryWorkspace(root,'nine_d',repo_root=repo_root)
    receipt=workspace.read_record('evaluations',evaluation_id)
    if receipt['model_spec'].get('evaluator_id')!=COMPARISON:
        raise ValueError('complete_transition_comparison_receipt_required')
    contract=read_json(workspace._path('contracts',receipt['experiment_key']))
    if (digest(contract)!=receipt['contract_sha256'] or contract['model_spec']!=receipt['model_spec']
            or receipt['evaluator_sha256']!=evaluator_fingerprint(COMPARISON)):
        raise ValueError('current_frozen_9D_contract_required')
    assessment=receipt['assessment'];information=assessment.get('information_contract',{})
    variants=assessment.get('variants',{});costs=assessment.get('arm_costs',{})
    required={f'{arm}_{size}' for size in (3,9,12) for arm in ('candidate','generic','conventional_pca')}
    required|={f'candidate_without_{i}_9' for i in receipt['model_spec']['ablate_indices']}
    if (not assessment.get('baseline_fidelity_verified') or not information.get('same_rows_actions_history_and_preprocessing_access')
            or not required<=set(variants) or not all(len({costs[f'{arm}_{size}']['readout_parameters']
                for arm in ('candidate','generic','conventional_pca')})==1 for size in (3,9,12))):
        raise ValueError('matched_9D_controls_and_ablations_required')
    group={'snapshot_id':receipt['snapshot_id'],'evaluator_sha256':receipt['evaluator_sha256'],
           'observation':receipt['model_spec']['observation'],'partitions':assessment['partition_commitments'],
           'information_contract':information}
    result={'generation':generation_name,'evaluation_id':evaluation_id,'receipt_sha256':digest(receipt),
        'comparison_group':digest(group),'comparison_contract':group,'variants':variants,
        'phase_costs':assessment.get('phase_costs',{}),'representation_costs':assessment.get('representation_costs',{}),
        'checks':assessment['checks'],'mechanism_diagnostics':assessment.get('analytical_diagnostics',{}),
        'mechanism_scope':assessment.get('analytical_diagnostic_scope'),
        'interpretation':'Compare generations only within identical comparison_group; analytical mechanism diagnostics are separate from equal-information learned models.',
        'recursive_learning_causality':'not_established','scientific_allowance_added':0}
    path=output/'nine_d_checkpoints'/generation_name/(identifier(evaluation_id)+'.json')
    if path.exists():
        previous=checked(path)
        if {k:v for k,v in previous.items() if k!='sha256'}!=result:raise ValueError('immutable_9D_checkpoint_changed')
        return previous
    return save(path,result)
