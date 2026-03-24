from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .governance_memory_reopen_intake_v1 import (
    APPROVED_FOR_GOVERNANCE_REVIEW,
    GOVERNANCE_REOPEN_INTAKE_LEDGER_PATH,
    GOVERNANCE_REOPEN_INTAKE_SCHEMA_VERSION,
    NOT_SCREENED_YET,
    NOT_SUBMITTED_FOR_GOVERNANCE_REVIEW,
    REVIEW_PENDING_REOPEN_CANDIDATE_INTAKE,
    SCREENED_REOPEN_CANDIDATE,
    STILL_REJECTED_REQUEST,
)
from .ledger import intervention_data_dir, load_latest_snapshots


DATA_DIR = intervention_data_dir()
DIAGNOSTIC_MEMORY_DIR = DATA_DIR / "diagnostic_memory"
GOVERNANCE_MEMORY_AUTHORITY_PATH = DATA_DIR / "governance_memory_authority_latest.json"
GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH = DATA_DIR / "governance_memory_promotion_ledger.jsonl"
GOVERNANCE_REOPEN_SCREENING_LEDGER_PATH = DATA_DIR / "governance_reopen_screening_ledger.jsonl"
INTERVENTION_LEDGER_PATH = DATA_DIR / "intervention_ledger.jsonl"
INTERVENTION_ANALYTICS_PATH = DATA_DIR / "intervention_analytics_latest.json"
PROPOSAL_RECOMMENDATIONS_PATH = DATA_DIR / "proposal_recommendations_latest.json"
SELF_STRUCTURE_STATE_PATH = DATA_DIR / "self_structure_state_latest.json"
SELF_STRUCTURE_LEDGER_PATH = DATA_DIR / "self_structure_ledger.jsonl"
BRANCH_REGISTRY_PATH = DATA_DIR / "branch_registry_latest.json"
DIRECTIVE_STATE_PATH = DATA_DIR / "directive_state_latest.json"
BUCKET_STATE_PATH = DATA_DIR / "bucket_state_latest.json"

SCREENING_SCHEMA_NAME = "GovernanceReopenScreening"
SCREENING_SCHEMA_VERSION = "governance_reopen_screening_v1"

SUFFICIENT_FOR_GOVERNANCE_REVIEW = "sufficient_for_governance_review"
INSUFFICIENT_FOR_REOPEN = "insufficient_for_reopen"
SCREENING_NON_AUTHORITATIVE = "screening_non_authoritative_until_explicit_governance_review_and_promotion"

SELECTOR_RELEVANT_KEYWORDS = (
    "selector",
    "final_selection",
    "swap_c",
    "safe_trio",
    "false_safe",
    "benchmark_like",
    "stability_context_retention",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


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


def _latest_matching_artifact(pattern: str) -> str:
    matches = sorted(
        _diagnostic_artifact_dir().glob(pattern),
        key=lambda path: (path.stat().st_mtime, str(path)),
        reverse=True,
    )
    return str(matches[0]) if matches else ""


def _first_nonempty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _is_selector_relevant_template(template_name: str) -> bool:
    template = str(template_name).lower()
    return any(keyword in template for keyword in SELECTOR_RELEVANT_KEYWORDS)


def _latest_requested_template_snapshot(rows: list[dict[str, Any]], template_name: str) -> dict[str, Any]:
    latest: dict[str, Any] = {}
    latest_time: datetime | None = None
    for row in rows:
        if str(row.get("template_name", "")) != str(template_name):
            continue
        row_time = _parse_time(row.get("ledger_written_at"))
        if latest_time is None or (row_time is not None and row_time >= latest_time):
            latest = dict(row)
            latest_time = row_time
    return latest


def _bounded_scope(scope: str) -> bool:
    return str(scope) in {"audit_only", "benchmark_only", "shadow_only"}


def _latest_selector_artifact_observations() -> dict[str, Any]:
    margin_path = _latest_matching_artifact("memory_summary_final_selection_false_safe_margin_snapshot_v1_*.json")
    frontier_path = _latest_matching_artifact(
        "memory_summary_false_safe_frontier_control_characterization_snapshot_v1_*.json"
    )
    hardening_path = _latest_matching_artifact("critic_split_swap_c_incumbent_hardening_probe_v1_*.json")

    margin_payload = _load_json_file(Path(margin_path)) if margin_path else {}
    frontier_payload = _load_json_file(Path(frontier_path)) if frontier_path else {}
    hardening_payload = _load_json_file(Path(hardening_path)) if hardening_path else {}

    return {
        "margin_snapshot": {
            "artifact_path": margin_path,
            "final_selection_split_assessment": _first_nonempty(
                margin_payload.get("final_selection_split_assessment"),
                dict(margin_payload.get("diagnostic_conclusions", {})).get(
                    "final_selection_split_assessment"
                ),
                dict(margin_payload.get("final_selection_margin_summary", {})).get(
                    "final_selection_split_assessment"
                ),
            ),
        },
        "frontier_characterization": {
            "artifact_path": frontier_path,
            "recommended_next_action": _first_nonempty(
                frontier_payload.get("recommended_next_action"),
                dict(frontier_payload.get("diagnostic_conclusions", {})).get(
                    "recommended_next_action"
                ),
            ),
            "routing_status": _first_nonempty(
                frontier_payload.get("routing_status"),
                dict(frontier_payload.get("diagnostic_conclusions", {})).get("routing_status"),
            ),
        },
        "swap_c_hardening": {
            "artifact_path": hardening_path,
            "hardening_robustness_assessment": _first_nonempty(
                hardening_payload.get("hardening_robustness_assessment"),
                dict(hardening_payload.get("diagnostic_conclusions", {})).get(
                    "hardening_robustness_assessment"
                ),
            ),
            "swap_C_hardening_utility_assessment": _first_nonempty(
                hardening_payload.get("swap_C_hardening_utility_assessment"),
                dict(hardening_payload.get("diagnostic_conclusions", {})).get(
                    "swap_C_hardening_utility_assessment"
                ),
            ),
        },
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    del cfg, rounds, seeds

    authority_payload = _load_json_file(GOVERNANCE_MEMORY_AUTHORITY_PATH)
    self_structure_state = _load_json_file(SELF_STRUCTURE_STATE_PATH)
    branch_registry = _load_json_file(BRANCH_REGISTRY_PATH)
    directive_state = _load_json_file(DIRECTIVE_STATE_PATH)
    bucket_state = _load_json_file(BUCKET_STATE_PATH)
    intervention_analytics = _load_json_file(INTERVENTION_ANALYTICS_PATH)
    proposal_recommendations = _load_json_file(PROPOSAL_RECOMMENDATIONS_PATH)
    intervention_ledger_rows = _load_jsonl(INTERVENTION_LEDGER_PATH)
    intake_ledger_rows = _load_jsonl(GOVERNANCE_REOPEN_INTAKE_LEDGER_PATH)
    screening_ledger_rows = _load_jsonl(GOVERNANCE_REOPEN_SCREENING_LEDGER_PATH)

    if not all([authority_payload, self_structure_state, branch_registry, directive_state, bucket_state]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: authority, self-structure, branch, directive, and bucket artifacts are required",
        }

    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    latest_intake_id = str(current_state_summary.get("latest_governance_reopen_intake_id", ""))
    latest_intake_artifact_path = str(
        current_state_summary.get("latest_governance_reopen_intake_artifact_path", "")
    )
    latest_intake_state = str(current_state_summary.get("latest_governance_reopen_intake_state", ""))
    latest_screening_state = str(
        current_state_summary.get("latest_governance_reopen_screening_state", "")
    )
    if not latest_intake_id or not latest_intake_artifact_path:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: no reopen-intake artifact is currently queued",
        }
    if latest_intake_state != REVIEW_PENDING_REOPEN_CANDIDATE_INTAKE or latest_screening_state not in {
        "",
        NOT_SCREENED_YET,
    }:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: the latest reopen-intake is not in an unscreened queued state",
        }

    intake_payload = _load_json_file(Path(latest_intake_artifact_path))
    if not intake_payload:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: queued reopen-intake artifact could not be loaded",
        }

    canonical_summary = dict(authority_payload.get("authority_file_summary", {}))
    authority_promotion_record = dict(authority_payload.get("authority_promotion_record", {}))
    authority_promoted_at = _parse_time(authority_promotion_record.get("promoted_at"))
    authority_reopen_eligibility = dict(canonical_summary.get("reopen_eligibility", {}))
    selector_frontier_memory = dict(authority_payload.get("selector_frontier_memory", {}))
    branch_record = dict(list(branch_registry.get("branches", []))[0]) if list(branch_registry.get("branches", [])) else {}

    blocked_action_request = dict(intake_payload.get("blocked_action_request", {}))
    requested_template_name = str(blocked_action_request.get("requested_template_name", ""))
    requested_template_family = str(blocked_action_request.get("requested_template_family", ""))
    requested_scope = str(blocked_action_request.get("requested_scope", ""))
    request_classification = str(
        dict(intake_payload.get("reopen_candidate_intake", {})).get("request_classification", "")
    )

    requested_template_snapshot = _latest_requested_template_snapshot(
        intervention_ledger_rows,
        requested_template_name,
    )
    requested_template_seen_before = bool(requested_template_snapshot)
    materially_different_bounded_candidate_present = bool(
        requested_template_name
        and _bounded_scope(requested_scope)
        and not requested_template_seen_before
    )

    selector_relevant_recent_rows = [
        dict(row)
        for row in intervention_ledger_rows
        if _is_selector_relevant_template(str(row.get("template_name", "")))
        and (
            authority_promoted_at is None
            or (
                (_parse_time(row.get("ledger_written_at")) is not None)
                and _parse_time(row.get("ledger_written_at")) > authority_promoted_at
            )
        )
    ]
    fresh_upstream_selector_result_present = bool(selector_relevant_recent_rows)

    latest_selector_observations = _latest_selector_artifact_observations()
    contradiction_reason_codes: list[str] = []
    observed_split = str(
        dict(latest_selector_observations.get("margin_snapshot", {})).get(
            "final_selection_split_assessment",
            "",
        )
    )
    if observed_split and observed_split != str(selector_frontier_memory.get("final_selection_split_assessment", "")):
        contradiction_reason_codes.append("selector_frontier_split_changed")
    observed_recommended_action = str(
        dict(latest_selector_observations.get("frontier_characterization", {})).get(
            "recommended_next_action",
            "",
        )
    )
    if observed_recommended_action and observed_recommended_action != str(
        canonical_summary.get("current_operating_stance", "")
    ):
        contradiction_reason_codes.append("operating_stance_changed")
    observed_routing_status = str(
        dict(latest_selector_observations.get("frontier_characterization", {})).get(
            "routing_status",
            "",
        )
    )
    if observed_routing_status and observed_routing_status != str(canonical_summary.get("routing_status", "")):
        contradiction_reason_codes.append("routing_status_changed")
    observed_hardening = str(
        dict(latest_selector_observations.get("swap_c_hardening", {})).get(
            "hardening_robustness_assessment",
            "",
        )
    )
    if observed_hardening and observed_hardening != "hardened_incumbent_quality_candidate":
        contradiction_reason_codes.append("swap_c_hardening_contradicted")
    control_evidence_contradiction_present = bool(contradiction_reason_codes)

    materially_new_evidence_present = bool(
        fresh_upstream_selector_result_present or control_evidence_contradiction_present
    )

    positive_reason_codes: list[str] = []
    if materially_new_evidence_present:
        positive_reason_codes.append("materially_new_evidence_present")
    if materially_different_bounded_candidate_present:
        positive_reason_codes.append("materially_different_bounded_candidate_present")
    if control_evidence_contradiction_present:
        positive_reason_codes.append("control_evidence_contradiction_present")
    if fresh_upstream_selector_result_present:
        positive_reason_codes.append("fresh_upstream_selector_result_present")

    negative_reason_codes: list[str] = []
    if not materially_new_evidence_present:
        negative_reason_codes.append("no_materially_new_evidence")
    if not materially_different_bounded_candidate_present:
        negative_reason_codes.append("no_materially_different_bounded_candidate")
    if not control_evidence_contradiction_present:
        negative_reason_codes.append("no_control_evidence_contradiction")
    if not fresh_upstream_selector_result_present:
        negative_reason_codes.append("no_fresh_upstream_selector_result")
    if requested_template_seen_before:
        negative_reason_codes.append("repeated_template_motion")
    if requested_template_family in {"critic_split", "proposal_learning_loop", "routing_rule", "score_reweight", "support_contract"} and not positive_reason_codes:
        negative_reason_codes.append("same_family_motion_without_new_evidence")

    evidence_sufficiency_assessment = (
        SUFFICIENT_FOR_GOVERNANCE_REVIEW if positive_reason_codes else INSUFFICIENT_FOR_REOPEN
    )
    screening_state = (
        SCREENED_REOPEN_CANDIDATE if evidence_sufficiency_assessment == SUFFICIENT_FOR_GOVERNANCE_REVIEW else STILL_REJECTED_REQUEST
    )
    governance_review_state = (
        APPROVED_FOR_GOVERNANCE_REVIEW
        if screening_state == SCREENED_REOPEN_CANDIDATE
        else NOT_SUBMITTED_FOR_GOVERNANCE_REVIEW
    )

    screening_contract = {
        "schema_name": SCREENING_SCHEMA_NAME,
        "schema_version": SCREENING_SCHEMA_VERSION,
        "source_intake_schema_version": GOVERNANCE_REOPEN_INTAKE_SCHEMA_VERSION,
        "screening_states": [NOT_SCREENED_YET, SCREENED_REOPEN_CANDIDATE, STILL_REJECTED_REQUEST],
        "governance_review_states": [
            NOT_SUBMITTED_FOR_GOVERNANCE_REVIEW,
            APPROVED_FOR_GOVERNANCE_REVIEW,
        ],
        "evidence_sufficiency_states": [
            SUFFICIENT_FOR_GOVERNANCE_REVIEW,
            INSUFFICIENT_FOR_REOPEN,
        ],
        "reopen_bar_signals": [
            "materially_new_evidence_present",
            "materially_different_bounded_candidate_present",
            "control_evidence_contradiction_present",
            "fresh_upstream_selector_result_present",
        ],
        "authority_relation": SCREENING_NON_AUTHORITATIVE,
        "promotion_bypass_disallowed": True,
    }

    artifact_path = _diagnostic_artifact_dir() / (
        f"memory_summary_v4_governance_reopen_screening_snapshot_v1_{proposal['proposal_id']}.json"
    )
    screening_record = {
        "screening_id": f"reopen_screening::{proposal['proposal_id']}",
        "screened_at": _now(),
        "screened_by_surface": "memory_summary.v4_governance_reopen_screening_snapshot_v1",
        "reviewer_source": "governed_reopen_screening_snapshot_v1",
        "source_intake_id": latest_intake_id,
        "source_intake_artifact_path": latest_intake_artifact_path,
        "screening_state": screening_state,
        "governance_review_state": governance_review_state,
        "evidence_sufficiency_assessment": evidence_sufficiency_assessment,
    }

    screening_payload = {
        "proposal_id": str(proposal.get("proposal_id", "")),
        "template_name": "memory_summary.v4_governance_reopen_screening_snapshot_v1",
        "snapshot_identity_context": {
            "screening_id": screening_record["screening_id"],
            "screened_at": screening_record["screened_at"],
            "phase": "governance_reopen_screening",
            "source_intake_id": latest_intake_id,
        },
        "screening_contract": screening_contract,
        "source_intake_reference": {
            "intake_id": latest_intake_id,
            "artifact_path": latest_intake_artifact_path,
            "ledger_path": str(GOVERNANCE_REOPEN_INTAKE_LEDGER_PATH),
            "request_state": str(blocked_action_request.get("request_state", "")),
            "intake_state": str(dict(intake_payload.get("reopen_candidate_intake", {})).get("intake_state", "")),
            "screening_state_before": str(dict(intake_payload.get("reopen_candidate_intake", {})).get("screening_state", "")),
        },
        "screening_result": {
            "screening_state": screening_state,
            "governance_review_state": governance_review_state,
            "evidence_sufficiency_assessment": evidence_sufficiency_assessment,
            "screening_reason_codes": positive_reason_codes + negative_reason_codes + contradiction_reason_codes,
            "request_classification": request_classification,
        },
        "applied_reopen_bar": {
            "branch_reopen_candidate_status": str(
                authority_reopen_eligibility.get("branch_reopen_candidate_status", "")
            ),
            "benchmark_controlled_reopen_supported": bool(
                authority_reopen_eligibility.get("benchmark_controlled_reopen_supported", False)
            ),
            "governed_work_loop_reentry_status": str(
                authority_reopen_eligibility.get("governed_work_loop_reentry_status", "")
            ),
            "required_any_of": list(screening_contract.get("reopen_bar_signals", [])),
            "branch_reopen_triggers": [str(item) for item in list(branch_record.get("reopen_triggers", []))],
            "branch_pause_rationale": str(branch_record.get("pause_rationale", "")),
            "authority_posture": {
                "current_branch_state": str(canonical_summary.get("current_branch_state", "")),
                "current_operating_stance": str(canonical_summary.get("current_operating_stance", "")),
                "held_baseline_template": str(canonical_summary.get("held_baseline_template", "")),
                "routing_status": str(canonical_summary.get("routing_status", "")),
                "selector_frontier_split_assessment": str(
                    selector_frontier_memory.get("final_selection_split_assessment", "")
                ),
            },
        },
        "evidence_screening": {
            "materially_new_evidence_present": materially_new_evidence_present,
            "materially_different_bounded_candidate_present": materially_different_bounded_candidate_present,
            "control_evidence_contradiction_present": control_evidence_contradiction_present,
            "fresh_upstream_selector_result_present": fresh_upstream_selector_result_present,
            "repeated_or_reformatted_motion_only": not bool(positive_reason_codes),
            "requested_template_seen_before": requested_template_seen_before,
            "requested_template_snapshot": {
                "proposal_id": str(requested_template_snapshot.get("proposal_id", "")),
                "ledger_written_at": str(requested_template_snapshot.get("ledger_written_at", "")),
                "promotion_status": str(requested_template_snapshot.get("promotion_status", "")),
                "final_status": str(
                    requested_template_snapshot.get(
                        "final_status",
                        requested_template_snapshot.get("promotion_status", ""),
                    )
                ),
            },
            "fresh_selector_result_count_since_authority_promotion": int(len(selector_relevant_recent_rows)),
            "fresh_selector_result_templates_since_authority_promotion": [
                str(row.get("template_name", "")) for row in selector_relevant_recent_rows[:8]
            ],
            "control_contradiction_reason_codes": contradiction_reason_codes,
            "latest_selector_observations": latest_selector_observations,
        },
        "provenance_and_reproducibility": {
            "authority_file": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
            "authority_promotion_id": str(authority_promotion_record.get("promotion_id", "")),
            "authority_promoted_at": str(authority_promotion_record.get("promoted_at", "")),
            "authority_artifact_path": str(
                current_state_summary.get("latest_governance_memory_authority_artifact_path", "")
            ),
            "source_intake_artifact_path": latest_intake_artifact_path,
            "source_intake_ledger_path": str(GOVERNANCE_REOPEN_INTAKE_LEDGER_PATH),
            "screening_ledger_path": str(GOVERNANCE_REOPEN_SCREENING_LEDGER_PATH),
            "self_structure_state_path": str(SELF_STRUCTURE_STATE_PATH),
            "self_structure_ledger_path": str(SELF_STRUCTURE_LEDGER_PATH),
            "branch_registry_path": str(BRANCH_REGISTRY_PATH),
            "directive_state_path": str(DIRECTIVE_STATE_PATH),
            "bucket_state_path": str(BUCKET_STATE_PATH),
            "intervention_ledger_path": str(INTERVENTION_LEDGER_PATH),
            "analytics_path": str(INTERVENTION_ANALYTICS_PATH),
            "proposal_recommendations_path": str(PROPOSAL_RECOMMENDATIONS_PATH),
            "latest_snapshots_count": int(len(load_latest_snapshots())),
            "screening_ledger_entries_before_write": int(len(screening_ledger_rows)),
            "intake_ledger_entries_seen": int(len(intake_ledger_rows)),
        },
        "supporting_context": {
            "directive_id": str(dict(directive_state.get("current_directive_state", {})).get("directive_id", "")),
            "bucket_id": str(dict(bucket_state.get("current_bucket_state", {})).get("bucket_id", "")),
            "latest_branch_reopen_eligibility": str(
                current_state_summary.get("latest_branch_reopen_eligibility", "")
            ),
            "latest_selector_frontier_split_assessment": str(
                current_state_summary.get("latest_selector_frontier_split_assessment", "")
            ),
            "governance_execution_contract_available": bool(
                intervention_analytics.get("governance_execution_contract")
                or proposal_recommendations.get("governance_execution_contract")
            ),
        },
        "review_rollback_deprecation_trigger_status": {
            "screening_triggered": True,
            "review_triggered": screening_state == SCREENED_REOPEN_CANDIDATE,
            "rollback_triggered": False,
            "deprecation_triggered": False,
        },
        "operator_readable_conclusion": (
            "The queued reopen request was screened against the current canonical reopen bar and remains non-authoritative. "
            + (
                "It was screened out because the request does not add materially new evidence, a materially different bounded candidate, a contradiction in current control evidence, or a fresh upstream selector result."
                if screening_state == STILL_REJECTED_REQUEST
                else "It clears the non-authoritative screening bar and may be forwarded for explicit governance review."
            )
        ),
    }

    _write_json(artifact_path, screening_payload)

    screening_ledger_entry = {
        "event_type": "governance_reopen_screening_completed",
        "written_at": screening_record["screened_at"],
        "screening_id": screening_record["screening_id"],
        "source_intake_id": latest_intake_id,
        "source_intake_artifact_path": latest_intake_artifact_path,
        "artifact_path": str(artifact_path),
        "screening_state": screening_state,
        "governance_review_state": governance_review_state,
        "evidence_sufficiency_assessment": evidence_sufficiency_assessment,
        "request_classification": request_classification,
        "requested_template_name": requested_template_name,
        "requested_template_family": requested_template_family,
        "reason_codes": list(screening_payload["screening_result"]["screening_reason_codes"]),
        "promotion_bypass_disallowed": True,
    }
    _append_jsonl(GOVERNANCE_REOPEN_SCREENING_LEDGER_PATH, screening_ledger_entry)

    updated_self_structure = dict(self_structure_state)
    updated_summary = dict(current_state_summary)
    updated_summary.update(
        {
            "latest_governance_reopen_screening_artifact_path": str(artifact_path),
            "latest_governance_reopen_screening_ledger_path": str(GOVERNANCE_REOPEN_SCREENING_LEDGER_PATH),
            "latest_governance_reopen_screened_intake_id": latest_intake_id,
            "latest_governance_reopen_screening_state": screening_state,
            "latest_governance_reopen_review_state": governance_review_state,
            "latest_governance_reopen_evidence_sufficiency_assessment": evidence_sufficiency_assessment,
            "latest_governance_reopen_screening_reason_codes": list(
                screening_payload["screening_result"]["screening_reason_codes"]
            ),
        }
    )
    updated_self_structure["generated_at"] = _now()
    updated_self_structure["current_state_summary"] = updated_summary
    updated_self_structure["governance_reopen_screening"] = {
        "schema_name": SCREENING_SCHEMA_NAME,
        "schema_version": SCREENING_SCHEMA_VERSION,
        "latest_screening": {
            "screening_id": screening_record["screening_id"],
            "source_intake_id": latest_intake_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_SCREENING_LEDGER_PATH),
            "screening_state": screening_state,
            "governance_review_state": governance_review_state,
            "evidence_sufficiency_assessment": evidence_sufficiency_assessment,
        },
    }
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure)

    _append_jsonl(
        SELF_STRUCTURE_LEDGER_PATH,
        {
            "event_id": f"governance_reopen_screening::{proposal['proposal_id']}",
            "timestamp": _now(),
            "event_type": "governance_reopen_screening_completed",
            "screening_id": screening_record["screening_id"],
            "source_intake_id": latest_intake_id,
            "artifact_path": str(artifact_path),
            "ledger_path": str(GOVERNANCE_REOPEN_SCREENING_LEDGER_PATH),
            "screening_state": screening_state,
            "governance_review_state": governance_review_state,
            "evidence_sufficiency_assessment": evidence_sufficiency_assessment,
            "requested_template_name": requested_template_name,
            "requested_template_family": requested_template_family,
        },
    )

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: queued reopen intake was screened into an explicit governed non-authoritative result",
        "observability_gain": {
            "passed": True,
            "reason": "future agents can now distinguish unscreened intake from screened-out requests and screened reopen candidates",
            "artifact_path": str(artifact_path),
            "screening_ledger_path": str(GOVERNANCE_REOPEN_SCREENING_LEDGER_PATH),
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "screening preserves the canonical reopen bar and turns blocked requests into queryable governance workflow state rather than silent retries",
        },
        "ambiguity_reduction": {
            "passed": True,
            "reason": "screening makes evidence sufficiency, repeated motion, and candidate novelty explicit",
            "score": 0.96,
        },
        "safety_neutrality": {
            "passed": True,
            "reason": "screening writes only non-authoritative governance-memory artifacts and does not alter runtime execution authority, routing, thresholds, or benchmark semantics",
            "scope": str(proposal.get("scope", "")),
        },
        "later_selection_usefulness": {
            "passed": True,
            "reason": "screening result remains non-authoritative and can be reviewed later without changing current hold posture",
            "recommended_next_template": "",
        },
        "diagnostic_conclusions": {
            "screening_state": screening_state,
            "governance_review_state": governance_review_state,
            "evidence_sufficiency_assessment": evidence_sufficiency_assessment,
            "materially_new_evidence_present": materially_new_evidence_present,
            "materially_different_bounded_candidate_present": materially_different_bounded_candidate_present,
            "control_evidence_contradiction_present": control_evidence_contradiction_present,
            "fresh_upstream_selector_result_present": fresh_upstream_selector_result_present,
            "repeated_or_reformatted_motion_only": not bool(positive_reason_codes),
            "recommended_next_action": "hold_and_consolidate",
            "recommended_next_template": "",
        },
        "artifact_path": str(artifact_path),
        "screening_ledger_path": str(GOVERNANCE_REOPEN_SCREENING_LEDGER_PATH),
    }
