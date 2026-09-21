"""One explicit, two-call maximum research continuation per frozen snapshot.

Method success supplies eligibility, not authority. The operator issues a grant;
normal research tools, source checks, controls and cumulative costs still apply.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

from . import research_procedures as procedures
from .research_tools import digest, read_json, write_json


def issue(root: Path, candidate_id: str, *, calls: int, authority_reference: str, policy: Any,
          repo_root: Path | None = None) -> dict[str, Any]:
    from .research_maintenance import _inputs
    from .theory_workspace import TheoryWorkspace
    from .theory_allowance import _controls_allow
    if type(calls) is not int or not 1 <= calls <= 2 or not authority_reference.strip():
        raise ValueError("explicit_bounded_method_continuation_required")
    candidate = procedures.read(root, "candidates", candidate_id)
    adopted = next((r for r in procedures.context(root) if r["id"] == candidate_id), None)
    if not adopted: raise ValueError("current_independently_adopted_method_required")
    failure = procedures.read(root, "failures", candidate["failure_id"])
    if not failure.get("theory_subject_id"): raise ValueError("theory_method_continuation_required")
    workspace = TheoryWorkspace(root, failure["theory_subject_id"], repo_root=repo_root)
    state = read_json(root/failure["parent_path"]); work = state["work"]
    previous = [procedures.read(root, "continuation_grants", p.stem) for p in (root/"research_methods/continuation_grants").glob("*.json")]
    for grant in previous:
        if grant["snapshot_id"] == failure["source_snapshot_id"] or grant["parent_id"] == failure["parent_id"]:
            if grant["candidate_id"] == candidate_id and grant["calls"] == calls and grant["authority_reference"] == authority_reference:
                return grant
            raise ValueError("snapshot_method_continuation_already_assigned")
    inputs = _inputs(root, failure, repo_root=repo_root)
    command = procedures.run(candidate["procedure"], inputs).get("command")
    if not command or command["command"] != "inspect_dependency": raise ValueError("verified_executable_method_action_required")
    if not _controls_allow(workspace, policy) or state.get("inflight") or not state["state"].startswith("waiting_"):
        raise ValueError("settled_authorized_research_required")
    if (state["usage"]["tool_calls"] >= work["limits"]["tool_calls"]
            or work["limits"]["compute_seconds"]-state["usage"]["compute_seconds"] < 30):
        raise ValueError("remaining_research_resources_required")
    prior_limit = state.get("call_allowance", {}).get("effective_model_call_limit", work["limits"]["model_calls"])
    if state["usage"]["model_calls"] < prior_limit: raise ValueError("use_remaining_research_allowance_first")
    review = procedures.read(root, "reviews", adopted["review_id"])
    return procedures.store(root, "continuation_grants", {"candidate_id": candidate_id, "review_id": review["id"],
        "evaluation_id": review["evaluation_id"], "failure_id": failure["id"], "parent_id": failure["parent_id"],
        "parent_path": failure["parent_path"], "snapshot_id": work["snapshot_id"], "work_sha256": digest(work),
        "usage_before": state["usage"], "failure": state["feedback"], "calls": calls,
        "maximum_model_calls": state["usage"]["model_calls"]+calls, "first_command": command,
        "authority_reference": authority_reference, "all_other_limits_unchanged": True})


def _grant(root: Path, run_id: str) -> dict[str, Any] | None:
    rows = [procedures.read(root, "continuation_grants", p.stem) for p in (root/"research_methods/continuation_grants").glob("*.json")]
    matching = [r for r in rows if r["parent_id"] == run_id]
    if len(matching) > 1: raise ValueError("ambiguous_method_continuation_grants")
    return matching[0] if matching else None


def apply(workspace: Any, work: Mapping[str, Any], state: dict[str, Any], policy: Any,
          *, previous_state: str | None = None) -> dict[str, Any]:
    from .theory_allowance import _controls_allow
    grant = _grant(workspace.root, work["run_id"])
    if not grant or not state: return state
    if grant["work_sha256"] != digest(work) or any(state["usage"][k] < v for k, v in grant["usage_before"].items()):
        raise ValueError("method_continuation_lineage_or_usage_changed")
    original = copy.deepcopy(state)
    terminal = [procedures.read(workspace.root,"continuation_results",p.stem)
        for p in (workspace.root/"research_methods/continuation_results").glob("*.json")]
    terminal = [r for r in terminal if r["grant_id"]==grant["id"]]
    from . import method_repair
    repair = method_repair.authorization(workspace.root, grant['id'])
    repair_open = bool(repair and not method_repair.finished(workspace.root, repair))
    if repair:
        if repair['work_sha256'] != digest(work) or any(state['usage'][k] < v for k,v in repair['usage_before'].items()):
            raise ValueError('repair_usage_rollback_or_contract_changed')
        if repair['implementation'] != procedures.implementation(): repair_open = False
    if repair_open: terminal = []
    for path in (workspace.root/"research_methods/procedure_uses").glob("*.json"):
        used=procedures.read(workspace.root,"procedure_uses",path.stem)
        if used["grant_id"]==grant["id"] and any(state["usage"][k]<v for k,v in used["usage"].items()):
            raise ValueError("method_continuation_usage_rollback")
    required_review = repair['review_id'] if repair_open else grant['review_id']
    adopted = next((r for r in procedures.context(workspace.root) if r["id"] == grant["candidate_id"] and r["review_id"] == required_review), None)
    controls = _controls_allow(workspace, policy)
    usage = state["usage"]
    remaining = max(0, grant["maximum_model_calls"]-usage["model_calls"])
    resources = all(usage[k]<work["limits"][k] for k in ("tool_calls","compute_seconds"))
    status = "consumed" if not remaining else "closed" if terminal else "stale_method" if not adopted else "resources_exhausted" if not resources else "paused" if not controls else "active"
    allowance = dict(state.get("call_allowance", {}))
    base = allowance.get("pre_method_limit", allowance.get("effective_model_call_limit", work["limits"]["model_calls"]))
    effective = max(base, grant["maximum_model_calls"]) if status == "active" else base
    if status == "active" and not state.get("inflight"):
        if repair_open and not state.get('repair_authorization_id'):
            if state['usage'] != repair['usage_before']: raise ValueError('repair_initial_usage_changed')
            workspace.assert_current_sources()
            state.update(repair_authorization_id=repair['id'], state='ready', feedback='')
        elif not state.get("method_continuation_id"):
            if state["usage"] != grant["usage_before"] or state.get("feedback") != grant["failure"]:
                raise ValueError("method_continuation_failure_state_changed")
            workspace.assert_current_sources()
            state.update(method_continuation_id=grant["id"], state="ready", feedback="")
        elif previous_state == "ready" or state.get("feedback") == "": state["state"] = "ready"
    if status != "active" and not state.get("inflight") and usage["model_calls"] >= base:
        state["state"] = "waiting_for_changed_input"
    state["call_allowance"] = {**allowance, "pre_method_limit": base, "effective_model_call_limit": effective,
        "remaining_model_calls": max(0, effective-usage["model_calls"]), "method_continuation_id": grant["id"],
        "method_continuation_status": status, "method_continuation_calls": grant["calls"],
        "required_first_action": grant["first_command"] if usage["model_calls"]==(
            repair['usage_before']['model_calls'] if repair_open else grant["usage_before"]["model_calls"]) else None,
        "work_state": state["state"], "blocked_reason": state.get("feedback", "") if state["state"].startswith("waiting_") else "",
        "scientific_progress_credited": False}
    if state != original: write_json(workspace._path("runs", work["run_id"]), state)
    return state


def validate_first_action(root: Path, state: Mapping[str, Any], candidate: Mapping[str, Any]) -> None:
    grant = _grant(root, state["id"])
    from .method_repair import authorization
    repair = authorization(root, grant['id']) if grant else None
    before = repair['usage_before']['model_calls'] if repair else grant['usage_before']['model_calls'] if grant else -1
    if not grant or state["usage"]["model_calls"] != before+1: return
    expected = grant["first_command"]
    if candidate.get("command") != expected["command"] or any(candidate.get("arguments", {}).get(k) != v
            for k, v in expected["arguments"].items() if k != "question"):
        raise ValueError("method_continuation_requires_reviewed_first_action")


def record_outcome(workspace: Any, state: Mapping[str, Any]) -> None:
    from .method_repair import record_outcome as repaired_outcome
    if repaired_outcome(workspace, state): return
    grant = _grant(workspace.root, state["id"])
    if not grant or state["usage"]["model_calls"] <= grant["usage_before"]["model_calls"]: return
    for path in (workspace.root/"research_methods/continuation_results").glob("*.json"):
        if procedures.read(workspace.root,"continuation_results",path.stem)["grant_id"]==grant["id"]:return
    call = state["usage"]["model_calls"]
    turn = read_json(workspace._path("turns", state["id"]+"-"+str(call)))
    model = read_json(workspace._path("model_turns", state["id"]+"-"+str(call)))
    verified = bool(turn and digest(turn.get("result")) == turn.get("result_sha256") and model.get("response") == turn.get("command"))
    use = procedures.store(workspace.root, "procedure_uses", {"grant_id": grant["id"], "candidate_id": grant["candidate_id"],
        "run_id": state["id"], "call": call, "command": turn.get("command", model.get("response")),
        "result_sha256": turn.get("result_sha256"), "verified_execution": verified,
        "reviewed_method_application": verified and call == grant["usage_before"]["model_calls"]+1,
        "usage": state["usage"], "feedback": state.get("feedback", ""), "live_research_growth_demonstrated": False})
    if not verified or state["state"].startswith("waiting_") or call >= grant["maximum_model_calls"]:
        record = procedures.store(workspace.root, "continuation_results", {"grant_id": grant["id"], "last_use_id": use["id"],
            "state": "failed" if not verified else "completed_bounded_continuation", "usage": state["usage"],
            "requires_independent_outcome_review": True, "live_research_growth_demonstrated": False})
        pointer = workspace.root/"research_methods/continuation_outcomes"/(grant["id"]+".json")
        if not pointer.exists(): write_json(pointer, {"result_id": record["id"]})
