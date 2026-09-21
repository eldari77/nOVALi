"""Independent workflow fixtures and acceptance; never used to author live work."""
from __future__ import annotations
import copy
from pathlib import Path
from typing import Any
from . import directive_candidates as candidates, directive_obligations as obligations, child_review
from .child_repairs import absent_method,finding_rows
from .research_tools import read_json,write_json,digest


def prepare_inputs(root: Path, adapter: str, *, seed_candidate: bool = True) -> dict[str, Any]:
    frozen={}
    for phase in ('train','reuse'):
        if adapter=='interface_contract':
            field='checked' if phase=='train' else 'indexed'
            data={'entries':[{'label':'entry alpha',field:True},{'label':'entry beta',**({field:None} if phase=='train' else {})}]}
            write_json(root/'conveyor/campaigns'/('directive-'+phase)/'drafts/validation_fixtures.json',data)
            folder=root/'conveyor/research/episodes'/('research-'+phase)
            contract=read_json(folder/'contract.json');state=read_json(folder/'state.json')
            contract['task']['directive_text']=(
                'Define and execute a proposed measurement on /entries in drafts/validation_fixtures.json. '
                +('Measure the fraction of records with a present checked field, with ratio >= 1.' if phase=='train' else
                  'For this different archive question, count records with a present indexed field, with count >= 2.')
                +' Missing fields count as absent; explicit unresolved values yield unknown. External truth remains unverified. '
                'Use measure_interface; choose an operational definition and falsifier, predict the derived value and outcome, and propose a reusable method.')
            state['contract_sha256']=digest(contract);write_json(folder/'contract.json',contract);write_json(folder/'state.json',state)
        frozen[phase]=obligations.build(root,'research-'+phase)
    if not seed_candidate: return frozen
    if adapter=='evidence_binding':return frozen  # Original rejected citations already supply the failure.
    context=obligations.projection(frozen['train']); selected=next(o for o in context['obligations'] if o['adapter']==adapter)
    if adapter=='record_extraction':
        record=context['records'][0]
        payload={'row_id':record['row_id'],'fields':[{'field':f,'state':candidates._value(record['record'],f)[0],
            'value':candidates._value(record['record'],f)[1]} for f in context['required_fields']]}
        finding={'scope':'method','path':'/method/steps','code':'no_reusable_procedure',
            'finding':'The supplied artifact extraction is acceptable but a reusable method has not been defined.',
            'verification':'Independently check complete current-input bindings. Artifact acceptance must remain separate from method adoption.'}
    else:
        payload={'module':'archive validator','responsibility':'Check records before handoff','input':'supplied records',
            'output':'bounded measurement result','artifact_ref':context['target_artifact'],
            'fixture_ref':'drafts/validation_fixtures.json','metric':'completeness','unit':'ratio','operator':'>=',
            'threshold':1,'invalid_input_behavior':'unknown_and_stop','assumptions':['Only frozen artifact contents are measured.']}
        finding={'scope':'artifact','path':'/payload/metric','code':'measurement_not_operational',
            'finding':'A completeness label does not define or execute the requested measurement.',
            'verification':'Bind the requested records and field, derive the specified quantity, and retain unknown values.'}
    response={'intent':'revise','obligation_id':selected['id'],'method':absent_method(adapter),'payload':payload,
        'rationale':'Frozen deficient evaluation proposal; this is not a live Novali output.','lesson_id':'none','lesson_use':'new'}
    seed=candidates.propose(root,frozen['train'],context,response,episode_id='frozen-seed',author='Independent evaluation fixture')
    candidates.review(root,seed['id'],decision='revise',reviewer='Frozen independent workflow reviewer',
        authority_reference='Isolated fixture with retained scoped findings',findings=[finding])
    frozen['train']=child_review.pending(root,candidate_id=seed['id'])[0]
    # Exercise rejection with unresolved findings, separately from all learning credit.
    rejected=candidates.propose(root,frozen['train'],obligations.projection(frozen['train']),response,
        episode_id='frozen-rejection-control',author='Independent rejection control')
    receipt=candidates.review(root,rejected['id'],decision='reject',reviewer='Frozen independent rejection control',
        authority_reference='Reject this unresolved fixture without claiming a repair')
    write_json(root/'workflow-rejection-control.json',{'candidate_id':rejected['id'],'review_id':receipt['id'],
        'unresolved_findings_retained':bool(receipt.get('unresolved_findings')),'learning_credit':False})
    return frozen


def judge(candidate: dict[str, Any]) -> list[dict[str, str]]:
    adapter=candidate['assessment']['adapter'];assessment=candidate['assessment'];payload=assessment['payload']
    if adapter=='evidence_binding':
        ok=bool(assessment.get('citation_replay',{}).get('original_verifier_passed') and payload.get('evidence_selection_receipts'))
        if not ok:return [{'scope':'artifact','path':'/payload','code':'original_citation_correction_required',
            'finding':'The original rejected citation was not repaired with a traceable cached selection.',
            'verification':'Replay the original claim verifier using source-linked selections.'}]
        if candidate['context'].get('relevance_contract'):
            relation=candidate['context'].get('relevance_assessment',{}).get('evidence_relation')
            if relation!='direct_support':
                return [{'scope':'artifact','path':'/evidence_use/relation','code':'relation_disagrees_with_retained_claim',
                    'finding':'These source passages reproduce the retained observation claims; the selected relation does not describe that agreement.',
                    'verification':'Compare the complete retained claim with its selected source passage and classify the actual relation.'}]
    if adapter=='interface_contract':
        train=candidate['frozen']['directive_id']=='directive-train'
        expected=('fraction_present','checked','ratio',1) if train else ('count_present','indexed','count',2)
        measured=payload.get('measurement_result',{});spec=payload.get('measurement',{})
        actual=(spec.get('operation'),spec.get('field'),payload.get('unit'),payload.get('threshold'))
        if (actual!=expected or payload.get('operator')!='>=' or measured.get('pointer')!='/entries'
                or measured.get('counterexamples') or measured.get('artifact_ref')!='drafts/validation_fixtures.json'):
            return [{'scope':'artifact','path':'/payload/measurement','code':'measurement_does_not_match_frozen_question',
                'finding':'The procedure did not execute the quantity requested for these current records.',
                'verification':'Recheck the current question, source, operation, field, units and threshold; do not substitute an easier metric.'}]
    return []


def acceptance(root: Path, candidate: dict[str, Any]) -> list[dict[str,str]]:
    findings=judge(candidate)
    if findings:
        candidates.review(root,candidate['id'],decision='reject',reviewer='Frozen independent semantic evaluator',
            authority_reference='Frozen workflow acceptance failed; no delivery or adoption')
        raise ValueError(findings[0]['code'])
    eligible=candidate['assessment'].get('method_assessment',{}).get('eligible_for_independent_adoption')
    return [{'finding_id':f['id'],'evidence_reference':'Independent frozen checker for candidate '+candidate['id'],
        'explanation':'The independent source and question checks passed for this finding scope.'}
        for f in finding_rows(candidate['context']) if f.get('scope','both')!='method' or eligible]
