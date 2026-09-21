"""Offline negative controls for 9D axis growth; no learner or live state access.

Run with ``python -m benchmarks.nine_d_null_probe --help``. These controls use
the explicit MultiAgentEnvironment, not the proposal runner's SimpleTriadEnv.
They test whether axis increases alone can identify learning, not whether a
trained 9D policy outperforms another architecture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
from pathlib import Path
from typing import Any

import torch

from environment.multi_agent_env import MultiAgentEnvironment


AXES = ("c1", "c2", "c3")
CONDITIONS = ("zero_action", "random_action")


def _axis_values(env: MultiAgentEnvironment) -> dict[str, float]:
    values = env.layout.named_state(env.world)
    return {axis: float(values[axis].item()) for axis in AXES}


def _trial(seed: int, steps: int, condition: str) -> dict[str, Any]:
    # Isolate the environment's global CPU RNG. Action draws use another stream,
    # so the paired controls see the same initial state and exogenous noise.
    with torch.random.fork_rng(devices=[]), torch.no_grad():
        torch.random.default_generator.manual_seed(seed)
        action_rng = torch.Generator(device="cpu").manual_seed(seed + 1_000_003)
        env = MultiAgentEnvironment(state_dim=12, n_agents=3, device=torch.device("cpu"))
        initial = _axis_values(env)
        rewards = []
        action_abs_max = 0.0
        for _ in range(steps):
            actions = torch.zeros(3, 12)
            if condition == "random_action":
                actions = 2.0 * torch.rand(3, 12, generator=action_rng) - 1.0
            action_abs_max = max(action_abs_max, float(actions.abs().max().item()))
            _, reward, _, _ = env.step(actions)
            rewards.append(reward)
        final = _axis_values(env)
    return {
        "initial": initial,
        "final": final,
        "delta": {axis: final[axis] - initial[axis] for axis in AXES},
        "mean_environment_reward": statistics.fmean(rewards),
        "action_abs_max": action_abs_max,
        "learning_updates": 0,
    }


def run_null_probe(*, seeds: tuple[int, ...] = tuple(range(12)), steps: int = 32) -> dict[str, Any]:
    """Return deterministic, paired no-learning controls with raw seed results."""
    if not seeds or any(type(seed) is not int or not 0 <= seed < 2**63 for seed in seeds):
        raise ValueError("seeds must contain nonnegative integers below 2**63")
    if len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be unique independent replicates")
    if type(steps) is not int or steps < 1:
        raise ValueError("steps must be a positive integer")

    trials = [
        {"seed": seed, **{condition: _trial(seed, steps, condition) for condition in CONDITIONS}}
        for seed in seeds
    ]
    summary: dict[str, Any] = {}
    for condition in CONDITIONS:
        summary[condition] = {}
        for axis in AXES:
            deltas = [row[condition]["delta"][axis] for row in trials]
            summary[condition][axis] = {
                "initial_mean": statistics.fmean(row[condition]["initial"][axis] for row in trials),
                "final_mean": statistics.fmean(row[condition]["final"][axis] for row in trials),
                "delta_mean": statistics.fmean(deltas),
                "delta_sample_std": statistics.stdev(deltas) if len(deltas) > 1 else None,
                "positive_delta_seed_count": sum(delta > 0.0 for delta in deltas),
            }
        summary[condition]["mean_environment_reward"] = statistics.fmean(
            row[condition]["mean_environment_reward"] for row in trials
        )

    source_root = Path(__file__).resolve().parents[1]
    source_paths = (
        "benchmarks/nine_d_null_probe.py",
        "environment/multi_agent_env.py",
        "theory/nined_core.py",
    )
    return {
        "schema_name": "NineDNullLearningProbe",
        "schema_version": 1,
        "environment": "environment.multi_agent_env.MultiAgentEnvironment",
        "seeds": list(seeds),
        "steps_per_trial": steps,
        "state_dim": 12,
        "n_agents": 3,
        "environment_parameters": "constructor defaults; CPU float32",
        "python_version": platform.python_version(),
        "torch_version": str(torch.__version__),
        "source_sha256": {
            path: hashlib.sha256((source_root / path).read_bytes()).hexdigest() for path in source_paths
        },
        "learned_capability_demonstrated": False,
        "interpretation": "Axis increases in these controls arise without learning. A trained-agent comparison is still required.",
        "zero_action_axes_rising_without_learning": [
            axis for axis in AXES if summary["zero_action"][axis]["delta_mean"] > 0.0
        ],
        "summary": summary,
        "paired_final_axis_delta_random_minus_zero": {
            axis: statistics.fmean(
                row["random_action"]["final"][axis] - row["zero_action"]["final"][axis]
                for row in trials
            )
            for axis in AXES
        },
        "trials": trials,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(12)))
    parser.add_argument("--steps", type=int, default=32)
    parser.add_argument("--output", type=Path, help="Optional JSON report; otherwise print to stdout.")
    args = parser.parse_args()
    try:
        report = run_null_probe(seeds=tuple(args.seeds), steps=args.steps)
    except ValueError as exc:
        parser.error(str(exc))
    encoded = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
        print(f"Wrote no-learning control report: {args.output}")
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
