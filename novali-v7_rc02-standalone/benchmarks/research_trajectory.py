"""Opt-in real-planner trajectories. Synthetic state only; never live research.

Run as a module with --output DIR. Each bounded step starts a fresh Python
process, so all arms must retain evidence and budgets through actual restarts.
The legacy arm ablates the new method catalog and persistent evidence context;
it is not a claim to reproduce every detail of a historic deployment.
"""
from __future__ import annotations

import argparse
import copy
import dataclasses
import json
import hashlib
import subprocess
import sys
import time
from pathlib import Path
from unittest import mock

from operator_shell import theory_runtime as runtime, theory_methods as methods
from operator_shell.research_episodes import ResearchPolicy
from operator_shell.research_runtime import local_planner
from operator_shell.research_tools import digest, read_json, write_json
from operator_shell.theory_workspace import TheoryWorkspace

CASES = [
    {"id": "unit_conversion", "domain": "measurement", "mode": "fresh",
     "source": "Investigate the finite claim that (u-32)*5/9*9/5+32 equals u for u in [-40,0,32,68,212]. Form the proposition, test it independently, and record a scoped decision. Do not infer a universal theorem from a finite test.",
     "expected": "evaluation_and_decision"},
    {"id": "tariff_retention", "domain": "accounting", "mode": "displaced_context",
     "source": "Investigate whether 2*q+3 equals 5*q for q in [-2,-1,0,1,2]. Retain any counterexamples and record a scoped decision. A tariff description is not evidence of equality.",
     "expected": "counterexample_and_rejection"},
    {"id": "queue_latency", "domain": "distributed_systems", "mode": "unsupported_recovery",
     "source": "Investigate whether this queue service has p95 latency below 20 milliseconds at 100 requests per second. There are no request timing samples, service runner, or queue evaluator in this workspace. The available finite arithmetic checker cannot measure queue latency. Formulate a precise capability request if the necessary observable is unavailable.",
     "expected": "scoped_capability_request"},
]


def policy():
    return dataclasses.replace(ResearchPolicy(), enabled=True, theory_subject_ids=("fixture",),
        max_theory_model_calls=4, max_theory_tool_calls=6, max_theory_compute_seconds=720,
        max_theory_evaluations=1, max_output_tokens=1400, model_timeout_seconds=180)


def implementation_fingerprint():
    base = Path(__file__).resolve().parents[1]
    paths = ["operator_shell/" + name + ".py" for name in
        ("theory_runtime", "theory_methods", "planner_authoring", "theory_allowance", "research_runtime", "research_context", "theory_workspace", "theory_evaluators", "research_feedback", "research_semantics", "provider_recovery")]
    paths.append("benchmarks/research_trajectory.py")
    return {name: hashlib.sha256((base / name).read_bytes()).hexdigest() for name in paths}


def step(directory, arm):
    manifest = read_json(directory.parent.parent / "manifest.json")
    if manifest.get("implementation_sha256") and manifest["implementation_sha256"] != implementation_fingerprint():
        raise ValueError("evaluation_implementation_changed_after_freeze")
    root, repo = directory / "state", directory / "repo"
    work = read_json(directory / "work.json")
    provider = local_planner(policy())
    if arm == "legacy_catalog":
        original_context = runtime._planner_context
        def legacy_context(workspace, state):
            context = original_context(workspace, state)
            context.pop("evidence_memory", None); context.pop("method_feedback", None)
            # Restore the prior delivery shape when ablating persistent memory;
            # otherwise source projections would point to a removed field.
            context["prior_observations"] = [{"command": r["command"]["command"],
                "arguments_sha256": digest(r["command"]["arguments"]),
                "result": r["result"], "result_sha256": r["result_sha256"]}
                for r in state["observations"][-2:]]
            return context
        def legacy_contract(context): return runtime.THEORY_INSTRUCTIONS, runtime.THEORY_SCHEMA
        def legacy_provider(phase, context):
            response = provider(phase, context)
            legacy_provider.last_metadata = getattr(provider, "last_metadata", {})
            if response.get("command") in methods.COMMANDS:
                raise ValueError("command_not_in_legacy_catalog")
            return response
        with mock.patch.object(runtime, "_planner_context", legacy_context), mock.patch.object(methods, "planner_contract", legacy_contract):
            state = runtime.advance_theory(root, work, policy(), planner=legacy_provider, repo_root=repo)
    else:
        state = runtime.advance_theory(root, work, policy(), planner=provider, repo_root=repo)
    print(json.dumps({"state": state["state"], "usage": state["usage"], "feedback": state["feedback"]}), flush=True)


def run(output, cases_path=None, arms=None):
    output.mkdir(parents=True, exist_ok=True)
    if (output / "manifest.json").exists(): raise ValueError("evaluation_output_must_be_fresh")
    cases = read_json(cases_path)["cases"] if cases_path else CASES
    manifest = {"version": "research_trajectory_v1", "cases": cases, "policy": dataclasses.asdict(policy()),
        "implementation_sha256": implementation_fingerprint(),
        "arms": arms or ["legacy_catalog", "persistent_methods"], "restart": "fresh_process_every_step",
        "acceptance": "receipt and decision, informative rejection, or correctly scoped missing-capability request; no credit for claims or source volume",
        "evaluation_is_not_live_research": True}
    manifest["sha256"] = digest(manifest)
    write_json(output / "manifest.json", manifest)  # Freeze before any provider call.
    rows = []
    for case in cases:
        for arm in manifest["arms"]:
            directory = output / case["id"] / arm
            root, repo = directory / "state", directory / "repo"
            (repo / "theory/subjects").mkdir(parents=True)
            (repo / "evidence.md").write_text(case["source"], encoding="utf-8")
            write_json(repo / "theory/subjects/fixture.json", {"title": "Synthetic research method evaluation",
                "research_question": "Resolve the exact question in evidence.md using the registered evaluator or a scoped capability request.",
                "sources": ["evidence.md"], "evaluator_ids": ["finite_domain_v1"]})
            work = runtime.prepare_theory_work(root, "fixture", policy(), repo_root=repo)
            write_json(directory / "work.json", work)
            ws = TheoryWorkspace(root, "fixture", repo_root=repo)
            if case["mode"] != "fresh":
                # Controlled fixture setup counts against both arms' allowance.
                sid = next(iter(ws._snapshot()["sources"]))
                state = runtime.advance_theory(root, work, policy(), repo_root=repo, planner=lambda *args:
                    {"command": "inspect_source", "arguments": {"source_id": sid, "offset_chars": 0},
                     "why": "Acquire the synthetic task statement before the restart challenge."})
                state["observations"] = []
                if case["mode"] == "unsupported_recovery":
                    state["feedback"] = "unsupported_observable: the requested empirical measurement is not produced by finite_domain_v1"
                    state["method_feedback"] = methods.method_feedback(state["feedback"],
                        {"command": "submit_research_plan", "arguments": {"observable": "unsupported_empirical_measurement"}}, work["limits"])
                write_json(ws._path("runs", work["run_id"]), state)
            started = time.perf_counter()
            for turn in range(5):
                before = read_json(ws._path("runs", work["run_id"]))
                if before and (before["state"].startswith("waiting_") or before["usage"]["model_calls"] >= 4): break
                if ws._records("decisions"): break
                try:
                    process = subprocess.run([sys.executable, "-B", "-m", "benchmarks.research_trajectory", "--step", str(directory), "--arm", arm],
                        capture_output=True, text=True, timeout=245)
                except subprocess.TimeoutExpired:
                    # The persisted reservation is settled without another provider call.
                    runtime.advance_theory(root, work, policy(), repo_root=repo,
                        planner=lambda *args: (_ for _ in ()).throw(ValueError("evaluation_process_timeout")))
                    process = subprocess.CompletedProcess([], 124, "", "evaluation_step_timeout")
                write_json(directory / ("process-" + str(turn) + ".json"), {"returncode": process.returncode,
                    "stdout": process.stdout[-12000:], "stderr": process.stderr[-12000:]})
                state = read_json(ws._path("runs", work["run_id"]))
                print(json.dumps({"case": case["id"], "arm": arm, "step": turn,
                    "usage": state.get("usage"), "feedback": state.get("feedback"), "process_exit": process.returncode}), flush=True)
                if process.returncode: break
            state = read_json(ws._path("runs", work["run_id"]))
            evaluations, decisions = ws._records("evaluations"), ws._records("decisions")
            capabilities = [read_json(p) for p in (ws.base / "capability_requests").glob("*.json")]
            counterexamples = sum(e["assessment"]["metrics"].get("counterexample_count", 0) for e in evaluations)
            # Capability correctness is explicitly reviewable, not awarded just for existence.
            capability_scoped = bool(capabilities and all(len(capabilities[-1].get(k, "")) >= 8 for k in
                ("capability", "why_needed", "acceptance_test", "bounded_scope")))
            row = {"case": case["id"], "domain": case["domain"], "arm": arm, "state": state["state"],
                "usage": state["usage"], "feedback": state["feedback"], "evaluations": len(evaluations),
                "decisions": [d["decision"] for d in decisions], "counterexamples": counterexamples,
                "capability_requests": capabilities, "capability_structurally_scoped": capability_scoped,
                "failures": len(state.get("failures", [])), "elapsed_seconds": round(time.perf_counter()-started, 3),
                "restart_steps": len(list(directory.glob("process-*.json"))),
                "semantic_review_required": True, "growth_demonstrated": False}
            rows.append(row)
            write_json(output / "results.json", {"manifest_sha256": manifest["sha256"], "rows": rows,
                "complete": len(rows) == len(cases) * len(manifest["arms"]),
                "interpretation": "bounded synthetic trajectories; inspect proposition relevance and capability content before scoring; single-arm runs are not comparative evidence"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--step", type=Path)
    parser.add_argument("--arm", choices=["legacy_catalog", "persistent_methods"])
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--arms", nargs="+", choices=["legacy_catalog", "persistent_methods"])
    args = parser.parse_args()
    if args.step: step(args.step, args.arm)
    elif args.output: run(args.output, args.cases, args.arms)
    else: parser.error("--output or --step is required")
