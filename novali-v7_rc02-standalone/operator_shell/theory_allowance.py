"""Evidence-gated call extensions; callers hold the existing research OS lease.

Usage never resets. A source snapshot gets at most two grants, each with a frozen
receipt. Extensions buy a bounded opportunity to finish research, never growth credit.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from .research_tools import digest, read_json, write_json
from .theory_evaluators import evaluator_fingerprint
from .theory_workspace import TheoryWorkspace

if TYPE_CHECKING:
    from .research_episodes import ResearchPolicy

VERSION = "theory_call_renewal_v1"
COMPLETION_COMMANDS = ["register_claim", "propose_revision", "evaluate_revision",
                       "decide_revision", "inspect_record", "request_capability",
                       "retrieve_evidence", "inspect_dependency", "submit_research_plan",
                       "register_formal_claim", "submit_review_response", "check_measurement"]
RENEWABLE_FEEDBACK = {"", "theory_epoch_budget_exhausted", "one_typed_theory_command_required",
    "unchanged_theory_command_reuse_prior_observation",
    "Reused frozen evidence without a new acquisition charge. Continue from the supplied result."}


def _read_receipt(path: Path) -> dict[str, Any]:
    record = read_json(path)
    if record and record.get("sha256") != digest({k:v for k,v in record.items() if k != "sha256"}):
        raise ValueError("call_allowance_receipt_integrity_failure")
    return record


def _write_receipt(path: Path, body: Mapping[str, Any]) -> dict[str, Any]:
    record = {**body, "grants_execution_authority": False, "scientific_progress_credited": False}
    record["sha256"] = digest(record)
    existing = _read_receipt(path)
    if existing and existing != record:
        raise ValueError("immutable_call_allowance_receipt_conflict")
    if not existing:
        write_json(path, record)
    return record


def _controls_allow(workspace: TheoryWorkspace, policy: ResearchPolicy) -> bool:
    from . import conveyor
    root = workspace.root
    autonomy = read_json(root / "autonomy/status.json")
    charter = read_json(root / "autonomy/charter.json")
    snapshot = read_json(root / "conveyor/bounded_status_snapshot_latest.json")
    return bool(policy.enabled and workspace.subject_id in policy.theory_subject_ids
        and autonomy.get("active") and not autonomy.get("emergency_stop")
        and {"local_repo_state", "operator_state_artifacts"}.issubset(charter.get("approved_research_sources", []))
        and conveyor._load_scheduler(root).get("continuous_campaign_mode")
        and not snapshot.get("active_child_count") and not conveyor._active_children(root))


def _grants(workspace: TheoryWorkspace, work: Mapping[str, Any]) -> list[dict[str, Any]]:
    paths = list((workspace.base / "call_renewals").glob("*.json"))
    if len(paths) > 1024:
        raise ValueError("call_allowance_history_limit")
    records = [_read_receipt(path) for path in paths]
    return [r for r in records if r.get("snapshot_id") == work["snapshot_id"]]


def _verified_evidence(workspace: TheoryWorkspace, work: Mapping[str, Any], state: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve actual command receipts, not model assertions or mutable counters."""
    workspace.assert_current_sources()
    snapshot = workspace._snapshot()
    pages: dict[tuple[str, int], dict[str, Any]] = {}
    evaluations: dict[str, int] = {}
    for call in range(1, min(int(state["usage"]["model_calls"]), 36) + 1):
        key = work["run_id"] + "-" + str(call)
        turn = read_json(workspace._path("turns", key))
        if not turn:
            continue
        result, command = turn.get("result", {}), turn.get("command", {})
        model = read_json(workspace._path("model_turns", key))
        if digest(result) != turn.get("result_sha256") or model.get("response") != command:
            raise ValueError("call_allowance_evidence_integrity_failure")
        if command.get("command") == "inspect_source":
            source_id = result.get("id")
            if source_id not in snapshot["sources"]:
                raise ValueError("call_allowance_source_snapshot_changed")
            source = workspace.read_record("sources", source_id)
            offset = command["arguments"]["offset_chars"]
            end = min(len(source["content"]), offset + 4000)
            if (result.get("sha256") != source["sha256"] or result.get("offset_chars") != offset
                    or result.get("next_offset_chars") != end or result.get("text") != source["content"][offset:end]):
                raise ValueError("call_allowance_source_integrity_failure")
            if end > offset:
                pages[source_id, offset] = {"source_id": source_id, "path": source["path"],
                    "offset_chars": offset, "next_offset_chars": end, "result_sha256": turn["result_sha256"]}
        elif command.get("command") in {"evaluate_revision", "submit_research_plan"}:
            if command["command"] == "submit_research_plan":
                result = result["evaluation"]
            receipt = workspace.read_record("evaluations", result["id"])
            contract = read_json(workspace._path("contracts", receipt["experiment_key"]))
            pointer = read_json(workspace._path("experiment_index", receipt["experiment_key"]))
            if (receipt != result or receipt["snapshot_id"] != work["snapshot_id"]
                    or digest(contract) != receipt["contract_sha256"] or pointer.get("state") != "completed"
                    or pointer.get("receipt_id") != receipt["id"]
                    or pointer.get("contract_sha256") != receipt["contract_sha256"]
                    or contract.get("model_spec") != receipt["model_spec"]
                    or evaluator_fingerprint(contract["evaluator_id"]) != receipt["evaluator_sha256"]):
                raise ValueError("call_allowance_evaluation_integrity_failure")
            # A failed instrument fidelity gate is diagnostic repair evidence,
            # not a newly completed scientific evaluation that can renew calls.
            if contract["evaluator_id"] in {"nine_d_intervention_v1", "nine_d_comparison_v2"} and receipt.get("assessment", {}).get("validity") != "valid":
                continue
            evaluations.setdefault(receipt["id"], call)
    coverage = 0
    for source_id in snapshot["sources"]:
        end = 0
        for page in sorted((p for p in pages.values() if p["source_id"] == source_id), key=lambda p:p["offset_chars"]):
            coverage += max(0, page["next_offset_chars"] - max(end, page["offset_chars"]))
            end = max(end, page["next_offset_chars"])
    total = sum(row["characters"] for row in snapshot["sources"].values())
    sufficient = coverage >= min(8000, total) and len({p["source_id"] for p in pages.values()}) >= min(2, len(snapshot["sources"]))
    return {"source_pages": list(pages.values()), "unique_characters": coverage,
            "sufficient_source_coverage": bool(total and sufficient), "evaluations": evaluations}


def refresh_call_allowance(workspace: TheoryWorkspace, work: Mapping[str, Any], state: dict[str, Any], policy: ResearchPolicy) -> dict[str, Any]:
    if not state:
        return state
    if state.get("work") != dict(work):
        raise ValueError("theory_run_contract_integrity_failure")
    original = dict(state)
    base = work["limits"]["model_calls"]
    contract_path = workspace._path("call_allowances", work["run_id"])
    contract = _read_receipt(contract_path)
    if contract and (contract.get("work_sha256") != digest(work) or contract.get("base_calls") != base):
        raise ValueError("call_allowance_contract_integrity_failure")
    grants = _grants(workspace, work)
    own = sorted((r for r in grants if r["run_id"] == work["run_id"]), key=lambda r:r["index"])
    ceiling = base
    for index, grant in enumerate(own, 1):
        if (not contract or grant["index"] != index or grant["contract_sha256"] != contract["sha256"]
                or grant["previous_limit"] != ceiling or grant["new_limit"] != ceiling + contract["calls_per_renewal"]
                or index > contract["max_renewals"] or grant["usage_before"]["model_calls"] < ceiling):
            raise ValueError("call_allowance_grant_chain_integrity_failure")
        ceiling = grant["new_limit"]
    configured_ceiling = base + policy.max_theory_call_renewals * policy.max_theory_renewal_calls
    effective = min(ceiling, configured_ceiling)
    controls = _controls_allow(workspace, policy) if policy.max_theory_call_renewals else False
    usage = state["usage"]
    if state.get("allowance_suspended") and controls and effective > usage["model_calls"] and not state.get("inflight"):
        state.update(state="ready", allowance_suspended=False)
    reason = "allowance_available" if usage["model_calls"] < effective else "renewal_disabled"
    evidence = None
    # An immutable grant survives a crash between receipt creation and state update.
    pending_activation = bool(own and state.get("call_allowance", {}).get("active_grant_sha256") != own[-1]["sha256"]
        and usage == own[-1]["usage_before"] and not state.get("inflight") and controls
        and effective > usage["model_calls"])
    if policy.max_theory_call_renewals and usage["model_calls"] >= effective:
        reason = "renewal_ceiling_reached"
        max_renewals = min(policy.max_theory_call_renewals, contract["max_renewals"] if contract else 2)
        remaining_resources = (usage["tool_calls"] < work["limits"]["tool_calls"]
            and usage["evaluations"] < work["limits"]["evaluations"]
            and work["limits"]["compute_seconds"] - usage["compute_seconds"] >= min(30, policy.model_timeout_seconds) + 45)
        if not controls:
            reason = "renewal_control_gate_closed"
        elif state.get("inflight") or state.get("state") == "waiting_for_capability":
            reason = "renewal_requires_settled_research"
        elif not remaining_resources:
            reason = "renewal_requires_remaining_tool_compute_and_evaluation_budget"
        elif len(grants) >= max_renewals:
            reason = "renewal_ceiling_reached"
        elif state.get("feedback", "") not in RENEWABLE_FEEDBACK:
            reason = "renewal_cannot_bypass_unresolved_failure"
        elif len(grants) < max_renewals and (not contract or policy.max_theory_renewal_calls >= contract["calls_per_renewal"]):
            evidence = _verified_evidence(workspace, work, state)
            consumed = {key for grant in grants for key in grant["evidence_keys"]}
            baseline = {key for grant in grants for key in grant.get("evaluation_ids_at_grant", [])}
            fresh = sorted(key for key in evidence["evaluations"] if key not in consumed | baseline)
            bootstrap_key = "source_completion:" + work["snapshot_id"]
            keys, basis = (fresh[:1], "new_independent_evaluation") if fresh else ([], "")
            if not keys and bootstrap_key not in consumed and not own and evidence["sufficient_source_coverage"]:
                keys, basis = [bootstrap_key], "verified_sources_ready_for_synthesis"
            reason = "new_independent_evaluation_required" if own else "insufficient_verified_source_evidence"
            if keys:
                if not contract:
                    contract = _write_receipt(contract_path, {"version": VERSION, "run_id": work["run_id"],
                        "snapshot_id": work["snapshot_id"], "work_sha256": digest(work), "base_calls": base,
                        "max_renewals": policy.max_theory_call_renewals, "calls_per_renewal": policy.max_theory_renewal_calls})
                grant = _write_receipt(workspace._path("call_renewals", work["run_id"] + "-" + str(len(own) + 1)), {
                    "version": VERSION, "run_id": work["run_id"], "snapshot_id": work["snapshot_id"],
                    "index": len(own) + 1, "contract_sha256": contract["sha256"], "previous_limit": ceiling,
                    "new_limit": ceiling + contract["calls_per_renewal"], "usage_before": dict(usage),
                    "previous_feedback": state.get("feedback", ""), "basis": basis, "evidence_keys": keys,
                    "evaluation_ids_at_grant": sorted(r["id"] for r in workspace._records("evaluations") if r["snapshot_id"] == work["snapshot_id"]),
                    "source_read_history": evidence["source_pages"], "unique_source_characters": evidence["unique_characters"]})
                own.append(grant); grants.append(grant)
                effective = grant["new_limit"]; pending_activation = True; reason = "allowance_available"
    if pending_activation:
        state.update(state="ready", feedback="Call allowance extended for a bounded completion window. Use verified evidence memory, at most two unread claim dependency checks, and an executable research plan or precise capability request. Previous costs and failures remain recorded.")
    active = bool(own and usage["model_calls"] >= base)
    if active and state["state"] == "ready" and (not controls or effective <= usage["model_calls"] < ceiling) and not state.get("inflight"):
        state["allowance_suspended"] = True
    info = {"version": VERSION, "base_model_call_limit": base, "effective_model_call_limit": effective,
        "remaining_model_calls": max(0, effective - usage["model_calls"]), "renewal_count": len(own),
        "snapshot_renewal_count": len(grants), "renewal_reason": reason,
        "mode": "complete_research_cycle" if active else "base_allowance",
        "allowed_commands": COMPLETION_COMMANDS if active else [],
        "active_grant_sha256": own[-1]["sha256"] if own else None,
        "last_grant_basis": own[-1]["basis"] if own else None,
        "source_read_history": own[-1]["source_read_history"] if own else [],
        "controls_allow": controls, "grants_execution_authority": False, "scientific_progress_credited": False}
    if active and not controls and not state.get("inflight"):
        state.update(state="waiting_for_changed_input")
    if usage["model_calls"] >= effective and not state.get("inflight") and state["state"] != "waiting_for_capability":
        state.update(state="waiting_for_changed_input")
    if policy.max_theory_call_renewals or contract:
        info["work_state"] = state["state"]
        info["blocked_reason"] = state.get("feedback", "") if state["state"].startswith("waiting_") else ""
        state["call_allowance"] = info
    if state != original:
        write_json(workspace._path("runs", work["run_id"]), state)
    return state
