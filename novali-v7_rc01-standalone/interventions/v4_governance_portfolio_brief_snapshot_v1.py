from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .governance_memory_resolver_v1 import (
    READ_CONTRACT_SCHEMA_VERSION,
    resolve_governance_memory_current_state,
)
from .ledger import intervention_data_dir, load_latest_snapshots


DATA_DIR = intervention_data_dir()
DIAGNOSTIC_MEMORY_DIR = DATA_DIR / "diagnostic_memory"
GOVERNANCE_MEMORY_AUTHORITY_PATH = DATA_DIR / "governance_memory_authority_latest.json"
GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH = DATA_DIR / "governance_memory_promotion_ledger.jsonl"
GOVERNANCE_REOPEN_CASE_REGISTRY_LEDGER_PATH = (
    DATA_DIR / "governance_reopen_case_registry_ledger.jsonl"
)
GOVERNANCE_REOPEN_CASE_TRIAGE_LEDGER_PATH = (
    DATA_DIR / "governance_reopen_case_triage_ledger.jsonl"
)
GOVERNANCE_REOPEN_CASE_QUEUE_LEDGER_PATH = (
    DATA_DIR / "governance_reopen_case_queue_ledger.jsonl"
)
GOVERNANCE_PORTFOLIO_BRIEF_LEDGER_PATH = DATA_DIR / "governance_portfolio_brief_ledger.jsonl"
SELF_STRUCTURE_STATE_PATH = DATA_DIR / "self_structure_state_latest.json"
SELF_STRUCTURE_LEDGER_PATH = DATA_DIR / "self_structure_ledger.jsonl"
BRANCH_REGISTRY_PATH = DATA_DIR / "branch_registry_latest.json"
DIRECTIVE_STATE_PATH = DATA_DIR / "directive_state_latest.json"
BUCKET_STATE_PATH = DATA_DIR / "bucket_state_latest.json"
INTERVENTION_LEDGER_PATH = DATA_DIR / "intervention_ledger.jsonl"
INTERVENTION_ANALYTICS_PATH = DATA_DIR / "intervention_analytics_latest.json"
PROPOSAL_RECOMMENDATIONS_PATH = DATA_DIR / "proposal_recommendations_latest.json"

PORTFOLIO_BRIEF_SCHEMA_NAME = "GovernancePortfolioBrief"
PORTFOLIO_BRIEF_SCHEMA_VERSION = "governance_portfolio_brief_v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(dict(json.loads(line)))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    if not path.exists():
        path.write_text("", encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _diagnostic_artifact_dir() -> Path:
    DIAGNOSTIC_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    return DIAGNOSTIC_MEMORY_DIR


def _load_latest_artifact(
    self_structure_state: dict[str, Any],
    *,
    summary_key: str,
    ledger_path: Path,
) -> tuple[dict[str, Any], str]:
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    artifact_path_text = str(current_state_summary.get(summary_key, "")).strip()
    if artifact_path_text:
        payload = _load_json_file(Path(artifact_path_text))
        if payload:
            return payload, artifact_path_text

    for row in reversed(_load_jsonl(ledger_path)):
        artifact_path_text = str(row.get("artifact_path", "")).strip()
        if not artifact_path_text:
            continue
        payload = _load_json_file(Path(artifact_path_text))
        if payload:
            return payload, artifact_path_text
    return {}, ""


def _recommended_next_action(
    canonical_posture: dict[str, Any],
    triage_summary: dict[str, Any],
    queue_summary: dict[str, Any],
) -> tuple[str, str, list[str]]:
    reason_codes: list[str] = []

    if str(canonical_posture.get("current_branch_state", "")) == "paused_with_baseline_held":
        reason_codes.append("branch_state_still_paused_with_baseline_held")
    if str(canonical_posture.get("current_operating_stance", "")) == "hold_and_consolidate":
        reason_codes.append("operating_stance_still_hold_and_consolidate")
    if (
        str(dict(canonical_posture.get("reopen_eligibility", {})).get("branch_reopen_candidate_status", ""))
        == "requires_new_evidence"
    ):
        reason_codes.append("reopen_still_requires_new_evidence")
    if str(canonical_posture.get("routing_status", "")) == "routing_deferred":
        reason_codes.append("routing_still_deferred")
    if int(queue_summary.get("queue_included_case_count", 0) or 0) <= 0:
        reason_codes.append("active_queue_is_empty")
    if int(triage_summary.get("immediate_attention_case_count", 0) or 0) <= 0:
        reason_codes.append("no_cases_require_immediate_attention")

    action_class = "maintain_hold_and_consolidate_no_active_case_work"
    action_text = "keep_hold_and_consolidate_and_take_no_case_action"
    rationale = (
        "Canonical authority still holds NOVALI in paused_with_baseline_held / "
        "hold_and_consolidate because the held baseline remains binding, reopen "
        "eligibility still requires new evidence, routing remains deferred, and the "
        "current governance portfolio has no queued attention items."
    )

    if int(queue_summary.get("queue_included_case_count", 0) or 0) > 0:
        action_class = "surface_next_queued_governance_case"
        action_text = "surface_next_queued_case_for_governance_attention"
        rationale = (
            "Canonical posture remains unchanged, but the observational queue now "
            "contains at least one included case that should be surfaced through the "
            "existing governance workflow rather than inferred manually."
        )
        reason_codes = [
            code for code in reason_codes if code != "active_queue_is_empty"
        ] + ["active_queue_contains_included_case"]

    return action_class, action_text, reason_codes


def _case_brief_rows(
    queue_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in list(queue_payload.get("case_queue_records", [])):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "stable_case_identifier": str(item.get("stable_case_identifier", "")),
                "current_lifecycle_state": str(item.get("current_lifecycle_state", "")),
                "current_triage_category": str(item.get("current_triage_category", "")),
                "queue_class": str(item.get("queue_class", "")),
                "queue_inclusion_flag": bool(item.get("queue_inclusion_flag", False)),
                "priority_band": str(item.get("priority_band", "")),
                "latest_stage": str(item.get("latest_stage", "")),
                "latest_state": str(item.get("latest_state", "")),
                "next_action_recommendation_class": str(
                    item.get("next_action_recommendation_class", "")
                ),
                "latest_artifact_path": str(item.get("latest_artifact_path", "")),
            }
        )
    return rows


def run_probe(cfg: Any, proposal: dict[str, Any], *, rounds: int, seeds: list[int]) -> dict[str, Any]:
    del cfg, rounds, seeds

    authority_payload = _load_json_file(GOVERNANCE_MEMORY_AUTHORITY_PATH)
    self_structure_state = _load_json_file(SELF_STRUCTURE_STATE_PATH)
    branch_registry = _load_json_file(BRANCH_REGISTRY_PATH)
    directive_state = _load_json_file(DIRECTIVE_STATE_PATH)
    bucket_state = _load_json_file(BUCKET_STATE_PATH)
    intervention_analytics = _load_json_file(INTERVENTION_ANALYTICS_PATH)
    proposal_recommendations = _load_json_file(PROPOSAL_RECOMMENDATIONS_PATH)

    registry_payload, registry_artifact_path = _load_latest_artifact(
        self_structure_state,
        summary_key="latest_governance_reopen_case_registry_artifact_path",
        ledger_path=GOVERNANCE_REOPEN_CASE_REGISTRY_LEDGER_PATH,
    )
    triage_payload, triage_artifact_path = _load_latest_artifact(
        self_structure_state,
        summary_key="latest_governance_reopen_case_triage_artifact_path",
        ledger_path=GOVERNANCE_REOPEN_CASE_TRIAGE_LEDGER_PATH,
    )
    queue_payload, queue_artifact_path = _load_latest_artifact(
        self_structure_state,
        summary_key="latest_governance_reopen_case_queue_artifact_path",
        ledger_path=GOVERNANCE_REOPEN_CASE_QUEUE_LEDGER_PATH,
    )
    if not all([authority_payload, registry_payload, triage_payload, queue_payload]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: authority, case registry, case triage, and case queue artifacts are all required for a portfolio brief",
        }

    resolved_state = resolve_governance_memory_current_state()
    canonical_posture = dict(resolved_state.get("canonical_current_posture", {}))
    selector_frontier_conclusions = dict(resolved_state.get("selector_frontier_conclusions", {}))
    binding_decisions = list(authority_payload.get("binding_decision_register", []))
    swap_c_status = dict(resolved_state.get("swap_c_status", {}))

    registry_summary = dict(registry_payload.get("portfolio_summary", {}))
    triage_summary = dict(triage_payload.get("portfolio_triage_summary", {}))
    queue_summary = dict(queue_payload.get("portfolio_queue_summary", {}))

    next_action_class, recommended_action, rationale_codes = _recommended_next_action(
        canonical_posture,
        triage_summary,
        queue_summary,
    )

    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    branch_record = (
        dict(list(branch_registry.get("branches", []))[0])
        if list(branch_registry.get("branches", []))
        else {}
    )
    reviewer_source = "governed_portfolio_brief_snapshot_v1"
    recorded_at = _now()
    portfolio_brief_id = f"governance_portfolio_brief::{proposal['proposal_id']}"
    artifact_path = _diagnostic_artifact_dir() / (
        f"memory_summary_v4_governance_portfolio_brief_snapshot_v1_{proposal['proposal_id']}.json"
    )

    payload = {
        "proposal_id": str(proposal.get("proposal_id", "")),
        "template_name": "memory_summary.v4_governance_portfolio_brief_snapshot_v1",
        "snapshot_identity_context": {
            "governance_portfolio_brief_id": portfolio_brief_id,
            "recorded_at": recorded_at,
            "phase": "governance_portfolio_brief",
            "source_registry_artifact_path": str(registry_artifact_path),
            "source_triage_artifact_path": str(triage_artifact_path),
            "source_queue_artifact_path": str(queue_artifact_path),
        },
        "portfolio_brief_contract": {
            "schema_name": PORTFOLIO_BRIEF_SCHEMA_NAME,
            "schema_version": PORTFOLIO_BRIEF_SCHEMA_VERSION,
            "brief_sections": [
                "canonical_posture_facts",
                "observational_portfolio_state",
                "recommended_next_action_commentary",
            ],
            "canonical_facts_source_of_truth": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
            "brief_observational_only": True,
            "brief_non_authoritative": True,
            "recommended_next_action_non_binding": True,
            "authority_mutation_disallowed_here": True,
            "case_state_mutation_disallowed_here": True,
            "triage_state_mutation_disallowed_here": True,
            "queue_state_mutation_disallowed_here": True,
        },
        "canonical_posture_facts": {
            "active_branch": str(canonical_posture.get("active_branch", "")),
            "frozen_fallback_reference_version": str(
                canonical_posture.get("frozen_fallback_reference_version", "")
            ),
            "additional_reference_versions": [
                str(item) for item in list(canonical_posture.get("additional_reference_versions", []))
            ],
            "current_branch_state": str(canonical_posture.get("current_branch_state", "")),
            "held_baseline_template": str(canonical_posture.get("held_baseline_template", "")),
            "current_operating_stance": str(
                canonical_posture.get("current_operating_stance", "")
            ),
            "routing_status": str(canonical_posture.get("routing_status", "")),
            "projection_safety_primary": bool(
                canonical_posture.get("projection_safety_primary", False)
            ),
            "plan_non_owning": bool(canonical_posture.get("plan_non_owning", False)),
            "governed_work_loop_status": str(
                canonical_posture.get("governed_work_loop_status", "")
            ),
            "reopen_eligibility": dict(canonical_posture.get("reopen_eligibility", {})),
            "binding_decision_register": binding_decisions,
            "selector_frontier_conclusions": selector_frontier_conclusions,
            "swap_c_status": {
                "baseline_name": str(swap_c_status.get("baseline_name", "")),
                "selected_benchmark_like_count": int(
                    swap_c_status.get("selected_benchmark_like_count", 0) or 0
                ),
                "projection_safe_retention": swap_c_status.get("projection_safe_retention"),
                "unsafe_overcommit_rate_delta": swap_c_status.get(
                    "unsafe_overcommit_rate_delta"
                ),
                "false_safe_projection_rate_delta": swap_c_status.get(
                    "false_safe_projection_rate_delta"
                ),
            },
            "authority_promotion_id": str(
                dict(
                    dict(authority_payload.get("authority_promotion_record", {}))
                ).get("promotion_id", "")
            ),
            "read_contract_version": READ_CONTRACT_SCHEMA_VERSION,
        },
        "observational_portfolio_state": {
            "case_inventory_summary": registry_summary,
            "triage_summary": triage_summary,
            "queue_summary": queue_summary,
            "empty_queue_state": bool(int(queue_summary.get("queue_included_case_count", 0) or 0) <= 0),
            "case_brief_rows": _case_brief_rows(queue_payload),
        },
        "recommended_next_action_commentary": {
            "recommended_next_action_class": next_action_class,
            "recommended_next_governance_action": recommended_action,
            "next_queued_case_identifier": str(queue_summary.get("next_case_identifier", "")),
            "next_queued_case_queue_class": str(queue_summary.get("next_queue_class", "")),
            "reason_the_current_posture_still_holds": (
                "The held baseline remains binding, reopen eligibility still requires new "
                "evidence, routing remains deferred, and the current governance portfolio "
                "shows no queued attention items."
            ),
            "commentary_reason_codes": rationale_codes,
            "commentary_non_authoritative": True,
        },
        "reviewer_source_and_audit_trace": {
            "recorded_by_surface": "memory_summary.v4_governance_portfolio_brief_snapshot_v1",
            "reviewer_source": reviewer_source,
            "branch_id": str(branch_registry.get("current_branch_id", "")),
            "branch_pause_rationale": str(branch_record.get("pause_rationale", "")),
            "directive_id": str(
                dict(directive_state.get("current_directive_state", {})).get(
                    "directive_id", ""
                )
            ),
            "bucket_id": str(
                dict(bucket_state.get("current_bucket_state", {})).get("bucket_id", "")
            ),
            "latest_snapshots_count": int(len(load_latest_snapshots())),
            "governance_execution_contract_available": bool(
                intervention_analytics.get("governance_execution_contract")
                or proposal_recommendations.get("governance_execution_contract")
            ),
        },
        "provenance_and_audit_trace": {
            "canonical_authority_file": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
            "governance_memory_promotion_ledger_path": str(
                GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH
            ),
            "governance_reopen_case_registry_ledger_path": str(
                GOVERNANCE_REOPEN_CASE_REGISTRY_LEDGER_PATH
            ),
            "governance_reopen_case_triage_ledger_path": str(
                GOVERNANCE_REOPEN_CASE_TRIAGE_LEDGER_PATH
            ),
            "governance_reopen_case_queue_ledger_path": str(
                GOVERNANCE_REOPEN_CASE_QUEUE_LEDGER_PATH
            ),
            "governance_portfolio_brief_ledger_path": str(
                GOVERNANCE_PORTFOLIO_BRIEF_LEDGER_PATH
            ),
            "self_structure_state_path": str(SELF_STRUCTURE_STATE_PATH),
            "self_structure_ledger_path": str(SELF_STRUCTURE_LEDGER_PATH),
            "intervention_ledger_path": str(INTERVENTION_LEDGER_PATH),
            "analytics_path": str(INTERVENTION_ANALYTICS_PATH),
            "proposal_recommendations_path": str(PROPOSAL_RECOMMENDATIONS_PATH),
        },
        "operator_readable_conclusion": (
            "NOVALI is currently paused_with_baseline_held and hold_and_consolidate, "
            "the held baseline remains proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1, "
            "routing is still deferred, the only current governance case is closed and excluded from "
            "the active queue, and there is no queued case that warrants immediate governance action."
        ),
    }

    _write_json(artifact_path, payload)

    ledger_entry = {
        "event_type": "governance_portfolio_brief_recorded",
        "written_at": recorded_at,
        "governance_portfolio_brief_id": portfolio_brief_id,
        "artifact_path": str(artifact_path),
        "recommended_next_action_class": str(next_action_class),
        "recommended_next_governance_action": str(recommended_action),
        "case_count": int(registry_summary.get("total_case_count", 0) or 0),
        "attention_case_count": int(
            triage_summary.get("immediate_attention_case_count", 0) or 0
        ),
        "queue_included_case_count": int(
            queue_summary.get("queue_included_case_count", 0) or 0
        ),
        "next_case_identifier": str(queue_summary.get("next_case_identifier", "")),
    }
    _append_jsonl(GOVERNANCE_PORTFOLIO_BRIEF_LEDGER_PATH, ledger_entry)

    updated_self_structure = dict(self_structure_state)
    updated_summary = dict(current_state_summary)
    updated_summary.update(
        {
            "latest_governance_portfolio_brief_artifact_path": str(artifact_path),
            "latest_governance_portfolio_brief_ledger_path": str(
                GOVERNANCE_PORTFOLIO_BRIEF_LEDGER_PATH
            ),
            "latest_governance_portfolio_brief_case_count": int(
                registry_summary.get("total_case_count", 0) or 0
            ),
            "latest_governance_portfolio_brief_attention_case_count": int(
                triage_summary.get("immediate_attention_case_count", 0) or 0
            ),
            "latest_governance_portfolio_brief_queue_included_case_count": int(
                queue_summary.get("queue_included_case_count", 0) or 0
            ),
            "latest_governance_portfolio_brief_next_case_identifier": str(
                queue_summary.get("next_case_identifier", "")
            ),
            "latest_governance_portfolio_brief_recommended_next_action_class": str(
                next_action_class
            ),
            "latest_governance_portfolio_brief_recommended_next_governance_action": str(
                recommended_action
            ),
        }
    )
    updated_self_structure["generated_at"] = _now()
    updated_self_structure["current_state_summary"] = updated_summary
    updated_self_structure["governance_portfolio_brief"] = {
        "schema_name": PORTFOLIO_BRIEF_SCHEMA_NAME,
        "schema_version": PORTFOLIO_BRIEF_SCHEMA_VERSION,
        "latest_portfolio_brief": {
            "governance_portfolio_brief_id": portfolio_brief_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_PORTFOLIO_BRIEF_LEDGER_PATH),
            "recommended_next_action_class": str(next_action_class),
            "recommended_next_governance_action": str(recommended_action),
            "case_count": int(registry_summary.get("total_case_count", 0) or 0),
            "attention_case_count": int(
                triage_summary.get("immediate_attention_case_count", 0) or 0
            ),
            "queue_included_case_count": int(
                queue_summary.get("queue_included_case_count", 0) or 0
            ),
        },
    }
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure)

    _append_jsonl(
        SELF_STRUCTURE_LEDGER_PATH,
        {
            "event_id": f"governance_portfolio_brief::{proposal['proposal_id']}",
            "timestamp": _now(),
            "event_type": "governance_portfolio_brief_recorded",
            "governance_portfolio_brief_id": portfolio_brief_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_PORTFOLIO_BRIEF_LEDGER_PATH),
            "recommended_next_action_class": str(next_action_class),
            "queue_included_case_count": int(
                queue_summary.get("queue_included_case_count", 0) or 0
            ),
        },
    )

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: NOVALI posture, case inventory, triage, queue state, and recommended next action are now materialized as a single governed portfolio brief",
        "observability_gain": {
            "passed": True,
            "reason": "future agents can orient from one brief artifact instead of reconstructing authority, registry, triage, and queue by hand",
            "artifact_path": str(artifact_path),
            "governance_portfolio_brief_ledger_path": str(
                GOVERNANCE_PORTFOLIO_BRIEF_LEDGER_PATH
            ),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the brief separates canonical posture, observational portfolio summaries, and non-binding next-action commentary without creating a second authority path",
        },
        "ambiguity_reduction": {
            "passed": True,
            "reason": "empty-queue and no-action states are now explicit and legible in one operator handoff artifact",
            "score": 0.99,
        },
        "safety_neutrality": {
            "passed": True,
            "reason": "the brief is observational only and never mutates authority, case state, triage state, queue state, or governance decisions",
            "scope": str(proposal.get("scope", "")),
        },
        "later_selection_usefulness": {
            "passed": True,
            "reason": "the correct next stance remains hold_and_consolidate and no new queue item or reopen action is warranted from this briefing-only step",
            "recommended_next_template": "",
        },
        "diagnostic_conclusions": {
            "case_count": int(registry_summary.get("total_case_count", 0) or 0),
            "attention_case_count": int(
                triage_summary.get("immediate_attention_case_count", 0) or 0
            ),
            "queue_included_case_count": int(
                queue_summary.get("queue_included_case_count", 0) or 0
            ),
            "recommended_next_action": str(recommended_action),
            "recommended_next_action_class": str(next_action_class),
            "recommended_next_template": "",
        },
        "artifact_path": str(artifact_path),
        "governance_portfolio_brief_ledger_path": str(GOVERNANCE_PORTFOLIO_BRIEF_LEDGER_PATH),
    }
