"""Durable Novali-owned research episodes with frozen evaluation contracts.

The planner proposes experiments and interprets results. This module owns budgets,
evidence identity and verification. Completion means a reviewable research result;
only the existing support validators may accept project evidence or close gates.
"""
from __future__ import annotations

import copy
import json
import math
import operator
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .research_tools import (TOOLS, artifact_inventory, digest, identifier, normalize_action, read_json, run_tool, write_json)
from .support_retry import support_input_fingerprint
from . import research_learning as learning

EVALUATOR_VERSION = "research_evaluator_v2"
TERMINAL_STATES = {"completed", "waiting_for_changed_input", "waiting_for_capability", "superseded"}
FACT_FIELDS = {"manufacturer", "mpn", "datasheet_url", "electrical_rating", "unit_cost", "standards_reference"}
COMPARATORS = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le, "==": operator.eq}
Planner = Callable[[str, Mapping[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ResearchPolicy:
    enabled: bool = False
    directive_ids: tuple[str, ...] = ()
    max_model_calls: int = 4
    max_tool_calls: int = 6
    max_network_calls: int = 2
    max_compute_seconds: int = 360
    model_timeout_seconds: int = 90
    max_output_tokens: int = 1800
    min_tick_interval_seconds: int = 15
    max_episodes_per_input: int = 3
    theory_subject_ids: tuple[str, ...] = ()
    max_theory_model_calls: int = 12
    max_theory_tool_calls: int = 18
    max_theory_compute_seconds: int = 1800
    max_theory_evaluations: int = 3
    max_theory_call_renewals: int = 0
    max_theory_renewal_calls: int = 4
    max_theory_recovery_calls: int = 0

    def __post_init__(self) -> None:
        for name, lower, upper in (("max_model_calls", 1, 8), ("max_tool_calls", 1, 12),
                                   ("max_network_calls", 0, 4), ("max_compute_seconds", 10, 900),
                                   ("model_timeout_seconds", 1, 180), ("max_output_tokens", 256, 3000),
                                   ("min_tick_interval_seconds", 1, 300)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
                raise ValueError("invalid_research_budget_" + name)
        if type(self.max_episodes_per_input) is not int or not 1 <= self.max_episodes_per_input <= 4:
            raise ValueError("invalid_research_episode_budget")
        if len(self.directive_ids) > 12:
            raise ValueError("research_directive_limit")
        for item in self.directive_ids:
            identifier(item)
        if len(self.theory_subject_ids)>4:
            raise ValueError("theory_subject_limit")
        for item in self.theory_subject_ids: identifier(item)
        for name,low,high in (("max_theory_model_calls",1,24),("max_theory_tool_calls",1,32),
                              ("max_theory_compute_seconds",60,3600),("max_theory_evaluations",1,6),
                              ("max_theory_call_renewals",0,2),("max_theory_renewal_calls",1,6),
                              ("max_theory_recovery_calls",0,4)):
            value=getattr(self,name)
            if type(value) is not int or not low<=value<=high: raise ValueError("invalid_"+name)


def route_gaps(support: Mapping[str, Any], context: Mapping[str, Any]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    if support.get("support_pack_source_missing") or support.get("support_pack_consumability_state") == "metadata_only":
        gaps.append({"kind": "missing_artifact", "fields": ["support_pack_contents"],
                     "action": "reconstruct a new traceable candidate from available artifacts; do not relabel the missing pack"})
    rows = context.get("requested_rows") or support.get("requested_rows") or []
    for row in rows[:24]:
        fields = [str(field) for field in row.get("required_fields", [])[:32]]
        external = [field for field in fields if field in FACT_FIELDS and row.get("commercial_component_source_required")]
        design = [field for field in fields if field not in external]
        for kind, selected in (("external_fact", external), ("design_decision", design)):
            if selected:
                gaps.append({"kind": kind, "requested_row_id": str(row.get("requested_row_id", "")), "fields": selected})
    target = context.get("target_artifact") or support.get("target_artifact") or ""
    if target == "novelty_delta.json":
        gaps.append({"kind": "causal_or_novelty_claim", "fields": ["baseline_comparison"],
                     "action": "compare actual artifacts; content differences alone are not scientific novelty"})
    if not gaps:
        fields = list(context.get("missing_fields") or support.get("missing_fields") or [target or "research_deliverable"])
        gaps.append({"kind": "design_decision", "fields": fields[:32]})
    if support.get("operator_review_required") and support.get("support_state") == "pending_operator_review":
        gaps.append({"kind": "operator_review", "fields": ["review_decision"], "action": "preserve the review requirement"})
    return gaps


def _support_revision(support: Mapping[str, Any], context: Mapping[str, Any]) -> str:
    return support_input_fingerprint(support, source_plan={}, adapters={
        "target_artifact": context.get("target_artifact", ""),
        "requested_rows": context.get("requested_rows") or support.get("requested_rows") or [],
        "directive_text": context.get("directive_text", ""),
        "missing_fields": context.get("missing_fields", []),
        "required_gates": context.get("required_gates", []),
        "pack_missing": support.get("support_pack_source_missing", False),
        "pack_ref": support.get("satisfied_pack_ref", ""),
    })


def prepare_task(root: Path, support: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any]:
    directive_id = identifier(support.get("directive_id") or context.get("directive_id"))
    support_id = identifier(support.get("support_request_id"))
    artifacts = artifact_inventory(root, directive_id)
    requested = list(context.get("requested_rows") or support.get("requested_rows") or [])[:24]
    task = {"directive_id": directive_id, "support_request_id": support_id,
            "target_artifact": str(context.get("target_artifact") or support.get("target_artifact") or ""),
            "directive_text": str(context.get("directive_text", ""))[:10000],
            "requested_rows": requested, "gaps": route_gaps(support, context), "artifacts": artifacts,
            "support_revision": _support_revision(support, context),
            "support_contract_sha256": support_input_fingerprint(support, source_plan={}, adapters={}),
            "operator_review_required": bool(support.get("operator_review_required")),
            "grants_execution_authority": False}
    task["input_fingerprint"] = digest({"support_revision": task["support_revision"], "artifacts": artifacts,
                                         "evaluator": EVALUATOR_VERSION})
    return task


def episode_root(root: Path, episode_id: str) -> Path:
    return root / "conveyor/research/episodes" / identifier(episode_id)


def load_episode(root: Path, episode_id: str) -> dict[str, Any]:
    return read_json(episode_root(root, episode_id) / "state.json")


def _text(value: Any, name: str, minimum: int = 12, maximum: int = 2000) -> str:
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise ValueError("specific_" + name + "_required")
    return value.strip()


def validate_plan(plan: Mapping[str, Any], task: Mapping[str, Any], policy: ResearchPolicy) -> None:
    for name in ("question", "hypothesis", "falsification"):
        _text(plan.get(name), name)
    alternatives = plan.get("alternatives")
    if not isinstance(alternatives, list) or not 2 <= len(alternatives) <= 4:
        raise ValueError("competing_explanations_required")
    for alternative in alternatives:
        _text(alternative, "alternative")
    actions = plan.get("actions")
    if not isinstance(actions, list) or not 1 <= len(actions) <= min(4, policy.max_tool_calls):
        raise ValueError("bounded_executable_actions_required")
    actions = [normalize_action(action) for action in actions]
    ids = [identifier(action.get("id")) for action in actions]
    if len(set(ids)) != len(ids) or any(action.get("tool") not in TOOLS for action in actions):
        raise ValueError("invalid_research_actions")
    if any(action["tool"] not in task.get("allowed_tools", TOOLS) for action in actions):
        raise ValueError("research_tool_not_authorized_by_charter")
    if sum(action["tool"] in {"fetch_source", "search_sources"} for action in actions) > policy.max_network_calls:
        raise ValueError("network_budget_exceeded")
    for action in actions:
        required = {"inspect_artifact": ("artifact_ref",), "compare_artifacts": ("before_ref", "after_ref"),
                    "fetch_source": ("url",), "search_sources": ("query",), "simulate": ("spec",)}[action["tool"]]
        if any(not action.get(field) for field in required):
            raise ValueError("required_research_tool_arguments_missing")
        if len(json.dumps(action)) > 18000:
            raise ValueError("research_action_size_limit")
        for field in ("artifact_ref", "before_ref", "after_ref"):
            if field in action and action[field] not in task["artifacts"]:
                raise ValueError("artifact_not_in_frozen_inventory")
    prediction = plan.get("prediction", {})
    if (not isinstance(prediction, Mapping) or prediction.get("action_id") not in ids or prediction.get("operator") not in COMPARATORS
            or not isinstance(prediction.get("metric"), str)):
        raise ValueError("measurable_prediction_required")
    value = prediction.get("value")
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError("finite_prediction_threshold_required")
    predicted_action = next(action for action in actions if action["id"] == prediction["action_id"])
    if prediction["metric"] not in learning.metric_names(predicted_action):
        raise ValueError("prediction_metric_not_produced_by_selected_tool")
    if plan.get("nine_d_mechanism"):
        mechanism = plan["nine_d_mechanism"]
        for field in ("name", "decision_changed", "prediction", "falsifier"):
            _text(mechanism.get(field), "mechanism_" + field, minimum=5)
        if not any(action["tool"] == "simulate" and
                   {"baseline", "candidate", "ablation"}.issubset(action.get("spec", {}).get("variants", {}))
                   for action in actions):
            raise ValueError("nine_d_mechanism_requires_matched_ablation")


def _plan_fingerprint(plan: Mapping[str, Any]) -> str:
    # New thresholds or equivalent tool defaults do not acquire new evidence.
    return digest(sorted([learning.acquisition(action) for action in plan["actions"]], key=digest))


class ResearchCitationError(ValueError):
    def __init__(self, field_issues: list[dict[str, Any]]):
        self.field_issues = field_issues
        super().__init__('invalid_research_citations:' + ';'.join(i['path'] + ':' + i['code'] for i in field_issues))


def verify_result(plan: Mapping[str, Any], observations: list[dict[str, Any]],
                  interpretation: Mapping[str, Any]) -> dict[str, Any]:
    """Deterministic verifier. Model assertions cannot provide their own proof."""
    learning.evidence_options(observations)  # Verify hashes even for legacy quotations or proposal-only results.
    by_id = {row["action_id"]: row for row in observations}
    prediction = plan["prediction"]
    observed = by_id.get(prediction["action_id"], {})
    measured = observed.get("result", {}).get("metrics", {}).get(prediction["metric"])
    verdict = "inconclusive"
    if observed.get("ok") and isinstance(measured, (float, int)) and not isinstance(measured, bool) and math.isfinite(measured):
        verdict = "supported_in_this_test" if COMPARATORS[prediction["operator"]](measured, prediction["value"]) else "refuted"
    _text(interpretation.get("interpretation"), "interpretation")
    _text(interpretation.get("next_question"), "next_question")
    claims = interpretation.get("claims")
    if not isinstance(claims, list) or not 1 <= len(claims) <= 12:
        raise ValueError("bounded_research_claims_required")
    citation_issues = []
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            continue
        refs = claim.get('evidence_refs', [])
        if not isinstance(refs, list):
            citation_issues.append({'path': f'/claims/{index}/evidence_refs', 'code': 'array_of_action_id_strings_required',
                                    'available_action_ids': sorted(by_id)})
            continue
        for ref_index, ref in enumerate(refs):
            if not isinstance(ref, str) or ref not in by_id:
                citation_issues.append({'path': f'/claims/{index}/evidence_refs/{ref_index}',
                    'code': 'action_id_string_required' if not isinstance(ref, str) else 'unknown_evidence_ref',
                    'actual': ref, 'available_action_ids': sorted(by_id),
                    'repair': 'select a cached evidence_handle and its string action_id; retain the observation'})
    if citation_issues:
        raise ResearchCitationError(citation_issues)
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("research_claim_object_required")
        _text(claim.get("text"), "claim")
        if claim.get("kind") == "observation" and learning.bind_evidence_claim(claim, observations):
            continue
        refs = claim.get("evidence_refs", [])
        if not isinstance(refs, list) or any(ref not in by_id for ref in refs):
            raise ValueError("unknown_evidence_ref")
        if claim.get("kind") == "observation":
            if not refs:
                raise ValueError("observation_evidence_ref_required")
            quote_text = _text(claim.get("quote"), "observation_quote", minimum=8, maximum=400)
            texts = [str(by_id[ref].get("result", {}).get("text", "")) for ref in refs if by_id[ref].get("ok")]
            if not any(quote_text in text for text in texts):
                raise ValueError("observation_quote_not_in_evidence: copy one contiguous literal excerpt; classify inferences as proposals")
            # Only the literal observed excerpt is promoted as an observation.
            # The model's broader interpretation remains a proposal.
            claim["text"] = quote_text
        elif claim.get("kind") == "proposal":
            assumptions = claim.get("assumptions")
            if not isinstance(assumptions, list) or not assumptions:
                raise ValueError("proposal_assumptions_required")
            claim["evidence_basis"] = "recorded_observations_and_assumptions" if refs else "declared_assumptions_only"
        else:
            raise ValueError("claim_kind_must_be_observation_or_proposal")
    candidate = interpretation.get("candidate_artifact", {})
    if not isinstance(candidate, dict) or len(json.dumps(candidate)) > 24000:
        raise ValueError("candidate_artifact_size_limit")
    return {"evaluator_version": EVALUATOR_VERSION, "prediction_verdict": verdict,
            "hypothesis_verdict": "inconclusive",
            "hypothesis_assessment": "independent_claim_evaluation_required",
            "measurement_scope": observed.get("result", {}).get("scope", "unassessed"),
            "observed_metric": measured, "prediction": prediction,
            "successful_tool_count": sum(bool(row.get("ok")) for row in observations),
            "failed_tool_count": sum(not row.get("ok") for row in observations),
            "informative_rejection": False, "support_gate_passed": False,
            "growth_demonstrated": False, "nine_d_advantage_demonstrated": False,
            "interpretation_status": "proposal_for_existing_support_validation",
            "grants_execution_authority": False}


def _memory(root: Path, task: Mapping[str, Any]) -> list[dict[str, Any]]:
    found = []
    for sequence, (original, original_task) in enumerate(learning.experiences(root)):
        try:
            valid = (original_task.get("artifacts") == artifact_inventory(root, original_task["directive_id"])
                     and not source_dependency_events(root, original.get("observations", [])))
        except (ValueError, OSError, KeyError, TypeError):
            continue
        same_task = original_task.get("directive_id") == task["directive_id"]
        plan, interpretation = original.get("plan", {}), original.get("interpretation", {})
        failures = original.get("failures", [])
        lesson = failures[-1].get("lesson", {}) if failures else learning.failure_lesson(original.get("feedback", ""))
        overlap = len({x["kind"] for x in task.get("gaps", [])} &
                      {x["kind"] for x in original_task.get("gaps", [])})
        found.append((10 * same_task + overlap, sequence, {
            "episode_id": original["episode_id"], "state": original["state"], "input_still_valid": valid,
            "hypothesis_verdict": "inconclusive",  # Legacy diagnostic verdicts are not semantic proof.
            "prediction_verdict": original.get("verification", {}).get("prediction_verdict", "unassessed"),
            "question": plan.get("question", ""), "next_question": interpretation.get("next_question", "") if same_task else "",
            "claims": interpretation.get("claims", [])[:4] if same_task and valid else [],
            "methods_used": sorted({action["tool"] for action in plan.get("actions", [])}),
            "capability_request": original.get("capability_request", {}),
            "lesson": lesson if lesson.get("failure") else {},
            "experiment_fingerprint": _plan_fingerprint(plan) if plan else "",
            "same_input": original_task.get("input_fingerprint") == task["input_fingerprint"],
            "use": "consider procedure; revalidate applicability" if same_task and valid else "procedure only; do not transfer domain claims",
            "transfer_verified": False}))
    return [entry for _, _, entry in sorted(found, key=lambda row: row[:2])[-4:]]


def source_dependency_events(root: Path, observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stable changes in source validity can wake a bounded refresh investigation."""
    import hashlib

    events = []
    for observation in observations:
        result = observation.get("result", {})
        if not observation.get("ok") or result.get("evidence_kind") != "source_document":
            continue
        reason = ""
        try:
            if len(str(result.get("sha256", ""))) != 64 or set(result["sha256"]) - set("0123456789abcdef"):
                raise ValueError("invalid_source_hash")
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(result["retrieved_at"])).total_seconds()
            body = root / "conveyor/research/documents" / (result["sha256"] + ".html")
            latest = read_json(root / "conveyor/research/documents" / (digest(result["url"]) + ".json"))
            if age < -60 or age > 86400:
                reason = "source_refresh_required"
            elif (not body.is_file() or body.stat().st_size > 2_000_000
                  or hashlib.sha256(body.read_bytes()).hexdigest() != result["sha256"]):
                reason = "source_content_unavailable_or_changed"
            elif latest.get("sha256") != result["sha256"]:
                reason = "source_revision_changed"
        except (ValueError, OSError, KeyError, TypeError):
            reason = "source_dependency_unverifiable"
        if reason:
            events.append({"url": result.get("url", ""), "sha256": result.get("sha256", ""),
                           "retrieved_at": result.get("retrieved_at", ""), "reason": reason})
    return events


def _publish(root: Path, state: dict[str, Any], task: Mapping[str, Any]) -> None:
    directory = episode_root(root, state["episode_id"])
    packet = {"episode_id": state["episode_id"], "directive_id": task["directive_id"],
              "support_request_id": task["support_request_id"], "target_artifact": task["target_artifact"],
              "input_fingerprint": task["input_fingerprint"], "artifact_revisions": task["artifacts"],
              "plan": state["plan"], "observations": state["observations"],
              "interpretation": state["interpretation"], "verification": state["verification"],
              "usage": state["usage"], "grants_execution_authority": False,
              "candidate_status": "research_only_requires_existing_support_validation"}
    write_json(directory / "result.json", packet)
    revision = digest(packet)
    state["result_sha256"] = revision
    # A separate pointer avoids racing the support kernel's read/modify/write.
    # The consumer still validates directive, contract, evidence and revisions.
    write_json(root / "conveyor/research/handoffs" / (task["support_request_id"] + ".json"), {
        "episode_id": state["episode_id"], "result_sha256": revision,
        "input_fingerprint": task["input_fingerprint"], "grants_execution_authority": False})
    index_path = root / "conveyor/research/memory_index.json"
    index = read_json(index_path)
    entries = [row for row in index.get("entries", []) if row.get("episode_id") != state["episode_id"]]
    entries.append({"episode_id": state["episode_id"], "target_artifact": task["target_artifact"],
                    "directive_id": task["directive_id"], "result_sha256": revision})
    # Complete records remain on disk; the hot retrieval index is bounded.
    write_json(index_path, {"entries": entries[-64:], "grants_execution_authority": False})


def load_research_handoff(root: Path, support: Mapping[str, Any],
                          context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    pointer = read_json(root / "conveyor/research/handoffs" / (identifier(support["support_request_id"]) + ".json"))
    episode_id = pointer.get("episode_id")
    if not episode_id:
        return {}
    state = load_episode(root, episode_id)
    if state.get("state") != "completed":
        return {}
    packet = read_json(episode_root(root, episode_id) / "result.json")
    contract = read_json(episode_root(root, episode_id) / "contract.json")
    task = contract.get("task", {})
    if (digest(packet) != state.get("result_sha256") or packet.get("directive_id") != support.get("directive_id")
            or digest(contract) != state.get("contract_sha256") or pointer.get("result_sha256") != digest(packet)
            or task.get("support_contract_sha256") != support_input_fingerprint(support, source_plan={}, adapters={})
            or (context is not None and task.get("support_revision") != _support_revision(support, context))
            or packet.get("support_request_id") != support.get("support_request_id")
            or packet.get("artifact_revisions") != artifact_inventory(root, packet["directive_id"])):
        return {}
    for observation in packet.get("observations", []):
        result = observation.get("result", {})
        if observation.get("ok") and digest(result) != observation.get("result_sha256"):
            return {}
    if source_dependency_events(root, packet.get("observations", [])):
        return {}
    return packet


def directive_policy(policy: ResearchPolicy) -> dict[str, Any]:
    """Preserve the original directive contract when theory-only settings change."""
    return {key: value for key, value in asdict(policy).items()
            if key != "theory_subject_ids" and not key.startswith("max_theory_")}


def advance_episode(root: Path, task: Mapping[str, Any], policy: ResearchPolicy, *, planner: Planner) -> dict[str, Any]:
    if not policy.enabled or task["directive_id"] not in policy.directive_ids:
        return {"state": "disabled", "grants_execution_authority": False}
    episode_id = episode_identity(task, policy)
    directory = episode_root(root, episode_id)
    state = load_episode(root, episode_id)
    if not state:
        # Retain bounded pre-upgrade scheduler pointers before its next snapshot
        # replaces them. This indexes existing evidence without rewriting it.
        for prior_state, prior_task in learning.experiences(root):
            learning.remember(root, prior_state, prior_task)
        contract = {"task": dict(task), "budget": directive_policy(policy), "evaluator_version": EVALUATOR_VERSION,
                    "acceptance": "traceable research result; existing support gates remain authoritative",
                    "grants_execution_authority": False}
        write_json(directory / "contract.json", contract)
        state = {"episode_id": episode_id, "state": "planning", "contract_sha256": digest(contract),
                 "usage": {"model_calls": 0, "tool_calls": 0, "network_calls": 0, "compute_seconds": 0.0},
                 "plans_seen": [], "observations": [], "feedback": "", "created_at": datetime.now(timezone.utc).isoformat(),
                 "memory_considered": _memory(root, task), "grants_execution_authority": False}
        state["plans_seen"] = [item["experiment_fingerprint"] for item in state["memory_considered"] if item["same_input"]]
        write_json(directory / "state.json", state)
    contract = read_json(directory / "contract.json")
    if digest(contract) != state.get("contract_sha256") or contract.get("task") != dict(task):
        raise ValueError("research_contract_integrity_failure")
    if state.get("plan") and digest(state["plan"]) != state.get("plan_sha256"):
        raise ValueError("research_plan_integrity_failure")
    from .research_recovery import recover, feedback as method_feedback
    state = recover(root, task, policy, state)
    if state["state"] in TERMINAL_STATES:
        if state["state"] == "completed" and not state.get("result_sha256"):
            _publish(root, state, task)
            write_json(directory / "state.json", state)
            learning.remember(root, state, task)
        return state
    if contract.get("evaluator_version") != EVALUATOR_VERSION:
        raise ValueError("research_evaluator_changed_prepare_new_task")
    if artifact_inventory(root, task["directive_id"]) != task["artifacts"]:
        state["state"] = "superseded"
        write_json(directory / "state.json", state)
        return state
    usage = state["usage"]
    if usage["compute_seconds"] >= policy.max_compute_seconds:
        state.update(state="waiting_for_changed_input", feedback="compute_budget_exhausted")
        write_json(directory / "state.json", state)
        learning.remember(root, state, task)
        return state
    # A crash during a reserved action consumes its budget and is recorded as an
    # unknown outcome. It is never silently executed twice after restart.
    if state.get("inflight"):
        inflight = state.pop("inflight")
        if inflight["kind"] == "tool":
            state["observations"].append({"action_id": inflight["id"], "ok": False,
                                           "error": "interrupted_outcome_unknown"})
        else:
            state["feedback"] = "previous_model_call_interrupted; reserved budget retained"
        usage["compute_seconds"] += inflight.get("reserved_seconds", 0)
    remaining_seconds = policy.max_compute_seconds - usage["compute_seconds"]
    if remaining_seconds < 1:
        state.update(state="waiting_for_changed_input", feedback="compute_budget_exhausted")
        write_json(directory / "state.json", state)
        learning.remember(root, state, task)
        return state
    started = time.perf_counter()
    candidate_response = None
    try:
        if state["state"] == "planning":
            if usage["model_calls"] >= policy.max_model_calls:
                state.update(state="waiting_for_changed_input", feedback="model_budget_exhausted")
            else:
                usage["model_calls"] += 1
                state["inflight"] = {"kind": "model", "id": str(usage["model_calls"]),
                                     "reserved_seconds": min(policy.model_timeout_seconds, remaining_seconds)}
                write_json(directory / "state.json", state)
                from .research_feedback import feedback_context, validate_response, record_response
                from .research_semantics import VERSION as semantic_version, validate_capability_request
                from .research_change_review import context as change_context, check as check_change
                relevant_change = change_context(root, task)
                candidate = planner("plan", {"task": task, "budget": directive_policy(policy), "usage": usage,
                                               **({'change_review': relevant_change} if relevant_change else {}),
                                               "research_feedback": feedback_context(root, directory),
                                               "semantic_authoring_version": semantic_version,
                                               "feedback": state["feedback"], "prior_observations": state["observations"],
                                               "method_feedback": state.get("method_feedback", {}),
                                               "previous_rejected_response": state.get("last_rejected_response", {}),
                                               "remaining_compute_seconds": remaining_seconds,
                                               "memory": state["memory_considered"],
                                               "known_evidence": learning.evidence_brief(learning.known_evidence(root, task)),
                                               "failure_lesson": learning.failure_lesson(state["feedback"]) if state["feedback"] else {}})
                state.pop("inflight", None)
                learning.validate_model_object(candidate)
                candidate_response = candidate
                write_json(directory / f"model-{usage['model_calls']}.json", {
                    "phase": "plan", "response": candidate, "grants_execution_authority": False})
                if "capability_request" in candidate:
                    requested = candidate["capability_request"]
                    if set(candidate) != {"capability_request"}:
                        raise ValueError("bounded_capability_request_contract_required")
                    response = requested.get("review_response") if isinstance(requested, dict) else None
                    reviewed = None
                    if response:
                        if not isinstance(response, dict) or set(response) != {"review_id", "resolutions"}:
                            raise ValueError("typed_review_response_required")
                        reviewed = validate_response(root, directory, response["review_id"], response["resolutions"])
                    elif feedback_context(root, directory)["pending_reviews"]:
                        raise ValueError("pending_review_requires_linked_response")
                    requested = validate_capability_request(requested)
                    record = {
                        "episode_id": episode_id, "directive_id": task["directive_id"],
                        "support_request_id": task["support_request_id"], "contract_sha256": state["contract_sha256"],
                        "request": requested, "status": "proposed_capability_requires_existing_governance",
                        "grants_execution_authority": False}
                    record["id"] = "capability-" + digest(record)[:24]
                    request_path = root / "conveyor/research/capability_requests" / (record["id"] + ".json")
                    prior = read_json(request_path)
                    if prior and prior != record:
                        raise ValueError("immutable_capability_request_integrity_failure")
                    if not prior: write_json(request_path, record)
                    if reviewed:
                        linked = record_response(root, reviewed, request_path, response["resolutions"])
                        state["review_response_id"] = linked["id"]
                    state.update(state="waiting_for_capability", capability_request=requested,
                        capability_request_id=record["id"], feedback="")
                    return state  # The finally block retains this call's budget and experience.
                validate_plan(candidate, task, policy)
                if relevant_change:
                    state['change_assessment'] = check_change(candidate, relevant_change)
                fingerprint = _plan_fingerprint(candidate)
                known = learning.known_evidence(root, task)
                if (fingerprint in state["plans_seen"] or
                        all(learning.acquisition_key(task, action) in known for action in candidate["actions"])):
                    raise ValueError("unchanged_experiment_rejected_choose_different_evidence_or_method")
                state["plans_seen"].append(fingerprint)
                state.update(plan=copy.deepcopy(candidate), plan_sha256=digest(candidate), observations=[], state="executing", feedback="")
                write_json(directory / f"plan-{usage['model_calls']}.json", {"plan": candidate, "sha256": digest(candidate)})
        elif state["state"] == "executing":
            completed_ids = {row["action_id"] for row in state["observations"]}
            pending = [action for action in state["plan"]["actions"] if action["id"] not in completed_ids]
            if pending:
                action = pending[0]
                network = action["tool"] in {"fetch_source", "search_sources"}
                cached = learning.known_evidence(root, task).get(learning.acquisition_key(task, action))
                if cached:
                    reused = copy.deepcopy(cached["observation"])
                    reused.update(action_id=action["id"], reused_from_episode_id=cached["source_episode_id"])
                    state["observations"].append(reused)
                elif (usage["tool_calls"] >= policy.max_tool_calls
                        or (network and (usage["network_calls"] >= policy.max_network_calls or remaining_seconds < 20))):
                    state["observations"].append({"action_id": action["id"], "ok": False, "error": "tool_budget_exhausted"})
                else:
                    usage["tool_calls"] += 1
                    usage["network_calls"] += int(network)
                    state["inflight"] = {"kind": "tool", "id": action["id"], "reserved_seconds": 20 if network else 1}
                    write_json(directory / "state.json", state)
                    try:
                        result = run_tool(root, task, action)
                        state["observations"].append({"action_id": action["id"], "ok": True, "result": result,
                                                       "result_sha256": digest(result)})
                    except (ValueError, OSError, ArithmeticError, SyntaxError, TypeError, KeyError) as exc:
                        state["observations"].append({"action_id": action["id"], "ok": False, "error": str(exc)[:400]})
                    state.pop("inflight", None)
            if len(state["observations"]) == len(state["plan"]["actions"]):
                state["state"] = "interpreting"
        elif state["state"] == "interpreting":
            if usage["model_calls"] >= policy.max_model_calls:
                state.update(state="waiting_for_changed_input", feedback="interpretation_budget_exhausted")
            else:
                usage["model_calls"] += 1
                state["inflight"] = {"kind": "model", "id": str(usage["model_calls"]),
                                     "reserved_seconds": min(policy.model_timeout_seconds, remaining_seconds)}
                write_json(directory / "state.json", state)
                interpretation = planner("interpret", {"task": task, "plan": state["plan"],
                                                        "remaining_compute_seconds": remaining_seconds,
                                                        "previous_rejected_response": state.get("last_rejected_response", {}),
                                                        "citation_field_issues": state.get('citation_field_issues', []),
                                                        "observations": state["observations"], "feedback": state["feedback"],
                                                        "evidence_options": learning.evidence_options(state["observations"]),
                                                        "failure_lesson": learning.failure_lesson(state["feedback"]) if state["feedback"] else {}})
                state.pop("inflight", None)
                learning.validate_model_object(interpretation)
                candidate_response = copy.deepcopy(interpretation)
                write_json(directory / f"model-{usage['model_calls']}.json", {
                    "phase": "interpret", "response": interpretation, "grants_execution_authority": False})
                verification = verify_result(state["plan"], state["observations"], interpretation)
                state.update(interpretation=interpretation, verification=verification, state="completed", feedback="")
        else:
            raise ValueError("invalid_research_episode_state")
    except (ValueError, OSError, TimeoutError, KeyError, TypeError) as exc:
        state.pop("inflight", None)
        state["feedback"] = str(exc)[:600]
        state['citation_field_issues'] = getattr(exc, 'field_issues', [])
        state["method_feedback"] = method_feedback(exc, task, usage, policy)
        if candidate_response is not None:
            state["last_rejected_response"] = candidate_response
            try:
                rejected_identity = _plan_fingerprint(candidate_response) if state["state"] == "planning" else digest(candidate_response)
            except (KeyError, ValueError, TypeError):
                rejected_identity = digest(candidate_response)
            failure = {"phase": state["state"], "signature": digest([str(exc), rejected_identity]),
                       "lesson": learning.failure_lesson(str(exc))}
            failures = [*state.get("failures", []), failure][-8:]
            state["failures"] = failures
            if sum(item["signature"] == failure["signature"] for item in failures) >= 2:
                state.update(state="waiting_for_changed_input", feedback="repeated_failed_method_requires_changed_input: " + str(exc)[:400])
        # Reinterpretation failures retain real observations; planning failures
        # consume the same frozen budget instead of minting a new episode.
    finally:
        usage["compute_seconds"] = round(usage["compute_seconds"] + time.perf_counter() - started, 4)
        write_json(directory / "state.json", state)
        learning.remember(root, state, task)
    if state["state"] == "completed":
        _publish(root, state, task)
        write_json(directory / "state.json", state)
        learning.remember(root, state, task)
    return state


def episode_identity(task: Mapping[str, Any], policy: ResearchPolicy) -> str:
    return "research-" + digest([task["input_fingerprint"], directive_policy(policy), task.get("episode_index", 0)])[:24]
