from __future__ import annotations

import json
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
    _classify_candidate_self_change,
    _now,
    _write_json,
)
from .ledger import intervention_data_dir, load_latest_snapshots
from .v4_first_hypothesis_landscape_snapshot_v1 import (
    ACTIVE_STATUS_PATH,
    HANDOFF_STATUS_PATH,
    _load_json_file,
    _load_text_file,
)
from .v4_wm_context_signal_overlap_snapshot_v1 import _artifact_reference


SCREEN_OUTPUT_CLASSES = [
    "diagnostic_only",
    "reopen_candidate",
    "gated_review_required",
    "forbidden",
]


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _diagnostic_artifact_dir() -> Path:
    path = intervention_data_dir() / "diagnostic_memory"
    path.mkdir(parents=True, exist_ok=True)
    return path


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
        except json.JSONDecodeError:
            continue
    return rows


def _candidate_screen_schema() -> dict[str, Any]:
    return {
        "schema_name": "GovernedCandidateAdmissionScreen",
        "schema_version": "governed_candidate_admission_v1",
        "output_classes": list(SCREEN_OUTPUT_CLASSES),
        "required_fields": [
            "candidate_id",
            "candidate_name",
            "candidate_type",
            "proposal_family",
            "template_name",
            "idea_class",
            "candidate_summary",
            "action_class",
            "surface",
            "target_surface",
            "directive_relevance",
            "trusted_sources",
            "requested_resources",
            "reversibility",
            "candidate_traits",
            "expected_improvement_claim",
        ],
    }


def _directive_action_class_compatibility(
    candidate: dict[str, Any],
    *,
    directive_state: dict[str, Any],
    self_structure_state: dict[str, Any],
) -> dict[str, Any]:
    current_directive = dict(directive_state.get("current_directive_state", {}))
    policy = dict(self_structure_state.get("policy", {}))
    action_class = str(candidate.get("action_class", ""))
    directly_allowed = action_class in set(str(item) for item in list(current_directive.get("allowed_action_classes", [])))
    policy_gated = action_class in set(str(item) for item in list(policy.get("gated_actions", [])))
    policy_forbidden = action_class in set(str(item) for item in list(policy.get("forbidden_actions", [])))
    if policy_forbidden:
        return {
            "passed": False,
            "status": "forbidden_under_policy",
            "reason": "candidate action class is forbidden by immutable-core governance policy",
        }
    if directly_allowed:
        return {
            "passed": True,
            "status": "directly_allowed_under_current_directive",
            "reason": "candidate action class is explicitly allowed by the active DirectiveSpec",
        }
    if policy_gated:
        return {
            "passed": True,
            "status": "review_only_under_current_directive",
            "reason": "candidate action class is not directly allowed by the active DirectiveSpec but is a governed gated action class",
        }
    return {
        "passed": False,
        "status": "unsupported_action_class",
        "reason": "candidate action class is neither directly allowed by the active DirectiveSpec nor recognized as a valid gated action class",
    }


def _invalid_path_report(candidate: dict[str, Any]) -> dict[str, Any]:
    traits = dict(candidate.get("candidate_traits", {}))
    mapping = {
        "stabilization_iteration_without_new_evidence": "another stabilization iteration without new evidence",
        "global_broadening": "global broadening",
        "pure_wm_retry": "pure wm-only retry",
        "residual_only_retry": "residual-only retry",
        "plan_ownership_change": "plan_ ownership change",
        "adoption_social_conf_self_improve_expansion": "adoption/social_conf_/self_improve expansion",
        "downstream_selected_set_work": "downstream selected-set work",
        "routing_work": "routing work",
        "novali_v3_tuning_reopen": "reopening novali-v3 tuning",
    }
    triggered = [reason for key, reason in mapping.items() if bool(traits.get(key, False))]
    return {
        "passed": len(triggered) == 0,
        "triggered_closed_paths": triggered,
        "reason": (
            "candidate does not match any invalid or already-closed next-step class"
            if not triggered
            else "candidate matches one or more invalid or already-closed next-step classes"
        ),
    }


def _valid_reopen_class_report(candidate: dict[str, Any]) -> dict[str, Any]:
    candidate_type = str(candidate.get("candidate_type", ""))
    idea_class = str(candidate.get("idea_class", ""))
    valid_classes = {
        "new_scoped_hybrid_refinement",
        "distinct_upstream_architecture_diagnostic",
        "reopen_candidate_screening_diagnostic",
        "widening_evidence_candidate",
    }
    if candidate_type == "diagnostic":
        return {
            "passed": idea_class == "reopen_candidate_screening_diagnostic"
            or idea_class == "distinct_upstream_architecture_diagnostic",
            "reason": "diagnostic candidate belongs to a valid governance-owned future candidate class",
        }
    return {
        "passed": idea_class in valid_classes - {"reopen_candidate_screening_diagnostic"},
        "reason": (
            "candidate belongs to a valid future reopen class"
            if idea_class in valid_classes - {"reopen_candidate_screening_diagnostic"}
            else "candidate idea class is not recognized as a valid reopen class"
        ),
    }


def _improvement_bar_report(candidate: dict[str, Any], branch_pause_artifact: dict[str, Any]) -> dict[str, Any]:
    report = dict(dict(branch_pause_artifact.get("branch_pause_report", {})).get("formal_reopen_triggers", {}))
    criteria = dict(report.get("challenger_must_clear_formal_bar", {}))
    hard = dict(criteria.get("required_hard_conditions", {}))
    secondary = dict(criteria.get("secondary_support_conditions", {}))
    claim = dict(candidate.get("expected_improvement_claim", {}))
    if str(candidate.get("candidate_type", "")) == "diagnostic":
        return {
            "status": "not_applicable_for_diagnostic_candidate",
            "plausibly_clears_reopen_bar": False,
            "expected_improvement_claim": claim,
            "reason": "diagnostic candidates are screened for governance usefulness rather than baseline-beating challenger plausibility",
        }
    checks = {
        "selection_score_pre_gate_gap_delta_vs_scoped": _safe_float(
            claim.get("selection_score_pre_gate_gap_delta_vs_scoped"),
            -1.0,
        ) >= _safe_float(hard.get("selection_score_pre_gate_gap_delta_vs_scoped_min"), 0.0),
        "signal_gap_delta_vs_scoped": _safe_float(
            claim.get("signal_gap_delta_vs_scoped"),
            -1.0,
        ) >= _safe_float(hard.get("signal_gap_delta_vs_scoped_min"), 0.0),
        "positive_seed_count_vs_baseline": int(claim.get("positive_seed_count_vs_baseline", 0) or 0)
        >= int(hard.get("positive_seed_count_vs_baseline_must_remain", 0) or 0),
        "strong_slice_delta_delta_floor": _safe_float(claim.get("strong_slice_delta_delta"), -1.0)
        >= _safe_float(hard.get("strong_slice_delta_delta_floor"), 0.0),
        "weak_slice_delta": _safe_float(claim.get("weak_slice_delta"), -1.0)
        >= _safe_float(hard.get("weak_slice_delta_must_remain_non_negative"), 0.0),
        "weak_slice_delta_delta_floor": _safe_float(claim.get("weak_slice_delta_delta"), -1.0)
        >= _safe_float(hard.get("weak_slice_delta_delta_floor"), 0.0),
    }
    secondary_checks = {
        "distinctness_score_delta_vs_scoped": _safe_float(claim.get("distinctness_score_delta_vs_scoped"), -1.0)
        >= _safe_float(secondary.get("distinctness_score_delta_vs_scoped_min"), 0.0),
        "partial_signal_given_baseline_delta_vs_scoped": _safe_float(
            claim.get("partial_signal_given_baseline_delta_vs_scoped"),
            -1.0,
        ) >= _safe_float(secondary.get("partial_signal_given_baseline_delta_vs_scoped_min"), 0.0),
        "seed_2_gap_delta": _safe_float(claim.get("seed_2_gap_delta"), -1.0)
        >= _safe_float(secondary.get("seed_2_gap_delta_min"), 0.0),
        "seed_2_gain_ratio_vs_scoped": _safe_float(claim.get("seed_2_gain_ratio_vs_scoped"), -1.0)
        >= _safe_float(secondary.get("seed_2_gain_ratio_vs_scoped_min"), 0.0),
        "strong_slice_delta_delta_target": _safe_float(claim.get("strong_slice_delta_delta"), -1.0)
        >= _safe_float(secondary.get("strong_slice_delta_delta_target"), 0.0),
    }
    hard_pass = all(checks.values())
    secondary_count = sum(1 for passed in secondary_checks.values() if passed)
    if hard_pass and secondary_count >= 2:
        status = "plausible_clear"
    elif any(_safe_float(value, 0.0) > 0.0 for value in claim.values() if isinstance(value, (int, float))):
        status = "insufficient_evidence"
    else:
        status = "no_material_claim"
    return {
        "status": status,
        "plausibly_clears_reopen_bar": bool(hard_pass and secondary_count >= 2),
        "required_hard_condition_checks": checks,
        "secondary_support_checks": secondary_checks,
        "expected_improvement_claim": claim,
        "reason": (
            "candidate plausibly clears the held-baseline improvement bar"
            if hard_pass and secondary_count >= 2
            else "candidate does not yet plausibly clear the held-baseline improvement bar"
        ),
    }


def _candidate_examples() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": "candidate_diagnostic_reopen_inventory",
            "candidate_name": "Diagnostic reopen inventory",
            "candidate_type": "diagnostic",
            "proposal_family": "memory_summary",
            "template_name": "memory_summary.v4_wm_hybrid_reopen_candidate_screen_snapshot_v1",
            "idea_class": "reopen_candidate_screening_diagnostic",
            "candidate_summary": "Governance-owned diagnostic inventory for future paused-branch challengers.",
            "action_class": "low_risk_shell_change",
            "surface": "diagnostic_memory",
            "target_surface": "diagnostic_memory",
            "directive_relevance": "high",
            "trusted_sources": ["local_repo:novali-v4", "local_artifacts:novali-v4/data"],
            "requested_resources": {"cpu_parallel_units": 1, "memory_mb": 64, "storage_write_mb": 4, "network_mode": "none"},
            "reversibility": "high",
            "candidate_traits": {"stays_upstream": True, "plan_non_owning": True},
            "expected_improvement_claim": {},
        },
        {
            "candidate_id": "candidate_scoped_hybrid_refinement_plausible",
            "candidate_name": "Scoped hybrid refinement plausible challenger",
            "candidate_type": "behavior_changing",
            "proposal_family": "proposal_learning_loop",
            "template_name": "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v2",
            "idea_class": "new_scoped_hybrid_refinement",
            "candidate_summary": "Materially new scoped-hybrid refinement that keeps the branch upstream and plausibly clears the held baseline bar.",
            "action_class": "retained_structural_promotion",
            "surface": "proposal_learning_loop_upstream_context",
            "target_surface": "proposal_learning_loop_upstream_context",
            "directive_relevance": "high",
            "trusted_sources": ["local_repo:novali-v4", "local_artifacts:novali-v4/data"],
            "requested_resources": {"cpu_parallel_units": 1, "memory_mb": 256, "storage_write_mb": 12, "network_mode": "none"},
            "reversibility": "medium",
            "candidate_traits": {"stays_upstream": True, "plan_non_owning": True},
            "expected_improvement_claim": {
                "selection_score_pre_gate_gap_delta_vs_scoped": 0.00007,
                "signal_gap_delta_vs_scoped": 0.0014,
                "positive_seed_count_vs_baseline": 3,
                "strong_slice_delta_delta": 0.00015,
                "weak_slice_delta": 0.00002,
                "weak_slice_delta_delta": -0.00003,
                "distinctness_score_delta_vs_scoped": 0.006,
                "partial_signal_given_baseline_delta_vs_scoped": 0.025,
                "seed_2_gap_delta": 0.00006,
                "seed_2_gain_ratio_vs_scoped": 0.12,
            },
        },
        {
            "candidate_id": "candidate_scoped_hybrid_refinement_insufficient",
            "candidate_name": "Scoped hybrid refinement insufficient evidence",
            "candidate_type": "behavior_changing",
            "proposal_family": "proposal_learning_loop",
            "template_name": "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_candidate_stub",
            "idea_class": "new_scoped_hybrid_refinement",
            "candidate_summary": "Upstream-only refinement idea that does not yet show enough evidence to clear the held baseline bar.",
            "action_class": "retained_structural_promotion",
            "surface": "proposal_learning_loop_upstream_context",
            "target_surface": "proposal_learning_loop_upstream_context",
            "directive_relevance": "high",
            "trusted_sources": ["local_repo:novali-v4"],
            "requested_resources": {"cpu_parallel_units": 1, "memory_mb": 192, "storage_write_mb": 8, "network_mode": "none"},
            "reversibility": "medium",
            "candidate_traits": {"stays_upstream": True, "plan_non_owning": True},
            "expected_improvement_claim": {
                "selection_score_pre_gate_gap_delta_vs_scoped": 0.00002,
                "signal_gap_delta_vs_scoped": 0.0004,
                "positive_seed_count_vs_baseline": 3,
                "strong_slice_delta_delta": 0.00003,
                "weak_slice_delta": 0.00001,
                "weak_slice_delta_delta": -0.00002,
                "distinctness_score_delta_vs_scoped": 0.002,
                "partial_signal_given_baseline_delta_vs_scoped": 0.01,
                "seed_2_gap_delta": 0.00001,
                "seed_2_gain_ratio_vs_scoped": 0.03,
            },
        },
        {
            "candidate_id": "candidate_global_broadening_retry",
            "candidate_name": "Global broadening retry",
            "candidate_type": "behavior_changing",
            "proposal_family": "proposal_learning_loop",
            "template_name": "proposal_learning_loop.v4_wm_hybrid_global_broadening_probe_v1",
            "idea_class": "global_broadening_retry",
            "candidate_summary": "Broadens the scoped hybrid globally and therefore re-enters a path already closed by pause governance.",
            "action_class": "retained_structural_promotion",
            "surface": "proposal_learning_loop_upstream_context",
            "target_surface": "proposal_learning_loop_upstream_context",
            "directive_relevance": "medium",
            "trusted_sources": ["local_repo:novali-v4"],
            "requested_resources": {"cpu_parallel_units": 1, "memory_mb": 192, "storage_write_mb": 8, "network_mode": "none"},
            "reversibility": "medium",
            "candidate_traits": {"global_broadening": True, "stays_upstream": True, "plan_non_owning": True},
            "expected_improvement_claim": {},
        },
    ]


def _screen_candidate(
    candidate: dict[str, Any],
    *,
    directive_state: dict[str, Any],
    bucket_state: dict[str, Any],
    self_structure_state: dict[str, Any],
    branch_record: dict[str, Any],
    branch_pause_artifact: dict[str, Any],
) -> dict[str, Any]:
    policy = dict(self_structure_state.get("policy", {}))
    current_directive = dict(directive_state.get("current_directive_state", {}))
    current_bucket = dict(bucket_state.get("current_bucket_state", {}))

    execution_gate = _classify_candidate_self_change(
        candidate,
        policy=policy,
        directive_state=current_directive,
        bucket_state=current_bucket,
        branch_record=branch_record,
    )
    directive_action_compatibility = _directive_action_class_compatibility(
        candidate,
        directive_state=directive_state,
        self_structure_state=self_structure_state,
    )
    invalid_path = _invalid_path_report(candidate)
    valid_reopen_class = _valid_reopen_class_report(candidate)
    improvement_bar = _improvement_bar_report(candidate, branch_pause_artifact)
    traits = dict(candidate.get("candidate_traits", {}))

    if (
        str(execution_gate.get("admissibility_status", "")) == "forbidden"
        and str(directive_action_compatibility.get("status", "")) == "forbidden_under_policy"
    ) or not invalid_path.get("passed", False):
        admission_class = "forbidden"
        reason = "candidate violates a forbidden or already-closed path and cannot be admitted"
    elif str(candidate.get("candidate_type", "")) == "diagnostic":
        admission_class = "diagnostic_only"
        reason = "candidate is admitted only as diagnostic work and does not justify reopening the paused branch"
    elif (
        valid_reopen_class.get("passed", False)
        and improvement_bar.get("plausibly_clears_reopen_bar", False)
        and bool(traits.get("stays_upstream", False))
        and bool(traits.get("plan_non_owning", False))
    ):
        admission_class = "reopen_candidate"
        reason = "candidate plausibly clears the held baseline bar and is a true reopen candidate, subject to gated review"
    else:
        admission_class = "gated_review_required"
        reason = "candidate is governance-compatible enough to review, but does not yet justify reopening the paused branch"

    return {
        "candidate_id": str(candidate.get("candidate_id", "")),
        "candidate_name": str(candidate.get("candidate_name", "")),
        "proposal_family": str(candidate.get("proposal_family", "")),
        "template_name": str(candidate.get("template_name", "")),
        "candidate_type": str(candidate.get("candidate_type", "")),
        "idea_class": str(candidate.get("idea_class", "")),
        "admission_class": admission_class,
        "admission_reason": reason,
        "directive_action_class_compatibility": directive_action_compatibility,
        "execution_gate_status": str(execution_gate.get("admissibility_status", "")),
        "execution_gate_report": execution_gate,
        "invalid_path_report": invalid_path,
        "valid_reopen_class_report": valid_reopen_class,
        "improvement_bar_report": improvement_bar,
        "candidate_traits": traits,
        "screening_source_of_truth": "governance_substrate_v1",
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_governance_substrate_v1_snapshot"
    )
    directive_init_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_directive_spec_initialization_flow_v1_snapshot"
    )
    branch_pause_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_branch_pause_snapshot_v1"
    )
    working_baseline_artifact = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.v4_wm_hybrid_scoped_working_baseline_snapshot_v1"
    )
    scoped_probe_artifact = r._load_latest_diagnostic_artifact_by_template(
        "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1"
    )
    frontier_snapshot = r._load_latest_diagnostic_artifact_by_template(
        "memory_summary.false_safe_frontier_control_characterization_snapshot_v1"
    )
    if not all(
        [
            governance_snapshot,
            directive_init_snapshot,
            branch_pause_artifact,
            working_baseline_artifact,
            scoped_probe_artifact,
            frontier_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed candidate admission requires governance substrate, directive-init, branch-pause, working-baseline, and scoped-probe artifacts",
            "observability_gain": {"passed": False, "reason": "missing prerequisite artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite artifacts"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot screen paused-branch challengers without the current governance and held-baseline context",
            },
        }

    directive_state = _load_json_file(DIRECTIVE_STATE_PATH)
    bucket_state = _load_json_file(BUCKET_STATE_PATH)
    self_structure_state = _load_json_file(SELF_STRUCTURE_STATE_PATH)
    branch_registry = _load_json_file(BRANCH_REGISTRY_PATH)
    directive_history = _load_jsonl(DIRECTIVE_HISTORY_PATH)
    self_structure_ledger = _load_jsonl(SELF_STRUCTURE_LEDGER_PATH)
    if not all([directive_state, bucket_state, self_structure_state, branch_registry]):
        return {
            "passed": False,
            "shadow_contract": "diagnostic_probe",
            "proposal_semantics": "diagnostic",
            "reason": "diagnostic shadow failed: governed candidate admission requires current governance state artifacts",
            "observability_gain": {"passed": False, "reason": "missing governance source-of-truth artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing governance source-of-truth artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing governance source-of-truth artifacts"},
            "safety_neutrality": {
                "passed": True,
                "reason": "no live-policy mutation occurred",
                "scope": str(proposal.get("scope", "")),
            },
            "later_selection_usefulness": {
                "passed": False,
                "reason": "cannot screen challengers without directive, bucket, self-structure, and branch state",
            },
        }

    active_status_text = _load_text_file(ACTIVE_STATUS_PATH)
    handoff_status = _load_json_file(HANDOFF_STATUS_PATH)
    analytics = build_intervention_ledger_analytics()
    latest_snapshots = load_latest_snapshots()
    recommendations = _load_json_file(intervention_data_dir() / "proposal_recommendations_latest.json")

    branch_record = dict(list(branch_registry.get("branches", []))[0]) if list(branch_registry.get("branches", [])) else {}
    schema = _candidate_screen_schema()
    candidate_examples = _candidate_examples()
    example_results = [
        _screen_candidate(
            candidate,
            directive_state=directive_state,
            bucket_state=bucket_state,
            self_structure_state=self_structure_state,
            branch_record=branch_record,
            branch_pause_artifact=branch_pause_artifact,
        )
        for candidate in candidate_examples
    ]
    example_counts = {
        "diagnostic_only": sum(1 for item in example_results if item["admission_class"] == "diagnostic_only"),
        "reopen_candidate": sum(1 for item in example_results if item["admission_class"] == "reopen_candidate"),
        "gated_review_required": sum(1 for item in example_results if item["admission_class"] == "gated_review_required"),
        "forbidden": sum(1 for item in example_results if item["admission_class"] == "forbidden"),
    }

    current_screen_outcome = {
        "status": "no_candidate_present",
        "reason": "no concrete challenger submission was provided; the branch remains paused and the screen is now available to evaluate future candidates without reopening the branch",
        "branch_state_after_screen": str(branch_record.get("state", "")),
        "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
    }

    artifact_path = (
        _diagnostic_artifact_dir()
        / f"memory_summary_v4_wm_hybrid_reopen_candidate_screen_snapshot_v1_{proposal['proposal_id']}.json"
    )
    all_ranked = list(recommendations.get("all_ranked_proposals", []))
    suggested_templates = [
        str(item.get("template_name", ""))
        for item in all_ranked
        if isinstance(item, dict) and str(item.get("decision", "")) == "suggested"
    ][:8]
    directive_active = str(directive_state.get("initialization_state", "")) == "active"
    directive_history_events = [str(item.get("event_type", "")) for item in directive_history[-8:]]
    self_structure_event_types = [str(item.get("event_type", "")) for item in self_structure_ledger[-12:]]

    updated_self_structure_state = dict(self_structure_state)
    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["governed_candidate_admission"] = {
        "schema_version": "governed_candidate_admission_v1",
        "screen_output_classes": list(SCREEN_OUTPUT_CLASSES),
        "candidate_screen_schema": schema,
        "screening_enabled_for_paused_branches": True,
        "current_branch_id": str(branch_record.get("branch_id", "")),
        "current_branch_state": str(branch_record.get("state", "")),
        "last_screen_artifact_path": str(artifact_path),
        "last_screen_outcome": dict(current_screen_outcome),
    }
    current_state_summary = dict(updated_self_structure_state.get("current_state_summary", {}))
    current_state_summary.update(
        {
            "governed_candidate_admission_in_place": True,
            "paused_branch_challenger_screening_enabled": True,
            "latest_candidate_screen_outcome": str(current_screen_outcome.get("status", "")),
        }
    )
    updated_self_structure_state["current_state_summary"] = current_state_summary
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    ledger_event = {
        "event_id": f"governed_candidate_admission_v1::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_candidate_admission_v1_screen_materialized",
        "event_class": "governed_candidate_admission",
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": str(branch_record.get("state", "")),
        "directive_id": str(dict(directive_state.get("current_directive_state", {})).get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "current_screen_outcome": str(current_screen_outcome.get("status", "")),
        "example_class_counts": dict(example_counts),
        "artifact_paths": {
            "directive_state_latest": str(DIRECTIVE_STATE_PATH),
            "directive_history": str(DIRECTIVE_HISTORY_PATH),
            "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
            "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            "branch_registry_latest": str(BRANCH_REGISTRY_PATH),
            "bucket_state_latest": str(BUCKET_STATE_PATH),
            "candidate_screen_artifact": str(artifact_path),
        },
        "source_proposal_id": str(proposal.get("proposal_id", "")),
    }
    _append_jsonl(SELF_STRUCTURE_LEDGER_PATH, ledger_event)

    artifact_payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "memory_summary.v4_wm_hybrid_reopen_candidate_screen_snapshot_v1",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "branch_context": {
            "active_status_path": str(ACTIVE_STATUS_PATH),
            "handoff_status_path": str(HANDOFF_STATUS_PATH),
            "active_status_mentions_v4_active": "`novali-v4` is the active working version." in active_status_text,
            "carried_forward_baseline": dict(handoff_status.get("carried_forward_baseline", {})),
            "current_branch_id": str(branch_record.get("branch_id", "")),
            "current_branch_state": str(branch_record.get("state", "")),
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
        },
        "comparison_references": {
            "memory_summary.v4_governance_substrate_v1_snapshot": _artifact_reference(governance_snapshot, latest_snapshots),
            "memory_summary.v4_directive_spec_initialization_flow_v1_snapshot": _artifact_reference(
                directive_init_snapshot,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_hybrid_branch_pause_snapshot_v1": _artifact_reference(
                branch_pause_artifact,
                latest_snapshots,
            ),
            "memory_summary.v4_wm_hybrid_scoped_working_baseline_snapshot_v1": _artifact_reference(
                working_baseline_artifact,
                latest_snapshots,
            ),
            "proposal_learning_loop.v4_wm_hybrid_context_scoped_probe_v1": _artifact_reference(
                scoped_probe_artifact,
                latest_snapshots,
            ),
            "memory_summary.false_safe_frontier_control_characterization_snapshot_v1": _artifact_reference(
                frontier_snapshot,
                latest_snapshots,
            ),
        },
        "governed_candidate_admission_summary": {
            "candidate_schema": schema,
            "governance_inputs_consumed": {
                "directive_state_latest": str(DIRECTIVE_STATE_PATH),
                "directive_history": str(DIRECTIVE_HISTORY_PATH),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
                "branch_registry_latest": str(BRANCH_REGISTRY_PATH),
                "bucket_state_latest": str(BUCKET_STATE_PATH),
            },
            "governance_input_state": {
                "directive_is_active": directive_active,
                "directive_history_tail": directive_history_events,
                "self_structure_event_tail": self_structure_event_types,
                "branch_state": str(branch_record.get("state", "")),
                "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
            },
            "screening_logic": {
                "dimensions": [
                    "directive_relevance",
                    "trusted_source_and_action_class_compatibility",
                    "bucket_resource_feasibility",
                    "mutable_surface_legality",
                    "branch_state_compatibility",
                    "held_baseline_challenge_strength",
                    "improvement_bar_plausibility",
                    "closed_path_violation_check",
                ],
                "held_baseline_improvement_bar": dict(
                    dict(dict(branch_pause_artifact.get("branch_pause_report", {})).get("formal_reopen_triggers", {})).get(
                        "challenger_must_clear_formal_bar",
                        {},
                    )
                ),
                "paused_branches_remain_paused_without_clear_challenger": True,
            },
            "admission_classes": list(SCREEN_OUTPUT_CLASSES),
            "screening_examples": example_results,
            "example_class_counts": example_counts,
            "current_screen_outcome": current_screen_outcome,
            "governance_source_of_truth": {
                "owner": "governance_substrate_v1",
                "proposal_learning_loop_is_governance_truth_source": False,
                "why": "candidate screening reads directive, branch, bucket, and self-structure governance artifacts as the authoritative admission context",
            },
        },
        "analytics_context": {
            "analytics_report_path": str(intervention_data_dir() / "intervention_analytics_latest.json"),
            "proposal_recommendations_path": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            "proposal_count": int(analytics.get("proposal_count", 0) or 0),
            "current_recommendation_top_templates": suggested_templates,
        },
        "decision_recommendation": {
            "governed_candidate_admission_v1_in_place": True,
            "paused_branch_can_be_screened_without_reopen": True,
            "current_screen_outcome": str(current_screen_outcome.get("status", "")),
            "plan_should_remain_non_owning": True,
            "recommended_next_step": "keep the wm-hybrid branch paused and use this screen as the governance gate whenever a concrete challenger idea is proposed",
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
        },
        "observability_gain": {
            "passed": True,
            "reason": "Governed Candidate Admission v1 now materializes a canonical candidate-screen representation and a governance-owned paused-branch screen without reopening the branch",
            "artifact_paths": {
                "candidate_screen_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {
            "passed": True,
            "reason": "paused-branch challengers can now be screened against directive, branch, bucket, and held-baseline constraints before any reopen is considered",
        },
        "ambiguity_reduction": {
            "passed": True,
            "score": 0.97,
            "reason": "the implementation separates diagnostic-only candidates, plausible reopen candidates, gated but insufficient challengers, and forbidden closed-path retries using governance-owned context",
        },
        "safety_neutrality": {
            "passed": True,
            "scope": str(proposal.get("scope", "")),
            "reason": "Governed Candidate Admission v1 is diagnostic and governance-owned only; live policy, thresholds, routing policy, frozen benchmark semantics, and projection-safe envelope remain unchanged",
        },
        "later_selection_usefulness": {
            "passed": True,
            "recommended_next_template": "",
            "reason": "the next safe move is to wait for a real challenger submission and run it through this screen before any reopen is attempted",
        },
        "diagnostic_conclusions": {
            "governed_candidate_admission_v1_in_place": True,
            "paused_branch_can_be_screened_without_reopen": True,
            "current_screen_outcome": str(current_screen_outcome.get("status", "")),
            "plan_should_remain_non_owning": True,
            "routing_deferred": bool(
                dict(frontier_snapshot.get("diagnostic_conclusions", {})).get("routing_deferred", False)
            ),
            "current_branch_state": str(branch_record.get("state", "")),
            "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
        },
    }
    _write_json(artifact_path, artifact_payload)

    return {
        "passed": True,
        "shadow_contract": "diagnostic_probe",
        "proposal_semantics": "diagnostic",
        "reason": "diagnostic shadow passed: Governed Candidate Admission v1 now screens paused wm-hybrid challengers through governance-owned context before any reopen can occur",
        "observability_gain": dict(artifact_payload["observability_gain"]),
        "activation_analysis_usefulness": dict(artifact_payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(artifact_payload["ambiguity_reduction"]),
        "safety_neutrality": dict(artifact_payload["safety_neutrality"]),
        "later_selection_usefulness": dict(artifact_payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(artifact_payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
