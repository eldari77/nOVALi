"""Registered independent evaluators. Candidate expressions are data, never Python."""
from __future__ import annotations

import ast
import hashlib
import itertools
from importlib import metadata
import math
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping

from .research_tools import digest, evaluate_expression

REGISTRY = {
    "finite_domain_v1": {"kind": "mathematical", "max_cases": 256, "wall_seconds": 30,
                         "scope": "exact rational propositions on an explicit finite domain"},
    "nine_d_forecast_v1": {"kind": "empirical", "train_cases": 96, "discovery_cases": 32,
        "holdout_cases": 64, "retention_cases": 32, "transfer_cases": 64, "feature_count": 9,
        "readout_parameters": 40, "expression_nodes_per_feature": 80, "wall_seconds": 45,
        "scope": "prediction in the registered explicit 9D simulator; no physical or consciousness validation"},
}
from .nine_d_testing import REGISTRY as TESTING_REGISTRY
REGISTRY.update(TESTING_REGISTRY)

RELATIONS = {"==": lambda a,b:a==b, "<=": lambda a,b:a<=b, ">=": lambda a,b:a>=b,
             "<": lambda a,b:a<b, ">": lambda a,b:a>b}
VARIABLES = ("x", "y", "z", "t1", "t2", "t3", "c1", "c2", "c3")


def evaluator_fingerprint(evaluator_id: str) -> str:
    if evaluator_id not in REGISTRY:
        raise ValueError("unregistered_theory_evaluator")
    files = [Path(__file__), Path(__file__).with_name("theory_worker.py"), Path(__file__).with_name("research_tools.py"),
             Path(__file__).with_name("theory_workspace.py")]
    if evaluator_id == "nine_d_forecast_v1" or evaluator_id in TESTING_REGISTRY:
        root = Path(__file__).resolve().parents[1]
        files.extend([root / "theory/nined_core.py", root / "environment/multi_agent_env.py"])
    if evaluator_id in TESTING_REGISTRY:
        files.extend([Path(__file__).with_name("nine_d_testing.py"), Path(__file__).with_name("experiment_contracts.py"), Path(__file__).with_name("nine_d_estimator_worker.py")])
    dependencies={"python":list(sys.version_info[:3])}
    for package in (["numpy","torch"] if evaluator_id=="nine_d_forecast_v1" or evaluator_id in TESTING_REGISTRY else []):
        try:dependencies[package]=metadata.version(package)
        except metadata.PackageNotFoundError:dependencies[package]="unavailable"
    return digest({"registry": REGISTRY[evaluator_id], "dependencies":dependencies,"sources": {
        str(p.name): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}})


def _fraction(value: Any) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)) or len(str(value)) > 80:
        raise ValueError("bounded_rational_required")
    number = Fraction(str(value))
    if number.numerator.bit_length() > 256 or number.denominator.bit_length() > 256:
        raise ValueError("rational_size_limit")
    return number


def rational_expression(expression: str, variables: Mapping[str, Fraction]) -> Fraction:
    if not isinstance(expression, str) or not 1 <= len(expression) <= 500:
        raise ValueError("bounded_formal_expression_required")
    tree = ast.parse(expression, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 80:
        raise ValueError("formal_expression_node_limit")
    def visit(node, depth=0):
        if depth > 16: raise ValueError("formal_expression_depth_limit")
        if isinstance(node, ast.Constant): return _fraction(node.value)
        if isinstance(node, ast.Name) and node.id in variables: return variables[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            result = visit(node.operand, depth+1)
            return -result if isinstance(node.op, ast.USub) else result
        if isinstance(node, ast.BinOp):
            a,b = visit(node.left, depth+1), visit(node.right, depth+1)
            if isinstance(node.op, ast.Add): result=a+b
            elif isinstance(node.op, ast.Sub): result=a-b
            elif isinstance(node.op, ast.Mult): result=a*b
            elif isinstance(node.op, ast.Div): result=a/b
            elif isinstance(node.op, ast.Pow) and b.denominator==1 and 0 <= b <= 8: result=a**int(b)
            else: raise ValueError("formal_operation_not_supported")
            return _fraction(str(result))
        raise ValueError("formal_operation_not_supported")
    return visit(tree.body)


def validate_spec(spec: Mapping[str, Any]) -> None:
    if not isinstance(spec, Mapping) or spec.get("evaluator_id") not in REGISTRY:
        raise ValueError("unregistered_theory_evaluator")
    if spec["evaluator_id"] in TESTING_REGISTRY:
        from .nine_d_testing import validate_spec as validate_testing_spec
        validate_testing_spec(spec)
        return
    if spec["evaluator_id"] == "finite_domain_v1":
        if set(spec)!={"evaluator_id","property"}:
            raise ValueError("explicit_finite_evaluator_contract_required")
        prop = spec.get("property", {})
        if not isinstance(prop, Mapping) or set(prop) != {"domains", "left", "relation", "right"}:
            raise ValueError("explicit_finite_proposition_required")
        domains = prop["domains"]
        if not isinstance(domains, Mapping) or not 1 <= len(domains) <= 4 or prop["relation"] not in RELATIONS:
            raise ValueError("finite_domain_contract_required")
        count = 1
        values = {}
        for name, items in domains.items():
            if not isinstance(name, str) or not name.isidentifier() or not isinstance(items, list) or not 1 <= len(items) <= 16:
                raise ValueError("bounded_finite_domain_required")
            count *= len(items); values[name] = _fraction(items[0])
            for item in items: _fraction(item)
        if count > 256: raise ValueError("finite_domain_case_limit")
        rational_expression(prop["left"], values); rational_expression(prop["right"], values)
    else:
        if set(spec) != {"evaluator_id", "features", "ablate_indices"}:
            raise ValueError("explicit_feature_revision_and_ablation_required")
        features, ablate = spec["features"], spec["ablate_indices"]
        if not isinstance(features, list) or len(features) != 9:
            raise ValueError("matched_nine_feature_capacity_required")
        if not isinstance(ablate, list) or not 1 <= len(ablate) <= 8 or any(type(i) is not int or not 0 <= i < 9 for i in ablate) or len(set(ablate))!=len(ablate):
            raise ValueError("explicit_mechanism_ablation_required")
        variables = {key:0.25 for key in (*VARIABLES, *("a_"+x for x in VARIABLES))}
        for expression in features: evaluate_expression(expression, variables)


def finite_domain(spec: Mapping[str, Any]) -> dict[str, Any]:
    validate_spec(spec)
    prop = spec["property"]; names = sorted(prop["domains"])
    bad=[]; checked=0
    for values in itertools.product(*(prop["domains"][key] for key in names)):
        inputs = {key:_fraction(value) for key,value in zip(names,values)}
        left,right = rational_expression(prop["left"],inputs), rational_expression(prop["right"],inputs)
        checked+=1
        if not RELATIONS[prop["relation"]](left,right):
            bad.append({"inputs":{k:str(v) for k,v in inputs.items()},"left":str(left),"right":str(right)})
    return {"formal_status":"counterexample_found" if bad else "verified_on_declared_finite_domain",
            "metrics":{"counterexample_count":len(bad),"checked_cases":checked}, "counterexamples":bad[:3],
            "machine_proposition":prop,"prose_statement_verified":False,
            "revision_eligible":not bad,"scope":REGISTRY["finite_domain_v1"]["scope"],
            "general_theorem_proved":False,"growth_demonstrated":False,"nine_d_advantage_demonstrated":False}


def nine_d_forecast(spec: Mapping[str, Any], seed: int) -> dict[str, Any]:
    """Fit equal-size readouts on fixed splits from the actual 9D environment.

    All variants see the same 18 state/action inputs, training rows and targets.
    Original uses the current simulator's deterministic transition as its feature
    map; alternatives use an ordinary linear map, a generic random 9D map, or the
    candidate's bounded equations. Representation complexity is reported, not
    silently equated with readout parameter count.
    """
    import numpy as np
    import torch
    from environment.multi_agent_env import MultiAgentEnvironment
    validate_spec(spec); torch.set_num_threads(1)
    settings=REGISTRY["nine_d_forecast_v1"]
    arrays={}; examples=[]
    with torch.random.fork_rng(devices=[]), torch.no_grad():
        for split_index, split in enumerate(("train","discovery","holdout","retention","transfer")):
            torch.manual_seed((seed+split_index*100003) % (2**63-1))
            env=MultiAgentEnvironment(state_dim=9,n_agents=3,device=torch.device("cpu"),
                core_coupling=0.12 if split=="transfer" else 0.08,
                phase_gain=0.09 if split=="transfer" else 0.06)
            original=MultiAgentEnvironment(state_dim=9,n_agents=3,device=torch.device("cpu"),noise_scale=0)
            rows=[]; targets=[]; native=[]
            for i in range(settings[split+"_cases"]):
                if i%16==0: env.reset()
                state=env.world.clone(); actions=2*torch.rand(3,9)-1
                if split=="retention": actions*=0.1
                mean=actions.mean(dim=0)
                original.world=state.clone(); original._update_explicit_9d_core(mean)
                native.append(original.world.numpy().copy())
                env.step(actions)
                rows.append(torch.cat([state,mean]).numpy().copy())
                targets.append(env.layout.project_to_4d(env.world)[0].numpy().copy())
            arrays[split]=(np.asarray(rows,dtype=float),np.asarray(targets,dtype=float),np.asarray(native,dtype=float))
    raw_train=arrays["train"][0]; mean=raw_train.mean(0); scale=np.maximum(raw_train.std(0),1e-6)
    projection=np.linalg.qr(np.random.default_rng(1907).normal(size=(18,9)))[0]
    def features(split, variant):
        raw,_,native=arrays[split]
        if variant=="original": return native.copy()
        if variant=="conventional": return (raw[:,:9]+raw[:,9:]).copy()
        if variant=="generic_nine": return ((raw-mean)/scale)@projection
        values=[]
        for row in raw:
            inputs=dict(zip((*VARIABLES,*("a_"+x for x in VARIABLES)),map(float,row)))
            values.append([evaluate_expression(expression,inputs) for expression in spec["features"]])
        return np.asarray(values,dtype=float)
    variants={}; errors={}; fitted={}
    for variant in ("original","conventional","generic_nine","candidate","ablation"):
        train=features("train",variant); center=train.mean(0); spread=np.maximum(train.std(0),1e-6)
        if variant=="ablation": train[:,spec["ablate_indices"]]=center[spec["ablate_indices"]]
        x=np.column_stack([np.ones(len(train)),(train-center)/spread]); y=arrays["train"][1]
        penalty=np.eye(10)*0.001; penalty[0,0]=0
        coefficients=np.linalg.solve(x.T@x+penalty,x.T@y)
        fitted[variant]=(center,spread,coefficients)
        losses={}
        for split in ("discovery","holdout","retention","transfer"):
            values=features(split,variant)
            if variant=="ablation": values[:,spec["ablate_indices"]]=center[spec["ablate_indices"]]
            prediction=np.column_stack([np.ones(len(values)),(values-center)/spread])@coefficients
            per_case=np.mean((prediction-arrays[split][1])**2,axis=1)
            errors[(variant,split)]=per_case
            losses[split+"_mse"]=float(per_case.mean())
        variants[variant]=losses
    # Check both a deterministic refit and parameter restoration in a fresh
    # interpreter. This is estimator retention, not general skill transfer.
    center,spread,coef=fitted["candidate"]
    fresh=features("train","candidate"); design=np.column_stack([np.ones(len(fresh)),(fresh-center)/spread])
    penalty=np.eye(10)*0.001;penalty[0,0]=0
    restored=np.linalg.solve(design.T@design+penalty,design.T@arrays["train"][1])
    reproducible=bool(np.allclose(restored,coef,rtol=1e-12,atol=1e-12))
    replay_payload={"features":features("holdout","candidate").tolist(),"center":center.tolist(),
                    "spread":spread.tolist(),"coefficients":coef.tolist(),"targets":arrays["holdout"][1].tolist()}
    replay_code=("import json,sys,numpy as n; p=json.load(sys.stdin); "
        "x=(n.asarray(p['features'])-p['center'])/p['spread']; "
        "y=n.column_stack([n.ones(len(x)),x])@n.asarray(p['coefficients']); "
        "print(float(n.mean((y-n.asarray(p['targets']))**2)))")
    replay=subprocess.run([sys.executable,"-B","-c",replay_code],input=json.dumps(replay_payload),
                          text=True,capture_output=True,timeout=10)
    if replay.returncode:raise ValueError("estimator_restart_verification_failed")
    restored_mse=float(replay.stdout.strip())
    restarted=math.isclose(restored_mse,variants["candidate"]["holdout_mse"],rel_tol=1e-10,abs_tol=1e-10)
    wins={}
    for baseline in ("original","conventional","generic_nine","ablation"):
        # Consecutive steps in one trajectory are correlated. Compare the four
        # reset trajectories rather than treating all 64 rows as independent.
        delta=(errors[(baseline,"holdout")]-errors[("candidate","holdout")]).reshape(-1,16).mean(1)
        margin=max(1e-6,0.01*variants[baseline]["holdout_mse"])
        wins[baseline]=bool(float(delta.mean())-2*float(delta.std(ddof=1))/math.sqrt(len(delta))>margin)
    retention=variants["candidate"]["retention_mse"]<=variants["original"]["retention_mse"]*1.05+1e-6
    transfer=all(variants["candidate"]["transfer_mse"]<variants[v]["transfer_mse"] for v in wins)
    discovery_delta=errors[("candidate","discovery")]-errors[("original","discovery")]
    for i in np.argsort(discovery_delta)[-3:][::-1]:
        if discovery_delta[i]<=1e-6:continue
        examples.append({"partition":"discovery", "inputs":dict(zip((*VARIABLES,*("a_"+x for x in VARIABLES)),
                        map(float,arrays["discovery"][0][i]))), "target_projection":arrays["discovery"][1][i].tolist(),
                        "candidate_excess_squared_error":float(discovery_delta[i])})
    metrics={"candidate_holdout_mse":variants["candidate"]["holdout_mse"],
             "candidate_gain":variants["original"]["holdout_mse"]-variants["candidate"]["holdout_mse"],
             "counterexample_count":int(sum(discovery_delta>1e-6))}
    estimator={"center":center.tolist(),"spread":spread.tolist(),"coefficients":coef.tolist(),
               "model_spec":dict(spec),"fit_scope":"training_partition_only"}
    return {"metrics":metrics,"variants":variants,"counterexamples":examples,"matched_readout_parameters":40,
            "matched_training_cases":96,"shared_input_count":18,"candidate_feature_count":9,
            "candidate_expression_nodes":sum(sum(1 for _ in ast.walk(ast.parse(e,mode="eval"))) for e in spec["features"]),
            "representation_complexity_matched":False,"holdout_comparisons_passed":wins,
            "comparison_rule":"four reset trajectory mean gains minus two standard errors exceed 1 percent or 1e-6; screening heuristic, not a significance proof",
            "retained_estimator":estimator,"retained_estimator_sha256":digest(estimator),
            "retention_passed":bool(retention),"transfer_passed":bool(transfer),"refit_reproducible":reproducible,
            "estimator_restart_verified":restarted,"restart_holdout_mse":restored_mse,
            "revision_eligible":bool(all(wins.values()) and retention and transfer and reproducible and restarted),
            "prose_statement_verified":False,"formal_status":"not_a_formal_proof",
            "scope":settings["scope"],"nine_d_advantage_demonstrated":False,"growth_demonstrated":False,
            "holdout_exposure":"aggregate_scores_only; adaptive selection remains possible",
            "dataset_commitments":{name:digest([raw.tolist(),target.tolist()]) for name,(raw,target,_) in arrays.items()}}


def evaluate_registered(spec: Mapping[str, Any], seed: int) -> dict[str, Any]:
    validate_spec(spec)
    if spec["evaluator_id"] in TESTING_REGISTRY:
        from .nine_d_testing import evaluate
        return evaluate(spec, seed)
    return finite_domain(spec) if spec["evaluator_id"]=="finite_domain_v1" else nine_d_forecast(spec, seed)
