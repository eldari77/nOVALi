"""Versioned simulator instruments. The planner supplies hypotheses, never code.

The independent reference includes the outer update and both clamp stages.
Observation maps are applied before feature evaluation. Hidden states are never
passed to projected/history predictors. Simulator results have simulator scope.
"""
from __future__ import annotations

import ast
import hashlib
import time
from pathlib import Path
from typing import Any, Mapping

from .experiment_contracts import fields, integer, interval_outcome, number, validate_hypothesis
from .research_tools import digest, evaluate_expression

VERSION = "nine_d_complete_transition_v2"
INTERVENTION = "nine_d_intervention_v1"
COMPARISON = "nine_d_comparison_v2"
VARIABLES = ("x", "y", "z", "t1", "t2", "t3", "c1", "c2", "c3")
DEFAULTS = {"world_decay": .01, "social_gain": .02, "core_coupling": .08,
            "entropy_gain": .08, "phase_gain": .06, "consciousness_gain": .10}
WIDTHS = (3, 9, 12)
SPLITS = {"train": 96, "discovery": 32, "holdout": 64, "retention": 32, "transfer": 64}
REGISTRY = {
    INTERVENTION: {"kind": "empirical", "wall_seconds": 45, "max_steps": 8,
        "discovery_pairs": 4, "independent_pairs": 8,
        "scope": "paired interventions on declared simulator states only; no physical interpretation"},
    COMPARISON: {"kind": "empirical", "wall_seconds": 45, "partitions": SPLITS,
        "widths": list(WIDTHS), "max_expression_nodes": 80, "max_ablation_groups": 3,
        "scope": "matched-information synthetic forecasting; dimensions are not evidence of physical ontology"},
}
METRICS = {INTERVENTION: ["effect_mean", "effect_lower", "effect_upper"],
           COMPARISON: ["candidate_gain", "candidate_holdout_mse", "counterexample_count"]}


def observation_names(observation: Mapping[str, Any]) -> list[str]:
    fields(observation, {"mode", "history_steps"}, "observation")
    mode = observation["mode"]
    if mode not in ("full", "projected", "history"):
        raise ValueError("observation.mode: full, projected or history required")
    depth = integer(observation["history_steps"], 1, 4, "observation.history_steps")
    if (mode == "history" and depth < 2) or (mode != "history" and depth != 1):
        raise ValueError("observation.history_steps: full/projected require 1; history requires 2..4")
    if mode == "full":
        names = list(VARIABLES)
    else:
        names = [f"o{lag}_{axis}" for lag in range(depth) for axis in ("x", "y", "z", "t")]
    # Every arm receives the same known control, including non-spatial actions.
    return names + ["a_" + name for name in VARIABLES]


def validate_spec(spec: Mapping[str, Any]) -> None:
    evaluator = spec.get("evaluator_id")
    if evaluator == INTERVENTION:
        fields(spec, {"evaluator_id", "hypothesis", "controls", "intervention", "observation", "observable", "noise_scale"}, "model_spec")
        validate_hypothesis(spec["hypothesis"])
        control = spec["controls"]
        fields(control, {"initial_state", "actions", "steps", "parameters"}, "controls")
        if not isinstance(control["initial_state"], list) or len(control["initial_state"]) != 9:
            raise ValueError("controls.initial_state: all nine coordinates required")
        for i, value in enumerate(control["initial_state"]):
            number(value, -100, 100, f"controls.initial_state[{i}]")
        if not isinstance(control["actions"], list) or len(control["actions"]) != 3:
            raise ValueError("controls.actions: three agent vectors required")
        for i, row in enumerate(control["actions"]):
            if not isinstance(row, list) or len(row) != 9:
                raise ValueError(f"controls.actions[{i}]: nine action values required")
            for j, value in enumerate(row):
                number(value, -1, 1, f"controls.actions[{i}][{j}]")
        integer(control["steps"], 1, 8, "controls.steps")
        fields(control["parameters"], set(DEFAULTS), "controls.parameters")
        for name, value in control["parameters"].items():
            number(value, 0, .25, "controls.parameters." + name)
        change = spec["intervention"]
        fields(change, {"target", "name", "value"}, "intervention")
        target, name = change["target"], change["name"]
        if target == "parameter" and name in DEFAULTS:
            old = control["parameters"][name]
            number(change["value"], 0, .25, "intervention.value")
        elif target in ("state", "action") and name in VARIABLES:
            index = VARIABLES.index(name)
            old = control["initial_state"][index] if target == "state" else None
            bound = 100 if target == "state" else 1
            number(change["value"], -bound, bound, "intervention.value")
            if target == "action" and all(row[index] == change["value"] for row in control["actions"]):
                raise ValueError("intervention: changed action required")
        else:
            raise ValueError("intervention: one registered state, action or parameter required")
        if old == change["value"]:
            raise ValueError("intervention: substantive controlled change required")
        observation_names(spec["observation"])
        observable = spec["observable"]
        fields(observable, {"index", "statistic", "unit"}, "observable")
        integer(observable["index"], 0, 8 if spec["observation"]["mode"] == "full" else 3, "observable.index")
        if observable["statistic"] not in ("final_difference", "history_mean_difference") or observable["unit"] != "simulator_coordinate":
            raise ValueError("observable: registered statistic and simulator_coordinate unit required")
        if observable["statistic"] == "history_mean_difference" and (spec["observation"]["mode"] != "history" or control["steps"] < spec["observation"]["history_steps"]):
            raise ValueError("observable: enough post-intervention history steps required")
        if type(spec["noise_scale"]) not in (float, int) or spec["noise_scale"] not in (0, .01):
            raise ValueError("noise_scale: registered 0 or 0.01 regime required")
    elif evaluator == COMPARISON:
        fields(spec, {"evaluator_id", "observation", "features", "ablate_indices", "disable_parameters"}, "model_spec")
        names = observation_names(spec["observation"])
        if not isinstance(spec["features"], list) or len(spec["features"]) != 12:
            raise ValueError("features: twelve ordered expressions required; prefixes define widths 3, 9 and 12")
        for index, expression in enumerate(spec["features"]):
            try:
                evaluate_expression(expression, dict.fromkeys(names, .25))
            except (ValueError, TypeError, SyntaxError, ArithmeticError) as exc:
                raise ValueError(f"features[{index}]: {exc}") from exc
        ablations = spec["ablate_indices"]
        if not isinstance(ablations, list) or not 1 <= len(ablations) <= 3 or any(type(i) is not int or not 0 <= i < 9 for i in ablations) or len(set(ablations)) != len(ablations):
            raise ValueError("ablate_indices: one to three unique feature indices 0..8 required")
        disabled = spec["disable_parameters"]
        if not isinstance(disabled, list) or len(disabled) > 3 or any(type(k) is not str or k not in DEFAULTS for k in disabled) or len(set(disabled)) != len(disabled):
            raise ValueError("disable_parameters: up to three distinct registered mechanisms required")
        if disabled and spec["observation"]["mode"] != "full":
            raise ValueError("disable_parameters: transition predictor requires full observation; use paired interventions for partial observations")
    else:
        raise ValueError("unregistered_theory_evaluator")


def transition_reference(state, mean_action, parameters: Mapping[str, float]):
    """Independent float64 reference for the complete deterministic 9D world step."""
    import torch
    prev = (1 - parameters["world_decay"]) * state + parameters["social_gain"] * mean_action
    spatial_next = prev[:3] + parameters["social_gain"] * (mean_action[:3] + parameters["core_coupling"] * torch.tanh(prev[6:9]))
    spatial = torch.tanh(spatial_next)
    motion = torch.linalg.vector_norm(spatial - prev[:3])
    t2 = prev[4] + parameters["entropy_gain"] * (motion + .5 * (mean_action ** 2).mean() - .15 * prev[8])
    t3 = torch.tanh(prev[5] + parameters["phase_gain"] * (mean_action[5] + .5 * prev[4] + .3 * prev[7]))
    gain = 2 * parameters["consciousness_gain"]
    c1 = torch.sigmoid(gain * (torch.linalg.vector_norm(spatial_next) + 1 / (1 + motion) + .25 * prev[8]))
    c2 = torch.sigmoid(gain * (1 / (1 + torch.abs(t2)) + .5 * torch.cos(t3) + .25 * prev[6]))
    c3 = torch.sigmoid(gain * (.6 * c2 + .4 * c1 - .2 * torch.abs(t2) + .2 * torch.cos(t3)))
    # The simulator clamps twice: once inside the update, again in clamp_core.
    return torch.cat((torch.tanh(spatial), (prev[3] + 1).reshape(1),
        torch.tanh(torch.tanh(t2)).reshape(1), torch.tanh(t3).reshape(1), torch.sigmoid(torch.stack((c1, c2, c3)))))


def _environment(parameters=None, noise=0):
    import torch
    from environment.multi_agent_env import MultiAgentEnvironment
    return MultiAgentEnvironment(state_dim=9, n_agents=3, dtype=torch.float64,
        noise_scale=noise, **(DEFAULTS if parameters is None else parameters))


def provenance() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    return {"transition_version": VERSION, "state_layout": list(VARIABLES), "dtype": "float64",
        "update_order": ["outer decay + social action + world noise", "explicit core update", "core clamp"],
        "sources": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in ("environment/multi_agent_env.py", "theory/nined_core.py")},
        "projection": "NineDLayout.project_to_4d(world); not the agent observation vector",
        "scope": "nine-coordinate world transition; agent bias, rewards and auxiliary dimensions are outside this instrument"}


def fidelity_check(reference=None) -> dict[str, Any]:
    """Failure prevents all comparative credit and yields the first exact witness."""
    import torch
    reference = transition_reference if reference is None else reference
    maximum = 0.; checked = 0
    # Fixed boundary suite is independent of the private experiment partitions.
    with torch.random.fork_rng():
        torch.manual_seed(901)
        for index in range(24):
            parameters = dict(DEFAULTS)
            if index >= 6:
                parameters[list(DEFAULTS)[(index - 6) % 6]] = (0., .25)[((index - 6) // 6) % 2]
            state = torch.full((9,), (-100., -1., 0., .5, 1., 100.)[index % 6], dtype=torch.float64)
            actions = torch.rand((3, 9), dtype=torch.float64) * 2 - 1
            if index < 3:
                actions.fill_((-1., 0., 1.)[index])
            env = _environment(parameters)
            env.world = state.clone()
            for step in range(4):
                before = env.world.clone()
                expected = reference(before, actions.mean(0), parameters)
                env.step(actions)
                error = float(torch.max(torch.abs(expected - env.world)))
                checked += 1
                if not torch.isfinite(expected).all() or error > 1e-10:
                    return {"passed": False, "cases_checked": checked, "tolerance": 1e-10,
                        "counterexample": {"case": index, "step": step, "state": before.tolist(),
                            "actions": actions.tolist(), "parameters": parameters,
                            "reference": expected.tolist(), "actual": env.world.tolist(), "max_error": error},
                        "provenance": provenance()}
                maximum = max(maximum, error)
    return {"passed": True, "cases_checked": checked, "maximum_error": maximum,
        "tolerance": 1e-10, "provenance": provenance()}


def observe(history: list, observation: Mapping[str, Any], action):
    import numpy as np
    from theory.nined_core import NineDLayout
    names = observation_names(observation)
    if observation["mode"] == "full":
        values = history[-1].tolist()
    else:
        depth = observation["history_steps"]
        if len(history) < depth:
            raise ValueError("observation_history_incomplete")
        layout = NineDLayout(9)
        values = [value for state in reversed(history[-depth:]) for value in layout.project_to_4d(state).squeeze(0).tolist()]
    return names, np.asarray(values + action.tolist(), dtype=float)


def intervention(spec: Mapping[str, Any], seed: int) -> dict[str, Any]:
    import torch
    from theory.nined_core import NineDLayout
    control, change = spec["controls"], spec["intervention"]
    effects = {"discovery": [], "independent": []}
    rows = []
    layout = NineDLayout(9)
    with torch.random.fork_rng():
        for partition, count in (("discovery", 4), ("independent", 8)):
            for repetition in range(count):
                trajectories = []
                for treated in (False, True):
                    torch.manual_seed((seed + repetition + (1000 if partition == "independent" else 0)) % (2**63))
                    parameters = dict(control["parameters"])
                    if treated and change["target"] == "parameter":
                        parameters[change["name"]] = change["value"]
                    env = _environment(parameters, spec["noise_scale"])
                    env.world = torch.tensor(control["initial_state"], dtype=torch.float64)
                    action = torch.tensor(control["actions"], dtype=torch.float64)
                    if treated and change["target"] == "state":
                        env.world[VARIABLES.index(change["name"])] = change["value"]
                    if treated and change["target"] == "action":
                        action[:, VARIABLES.index(change["name"])] = change["value"]
                    values = []
                    for _ in range(control["steps"]):
                        env.step(action)
                        state = env.world if spec["observation"]["mode"] == "full" else layout.project_to_4d(env.world).squeeze(0)
                        values.append(float(state[spec["observable"]["index"]]))
                    depth = spec["observation"]["history_steps"] if spec["observable"]["statistic"] == "history_mean_difference" else 1
                    trajectories.append(sum(values[-depth:]) / depth)
                effects[partition].append(trajectories[1] - trajectories[0])
                if partition == "discovery":
                    rows.append({"partition": partition, "control": trajectories[0], "treated": trajectories[1], "effect": trajectories[1] - trajectories[0]})
    values = effects["independent"]
    lower, upper = min(values) - 1e-8, max(values) + 1e-8
    outcome = interval_outcome(spec["hypothesis"]["prediction"], lower, upper)
    return {"hypothesis_outcome": outcome, "revision_eligible": outcome == "supported",
        "metrics": {"effect_mean": sum(values) / len(values), "effect_lower": lower, "effect_upper": upper},
        "interval_rule": "observed independent paired-replicate envelope plus 1e-8 numerical tolerance; not a population confidence interval",
        "discovery_observations": rows, "partitions": {k: {"pairs": len(v), "commitment": digest(v)} for k, v in effects.items()},
        "noise_control": "identical RNG state for each pair; disjoint discovery/independent seeds",
        "steps_executed": 24 * control["steps"], "observation": spec["observation"],
        "observable": spec["observable"], "scope": "Declared intervention and initial state in this simulator only; stochastic population generalization remains untested"}


def _dataset(spec: Mapping[str, Any], seed: int):
    import numpy as np
    import torch
    from theory.nined_core import NineDLayout
    data = {}; layout = NineDLayout(9)
    with torch.random.fork_rng():
        for split_index, (partition, count) in enumerate(SPLITS.items()):
            torch.manual_seed((seed + 100003 * (split_index + 1)) % (2**63))
            inputs, targets, oracle, removed = [], [], [], {k: [] for k in spec["disable_parameters"]}
            for row in range(count):
                if row % 16 == 0:
                    params = dict(DEFAULTS)
                    if partition == "transfer":
                        params.update(core_coupling=.12, phase_gain=.09)
                    env = _environment(params, .01)
                    history = [env.world.clone()]
                    while len(history) < spec["observation"]["history_steps"]:
                        env.step(torch.zeros((3, 9), dtype=torch.float64)); history.append(env.world.clone())
                actions = torch.rand((3, 9), dtype=torch.float64) * 2 - 1
                if partition == "retention":
                    actions *= .1
                mean = actions.mean(0)
                _, visible = observe(history, spec["observation"], mean)
                inputs.append(visible)
                if spec["observation"]["mode"] == "full":
                    oracle.append(layout.project_to_4d(transition_reference(env.world, mean, params)).squeeze(0).tolist())
                    for name in removed:
                        removed[name].append(layout.project_to_4d(transition_reference(env.world, mean, {**params, name: 0.})).squeeze(0).tolist())
                env.step(actions); history.append(env.world.clone())
                history = history[-4:]
                targets.append(layout.project_to_4d(env.world).squeeze(0).tolist())
            data[partition] = {"inputs": np.asarray(inputs), "targets": np.asarray(targets),
                "reference": np.asarray(oracle), "mechanisms": {k: np.asarray(v) for k, v in removed.items()}}
    return data


def comparison(spec: Mapping[str, Any], seed: int) -> dict[str, Any]:
    import numpy as np
    started = time.perf_counter()
    data = _dataset(spec, seed)
    phases = {"data_generation_seconds": time.perf_counter() - started}
    started = time.perf_counter()
    names = observation_names(spec["observation"])
    center = data["train"]["inputs"].mean(0)
    scale = np.maximum(data["train"]["inputs"].std(0), 1e-8)
    normalized = {k: (v["inputs"] - center) / scale for k, v in data.items()}
    _, _, pca = np.linalg.svd(normalized["train"], full_matrices=False)
    rng = np.random.default_rng(1907)
    generic = rng.normal(size=(len(names), 12)) / np.sqrt(len(names))
    phases["shared_normalization_and_baseline_preparation_seconds"] = time.perf_counter() - started
    started = time.perf_counter()
    candidate = {key: np.array([[evaluate_expression(expression, dict(zip(names, row))) for expression in spec["features"]]
                               for row in value["inputs"]]) for key, value in data.items()}
    phases["candidate_feature_evaluation_seconds"] = time.perf_counter() - started
    variants = {}; predictions = {}; costs = {}; retained = {}
    for width in WIDTHS:
        mappings = {"candidate": {k: v[:, :width] for k, v in candidate.items()},
            "conventional_pca": {k: v @ pca[:width].T for k, v in normalized.items()},
            "generic": {k: v @ generic[:, :width] for k, v in normalized.items()}}
        if width == 9:
            for index in spec["ablate_indices"]:
                mappings[f"candidate_without_{index}"] = {k: v[:, :width].copy() for k, v in candidate.items()}
                for value in mappings[f"candidate_without_{index}"].values():
                    value[:, index] = candidate["train"][:, index].mean()
        for method, features in mappings.items():
            started = time.perf_counter(); name = f"{method}_{width}"
            feature_center = features["train"].mean(0)
            feature_scale = np.maximum(features["train"].std(0), 1e-8)
            designs = {k: np.column_stack((np.ones(len(v)), (v - feature_center) / feature_scale)) for k, v in features.items()}
            penalty = np.eye(width + 1) * .001; penalty[0, 0] = 0
            train = designs["train"]
            weights = np.linalg.solve(train.T @ train + penalty, train.T @ data["train"]["targets"])
            predicted = {k: v @ weights for k, v in designs.items()}
            predictions[name] = predicted
            variants[name] = {k + "_mse": float(np.mean((predicted[k] - data[k]["targets"]) ** 2)) for k in SPLITS if k != "train"}
            costs[name] = {"train_rows": len(train), "readout_parameters": (width + 1) * 4,
                "feature_slots": width, "fits": 1, "readout_seconds": time.perf_counter() - started,
                "evaluated_rows": sum(SPLITS.values()), "readout_design_cells": sum(SPLITS.values()) * (width + 1)}
            if name == "candidate_9":
                retained = {"coefficients": weights.tolist(), "feature_center": feature_center.tolist(),
                    "feature_scale": feature_scale.tolist(), "observation": spec["observation"], "features": spec["features"][:9],
                    "training_commitment": digest(data["train"]["inputs"].tolist()), "target": "next project_to_4d(world)"}
    diagnostics = {}
    if spec["observation"]["mode"] == "full":
        diagnostics["complete_transition"] = {k + "_mse": float(np.mean((v["reference"] - v["targets"]) ** 2)) for k, v in data.items() if k != "train"}
        for mechanism in spec["disable_parameters"]:
            diagnostics["without_" + mechanism] = {k + "_mse": float(np.mean((v["mechanisms"][mechanism] - v["targets"]) ** 2)) for k, v in data.items() if k != "train"}
    candidate_loss = variants["candidate_9"]["holdout_mse"]
    controls = ["generic_9", "conventional_pca_9"]
    controls += [f"candidate_without_{index}_9" for index in spec["ablate_indices"]]
    gains = {name: variants[name]["holdout_mse"] - candidate_loss for name in controls}
    # Four independent trajectory blocks; this conservative margin is a benchmark
    # criterion, never a claim of statistical significance or universal superiority.
    bounds = {}
    for name in controls:
        differences = ((predictions[name]["holdout"] - data["holdout"]["targets"]) ** 2
            - (predictions["candidate_9"]["holdout"] - data["holdout"]["targets"]) ** 2).mean(1).reshape(4, 16).mean(1)
        bounds[name] = float(differences.mean() - 2 * differences.std(ddof=1) / 2)
    checks = {"heldout_margin": all(v > 1e-6 for v in bounds.values()),
        "transfer": all(variants["candidate_9"]["transfer_mse"] < variants[n]["transfer_mse"] for n in controls),
        "retention": all(variants["candidate_9"]["retention_mse"] <= variants[n]["retention_mse"] * 1.05 + 1e-6 for n in controls)}
    worst = np.argsort(((predictions["candidate_9"]["discovery"] - data["discovery"]["targets"]) ** 2).mean(1))[-3:]
    counterexamples = [{"partition": "discovery", "inputs": dict(zip(names, data["discovery"]["inputs"][i].tolist())),
        "observed_projection": data["discovery"]["targets"][i].tolist(), "predicted_projection": predictions["candidate_9"]["discovery"][i].tolist()} for i in worst]
    # A fresh interpreter restores the candidate and predicts an unseen transfer
    # partition. This proves estimator serialization only, not planner learning.
    import json
    import os
    import subprocess
    import sys
    payload = {"estimator": retained, "inputs": data["transfer"]["inputs"].tolist()}
    restart = subprocess.run([sys.executable, "-B", str(Path(__file__).with_name("nine_d_estimator_worker.py"))],
        input=json.dumps(payload), text=True, capture_output=True, timeout=10,
        env={k: v for k, v in os.environ.items() if k in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")})
    restored = np.asarray(json.loads(restart.stdout)) if restart.returncode == 0 else np.asarray([])
    checks["estimator_restart"] = bool(restored.shape == predictions["candidate_9"]["transfer"].shape and np.allclose(restored, predictions["candidate_9"]["transfer"], atol=1e-10, rtol=0))
    variants["candidate"] = dict(variants["candidate_9"])
    return {"revision_eligible": all(checks.values()), "variants": variants, "checks": checks,
        "metrics": {"candidate_holdout_mse": candidate_loss, "candidate_gain": min(gains.values()), "counterexample_count": len(counterexamples)},
        "counterexamples": counterexamples, "paired_block_gain_lower_margin": bounds,
        "analytical_diagnostics": diagnostics, "analytical_diagnostic_scope": "full-state deterministic reference with known parameters; zero fitted parameters; excluded from learned equal-width comparisons",
        "observation": spec["observation"], "visible_inputs": names, "arm_costs": costs, "phase_costs": phases,
        "representation_costs": {"candidate_expression_nodes": [sum(1 for _ in ast.walk(ast.parse(expression, mode="eval"))) for expression in spec["features"]],
            "candidate_expression_evaluations": 12 * sum(SPLITS.values()), "generic_map_entries": int(generic.size),
            "pca_fitted_map_entries": int(pca[:12].size), "shared_input_normalization_values": len(names) * 2,
            "readout_feature_normalization_values_per_arm": "2 * feature_slots",
            "scope": "preparation and feature-map costs are reported separately from readouts; CPU time is measured, not asserted equal"},
        "information_contract": {"same_rows_actions_history_and_preprocessing_access": True,
            "hidden_state_available": spec["observation"]["mode"] == "full", "normalization_fit": "training only",
            "splits": SPLITS, "widths": list(WIDTHS), "readout_rule": "one ridge fit per arm, lambda 0.001, no hyperparameter search",
            "capacity_scope": "readout counts matched within width; total representation complexity differs and is reported; width effects include parameter count changes",
            "feature_rules": {"candidate": "12 planner-authored expressions; <=80 AST nodes each", "generic": "fixed random linear map", "conventional_pca": "training-only PCA"},
            "selection_rule": "acceptance uses preregistered width 9; other sizes are diagnostics, not post-hoc winners"},
        "partition_commitments": {k: digest({q: v[q].tolist() for q in ("inputs", "targets")}) for k, v in data.items()},
        "retained_estimator": retained, "estimator_restart_verified": checks["estimator_restart"],
        "restart_scope": "restored estimator produces the same predictions on transfer inputs; real planner method selection and learning are not tested",
        "scope": "Synthetic next-projection forecast; projected/history scores do not identify hidden states; no general 9D advantage established"}


def evaluate(spec: Mapping[str, Any], seed: int) -> dict[str, Any]:
    validate_spec(spec)
    started = time.perf_counter()
    fidelity = fidelity_check()
    common = {"fidelity": fidelity, "baseline_fidelity_verified": fidelity["passed"],
        "prose_statement_verified": False, "nine_d_advantage_established": False, "growth_credit": False,
        "method_adoption": False, "grants_execution_authority": False, "allowance_added": 0,
        "frozen_spec_sha256": digest(spec), "provenance": provenance()}
    if not fidelity["passed"]:
        return {**common, "validity": "invalid_baseline", "hypothesis_outcome": "inconclusive", "revision_eligible": False, "metrics": {}}
    result = intervention(spec, seed) if spec["evaluator_id"] == INTERVENTION else comparison(spec, seed)
    return {**common, **result, "validity": "valid", "elapsed_seconds": time.perf_counter() - started}


def model_schemas(authorized: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Provider shapes mirror the registered instruments, filtered by authority."""
    def obj(properties):
        return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}
    def enum(values):
        values = list(values)
        return {"type": "string" if all(isinstance(v, str) for v in values) else "number", "enum": values}
    def array(items, minimum, maximum):
        return {"type": "array", "items": items, "minItems": minimum, "maxItems": maximum}
    def numeric(low, high):
        return {"type": "number", "minimum": low, "maximum": high}
    observation = obj({"mode": enum(("full", "projected", "history")), "history_steps": {"type": "integer", "minimum": 1, "maximum": 4}})
    prediction = obj({"relation": enum(("==", "<", ">", "<=", ">=")), "value": numeric(-1e6, 1e6)})
    falsifier = obj({"relation": enum(("!=", "==", "<", ">", "<=", ">=")), "value": numeric(-1e6, 1e6)})
    schemas = []
    if INTERVENTION in authorized:
        schemas.append(obj({"evaluator_id": enum((INTERVENTION,)),
            "hypothesis": obj({"statement": {"type": "string", "minLength": 8, "maxLength": 256}, "prediction": prediction, "falsifier": falsifier}),
            "controls": obj({"initial_state": array(numeric(-100, 100), 9, 9),
                "actions": array(array(numeric(-1, 1), 9, 9), 3, 3), "steps": {"type": "integer", "minimum": 1, "maximum": 8},
                "parameters": obj({k: numeric(0, .25) for k in DEFAULTS})}),
            "intervention": obj({"target": enum(("state", "action", "parameter")), "name": enum((*VARIABLES, *DEFAULTS)), "value": numeric(-100, 100)}),
            "observation": observation, "observable": obj({"index": {"type": "integer", "minimum": 0, "maximum": 8},
                "statistic": enum(("final_difference", "history_mean_difference")), "unit": enum(("simulator_coordinate",))}),
            "noise_scale": enum((0, .01))}))
    if COMPARISON in authorized:
        schemas.append(obj({"evaluator_id": enum((COMPARISON,)), "observation": observation,
            "features": array({"type": "string", "minLength": 1, "maxLength": 256}, 12, 12),
            "ablate_indices": array({"type": "integer", "minimum": 0, "maximum": 8}, 1, 3),
            "disable_parameters": array(enum(DEFAULTS), 0, 3)}))
    return schemas


def planner_help(authorized: Mapping[str, Any]) -> str:
    lines = []
    if any(key in authorized for key in REGISTRY):
        lines.append("New simulator instruments require a complete-transition fidelity receipt. They provide no physical proof, method adoption, or extra allowance. Controls and hypotheses are YOUR choices. Observation is {mode:full|projected|history,history_steps:1 for full/projected or 2..4 for history}. Full exposes nine state values; projected exposes only project_to_4d(world); history exposes that projection in newest-first order. All predictors get the same known nine mean actions. Units are simulator coordinates, not validated physical units. Use submit_research_plan with a matching empirical operationalization evaluator_id:metric, reserving 2 tools, 1 evaluation, 46 seconds.")
    if INTERVENTION in authorized:
        lines.append("nine_d_intervention_v1 model_spec: {evaluator_id,hypothesis:{statement,prediction:{relation,value},falsifier:{relation,value}},controls:{initial_state:[9 numbers -100..100 in x,y,z,t1,t2,t3,c1,c2,c3 order],actions:[3 arrays of 9 values -1..1],steps:1..8,parameters:{world_decay,social_gain,core_coupling,entropy_gain,phase_gain,consciousness_gain: each 0..0.25}},intervention:{target:state|action|parameter,name:coordinate or parameter,value:changed bounded number},observation,observable:{index:0..8 full or 0..3 projected/history,statistic:final_difference|history_mean_difference,unit:simulator_coordinate},noise_scale:0|0.01}. An action intervention sets that coordinate for all three agents. All other controls stay fixed. History mean requires steps>=history_steps. Outcome is treated minus control, independently measured on 8 paired noise replicates (4 discovery pairs give feedback). Prediction/falsifier must negate each other and exactly match the plan's effect_mean prediction. Finite observed-range bounds plus numerical tolerance yield supported/refuted/inconclusive; this is not a population confidence interval. Do not infer effects outside the declared initial state/regime. Metrics: effect_mean, effect_lower, effect_upper; plans use effect_mean.")
    if COMPARISON in authorized:
        lines.append("nine_d_comparison_v2 model_spec: {evaluator_id,observation,features:[12 ordered bounded arithmetic expressions],ablate_indices:[1..3 distinct indices 0..8],disable_parameters:[0..3 registered parameter names; full observation only]}. Feature prefixes compare sizes 3,9,12 with conventional training-only PCA and generic random maps; individual selected features are disabled at width 9. Full-state inputs: x,y,z,t1,t2,t3,c1,c2,c3. Projected/history inputs: o0_x,o0_y,o0_z,o0_t (newest), then o1_x,... up to depth-1. All modes also expose a_x,a_y,a_z,a_t1,a_t2,a_t3,a_c1,a_c2,a_c3. No hidden state or future input in partial modes. One ridge fit per arm; 96 common training rows; same discovery/hidden/retention/transfer partitions; readout counts match within size but change across sizes. Native complete-transition and parameter-removal diagnostics use full state and known simulator parameters and are reported separately from learned models. Metrics: candidate_holdout_mse,candidate_gain,counterexample_count; acceptance is frozen at width 9, never whichever size wins. Scores cannot establish that nine dimensions are necessary, identify hidden state, or verify prose.")
    return "\n" + "\n".join(lines) + "\n" if lines else ""
