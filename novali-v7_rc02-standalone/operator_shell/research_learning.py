"""Domain-independent research experience, evidence reuse and citation identity.

Procedures can inform other tasks. Observations remain bound to their original
task, input revisions and tool semantics; retrieval never establishes transfer.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any, Mapping

from .research_tools import digest, identifier, normalize_action, read_json, write_json

LEARNING_VERSION = "research_learning_v1"
CACHEABLE_TOOLS = {"inspect_artifact", "compare_artifacts", "simulate"}


def metric_names(action: Mapping[str, Any]) -> set[str]:
    action = normalize_action(action)
    if action["tool"] == "simulate":
        spec = action.get("spec")
        if not isinstance(spec, Mapping) or not isinstance(spec.get("variants"), Mapping):
            raise ValueError("simulation_spec_and_variants_objects_required")
        names = {f"{name}_mse" for name in spec["variants"]}
        if "candidate_mse" in names:
            names.add("candidate_gain")
        return names
    return {"inspect_artifact": {"bytes", "numeric_token_count"},
            "compare_artifacts": {"content_changed"}, "search_sources": {"result_count"},
            "fetch_source": {"bytes", "visible_chars"}}[action["tool"]]


def validate_model_object(value: Any) -> None:
    if not isinstance(value, dict):
        raise ValueError("research_model_object_required")
    if len(json.dumps(value, allow_nan=False).encode()) > 24000:
        raise ValueError("research_model_object_size_limit")


def _index(root: Path, name: str) -> list[dict[str, Any]]:
    try:
        entries = read_json(root / "conveyor/research" / name).get("entries", [])
        return [row for row in entries[-64:] if isinstance(row, dict)] if isinstance(entries, list) else []
    except (ValueError, OSError, TypeError):
        return []


def acquisition(action: Mapping[str, Any]) -> dict[str, Any]:
    """Only arguments actually used by a tool identify an acquisition."""
    action = normalize_action(action)
    tool = action["tool"]
    fields = {"inspect_artifact": ("artifact_ref", "offset_chars"),
              "compare_artifacts": ("before_ref", "after_ref"), "simulate": ("spec",),
              "fetch_source": ("url", "expected_mpn", "requested_row_id", "expected_manufacturer"),
              "search_sources": ("query",)}[tool]
    selected = {key: action[key] for key in fields if key in action}
    if tool == "inspect_artifact":
        selected.setdefault("offset_chars", 0)
    if tool == "search_sources":
        selected["query"] = str(selected.get("query", "")).strip()
    return {"tool": tool, **selected}


def acquisition_key(task: Mapping[str, Any], action: Mapping[str, Any]) -> str:
    method = acquisition(action)
    revisions = {method[key]: task.get("artifacts", {}).get(method[key])
                 for key in ("artifact_ref", "before_ref", "after_ref") if key in method}
    return digest({"tool_semantics": "bounded_research_tools_v1", "directive": task["directive_id"],
                   "method": method, "revisions": revisions})


def remember(root: Path, state: Mapping[str, Any], task: Mapping[str, Any]) -> None:
    path = root / "conveyor/research/experience_index.json"
    # An invalid retrieval index must not stall an otherwise valid experiment.
    # Episode records remain authoritative and are never removed by compaction.
    try:
        read_json(path)
    except (ValueError, OSError, TypeError):
        return
    entries = _index(root, "experience_index.json")
    item = {"episode_id": state["episode_id"], "state_sha256": digest(state),
            "directive_id": task["directive_id"], "target_artifact": task["target_artifact"]}
    if item in entries:
        return
    entries = [row for row in entries if row.get("episode_id") != item["episode_id"]]
    write_json(path, {"entries": [*entries, item][-64:], "grants_execution_authority": False})


def experiences(root: Path) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Bounded integrity-checked retrieval, including legacy completed episodes."""
    legacy = _index(root, "memory_index.json")
    recent = _index(root, "experience_index.json")
    # The scheduler's bounded pointers also expose pre-upgrade failed episodes.
    # They must pass the same contract, plan and observation integrity checks.
    try:
        snapshot = read_json(root / "conveyor/research/latest.json")
        prior = [{"episode_id": row["episode_id"], "from_scheduler_snapshot": True}
                 for row in snapshot.get("directives", [])[:12] if row.get("episode_id")]
    except (ValueError, OSError, TypeError):
        prior = []
    entries = {row["episode_id"]: row for row in [*prior, *legacy, *recent] if row.get("episode_id")}
    selected = []
    for row in list(entries.values())[-64:]:
        try:
            directory = root / "conveyor/research/episodes" / identifier(row["episode_id"])
            state, contract = read_json(directory / "state.json"), read_json(directory / "contract.json")
            if not state or digest(contract) != state.get("contract_sha256"):
                continue
            if row.get("state_sha256") and digest(state) != row["state_sha256"]:
                continue
            if state.get("plan") and digest(state["plan"]) != state.get("plan_sha256"):
                continue
            if state.get("state") == "completed":
                packet = read_json(directory / "result.json")
                if (not packet or digest(packet) != state.get("result_sha256")
                        or packet.get("plan") != state.get("plan")
                        or packet.get("observations") != state.get("observations")
                        or packet.get("interpretation") != state.get("interpretation")):
                    continue
            elif not row.get("state_sha256") and not row.get("from_scheduler_snapshot"):
                continue
            if any(ob.get("ok") and digest(ob.get("result")) != ob.get("result_sha256")
                   for ob in state.get("observations", [])):
                continue
            selected.append((state, contract["task"]))
        except (ValueError, OSError, KeyError, TypeError):
            continue
    return selected


def known_evidence(root: Path, task: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    known = {}
    for state, original_task in experiences(root):
        if original_task.get("directive_id") != task["directive_id"]:
            continue
        actions = {a["id"]: a for a in state.get("plan", {}).get("actions", [])}
        for observation in state.get("observations", []):
            action = actions.get(observation.get("action_id"), {})
            if not observation.get("ok") or action.get("tool") not in CACHEABLE_TOOLS:
                continue
            try:
                key = acquisition_key(original_task, action)
                if key != acquisition_key(task, action):
                    continue
            except (ValueError, KeyError, TypeError):
                continue
            known[key] = {"action": acquisition(action), "observation": copy.deepcopy(observation),
                          "source_episode_id": state["episode_id"]}
    return dict(list(known.items())[-24:])


def evidence_brief(known: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [{"acquisition_key": key, "action": row["action"], "source_episode_id": row["source_episode_id"],
             "result_sha256": row["observation"]["result_sha256"],
             "metrics": row["observation"]["result"].get("metrics", {}),
             "scope": row["observation"]["result"].get("scope", "unassessed"),
             "excerpt": str(row["observation"]["result"].get("text", ""))[:400],
             "use": "reuse recorded observation; choose an unresolved question and new evidence or method"}
            for key, row in list(known.items())[-12:]]


def failure_lesson(error: str) -> dict[str, str]:
    if "unchanged_experiment" in error:
        strategy = "reuse_observation_choose_new_evidence_or_method"
    elif "inventory" in error or "not_allowed" in error or "not_authorized" in error:
        strategy = "use_available_evidence_or_request_capability"
    elif "quote" in error or "evidence_ref" in error or "evidence_handle" in error:
        strategy = "select_recorded_evidence_handle_repair_only_failed_claim"
    elif "budget" in error or "timed out" in error:
        strategy = "reduce_scope_or_wait_for_changed_resources"
    else:
        strategy = "repair_reported_contract_field_before_retrying"
    return {"failure": error[:400], "next_strategy": strategy,
            "scope": "procedural_lesson_not_domain_evidence"}


def evidence_options(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Give the model bounded handles; resolve claims from original data."""
    options = []
    for row in observations[:12]:
        if not row.get("ok"):
            continue
        result = row.get("result", {})
        revision = digest(result)
        if row.get("result_sha256") and revision != row["result_sha256"]:
            raise ValueError("observation_integrity_failure")
        text = str(result.get("text", ""))[:4000]
        pieces = [("text", str(start), text[start:start + 160]) for start in range(0, min(len(text), 1600), 160)
                  if len(text[start:start + 160].strip()) >= 8]
        pieces.extend(("metric", key, f"{key} = {value}") for key, value in sorted(result.get("metrics", {}).items())[:8]
                      if isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value))
        for kind, location, value in pieces:
            options.append({"handle": "evidence-" + digest([row["action_id"], revision, kind, location])[:24],
                            "action_id": row["action_id"], "kind": kind, "text": value,
                            "scope": result.get("scope", "unassessed"), "result_sha256": revision})
    return options[:64]


def bind_evidence_claim(claim: dict[str, Any], observations: list[dict[str, Any]]) -> bool:
    handle = claim.get("evidence_handle")
    if not handle:
        return False
    option = next((item for item in evidence_options(observations) if item["handle"] == handle), None)
    if option is None:
        raise ValueError("unknown_evidence_handle")
    if claim.get("evidence_refs") and claim["evidence_refs"] != [option["action_id"]]:
        raise ValueError("evidence_handle_action_mismatch")
    claim.update(text=option["text"], quote=option["text"], evidence_refs=[option["action_id"]],
                 evidence_basis="recorded_" + option["kind"], evidence_scope=option["scope"],
                 evidence_result_sha256=option["result_sha256"])
    return True
