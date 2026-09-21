"""Immutable claims, theory revisions and independently evaluated research decisions."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .research_tools import digest, identifier, read_json, write_json
from .theory_evaluators import REGISTRY, RELATIONS, evaluator_fingerprint, validate_spec

PUBLIC_KINDS={"sources","claims","revisions","evaluations","decisions"}
REPO_ROOT=Path(__file__).resolve().parents[1]


def text(value: Any, field: str, maximum=2000) -> str:
    if not isinstance(value,str) or not 8<=len(value.strip())<=maximum:
        raise ValueError("specific_"+field+"_required")
    return value.strip()


def strings(value: Any, field: str, *, minimum=0, maximum=12) -> list[str]:
    if not isinstance(value,list) or not minimum<=len(value)<=maximum or any(not isinstance(x,str) for x in value):
        raise ValueError("bounded_"+field+"_required")
    return value


class TheoryWorkspace:
    def __init__(self, root: Path, subject_id: str, *, repo_root: Path|None=None):
        self.root=Path(root); self.subject_id=identifier(subject_id)
        self.repo=(repo_root or REPO_ROOT).resolve()
        subjects=(self.root/"theory/subjects").resolve()
        self.base=(subjects/self.subject_id).resolve()
        if not self.base.is_relative_to(subjects): raise ValueError("theory_workspace_path_rejected")

    def _path(self, kind: str, key: str) -> Path:
        path=(self.base/kind/(identifier(key)+".json")).resolve()
        if not path.is_relative_to(self.base): raise ValueError("theory_workspace_path_rejected")
        return path

    def _store(self, kind: str, payload: Mapping[str,Any], prefix: str) -> dict[str,Any]:
        body={**copy.deepcopy(dict(payload)),"grants_execution_authority":False}
        key=prefix+"-"+digest(body)[:24]
        record={"id":key,**body};path=self._path(kind,key)
        if path.exists():
            if read_json(path)!=record: raise ValueError("immutable_theory_record_corrupt")
        else: write_json(path,record)
        return record

    def read_record(self, kind: str, key: str) -> dict[str,Any]:
        if kind not in PUBLIC_KINDS: raise ValueError("private_or_unknown_theory_record")
        record=read_json(self._path(kind,key))
        if not record: raise ValueError("theory_record_not_found")
        body={k:v for k,v in record.items() if k!="id"}
        prefix=key.rsplit("-",1)[0]
        if record.get("id")!=key or key!=prefix+"-"+digest(body)[:24]:
            raise ValueError("theory_record_integrity_failure")
        return record

    def initialize(self, *, publish: bool = True) -> dict[str,Any]:
        descriptor_path=(self.repo/"theory/subjects"/(self.subject_id+".json")).resolve()
        if not descriptor_path.is_relative_to(self.repo): raise ValueError("subject_path_rejected")
        config=read_json(descriptor_path,limit=24000)
        if not config: raise ValueError("unregistered_theory_subject")
        sources={}
        for reference in strings(config.get("sources"),"sources",minimum=1,maximum=8):
            relative=Path(reference)
            path=(self.repo/relative).resolve()
            if (relative.is_absolute() or ".." in relative.parts or not path.is_relative_to(self.repo)
                    or path.suffix not in {".py",".md",".json"} or path.stat().st_size>150000):
                raise ValueError("theory_source_path_or_size_rejected")
            content=path.read_text(encoding="utf-8")
            source=self._store("sources",{"path":relative.as_posix(),"content":content,
                "sha256":hashlib.sha256(path.read_bytes()).hexdigest()},"source")
            sources[source["id"]]={"path":relative.as_posix(),"sha256":source["sha256"],"characters":len(content)}
        evaluator_ids=strings(config.get("evaluator_ids"),"evaluators",minimum=1,maximum=4)
        if any(key not in REGISTRY for key in evaluator_ids): raise ValueError("unregistered_theory_evaluator")
        body={"subject_id":self.subject_id,"title":text(config.get("title"),"title"),
            "research_question":text(config.get("research_question"),"research_question"),"sources":sources,
            "evaluators":{key:{**REGISTRY[key],"sha256":evaluator_fingerprint(key)} for key in evaluator_ids}}
        snapshot_id="snapshot-"+digest(body)[:24]
        original=self._store("revisions",{"snapshot_id":snapshot_id,"parent_revision_id":None,"claim_ids":[],
            "changes":[],"model_spec":{"implementation":"registered_source_snapshot"},
            "status":"original_source_snapshot","sources":sources},"revision")
        snapshot={**body,"snapshot_id":snapshot_id,"original_revision_id":original["id"]}
        path=self.base/"snapshot.json"
        if publish and read_json(path)!=snapshot: write_json(path,snapshot)
        return snapshot

    def _snapshot(self) -> dict[str,Any]:
        snapshot=read_json(self.base/"snapshot.json")
        return snapshot or self.initialize()

    def assert_current_sources(self) -> None:
        for record in self._snapshot()["sources"].values():
            path=(self.repo/record["path"]).resolve()
            if not path.is_relative_to(self.repo) or hashlib.sha256(path.read_bytes()).hexdigest()!=record["sha256"]:
                raise ValueError("source_revision_changed")

    def _records(self, kind: str) -> list[dict[str,Any]]:
        paths=sorted((self.base/kind).glob("*.json"),key=lambda p:p.stat().st_mtime_ns)
        records=[]
        # Bound active context without invalidating or deleting older epochs.
        # Historical content-addressed records remain readable by their IDs.
        for path in paths[-128:]:
            records.append(self.read_record(kind,path.stem))
        return records

    def register_claim(self, claim: Mapping[str,Any]) -> dict[str,Any]:
        self.assert_current_sources(); snapshot=self._snapshot()
        if not isinstance(claim,Mapping) or len(json.dumps(claim,allow_nan=False))>16000:
            raise ValueError("bounded_theory_claim_required")
        kind=claim.get("kind")
        if kind not in {"mathematical","empirical","interpretive"}: raise ValueError("explicit_claim_kind_required")
        definitions=claim.get("definitions")
        if not isinstance(definitions,Mapping) or not 1<=len(definitions)<=12:
            raise ValueError("explicit_claim_definitions_required")
        definitions={str(k):text(v,"definition",500) for k,v in definitions.items()}
        assumptions=[text(x,"assumption",500) for x in strings(claim.get("assumptions"),"assumptions",minimum=1,maximum=8)]
        dependencies=strings(claim.get("dependencies",[]),"dependencies",maximum=8)
        for dep in dependencies:
            if self.read_record("claims",dep)["snapshot_id"]!=snapshot["snapshot_id"]:
                raise ValueError("dependency_source_revision_changed")
        source_ids=strings(claim.get("source_ids"),"source_ids",minimum=1,maximum=8)
        if any(key not in snapshot["sources"] for key in source_ids): raise ValueError("claim_source_binding_required")
        payload={"snapshot_id":snapshot["snapshot_id"],"kind":kind,"statement":text(claim.get("statement"),"statement"),
            "definitions":definitions,"assumptions":assumptions,"scope":text(claim.get("scope"),"scope"),
            "dependencies":dependencies,"source_ids":source_ids,"status":"unassessed"}
        if kind=="mathematical":
            formal=claim.get("formal_spec")
            validate_spec({"evaluator_id":"finite_domain_v1","property":formal})
            payload["formal_spec"]=formal
        else:
            payload["operationalization"]=text(claim.get("operationalization"),"operationalization")
            payload["falsification"]=text(claim.get("falsification"),"falsification")
        if sum(r["snapshot_id"]==snapshot["snapshot_id"] for r in self._records("claims"))>=64:
            raise ValueError("theory_claim_count_limit")
        return self._store("claims",payload,"claim")

    def propose_revision(self, proposal: Mapping[str,Any]) -> dict[str,Any]:
        self.assert_current_sources();snapshot=self._snapshot()
        parent=self.read_record("revisions",identifier(proposal.get("parent_revision_id")))
        if parent.get("snapshot_id")!=snapshot["snapshot_id"]: raise ValueError("revision_parent_source_changed")
        claim_ids=strings(proposal.get("claim_ids"),"claim_ids",minimum=1,maximum=8)
        claims=[self.read_record("claims",key) for key in claim_ids]
        if any(c["snapshot_id"]!=snapshot["snapshot_id"] for c in claims): raise ValueError("claim_source_revision_changed")
        spec=proposal.get("model_spec");validate_spec(spec)
        if spec["evaluator_id"] not in snapshot["evaluators"]: raise ValueError("evaluator_not_authorized_for_subject")
        if spec["evaluator_id"]=="finite_domain_v1" and any(c.get("formal_spec")!=spec["property"] for c in claims):
            raise ValueError("formal_proposition_must_match_claim")
        if spec["evaluator_id"]!="finite_domain_v1" and any(c["kind"]=="mathematical" for c in claims):
            raise ValueError("empirical_evaluation_cannot_prove_mathematical_claim")
        changes=proposal.get("changes")
        if not isinstance(changes,list) or not 1<=len(changes)<=8: raise ValueError("explicit_theory_changes_required")
        for change in changes:
            if not isinstance(change,dict) or change.get("target") not in {"definition","assumption","scope","equation","mechanism"}:
                raise ValueError("typed_theory_change_required")
            for field in ("before","after","reason"): text(change.get(field),field)
        predictions=proposal.get("predictions")
        if spec["evaluator_id"] == "nine_d_intervention_v1" and predictions != [{"metric": "effect_mean", **spec["hypothesis"]["prediction"]}]:
            raise ValueError("intervention_revision_prediction_must_match_machine_hypothesis")
        from .nine_d_testing import METRICS as testing_metrics
        allowed_metrics=set(testing_metrics.get(spec["evaluator_id"],
            {"counterexample_count","checked_cases"} if spec["evaluator_id"]=="finite_domain_v1" else {"candidate_holdout_mse","candidate_gain","counterexample_count"}))
        if not isinstance(predictions,list) or not 1<=len(predictions)<=4: raise ValueError("frozen_theory_predictions_required")
        for prediction in predictions:
            if (not isinstance(prediction,dict) or prediction.get("relation") not in RELATIONS
                    or prediction.get("metric") not in allowed_metrics
                    or type(prediction.get("value")) not in (int,float) or not math.isfinite(prediction["value"])):
                raise ValueError("measurable_theory_prediction_required")
        if sum(r["snapshot_id"]==snapshot["snapshot_id"] for r in self._records("revisions"))>=64:
            raise ValueError("theory_revision_count_limit")
        return self._store("revisions",{"snapshot_id":snapshot["snapshot_id"],"parent_revision_id":parent["id"],
            "claim_ids":claim_ids,"changes":changes,"model_spec":spec,"predictions":predictions,
            "mechanism":text(proposal.get("mechanism"),"mechanism"),
            "falsification":text(proposal.get("falsification"),"falsification"),"status":"proposed"},"revision")

    def _run_evaluator(self, contract: Mapping[str,Any], seed: int) -> dict[str,Any]:
        env={"PATH":os.defpath,"PYTHONDONTWRITEBYTECODE":"1","OMP_NUM_THREADS":"1","MKL_NUM_THREADS":"1",
             "OPENBLAS_NUM_THREADS":"1"}
        for key in ("SYSTEMROOT","WINDIR","TEMP","TMP"):
            if key in os.environ:env[key]=os.environ[key]
        payload={"model_spec":contract["model_spec"],"seed":seed,"evaluator_sha256":contract["evaluator_sha256"]}
        with tempfile.TemporaryDirectory(prefix="novali-theory-eval-") as working:
            result=subprocess.run([sys.executable,"-B",str(Path(__file__).with_name("theory_worker.py"))],
                input=json.dumps(payload),text=True,capture_output=True,cwd=working,env=env,
                timeout=REGISTRY[contract["evaluator_id"]]["wall_seconds"])
        if len(result.stdout)>200000: raise ValueError("evaluator_output_size_limit")
        parsed=json.loads(result.stdout)
        if result.returncode or parsed.get("error_class"):
            raise ValueError("registered_evaluator_failed: "+str(parsed.get("error","worker failed"))[:300])
        return parsed

    def _retention_reference(self, revision: Mapping[str,Any]) -> dict[str,Any]:
        evaluator = revision["model_spec"].get("evaluator_id")
        if evaluator not in {"nine_d_forecast_v1", "nine_d_comparison_v2"}:return {}
        accepted=read_json(self.base/"accepted.json")
        if (accepted.get("snapshot_id")!=revision["snapshot_id"] or not accepted.get("revision_id")
                or accepted["revision_id"]==revision["id"]):return {}
        decision=self.read_record("decisions",accepted["decision_id"])
        if decision["decision"]!="accept" or decision["revision_id"]!=accepted["revision_id"]:
            raise ValueError("accepted_revision_integrity_failure")
        receipt=self.read_record("evaluations",decision["evaluation_id"])
        if receipt["model_spec"].get("evaluator_id")!=evaluator:return {}
        if evaluator == "nine_d_comparison_v2" and receipt["model_spec"]["observation"] != revision["model_spec"]["observation"]:
            raise ValueError("accepted_observation_changed_requires_separate_research_subject")
        return {"revision_id":accepted["revision_id"],"evaluation_id":receipt["id"],
                "candidate_metrics":receipt["assessment"]["variants"]["candidate"]}

    def evaluate_revision(self, revision_id: str) -> dict[str,Any]:
        self.assert_current_sources();snapshot=self._snapshot(); revision=self.read_record("revisions",revision_id)
        if revision.get("snapshot_id")!=snapshot["snapshot_id"]: raise ValueError("revision_source_changed")
        spec=revision["model_spec"];validate_spec(spec); evaluator_id=spec["evaluator_id"]
        evaluator_hash=evaluator_fingerprint(evaluator_id)
        if evaluator_hash!=snapshot["evaluators"][evaluator_id]["sha256"]: raise ValueError("evaluator_revision_changed")
        retention_reference=self._retention_reference(revision)
        experiment_key="experiment-"+digest([snapshot["snapshot_id"],spec,evaluator_hash,retention_reference])[:24]
        pointer_path=self._path("experiment_index",experiment_key);existing=read_json(pointer_path)
        if existing.get("receipt_id"): return self.read_record("evaluations",existing["receipt_id"])
        if existing: raise ValueError("evaluation_interrupted_or_failed_budget_retained")
        existing_jobs=[read_json(p) for p in (self.base/"experiment_index").glob("*.json")]
        if sum(job.get("snapshot_id")==snapshot["snapshot_id"] for job in existing_jobs)>=6:
            raise ValueError("theory_evaluation_budget_exhausted")
        private_path=self._path("private",snapshot["snapshot_id"])
        private=read_json(private_path)
        if not private:
            private={"secret_seed":secrets.randbits(62)};write_json(private_path,private)
        contract={"snapshot_id":snapshot["snapshot_id"],"revision_id":revision_id,"evaluator_id":evaluator_id,
            "evaluator_sha256":evaluator_hash,"model_spec":spec,"predictions":revision["predictions"],
            "budget":REGISTRY[evaluator_id],"private_seed_commitment":digest(private),
            "retention_reference":retention_reference,
            "acceptance_rule":"registered evaluator controls; model predictions cannot change acceptance"}
        write_json(self._path("contracts",experiment_key),contract)
        write_json(pointer_path,{"snapshot_id":snapshot["snapshot_id"],"state":"running","contract_sha256":digest(contract)})
        try:
            assessment=self._run_evaluator(contract,private["secret_seed"])
            self.assert_current_sources()
            if evaluator_fingerprint(evaluator_id)!=evaluator_hash: raise ValueError("evaluator_revision_changed")
            if retention_reference:
                current=assessment["variants"]["candidate"]
                prior=retention_reference["candidate_metrics"]
                checks={key:current[key]<=prior[key]*1.05+1e-6 for key in ("holdout_mse","retention_mse","transfer_mse")}
                assessment["prior_revision_retention"]={"reference":retention_reference,"checks":checks,
                    "passed":all(checks.values()),"rule":"no more than 5 percent or 1e-6 loss regression on any registered partition"}
                assessment["revision_eligible"]=bool(assessment["revision_eligible"] and all(checks.values()))
            predictions=[]
            for row in revision["predictions"]:
                measured=assessment.get("metrics",{}).get(row["metric"])
                predictions.append({**row,"observed":measured,"passed":RELATIONS[row["relation"]](measured,row["value"]) if measured is not None else None})
            receipt=self._store("evaluations",{"snapshot_id":snapshot["snapshot_id"],"experiment_key":experiment_key,
                "evaluated_revision_id":revision_id,"model_spec":spec,"contract_sha256":digest(contract),
                "assessment":assessment,"prediction_results":predictions,"evaluator_sha256":evaluator_hash},"evaluation")
            write_json(pointer_path,{"snapshot_id":snapshot["snapshot_id"],"state":"completed","receipt_id":receipt["id"],
                "contract_sha256":digest(contract)})
            return receipt
        except Exception as exc:
            write_json(pointer_path,{"snapshot_id":snapshot["snapshot_id"],"state":"failed",
                "error_class":type(exc).__name__,"error":str(exc)[:400],"contract_sha256":digest(contract)})
            raise

    def decide_revision(self, revision_id: str, decision: str) -> dict[str,Any]:
        if decision not in {"accept","reject","revise"}: raise ValueError("explicit_revision_decision_required")
        self.assert_current_sources();revision=self.read_record("revisions",revision_id);snapshot=self._snapshot()
        if revision.get("snapshot_id")!=snapshot["snapshot_id"]: raise ValueError("revision_source_changed")
        receipts=[r for r in self._records("evaluations") if r["snapshot_id"]==snapshot["snapshot_id"] and r["model_spec"]==revision["model_spec"]]
        receipt=receipts[-1] if receipts else {}
        if receipt:
            contract=read_json(self._path("contracts",receipt["experiment_key"]))
            pointer=read_json(self._path("experiment_index",receipt["experiment_key"]))
            if (not contract or digest(contract)!=receipt["contract_sha256"]
                    or pointer.get("contract_sha256")!=receipt["contract_sha256"]
                    or pointer.get("receipt_id")!=receipt["id"]
                    or contract.get("model_spec")!=revision["model_spec"]):
                raise ValueError("evaluation_contract_integrity_failure")
            if evaluator_fingerprint(contract["evaluator_id"])!=receipt["evaluator_sha256"]:
                raise ValueError("evaluator_revision_changed")
            if decision=="accept" and contract.get("retention_reference",{})!=self._retention_reference(revision):
                raise ValueError("accepted_reference_changed_requires_evaluation")
        if decision=="accept" and (not receipt or not receipt["assessment"].get("revision_eligible")):
            raise ValueError("independent_evaluation_did_not_accept")
        result=self._store("decisions",{"snapshot_id":snapshot["snapshot_id"],"revision_id":revision_id,
            "decision":decision,"evaluation_id":receipt.get("id"),"acceptance_scope":receipt.get("assessment",{}).get("scope"),
            "prediction_provenance":"frozen_on_evaluated_revision" if receipt.get("evaluated_revision_id")==revision_id else "reused_receipt_from_equivalent_model_spec",
            "evaluated_revision_id":receipt.get("evaluated_revision_id"),
            "runtime_implementation_changed":False},"decision")
        if decision=="accept":
            write_json(self.base/"accepted.json",{"snapshot_id":snapshot["snapshot_id"],"revision_id":revision_id,
                "decision_id":result["id"],"grants_execution_authority":False})
        elif read_json(self.base/"accepted.json").get("revision_id")==revision_id:
            write_json(self.base/"accepted.json",{"snapshot_id":snapshot["snapshot_id"],"revision_id":None,
                "decision_id":result["id"],"grants_execution_authority":False})
        return result

    def public_context(self) -> dict[str,Any]:
        snapshot=self._snapshot(); epoch=snapshot["snapshot_id"]
        claims=[r for r in self._records("claims") if r["snapshot_id"]==epoch]
        revisions=[r for r in self._records("revisions") if r["snapshot_id"]==epoch and r.get("parent_revision_id")]
        evaluations=[r for r in self._records("evaluations") if r["snapshot_id"]==epoch]
        decisions=[r for r in self._records("decisions") if r["snapshot_id"]==epoch]
        frontier=[]
        for revision in revisions:
            matched=[e for e in evaluations if e["model_spec"]==revision["model_spec"]]
            decision=next((d for d in reversed(decisions) if d["revision_id"]==revision["id"]),{})
            if decision.get("decision") in {"accept","reject"}:continue
            reason=("counterexample_requires_refinement" if matched and not matched[-1]["assessment"].get("revision_eligible")
                    else "evaluated_revision_requires_decision" if matched else "untested_revision_requires_evaluation")
            frontier.append({"target_id":revision["id"],"reason":reason,"evaluation_id":matched[-1]["id"] if matched else None})
        used={c for revision in revisions for c in revision["claim_ids"]}
        frontier.extend({"target_id":c["id"],"reason":"unassessed_claim_requires_testable_revision"} for c in claims if c["id"] not in used)
        if not claims:frontier.append({"target_id":epoch,"reason":"extract_explicit_claim_from_sources"})
        accepted=read_json(self.base/"accepted.json")
        return {"subject":snapshot,"claims":claims[-12:],"revisions":[{k:v for k,v in r.items() if k!="model_spec"} for r in revisions[-8:]],
            "evaluations":[{"id":r["id"],"evaluated_revision_id":r["evaluated_revision_id"],"assessment":r["assessment"]} for r in evaluations[-4:]],
            "decisions":decisions[-8:],"frontier":frontier[:12],
            "accepted_revision_id":accepted.get("revision_id") if accepted.get("snapshot_id")==epoch else None,
            "grants_execution_authority":False}
