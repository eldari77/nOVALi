"""A separately governed provider-repair reserve; all research costs persist."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

from .research_tools import digest, read_json, write_json, identifier
from .theory_workspace import TheoryWorkspace, text

VERSION = "provider_recovery_v1"


def _read(path: Path) -> dict[str, Any]:
    record = read_json(path)
    if record and record.get("sha256") != digest({k:v for k,v in record.items() if k != "sha256"}):
        raise ValueError("provider_recovery_receipt_integrity_failure")
    return record


def _write(path: Path, body: Mapping[str, Any]) -> dict[str, Any]:
    record = {"version": VERSION, **dict(body), "grants_execution_authority": False,
        "scientific_progress_credited": False}
    record["sha256"] = digest(record)
    if path.exists():
        if _read(path) != record:
            raise ValueError("immutable_provider_recovery_receipt_conflict")
    else:
        write_json(path, record)
    return record


def _probe_passed(probe: Mapping[str, Any]) -> bool:
    from scripts.verify_planner_format import expected_probe_values, probe_requests
    manifest = probe.get("manifest", {})
    if (probe.get("manifest_sha256") != digest(manifest) or probe.get("inflight")
            or probe.get("charged_model_calls") != 2 or len(probe.get("rows", [])) != 2
            or manifest.get("expected") != expected_probe_values()
            or manifest.get("requests") != probe_requests(manifest.get("provider", {}).get("model", ""))):
        raise ValueError("bounded_provider_probe_integrity_failure")
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("duplicate_probe_key")
            obj[key] = value
        return obj
    passed = []
    for row, expected in zip(probe["rows"], expected_probe_values()):
        try:
            result = json.loads(row["response"]["message"]["content"], object_pairs_hook=unique)
            passed.append(row.get("passed") is True and result == expected)
        except (ValueError, KeyError, TypeError):
            passed.append(False)
    return all(passed)


def register_repair(root: Path, before: Mapping[str, Any], after: Mapping[str, Any], *,
                    authority_reference: str) -> dict[str, Any]:
    text(authority_reference, "repair_authority", 500)
    old, new = before.get("manifest", {}).get("provider"), after.get("manifest", {}).get("provider")
    if (_probe_passed(before) or not _probe_passed(after) or not old or not new or old == new
            or before["manifest"]["requests"] != after["manifest"]["requests"]):
        raise ValueError("verified_failed_then_passing_provider_change_required")
    for identity in (old, new):
        if set(identity) != {"version", "model", "model_digest"} or not all(isinstance(v,str) and v for v in identity.values()):
            raise ValueError("explicit_provider_identity_required")
    body = {"before_provider": old, "after_provider": new, "before_probe": dict(before),
        "after_probe": dict(after), "authority_reference": authority_reference}
    key = "repair-" + digest(body)[:24]
    return _write(root / "research_recovery/repairs" / (key + ".json"), {"id": key, **body})


def current_provider_identity() -> dict[str, Any]:
    from scripts.verify_planner_format import provider_identity
    from .llm_interface import configured_ollama_base_url, configured_ollama_model
    return provider_identity(configured_ollama_base_url().rstrip("/"), configured_ollama_model())


def issue_grant(workspace: TheoryWorkspace, state: Mapping[str, Any], policy: Any, repair_id: str, *,
                calls: int, authority_reference: str) -> dict[str, Any]:
    """Operator-only amendment: at most one four-call reserve per source snapshot."""
    identifier(repair_id); text(authority_reference, "recovery_authority", 500)
    work = state["work"]; workspace.assert_current_sources()
    if (state.get("inflight") or state.get("state") != "waiting_for_changed_input"
            or type(calls) is not int or not 1 <= calls <= min(4, policy.max_theory_recovery_calls)):
        raise ValueError("settled_governed_recovery_reserve_required")
    attempt = read_json(workspace._path("model_turns", work["run_id"] + "-" + str(state["usage"]["model_calls"])))
    if not attempt:
        # Older runtimes retained a timeout's type/message digest and method
        # feedback, but did not write a model_turn for provider exceptions.
        # Preserve this provenance explicitly; never manufacture a provider reply.
        failure = state.get("feedback", "")
        method = state.get("method_feedback", {})
        if (failure in {"timed out", "timeout"} and state.get("failures", [])[-1:] == [digest(["TimeoutError", failure])]
                and method.get("reason") == failure and method.get("rejected_method", "missing") is None
                and method.get("costs_retained") is True
                and not workspace._path("turns", work["run_id"] + "-" + str(state["usage"]["model_calls"])).exists()):
            attempt = {"provider_error": failure, "evidence_kind": "legacy_persisted_timeout_state",
                "state_sha256": digest(state), "failure_digest": state["failures"][-1],
                "usage_at_attestation": dict(state["usage"]), "provider_response_available": False}
    error = attempt.get("provider_error", attempt.get("parse_error", ""))
    if (not error or state.get("feedback") != error
            or not any(term in error.lower() for term in ("timed out", "timeout", "json", "unterminated", "expecting", "duplicate"))):
        raise ValueError("recorded_provider_failure_required")
    repair = _read(workspace.root / "research_recovery/repairs" / (repair_id + ".json"))
    if not repair or not _probe_passed(repair["after_probe"]) or _probe_passed(repair["before_probe"]):
        raise ValueError("verified_provider_repair_required")
    path = workspace.root / "research_recovery/grants" / (work["run_id"] + ".json")
    for other in path.parent.glob("*.json"):
        grant = _read(other)
        if grant["snapshot_id"] == work["snapshot_id"] and other != path:
            raise ValueError("snapshot_recovery_reserve_already_assigned")
    return _write(path, {"run_id": work["run_id"], "snapshot_id": work["snapshot_id"], "work_sha256": digest(work),
        "repair_id": repair_id, "repair_sha256": repair["sha256"], "calls": calls,
        "usage_before": dict(state["usage"]), "failed_attempt": attempt,
        "failure": error, "authority_reference": authority_reference,
        "all_other_limits_unchanged": True, "lifetime_snapshot_grant_limit": 1})


def apply_grant(workspace: TheoryWorkspace, work: Mapping[str, Any], state: dict[str, Any], policy: Any,
                *, state_before_scientific_refresh: str | None = None) -> dict[str, Any]:
    if not state:
        return state
    grant = _read(workspace.root / "research_recovery/grants" / (work["run_id"] + ".json"))
    if not grant:
        return state
    if grant["work_sha256"] != digest(work) or grant["snapshot_id"] != work["snapshot_id"]:
        raise ValueError("provider_recovery_work_integrity_failure")
    repair = _read(workspace.root / "research_recovery/repairs" / (grant["repair_id"] + ".json"))
    if repair.get("sha256") != grant["repair_sha256"]:
        raise ValueError("provider_recovery_repair_integrity_failure")
    if any(state["usage"][k] < v for k,v in grant["usage_before"].items()):
        raise ValueError("provider_recovery_usage_regressed")
    if state.get("inflight"):
        return state
    status = read_json(workspace.root / "autonomy/status.json")
    original = copy.deepcopy(state)
    allowance = state.get("call_allowance", {})
    scientific_limit = allowance.get("scientific_model_call_limit", allowance.get("effective_model_call_limit", work["limits"]["model_calls"]))
    if (policy.max_theory_recovery_calls < grant["calls"] or not policy.enabled
            or (allowance.get("mode") == "complete_research_cycle" and not allowance.get("controls_allow"))
            or status.get("emergency_stop") or status.get("active") is False):
        state["call_allowance"] = {**allowance, "effective_model_call_limit": scientific_limit,
            "remaining_model_calls": max(0, scientific_limit-state["usage"]["model_calls"]), "provider_recovery_suspended": True}
        state["state"] = "waiting_for_changed_input"
        if state != original:
            write_json(workspace._path("runs", work["run_id"]), state)
        return state
    # refresh_call_allowance supplies a new base projection each cycle. Calling
    # this function twice on its own output must not add the reserve twice.
    effective = scientific_limit + grant["calls"]
    other_remaining = all(state["usage"][key] < work["limits"][key] for key in ("tool_calls", "compute_seconds", "evaluations"))
    activating = state.get("provider_recovery_grant_sha256") != grant["sha256"]
    if activating:
        if state["usage"] != grant["usage_before"] or state.get("feedback") != grant["failure"] or not other_remaining:
            raise ValueError("provider_recovery_failure_state_changed")
        if current_provider_identity() != repair["after_provider"]:
            raise ValueError("current_provider_does_not_match_verified_repair")
        state.update(provider_recovery_grant_sha256=grant["sha256"], state="ready", feedback="")
    elif (state["state"] == "waiting_for_changed_input"
            and (state_before_scientific_refresh == "ready" or state.get("feedback", "") in {"", "theory_epoch_budget_exhausted"})
            and state["usage"]["model_calls"] < effective and other_remaining):
        state["state"] = "ready"
    state["call_allowance"] = {**allowance, "scientific_model_call_limit": scientific_limit,
        "effective_model_call_limit": effective, "remaining_model_calls": max(0,effective-state["usage"]["model_calls"]),
        "provider_recovery_calls": grant["calls"], "provider_recovery_grant_sha256": grant["sha256"],
        "provider_recovery_suspended": False,
        "recovery_is_scientific_renewal": False, "grants_execution_authority": False}
    if state != original:
        write_json(workspace._path("runs", work["run_id"]), state)
    return state
