"""One method-upgrade retry within an existing directive contract and budget."""
from __future__ import annotations

from .research_tools import digest, read_json, write_json

VERSION = "research_method_feedback_v1"


def feedback(error, task, usage, policy):
    return {"version": VERSION, "reason": str(error)[:600],
        "allowed_tools": task.get("allowed_tools", []),
        "observable_catalog": {"inspect_artifact": ["bytes", "numeric_token_count"],
            "compare_artifacts": ["content_changed"], "search_sources": ["result_count"],
            "fetch_source": ["bytes", "visible_chars"], "simulate": ["variant_mse", "candidate_gain"]},
        "measurement_scope": "Content diagnostics measure content only. They cannot establish the domain hypothesis. A simulation establishes only its registered model scope.",
        "alternatives": ["Select different authorized evidence or a supported discriminating simulation.",
            "Use a recorded evidence handle to repair interpretation without reacquisition.",
            "Request the missing capability with a measurable acceptance test and bounded scope."],
        "remaining_budget": {k: max(0, getattr(policy, "max_" + k) - v) for k,v in usage.items()},
        "repeat_limit": 2, "costs_retained": True, "grants_execution_authority": False}


def recover(root, task, policy, state):
    if (not policy.enabled or not state or not state.get("state", "").startswith("waiting_") or state.get("inflight")):
        return state
    from .research_episodes import episode_root, artifact_inventory
    directory = episode_root(root, state["episode_id"])
    contract = read_json(directory / "contract.json")
    if digest(contract) != state.get("contract_sha256") or contract.get("task") != dict(task):
        raise ValueError("research_contract_integrity_failure")
    if artifact_inventory(root, task["directive_id"]) != task["artifacts"]: return state
    usage = state["usage"]
    if any(usage[k] >= getattr(policy, "max_" + k) for k in ("model_calls", "tool_calls", "compute_seconds")):
        return state
    from .research_feedback import resume_reviewed_work
    state = resume_reviewed_work(root, directory, state, policy.max_model_calls)
    if state["state"] == "planning":
        write_json(directory / "state.json", state)
        return state
    if (state.get("state") != "waiting_for_changed_input" or state.get("method_recovery_version") == VERSION
            or not state.get("feedback", "").startswith("repeated_failed_method_requires_changed_input: unchanged_experiment")):
        return state
    receipt = {"version": VERSION, "episode_id": state["episode_id"], "contract_sha256": state["contract_sha256"],
        "previous_feedback": state["feedback"], "retained_usage": dict(usage),
        "failures_sha256": digest(state.get("failures", [])), "grants_execution_authority": False}
    receipt["sha256"] = digest(receipt)
    path = directory / "method-recovery.json"
    previous = read_json(path)
    if previous and previous != receipt: raise ValueError("research_recovery_receipt_integrity_failure")
    if not previous: write_json(path, receipt)
    state.update(state="planning", method_recovery_version=VERSION,
        method_feedback=feedback(state["feedback"], task, usage, policy))
    # Keep the rejection, plans_seen, raw response and repeat counters visible.
    write_json(directory / "state.json", state)
    return state
