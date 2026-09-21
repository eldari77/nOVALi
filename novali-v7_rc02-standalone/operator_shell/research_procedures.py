"""Novali-authored bounded methods, independently tested before operator adoption.

Procedures compose permitted pure primitives. They cannot execute arbitrary code,
acquire evidence, grant calls, or approve their own results.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import string
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

from .research_tools import digest, read_json, write_json, identifier
from . import executable_measurement as measurement

VERSION="research_procedures_v1"
STEPS=("select_unread_dependency", "validate_command_binding", "check_units", "check_limits",
       "check_validity", "compute_metric", "check_boundary_cases")
PRECONDITIONS=("claim_linked_unread_dependency", "explicit_measurement")
STOPS=("unknown_input", "failed_check", "budget_exhausted")


def store(root: Path, kind: str, body: Mapping[str, Any]) -> dict[str, Any]:
    payload={"version":VERSION,**dict(body),"grants_execution_authority":False,"scientific_progress_credited":False}
    key=kind.rstrip("s")+"-"+digest(payload)[:24]
    result={"id":key,**payload}; path=root/"research_methods"/kind/(key+".json")
    if path.exists():
        if read_json(path)!=result: raise ValueError("immutable_method_record_integrity_failure")
    else:write_json(path,result)
    return result


def read(root: Path, kind: str, key: str) -> dict[str, Any]:
    identifier(key)
    result=read_json(root/"research_methods"/kind/(key+".json"))
    body={k:v for k,v in result.items() if k!="id"}
    if not result or result.get("id")!=key or key!=kind.rstrip("s")+"-"+digest(body)[:24]:
        raise ValueError("immutable_method_record_integrity_failure")
    return result


def implementation() -> dict[str,str]:
    base=Path(__file__).parent
    return {name:hashlib.sha256((base/name).read_bytes()).hexdigest()
        for name in ("research_procedures.py","executable_measurement.py","planner_authoring.py","theory_methods.py",
            "research_maintenance.py","research_runtime.py","research_semantics.py","theory_runtime.py",
            "method_contracts.py","method_learning.py","method_patches.py","method_continuation.py","research_feedback.py",
            "method_repair.py","learning_episodes.py","planner_resources.py","resource_experiments.py",
            "action_budget.py","experiment_learning.py","authoring_contract.py","authoring_recovery.py","hypothesis_decisions.py",
            "authoring_intents.py","learning_evidence.py","lesson_practice.py","observable_scope.py","method_context.py","lesson_review_budget.py","question_settlement.py",
            "lesson_applicability.py","practice_transaction.py","measurement_cache.py","practice_lessons.py",
            "learning_cycle_evidence.py", "directive_obligations.py", "directive_candidates.py", "child_directive_learning.py",
            "child_contracts.py", "child_review.py", "child_delivery.py", "child_learning_evidence.py",
            "child_repairs.py", "child_context.py", "child_failure_learning.py", "child_review_findings.py",
            "child_planning.py", "child_procedure_programs.py", "child_research_actions.py", "child_evidence_selection.py", "child_measurements.py",
            "child_execution.py", "child_failure_patterns.py", "child_retention_eval.py", "child_correction.py", "child_refinement.py", "research_change_review.py", "child_relevance.py", "theory_transition.py", "next_practice.py", "practice_experiments.py", "successor_evidence.py", "question_partitions.py", "question_failure_learning.py", "question_semantics.py", "question_revision.py", "question_quality.py", "question_repair.py", "question_focus.py", "question_feedback.py", "question_measurements.py", "question_diagnosis.py", "repair_outcomes.py", "recursive_growth.py", "recursive_evaluator.py", "recursive_contract.py","recursive_practice_checks.py","recursive_failure_review.py","recursive_corrections.py","recursive_rejections.py","recursive_causal.py","recursive_loop.py","recursive_questions.py","recursive_review_queue.py","recursive_use.py","recursive_expansion.py")}


def proof_dependencies(family: str) -> dict[str, str]:
    """Versioned semantic dependency manifest; interface plumbing is excluded."""
    if family not in {"dependency", "measurement"}:
        raise ValueError("unsupported_method_proof_family")
    names = {"validate", "run", "_score", "freeze_suite", "evaluate", "proof_dependencies", "suite_current"}
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names
             or isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in
                {"VERSION", "STEPS", "PRECONDITIONS", "STOPS"} for t in node.targets)]
    result = {"contract": "method_proof_v2", "family": family,
        "procedure_semantics": digest([ast.dump(node, include_attributes=False) for node in nodes]),
        "research_tools.py": hashlib.sha256(Path(__file__).with_name("research_tools.py").read_bytes()).hexdigest()}
    if family == "measurement":
        result["executable_measurement.py"] = hashlib.sha256(Path(measurement.__file__).read_bytes()).hexdigest()
    return result


def suite_current(suite: Mapping[str, Any]) -> bool:
    expected = proof_dependencies(suite["family"]) if suite.get("proof_contract") == "method_proof_v2" else implementation()
    return suite["implementation"] == expected


def validate(candidate: Mapping[str,Any]) -> None:
    if not isinstance(candidate,dict) or set(candidate)!={"name","rationale","preconditions","steps","stop_conditions","selection","question","expected_outcome"}:
        raise ValueError("typed_procedure_candidate_required")
    for key in ("name","rationale","question"):
        if not isinstance(candidate[key],str) or not 8<=len(candidate[key])<=200:
            raise ValueError("bounded_procedure_description_required")
    if (not isinstance(candidate["preconditions"],list) or len(candidate["preconditions"])!=1
            or candidate["preconditions"][0] not in PRECONDITIONS):
        raise ValueError("explicit_procedure_precondition_required")
    steps=candidate["steps"]
    if not isinstance(steps,list) or not 1<=len(steps)<=6 or any(step not in STEPS for step in steps) or len(set(steps))!=len(steps):
        raise ValueError("bounded_permitted_procedure_steps_required")
    if not isinstance(candidate["stop_conditions"],list) or sorted(candidate["stop_conditions"])!=sorted(STOPS):
        raise ValueError("procedure_must_preserve_stop_conditions")
    if candidate["selection"] not in ("earliest_offset","source_order") or candidate["expected_outcome"] not in ("validated_dependency_command","checked_measurement"):
        raise ValueError("typed_procedure_outcome_required")
    if candidate["expected_outcome"]=="validated_dependency_command":
        fields=[]
        try:
            for _,field,format_spec,conversion in string.Formatter().parse(candidate["question"]):
                if field is not None:
                    if field not in {"claim_id","source_id","offset_chars"} or format_spec or conversion:
                        raise ValueError("bounded_current_input_question_placeholders_required")
                    fields.append(field)
        except ValueError as exc:raise ValueError("bounded_current_input_question_placeholders_required") from exc
        if set(fields)!={"claim_id","source_id","offset_chars"} or re.search(r"(?:claim|source)-[A-Za-z0-9]",candidate["question"]):
            raise ValueError("procedure_question_requires_current_claim_source_and_offset_placeholders")


def schema(family: str | None=None) -> dict[str,Any]:
    from .planner_authoring import _object,_string,_enum
    shape = _object({"name":_string(8,100),"rationale":_string(8,200),
        "preconditions":{"type":"array","minItems":1,"maxItems":1,"items":_enum(list(PRECONDITIONS))},
        "steps":{"type":"array","minItems":1,"maxItems":6,"items":_enum(list(STEPS))},
        "stop_conditions":{"const":list(STOPS)},"selection":_enum(["earliest_offset","source_order"]),
        "question":_string(8,160),"expected_outcome":_enum(["validated_dependency_command","checked_measurement"])})
    if family in ("dependency","measurement"):
        dependency=family=="dependency"
        shape["properties"]["preconditions"]={"const":["claim_linked_unread_dependency" if dependency else "explicit_measurement"]}
        shape["properties"]["expected_outcome"]={"const":"validated_dependency_command" if dependency else "checked_measurement"}
        shape["properties"]["steps"]={"type":"array","minItems":1,"maxItems":2 if dependency else 5,
            "items":_enum(list(STEPS[:2] if dependency else STEPS[2:]))}
    return shape


def run(candidate: Mapping[str,Any], inputs: Mapping[str,Any], *, step_limit: int=6) -> dict[str,Any]:
    validate(candidate)
    done=[]; command=None; assessment=None
    try:
        if len(candidate["steps"])>step_limit: raise ValueError("budget_exhausted")
        if candidate["preconditions"]==["claim_linked_unread_dependency"]:
            if not inputs.get("dependency_choices"): raise ValueError("unknown_input")
        elif not inputs.get("executable"):raise ValueError("unknown_input")
        for step in candidate["steps"]:
            if step=="select_unread_dependency":
                choices=inputs.get("dependency_choices",[])
                if not choices:raise ValueError("unknown_input")
                key=(lambda r:(r["offset_chars"],r["source_id"],r["claim_id"])) if candidate["selection"]=="earliest_offset" else (lambda r:(r["source_id"],r["offset_chars"],r["claim_id"]))
                selected=sorted(choices,key=key)[0]
                command={"command":"inspect_dependency","arguments":{**selected,"question":candidate["question"].format_map(selected)}}
            elif step=="validate_command_binding":
                if command is None:raise ValueError("select_dependency_before_binding")
                args=command["arguments"]
                if (set(args)!={"claim_id","source_id","offset_chars","question"}
                        or type(args["offset_chars"]) is not int or args["offset_chars"]<0):
                    raise ValueError("typed_dependency_check_required")
                identifier(args["claim_id"]);identifier(args["source_id"])
                if {k:v for k,v in args.items() if k!="question"} not in inputs["dependency_choices"]:
                    raise ValueError("unread_claim_linked_dependency_required")
            else:
                executable=inputs.get("executable")
                if not executable:raise ValueError("unknown_input")
                measurement.validate(executable["spec"])
                if step=="compute_metric":
                    if not {"check_units","check_limits","check_validity"}<=set(done):
                        raise ValueError("validate_measurement_before_computation")
                    assessment=measurement.check(executable["spec"],executable["cases"])
                elif step=="check_boundary_cases":
                    if "compute_metric" not in done:raise ValueError("compute_before_boundary_check")
                    assessment=measurement.check(executable["spec"],executable["cases"],require_coverage=True)
            done.append(step)
        if candidate["expected_outcome"]=="validated_dependency_command":
            if "validate_command_binding" not in done:raise ValueError("binding_check_required")
        elif "check_boundary_cases" not in done:raise ValueError("boundary_check_required")
        return {"state":"checked","command":command,"assessment":assessment,"steps_used":len(done),"grants_execution_authority":False}
    except (ValueError,KeyError,TypeError) as exc:
        return {"state":"stopped","reason":str(exc),"steps_used":len(done),"grants_execution_authority":False}


def freeze_suite(root: Path, family: str) -> dict[str,Any]:
    """Hidden cases and acceptance are fixed before candidate generation."""
    cases=[]
    if family=="dependency":
        for domain,offset in (("documents",93),("configuration",0),("source_analysis",4011)):
            cases.append({"domain":domain,"role":"withheld","inputs":{"dependency_choices":[
                {"claim_id":"claim-"+domain,"source_id":"source-unread-"+domain,"offset_chars":offset}]},"expected":"valid_command"})
        cases.append({"domain":"regression","role":"regression","inputs":{"dependency_choices":[]},"expected":"stop"})
    elif family=="measurement":
        for domain,unit,threshold in (("length","mm",3),("latency","ms",7),("inventory","count",2)):
            spec={"quantity":"bounded difference","unit":unit,"statistic":"max_absolute_error","reference":0,
                "comparison":"<","threshold":threshold,"threshold_unit":unit,"sample_count":1,
                "validity":{"minimum":0,"maximum":100,"required_evidence":["provenance"]},"invalid_outcome":"indeterminate",
                "unresolved":[],"limits":{"samples":1,"seconds":5,"attempts":1}}
            rows=[{"kind":kind,"values":[value],"unit":unit,"evidence":evidence,"seconds":1,"attempts":1,"expected":expected}
                for kind,value,evidence,expected in (("below",threshold-1,["provenance"],"pass"),
                    ("boundary",threshold,["provenance"],"fail"),("above",threshold+1,["provenance"],"fail"),("invalid",0,[],"indeterminate"))]
            if domain=="latency":rows[1]["expected"]="pass"  # The method must expose this counterexample.
            cases.append({"domain":domain,"role":"withheld","inputs":{"executable":{"spec":spec,"cases":rows}},
                "expected":"counterexample" if domain=="latency" else "checked_measurement"})
        cases.append({"domain":"regression","role":"regression","inputs":{},"expected":"stop"})
    else:raise ValueError("unsupported_method_family_requires_capability_request")
    baseline={"name":"Conventional guarded method","rationale":"Frozen conventional method for an equal-budget comparison.",
        "preconditions":["claim_linked_unread_dependency" if family=="dependency" else "explicit_measurement"],
        "steps":["select_unread_dependency","validate_command_binding"] if family=="dependency" else
            ["check_units","check_limits","check_validity","compute_metric","check_boundary_cases"],
        "stop_conditions":list(STOPS),"selection":"source_order","question":"Does {source_id} at {offset_chars} support {claim_id}?",
        "expected_outcome":"validated_dependency_command" if family=="dependency" else "checked_measurement"}
    return store(root,"suites",{"family":family,"implementation":proof_dependencies(family),
        "proof_contract":"method_proof_v2","cases":cases,
        "step_limit_per_arm":6,"acceptance":"All withheld and regression cases, identical after process restart; no regression against frozen conventional baseline.",
        "baseline":baseline, "max_case_executions":12})


def _score(result: Mapping[str,Any], case: Mapping[str,Any]) -> bool:
    expected=case["expected"]
    if expected=="stop":return result.get("state")=="stopped"
    if result.get("state")!="checked":return False
    if expected=="valid_command":
        cmd=result.get("command") or {}; args=cmd.get("arguments",{})
        return (cmd.get("command")=="inspect_dependency" and set(args)=={"claim_id","source_id","offset_chars","question"}
            and {k:v for k,v in args.items() if k!="question"} in case["inputs"]["dependency_choices"])
    assessment=result.get("assessment") or {}
    return bool(assessment.get("counterexamples")) if expected=="counterexample" else assessment.get("passed") is True


def evaluate(root: Path, candidate_id: str, *, suite_id: str | None=None) -> dict[str,Any]:
    candidate=read(root,"candidates",candidate_id); original=read(root,"suites",candidate["suite_id"])
    suite=read(root,"suites",suite_id or candidate["suite_id"])
    if suite["family"]!=original["family"]:raise ValueError("method_revalidation_family_mismatch")
    if not suite_current(suite):raise ValueError("method_evaluator_changed_after_freeze")
    rows=[]
    for case in suite["cases"]:
        result=run(candidate["procedure"],case["inputs"],step_limit=suite["step_limit_per_arm"])
        baseline_result=run(suite["baseline"],case["inputs"],step_limit=suite["step_limit_per_arm"])
        rows.append({"domain":case["domain"],"role":case["role"],"passed":_score(result,case),"result":result,
            "baseline_passed":_score(baseline_result,case),"baseline_steps_used":baseline_result["steps_used"]})
    request={"procedure":candidate["procedure"],"inputs":[c["inputs"] for c in suite["cases"]],"step_limit":suite["step_limit_per_arm"]}
    process=subprocess.run([sys.executable,"-B","-m","operator_shell.research_procedures"],input=json.dumps(request),
        text=True,capture_output=True,timeout=20,check=True)
    restarted=json.loads(process.stdout)
    retained=restarted==[row["result"] for row in rows]
    baseline=sum(row["baseline_passed"] for row in rows)
    passed=all(r["passed"] for r in rows) and retained and sum(r["passed"] for r in rows)>=baseline
    return store(root,"evaluations",{"candidate_id":candidate_id,"suite_id":suite["id"],"rows":rows,
        "restart_retained":retained,"baseline_passes":baseline,"candidate_passes":sum(r["passed"] for r in rows),
        "case_executions":len(rows)*3,"passed":passed,"evidence_scope":"bounded_primitive_method_transfer_only",
        "comparative_improvement_demonstrated":sum(r["passed"] for r in rows)>baseline,
        "live_research_growth_demonstrated":False})


def review(root: Path, candidate_id: str, evaluation_id: str, *, decision: str, reviewer: str, authority_reference: str) -> dict[str,Any]:
    if decision not in ("approve","deny","revoke") or not reviewer.strip() or not authority_reference.strip():
        raise ValueError("explicit_independent_method_review_required")
    candidate=read(root,"candidates",candidate_id); evaluation=read(root,"evaluations",evaluation_id)
    suite=read(root,"suites",evaluation["suite_id"])
    original=read(root,"suites",candidate["suite_id"])
    if evaluation["candidate_id"]!=candidate_id or suite["family"]!=original["family"]:
        raise ValueError("method_evaluation_binding_mismatch")
    if decision=="approve" and (not evaluation["passed"] or not suite_current(suite)):
        raise ValueError("verified_current_method_evaluation_required")
    replay_attempt_id=""
    if decision=="approve":
        for path in sorted((root/"research_methods/attempts").glob("*.json"),key=lambda p:p.stat().st_mtime_ns)[-128:]:
            attempt=read(root,"attempts",path.stem)
            if (attempt.get("candidate_id")==candidate_id and attempt.get("evaluation_id")==evaluation_id
                    and attempt.get("outcome",{}).get("state")=="checked"):
                replay_attempt_id=attempt["id"]
        if not replay_attempt_id:raise ValueError("linked_successful_practice_receipt_required")
    previous=read_json(root/"research_methods/adoptions"/(candidate_id+".json"))
    if previous:
        prior=read(root,"reviews",previous["review_id"])
        if prior["decision"]==decision and prior["evaluation_id"]==evaluation_id:return prior
        if prior["decision"] in ("deny","revoke") and decision=="approve":
            raise ValueError("changed_candidate_required_after_denial_or_revocation")
    result=store(root,"reviews",{"candidate_id":candidate_id,"evaluation_id":evaluation_id,"decision":decision,
        "reviewer":reviewer,"authority_reference":authority_reference,"replay_attempt_id":replay_attempt_id,
        "previous_review_id":previous.get("review_id","")})
    write_json(root/"research_methods/adoptions"/(candidate_id+".json"),{"review_id":result["id"]})
    return result


def context(root: Path) -> list[dict[str,Any]]:
    accepted=[]
    for path in sorted((root/"research_methods/adoptions").glob("*.json"))[-32:]:
        decision=read(root,"reviews",read_json(path)["review_id"])
        if decision["decision"]!="approve":continue
        candidate=read(root,"candidates",decision["candidate_id"])
        evaluation=read(root,"evaluations",decision["evaluation_id"])
        suite=read(root,"suites",evaluation["suite_id"])
        original=read(root,"suites",candidate["suite_id"])
        attempt=read(root,"attempts",decision["replay_attempt_id"])
        if (not suite_current(suite) or not evaluation["passed"]
                or suite["family"]!=original["family"] or evaluation["candidate_id"]!=candidate["id"] or attempt.get("candidate_id")!=candidate["id"]
                or attempt.get("evaluation_id")!=evaluation["id"] or attempt.get("outcome",{}).get("state")!="checked"):continue
        accepted.append({"id":candidate["id"],"procedure":candidate["procedure"],"review_id":decision["id"],
            "evidence_scope":evaluation["evidence_scope"],"automatic_execution":False})
    return accepted[-3:]


if __name__=="__main__":
    payload=json.load(sys.stdin)
    print(json.dumps([run(payload["procedure"],value,step_limit=payload["step_limit"]) for value in payload["inputs"]]))
