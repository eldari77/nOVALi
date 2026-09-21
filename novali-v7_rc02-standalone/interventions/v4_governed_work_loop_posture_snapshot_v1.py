from __future__ import annotations

from pathlib import Path
from typing import Any

from .analytics import build_intervention_ledger_analytics
from .governance_substrate_v1 import (
    BRANCH_REGISTRY_PATH,
    BUCKET_STATE_PATH,
    DIRECTIVE_HISTORY_PATH,
    DIRECTIVE_STATE_PATH,
    SELF_STRUCTURE_LEDGER_PATH,
    SELF_STRUCTURE_STATE_PATH,
    _append_jsonl,
    _now,
    _write_json,
)
from .governed_skill_acquisition_v1 import _diagnostic_artifact_dir, _load_jsonl
from .ledger import intervention_data_dir, load_latest_snapshots
from .v4_first_hypothesis_landscape_snapshot_v1 import _load_json_file
from .v4_governed_capability_use_policy_snapshot_v1 import _latest_matching_artifact
from .v4_wm_context_signal_overlap_snapshot_v1 import _artifact_reference


def _resolve_artifact_path(raw_candidate: Any, pattern: str) -> Path | None:
    candidate = str(raw_candidate or "").strip()
    if not candidate or candidate == "None":
        fallback = _latest_matching_artifact(pattern)
        candidate = str(fallback or "").strip()
    return Path(candidate) if candidate else None


def _posture_classes() -> dict[str, str]:
    return {
        "keep_narrow_governed_loop_available": "keep the current governed work-loop path available, but only as a narrow governed execution posture",
        "allow_distinct_bounded_next_step": "allow another distinct bounded governed next step after separate screening and admission",
        "require_more_evidence_before_broad_execution": "block broader operational work-loop execution until more distinct evidence exists",
        "pause_if_low_yield_repetition": "pause continuation when the next step mostly repeats narrow low-yield work",
        "divert_if_capability_path_is_cleaner": "use held governed capability reuse when it is cleaner than direct work continuation",
        "review_if_consequence_rises": "require review if the next step becomes more decision-critical or consequence-heavy",
    }


def _narrowness_preservation_rules() -> list[str]:
    return [
        "Only distinct bounded next steps may continue the loop.",
        "Low-yield repetition should pause rather than compound.",
        "No silent promotion from narrow proven paths to broad operational execution.",
        "Capability use must stay separate from direct work and loop continuation.",
        "Paused capability lines stay paused unless a separate reopen screen clears them.",
        "No protected-surface drift, downstream selected-set work, plan_ ownership change, routing drift, or branch-state mutation.",
        "No unsupported multi-path operationalization and no untrusted external access.",
    ]


def _allowed_now(
    *,
    direct_work_posture: str,
    loop_continuation_posture: str,
    capability_use_posture: str,
) -> list[str]:
    return [
        f"Keep the current direct-work path available as `{direct_work_posture}` for distinct governance-maintenance work.",
        f"Keep the current loop-continuation path available as `{loop_continuation_posture}` when it adds distinct bounded value over the prior step.",
        "Run more than one governed step over time, but only when each next step is separately screened and admitted.",
        f"Reuse the held capability-use path as `{capability_use_posture}` when capability reuse is cleaner than direct work continuation.",
        "Preserve branch `paused_with_baseline_held`, `plan_` non-owning, routing deferred, and network mode `none`.",
    ]


def _not_allowed_yet() -> list[str]:
    return [
        "Broad execution expansion from narrow proven paths into general governed work-loop execution.",
        "Silent broadening from one successful continuation into unsupported multi-step operationalization.",
        "Hidden capability development, paused-line reopen, or new-skill creation inside work-loop continuation.",
        "Automatic parallelization or unsupported multi-path operational use across direct work, capability use, and development paths.",
        "Any live-policy, threshold, routing, frozen-benchmark, or projection-safe envelope change.",
    ]


def _path_relationships(
    *,
    direct_work_posture: str,
    loop_continuation_posture: str,
    capability_use_posture: str,
    capability_default_use_class: str,
) -> dict[str, Any]:
    return {
        "direct_work_path": {
            "work_item": "Governance state coherence audit refresh",
            "status": direct_work_posture,
            "role": "bounded direct governance-maintenance work when a distinct task fits cleanly without capability reuse or development pressure",
        },
        "loop_continuation_path": {
            "work_item": "Governance ledger consistency delta audit",
            "status": loop_continuation_posture,
            "role": "bounded continuation work that adds distinct value over the prior direct-work step without repeating the same narrow shape",
        },
        "held_capability_use_path": {
            "capability": "Local trace parser trial",
            "status": capability_use_posture,
            "default_use_class": capability_default_use_class,
            "role": "bounded governed reuse path when capability invocation is cleaner than direct work continuation",
        },
        "reopen_diversion_path": {
            "role": "required when a next step implies capability modification or a materially new bounded use-case inside a paused capability family",
        },
        "new_skill_diversion_path": {
            "role": "required when the next need falls outside current held capability families",
        },
        "review_path": {
            "role": "required when consequence, overlap, or decision criticality rises beyond the current low-risk posture",
        },
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governance_substrate_v1_snapshot")
    work_loop_policy_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_policy_snapshot_v1"
    )
    work_loop_candidate_screen_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v1"
    )
    work_loop_continuation_admission_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v1"
    )
    work_loop_execution_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1"
    )
    work_loop_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_work_loop_evidence_snapshot_v1"
    )
    direct_work_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_direct_work_evidence_snapshot_v1"
    )
    capability_use_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governed_capability_use_evidence_snapshot_v1"
    )
    if not all(
        [
            governance_snapshot,
            work_loop_policy_snapshot,
            work_loop_candidate_screen_snapshot,
            work_loop_continuation_admission_snapshot,
            work_loop_execution_snapshot,
            work_loop_evidence_snapshot,
            direct_work_evidence_snapshot,
            capability_use_evidence_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: work-loop posture review requires governance substrate, work-loop policy, candidate screen, continuation admission, continuation execution, work-loop evidence, direct-work evidence, and capability-use evidence artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite governed work-loop posture artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite governed work-loop posture artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite governed work-loop posture artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot define work-loop posture without the prerequisite governed chain"},
        }

    directive_state = _load_json_file(DIRECTIVE_STATE_PATH)
    bucket_state = _load_json_file(BUCKET_STATE_PATH)
    self_structure_state = _load_json_file(SELF_STRUCTURE_STATE_PATH)
    branch_registry = _load_json_file(BRANCH_REGISTRY_PATH)
    directive_history = _load_jsonl(DIRECTIVE_HISTORY_PATH)
    self_structure_ledger = _load_jsonl(SELF_STRUCTURE_LEDGER_PATH)
    intervention_ledger = _load_jsonl(intervention_data_dir() / "intervention_ledger.jsonl")
    analytics = build_intervention_ledger_analytics()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")
    latest_snapshots = load_latest_snapshots()
    if not all([directive_state, bucket_state, self_structure_state, branch_registry]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: current directive, bucket, self-structure, and branch state artifacts are required",
            "observability_gain": {"passed": False, "reason": "missing current directive, bucket, self-structure, or branch state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing current directive, bucket, self-structure, or branch state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing current directive, bucket, self-structure, or branch state"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot define posture without current governance state"},
        }

    current_directive = dict(directive_state.get("current_directive_state", {}))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    branches = list(branch_registry.get("branches", []))
    branch_record = dict(branches[0]) if branches else {}
    current_branch_state = str(branch_record.get("state", ""))
    governed_work_loop_policy = dict(self_structure_state.get("governed_work_loop_policy", {}))
    governed_directive_work_selection_policy = dict(self_structure_state.get("governed_directive_work_selection_policy", {}))
    governed_capability_use_policy = dict(self_structure_state.get("governed_capability_use_policy", {}))
    if current_branch_state != "paused_with_baseline_held" or not governed_work_loop_policy:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: branch must remain paused_with_baseline_held and governed work-loop policy state must exist",
            "observability_gain": {"passed": False, "reason": "missing work-loop state or branch mismatch"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing work-loop state or branch mismatch"},
            "ambiguity_reduction": {"passed": False, "reason": "missing work-loop state or branch mismatch"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot define posture without the loaded governing summaries"},
        }

    current_work_loop_readiness = str(current_state_summary.get("latest_governed_work_loop_readiness", ""))
    work_loop_evidence_outcome = dict(governed_work_loop_policy.get("last_work_loop_evidence_outcome", {}))
    posture_already_defined = bool(current_state_summary.get("governed_work_loop_posture_v1_defined")) or (
        str(current_state_summary.get("latest_governed_work_loop_posture_status", "")) == "defined"
    )
    readiness_satisfied = current_work_loop_readiness in {
        "ready_for_broader_work_loop_posture_layer",
        "ready_for_distinct_next_step_screen",
    }
    evidence_ready_for_posture = bool(work_loop_evidence_outcome.get("broader_work_loop_posture_ready", False))
    if not readiness_satisfied and not evidence_ready_for_posture and not posture_already_defined:
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: self-structure does not currently mark the work-loop as ready for broader posture formalization",
            "observability_gain": {"passed": False, "reason": "work-loop posture readiness not yet reached"},
            "activation_analysis_usefulness": {"passed": False, "reason": "work-loop posture readiness not yet reached"},
            "ambiguity_reduction": {"passed": False, "reason": "work-loop posture readiness not yet reached"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot define posture before work-loop evidence review marks readiness"},
        }

    work_loop_policy_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_policy_artifact_path"),
        "memory_summary_v4_governed_work_loop_policy_snapshot_v1_*.json",
    )
    work_loop_candidate_screen_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_candidate_screen_artifact_path"),
        "memory_summary_v4_governed_work_loop_candidate_screen_snapshot_v1_*.json",
    )
    work_loop_continuation_admission_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_work_loop_continuation_admission_artifact_path"),
        "memory_summary_v4_governed_work_loop_continuation_admission_snapshot_v1_*.json",
    )
    work_loop_execution_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_work_loop_continuation_execution_artifact_path"),
        "proposal_learning_loop_v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1_*.json",
    )
    work_loop_evidence_artifact_path = _resolve_artifact_path(
        governed_work_loop_policy.get("last_work_loop_evidence_artifact_path"),
        "memory_summary_v4_governed_work_loop_evidence_snapshot_v1_*.json",
    )
    direct_work_evidence_artifact_path = _resolve_artifact_path(
        governed_directive_work_selection_policy.get("last_direct_work_evidence_artifact_path"),
        "memory_summary_v4_governed_direct_work_evidence_snapshot_v1_*.json",
    )
    capability_use_evidence_artifact_path = _resolve_artifact_path(
        governed_capability_use_policy.get("last_invocation_evidence_artifact_path"),
        "memory_summary_v4_governed_capability_use_evidence_snapshot_v1_*.json",
    )
    if not all(
        [
            work_loop_policy_artifact_path,
            work_loop_candidate_screen_artifact_path,
            work_loop_continuation_admission_artifact_path,
            work_loop_execution_artifact_path,
            work_loop_evidence_artifact_path,
            direct_work_evidence_artifact_path,
            capability_use_evidence_artifact_path,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: expected governed posture artifact paths could not be resolved",
            "observability_gain": {"passed": False, "reason": "missing resolved posture artifact paths"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing resolved posture artifact paths"},
            "ambiguity_reduction": {"passed": False, "reason": "missing resolved posture artifact paths"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot define posture without resolved artifact paths"},
        }

    work_loop_policy_payload = _load_json_file(work_loop_policy_artifact_path)
    work_loop_candidate_screen_payload = _load_json_file(work_loop_candidate_screen_artifact_path)
    work_loop_continuation_admission_payload = _load_json_file(work_loop_continuation_admission_artifact_path)
    work_loop_execution_payload = _load_json_file(work_loop_execution_artifact_path)
    work_loop_evidence_payload = _load_json_file(work_loop_evidence_artifact_path)
    direct_work_evidence_payload = _load_json_file(direct_work_evidence_artifact_path)
    capability_use_evidence_payload = _load_json_file(capability_use_evidence_artifact_path)
    if not all(
        [
            work_loop_policy_payload,
            work_loop_candidate_screen_payload,
            work_loop_continuation_admission_payload,
            work_loop_execution_payload,
            work_loop_evidence_payload,
            direct_work_evidence_payload,
            capability_use_evidence_payload,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: one or more required posture artifacts could not be loaded",
            "observability_gain": {"passed": False, "reason": "failed to load required posture artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "failed to load required posture artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "failed to load required posture artifacts"},
            "safety_neutrality": {"passed": True, "reason": "no live-policy mutation occurred", "scope": str(proposal.get("scope", ""))},
            "later_selection_usefulness": {"passed": False, "reason": "cannot define posture without the loaded governing summaries"},
        }

    work_loop_policy_summary = dict(work_loop_policy_payload.get("governed_work_loop_policy_summary", {}))
    work_loop_evidence_summary = dict(work_loop_evidence_payload.get("governed_work_loop_evidence_summary", {}))
    direct_work_evidence_summary = dict(direct_work_evidence_payload.get("governed_direct_work_evidence_summary", {}))
    capability_use_evidence_summary = dict(capability_use_evidence_payload.get("governed_capability_use_evidence_summary", {}))
    posture_classes = _posture_classes()

    work_loop_diagnostic_conclusions = dict(work_loop_evidence_payload.get("diagnostic_conclusions", {}))
    direct_work_future_posture = str(dict(direct_work_evidence_summary.get("future_posture", {})).get("category", ""))
    loop_continuation_future_posture = str(dict(work_loop_evidence_summary.get("future_posture", {})).get("category", ""))
    capability_use_future_posture = str(dict(capability_use_evidence_summary.get("future_posture", {})).get("category", ""))
    capability_default_use_class = str(current_state_summary.get("latest_held_capability_default_use_class", ""))
    operationally_successful = bool(
        work_loop_diagnostic_conclusions.get("first_governed_work_loop_continuation_operationally_successful", False)
    )
    continuation_path_should_remain_available = bool(
        work_loop_diagnostic_conclusions.get("continuation_path_should_remain_available", False)
    )
    broader_posture_justified = bool(
        work_loop_diagnostic_conclusions.get("ready_for_broader_governed_work_loop_posture_layer", False)
    )
    broader_execution_not_yet_justified = not bool(
        dict(work_loop_evidence_summary.get("broader_project_alignment", {})).get(
            "ready_for_broader_governed_work_loop_execution_without_more_evidence",
            False,
        )
    )

    primary_posture_class = (
        "keep_narrow_governed_loop_available"
        if continuation_path_should_remain_available
        else "pause_if_low_yield_repetition"
    )
    active_posture_classes = [
        primary_posture_class,
        "allow_distinct_bounded_next_step" if broader_posture_justified else "pause_if_low_yield_repetition",
        "require_more_evidence_before_broad_execution" if broader_execution_not_yet_justified else "allow_distinct_bounded_next_step",
        "pause_if_low_yield_repetition",
        "divert_if_capability_path_is_cleaner",
        "review_if_consequence_rises",
    ]
    active_posture_classes = list(dict.fromkeys(active_posture_classes))

    allowed_now = _allowed_now(
        direct_work_posture=direct_work_future_posture,
        loop_continuation_posture=loop_continuation_future_posture,
        capability_use_posture=capability_use_future_posture,
    )
    not_allowed_yet = _not_allowed_yet()
    missing_evidence_for_broader_execution = list(
        dict(work_loop_evidence_summary.get("broader_project_alignment", {})).get(
            "further_evidence_needed_before_broader_governed_work_loop_execution",
            [],
        )
    )
    narrowness_preservation_rules = _narrowness_preservation_rules()
    path_relationships = _path_relationships(
        direct_work_posture=direct_work_future_posture,
        loop_continuation_posture=loop_continuation_future_posture,
        capability_use_posture=capability_use_future_posture,
        capability_default_use_class=capability_default_use_class,
    )

    current_posture = {
        "primary_posture_class": primary_posture_class,
        "active_posture_classes": active_posture_classes,
        "broader_posture_justified": broader_posture_justified,
        "broader_execution_not_yet_justified": broader_execution_not_yet_justified,
        "reason": (
            "bounded broader posture is justified because direct work and first loop continuation are both operationally successful and sufficiently governed, but broader execution remains blocked because the evidence chain is still too short and must prove another distinct bounded step first"
        ),
    }

    next_template = "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v2"
    recommended_next_execution_adjacent_step = {
        "template_name": next_template,
        "path_type": "work_loop_candidate_screen",
        "reason": "screen a second distinct next-step candidate set against the now-formalized posture so the next bounded continuation candidate can be admitted without unsupported broadening",
    }

    updated_self_structure_state = dict(self_structure_state)
    updated_work_loop_policy = dict(governed_work_loop_policy)
    updated_work_loop_policy["last_work_loop_posture_artifact_path"] = str(
        _diagnostic_artifact_dir() / f"memory_summary_v4_governed_work_loop_posture_snapshot_v1_{proposal['proposal_id']}.json"
    )
    updated_work_loop_policy["governed_work_loop_posture_schema"] = {
        "schema_name": "GovernedWorkLoopPostureReview",
        "schema_version": "governed_work_loop_posture_v1",
        "required_fields": [
            "current_posture",
            "active_posture_classes",
            "allowed_now",
            "not_allowed_yet",
            "missing_evidence_for_broader_execution",
            "narrowness_preservation_rules",
            "path_relationships",
            "recommended_next_execution_adjacent_step",
        ],
        "posture_classes": list(posture_classes.keys()),
    }
    updated_work_loop_policy["last_work_loop_posture_outcome"] = {
        "status": "defined",
        "current_posture": primary_posture_class,
        "broader_posture_justified": broader_posture_justified,
        "broader_execution_still_blocked": broader_execution_not_yet_justified,
        "best_next_template": next_template,
    }
    updated_work_loop_policy["best_next_template"] = next_template
    updated_self_structure_state["governed_work_loop_policy"] = updated_work_loop_policy

    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "governed_work_loop_posture_v1_defined": True,
            "latest_governed_work_loop_posture_status": "defined",
            "latest_governed_work_loop_posture": primary_posture_class,
            "latest_governed_work_loop_readiness": "ready_for_distinct_next_step_screen",
            "latest_governed_work_loop_best_next_template": next_template,
            "current_branch_state": current_branch_state,
            "plan_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "retained_skill_promotion_performed": False,
        }
    )
    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["current_state_summary"] = updated_current_state_summary

    artifact_path = _diagnostic_artifact_dir() / f"memory_summary_v4_governed_work_loop_posture_snapshot_v1_{proposal['proposal_id']}.json"
    updated_work_loop_policy["last_work_loop_posture_artifact_path"] = str(artifact_path)
    updated_self_structure_state["governed_work_loop_policy"] = updated_work_loop_policy
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    _append_jsonl(
        SELF_STRUCTURE_LEDGER_PATH,
        {
            "event_id": f"governed_work_loop_posture_snapshot_v1::{proposal['proposal_id']}",
            "timestamp": _now(),
            "event_type": "governed_work_loop_posture_snapshot_v1_materialized",
            "event_class": "governed_work_loop_posture",
            "directive_id": str(current_directive.get("directive_id", "")),
            "directive_state": str(directive_state.get("initialization_state", "")),
            "branch_id": str(branch_record.get("branch_id", "")),
            "branch_state": current_branch_state,
            "current_posture": primary_posture_class,
            "broader_posture_justified": broader_posture_justified,
            "broader_execution_still_blocked": broader_execution_not_yet_justified,
            "new_behavior_changing_branch_opened": False,
            "retained_promotion": False,
            "branch_state_mutation": False,
            "artifact_paths": {
                "governed_work_loop_policy_v1": str(work_loop_policy_artifact_path),
                "governed_work_loop_candidate_screen_v1": str(work_loop_candidate_screen_artifact_path),
                "governed_work_loop_continuation_admission_v1": str(work_loop_continuation_admission_artifact_path),
                "governed_work_loop_continuation_execution_v1": str(work_loop_execution_artifact_path),
                "governed_work_loop_evidence_v1": str(work_loop_evidence_artifact_path),
                "governed_work_loop_posture_v1": str(artifact_path),
            },
            "source_proposal_id": str(proposal.get("proposal_id", "")),
        },
    )

    all_ranked = list(recommendations.get("all_ranked_proposals", []))
    suggested_templates = [
        str(item.get("template_name", ""))
        for item in all_ranked
        if isinstance(item, dict) and str(item.get("decision", "")) == "suggested"
    ][:8]

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_governed_work_loop_posture_snapshot_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "branch_context": {
            "current_branch_id": str(branch_record.get("branch_id", "")),
            "current_branch_state": current_branch_state,
            "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
            "plan_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
        },
        "comparison_references": {
            "memory_summary.v4_governance_substrate_v1_snapshot": _artifact_reference(governance_snapshot, latest_snapshots),
            "memory_summary.v4_governed_work_loop_policy_snapshot_v1": _artifact_reference(
                work_loop_policy_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_work_loop_candidate_screen_snapshot_v1": _artifact_reference(
                work_loop_candidate_screen_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_work_loop_continuation_admission_snapshot_v1": _artifact_reference(
                work_loop_continuation_admission_snapshot, latest_snapshots
            ),
            "proposal_learning_loop.v4_governed_work_loop_governance_ledger_consistency_delta_audit_v1": _artifact_reference(
                work_loop_execution_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_work_loop_evidence_snapshot_v1": _artifact_reference(
                work_loop_evidence_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_direct_work_evidence_snapshot_v1": _artifact_reference(
                direct_work_evidence_snapshot, latest_snapshots
            ),
            "memory_summary.v4_governed_capability_use_evidence_snapshot_v1": _artifact_reference(
                capability_use_evidence_snapshot, latest_snapshots
            ),
        },
        "governed_work_loop_posture_summary": {
            "current_posture": current_posture,
            "posture_classes": posture_classes,
            "allowed_now": allowed_now,
            "not_allowed_yet": not_allowed_yet,
            "missing_evidence_for_broader_execution": missing_evidence_for_broader_execution,
            "narrowness_preservation_rules": narrowness_preservation_rules,
            "relationship_among_paths": path_relationships,
            "current_evidence_basis": {
                "first_loop_continuation_operationally_successful": operationally_successful,
                "continuation_path_should_remain_available": continuation_path_should_remain_available,
                "direct_work_future_posture": direct_work_future_posture,
                "loop_continuation_future_posture": loop_continuation_future_posture,
                "capability_use_future_posture": capability_use_future_posture,
                "broader_posture_justified": broader_posture_justified,
                "broader_execution_still_blocked": broader_execution_not_yet_justified,
            },
            "recommended_next_execution_adjacent_step": recommended_next_execution_adjacent_step,
            "governance_inputs_consumed": {
                "directive_state_latest": str(DIRECTIVE_STATE_PATH),
                "directive_history": str(DIRECTIVE_HISTORY_PATH),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
                "branch_registry_latest": str(BRANCH_REGISTRY_PATH),
                "bucket_state_latest": str(BUCKET_STATE_PATH),
                "intervention_ledger": str(intervention_data_dir() / "intervention_ledger.jsonl"),
                "intervention_analytics_latest": str(intervention_data_dir() / "intervention_analytics_latest.json"),
                "proposal_recommendations_latest": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            },
            "why_governance_remains_source_of_truth": {
                "owner": "governance_substrate_v1",
                "proposal_learning_loop_is_governance_truth_source": False,
                "reason": "the posture is derived from directive, bucket, branch, self-structure, work-loop policy, admission, execution, and evidence artifacts, so broader work-loop posture remains governance-owned rather than execution-owned",
            },
        },
        "analytics_context": {
            "analytics_report_path": str(intervention_data_dir() / "intervention_analytics_latest.json"),
            "proposal_recommendations_path": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            "proposal_count": int(analytics.get("proposal_count", 0) or 0),
            "current_recommendation_top_templates": suggested_templates,
            "directive_history_entry_count": int(len(directive_history)),
            "self_structure_ledger_entry_count": int(len(self_structure_ledger)),
            "intervention_ledger_entry_count": int(len(intervention_ledger)),
        },
        "observability_gain": {
            "passed": True,
            "reason": "the system now has a governance-owned statement of the current broader work-loop posture, including what is allowed now, what remains blocked, and what evidence is still missing before broader execution",
            "artifact_paths": {
                "governed_work_loop_posture_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "the posture layer formalizes how NOVALI can progress beyond one-off work items without silently broadening into unsupported execution",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.99,
            "reason": "the posture clarifies what is allowed now, what remains narrow, what still needs evidence, and which next step stays execution-adjacent",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "the posture snapshot is diagnostic-only; it opened no behavior-changing branch, mutated no branch state, promoted no retained skill, and changed no live behavior",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": next_template,
            "reason": "the next useful layer is to screen a second distinct next-step candidate set against this formalized posture so the next bounded continuation candidate can be admitted cleanly",
        },
        "diagnostic_conclusions": {
            "governed_work_loop_posture_v1_defined": True,
            "current_work_loop_posture": primary_posture_class,
            "broader_posture_justified": broader_posture_justified,
            "broader_execution_still_blocked": broader_execution_not_yet_justified,
            "new_behavior_changing_branch_opened": False,
            "branch_state_mutation_occurred": False,
            "retained_promotion_occurred": False,
            "plan_should_remain_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "best_next_template": next_template,
        },
    }
    _write_json(artifact_path, artifact_payload)

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: the current broader governed work-loop posture is now defined without broadening into unsupported execution",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
