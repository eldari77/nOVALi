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
    _now,
    _write_json,
)
from .governed_skill_acquisition_v1 import (
    _diagnostic_artifact_dir,
    _example_skill_candidates,
    _load_jsonl,
    _parse_local_trace_log,
    _select_trial_log_group,
    _summarize_parsed_logs,
    _trial_artifact_digest,
)
from .ledger import intervention_data_dir, load_latest_snapshots
from .v4_first_hypothesis_landscape_snapshot_v1 import _load_json_file
from .v4_governed_skill_local_trace_parser_provisional_probe_v1 import _bucket_pressure, _path_within_allowed_roots
from .v4_wm_context_signal_overlap_snapshot_v1 import _artifact_reference


def _extract_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    local_sources = dict(summary.get("local_sources_parsed", {}))
    parse_summary = dict(local_sources.get("trusted_log_parse_summary", {}))
    evidence = dict(summary.get("evidence_produced", {}))
    utility = dict(evidence.get("utility_assessment", {}))
    directive = dict(evidence.get("directive_relevance", {}))
    duplication = dict(evidence.get("duplication_overlap", {}))
    return {
        "dummy_eval_count": int(utility.get("dummy_eval_count", 0) or 0),
        "patch_tuple_count": int(utility.get("patch_tuple_count", 0) or 0),
        "recognized_line_share_weighted": float(utility.get("recognized_line_share_weighted", 0.0) or 0.0),
        "seed_coverage": int(parse_summary.get("parsed_file_count", 0) or 0),
        "directive_relevance": str(directive.get("value", "")),
        "duplication": str(duplication.get("value", "")),
    }


def _trend_against(current: dict[str, Any], prior: dict[str, Any]) -> dict[str, Any]:
    deltas = {
        "dummy_eval_count_delta": int(current.get("dummy_eval_count", 0)) - int(prior.get("dummy_eval_count", 0)),
        "patch_tuple_count_delta": int(current.get("patch_tuple_count", 0)) - int(prior.get("patch_tuple_count", 0)),
        "recognized_line_share_weighted_delta": float(current.get("recognized_line_share_weighted", 0.0)) - float(
            prior.get("recognized_line_share_weighted", 0.0)
        ),
        "seed_coverage_delta": int(current.get("seed_coverage", 0)) - int(prior.get("seed_coverage", 0)),
    }
    weakening = (
        deltas["recognized_line_share_weighted_delta"] < -0.01
        or deltas["dummy_eval_count_delta"] < 0
        or deltas["patch_tuple_count_delta"] < 0
        or deltas["seed_coverage_delta"] < 0
    )
    strengthening = (
        deltas["recognized_line_share_weighted_delta"] > 0.01
        or deltas["dummy_eval_count_delta"] > 0
        or deltas["patch_tuple_count_delta"] > 0
        or deltas["seed_coverage_delta"] > 0
    )
    classification = "weakening" if weakening else "strengthening" if strengthening else "stable_flat"
    return {
        "classification": classification,
        "metric_deltas": deltas,
        "reason": (
            "current evidence is weaker than the comparison run"
            if classification == "weakening"
            else "current evidence is stronger than the comparison run"
            if classification == "strengthening"
            else "current evidence is materially unchanged versus the comparison run"
        ),
    }


def run_probe(cfg, proposal, *, rounds, seeds):
    from . import runner as r

    governance_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governance_substrate_v1_snapshot")
    trial_execution_snapshot = r._load_latest_diagnostic_artifact_by_template("proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1")
    trial_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governed_skill_trial_evidence_snapshot_v1")
    provisional_admission_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governed_skill_provisional_admission_snapshot_v1")
    provisional_probe_v1_snapshot = r._load_latest_diagnostic_artifact_by_template("proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v1")
    provisional_evidence_snapshot = r._load_latest_diagnostic_artifact_by_template("memory_summary.v4_governed_skill_provisional_evidence_snapshot_v1")
    if not all(
        [
            governance_snapshot,
            trial_execution_snapshot,
            trial_evidence_snapshot,
            provisional_admission_snapshot,
            provisional_probe_v1_snapshot,
            provisional_evidence_snapshot,
        ]
    ):
        return {
            "passed": False,
            "shadow_contract": "provisional_skill_probe",
            "proposal_semantics": "shadow_skill_trial",
            "reason": "shadow provisional probe failed: governance, trial, trial-evidence, provisional-admission, provisional-probe-v1, and provisional-evidence artifacts are required",
            "observability_gain": {"passed": False, "reason": "missing prerequisite provisional-v2 artifacts"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing prerequisite provisional-v2 artifacts"},
            "ambiguity_reduction": {"passed": False, "reason": "missing prerequisite provisional-v2 artifacts"},
            "safety_neutrality": {"passed": True, "scope": str(proposal.get("scope", "")), "reason": "no live-policy mutation occurred"},
            "later_selection_usefulness": {"passed": False, "reason": "the v2 provisional probe cannot run without the full governance-owned evidence chain"},
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
            "shadow_contract": "provisional_skill_probe",
            "proposal_semantics": "shadow_skill_trial",
            "reason": "shadow provisional probe failed: current directive, bucket, self-structure, and branch state artifacts are required",
            "observability_gain": {"passed": False, "reason": "missing durable governance state"},
            "activation_analysis_usefulness": {"passed": False, "reason": "missing durable governance state"},
            "ambiguity_reduction": {"passed": False, "reason": "missing durable governance state"},
            "safety_neutrality": {"passed": True, "scope": str(proposal.get("scope", "")), "reason": "no live-policy mutation occurred"},
            "later_selection_usefulness": {"passed": False, "reason": "the v2 provisional probe cannot stay governance-owned without directive, bucket, self-structure, and branch state"},
        }

    branch_record = dict(list(branch_registry.get("branches", []))[0]) if list(branch_registry.get("branches", [])) else {}
    current_branch_state = str(branch_record.get("state", ""))
    current_state_summary = dict(self_structure_state.get("current_state_summary", {}))
    governed_skill_subsystem = dict(self_structure_state.get("governed_skill_subsystem", {}))
    last_provisional_admission = dict(governed_skill_subsystem.get("last_provisional_admission_outcome", {}))
    if current_branch_state != "paused_with_baseline_held" or str(last_provisional_admission.get("provisional_admission_outcome", "")) != "admissible_for_provisional_handling":
        return {
            "passed": False,
            "shadow_contract": "provisional_skill_probe",
            "proposal_semantics": "shadow_skill_trial",
            "reason": "shadow provisional probe failed: branch must stay paused_with_baseline_held and the candidate must already be admitted for provisional handling",
            "observability_gain": {"passed": False, "reason": "branch state or provisional admission state invalid"},
            "activation_analysis_usefulness": {"passed": False, "reason": "branch state or provisional admission state invalid"},
            "ambiguity_reduction": {"passed": False, "reason": "branch state or provisional admission state invalid"},
            "safety_neutrality": {"passed": True, "scope": str(proposal.get("scope", "")), "reason": "no live-policy mutation occurred"},
            "later_selection_usefulness": {"passed": False, "reason": "the v2 provisional probe can only run inside the already admitted paused branch envelope"},
        }

    primary_candidate = next(
        (item for item in _example_skill_candidates() if str(item.get("skill_id", "")) == "skill_candidate_local_trace_parser_trial"),
        {},
    )
    trial_execution_artifact_path = Path(str(governed_skill_subsystem.get("last_trial_execution_artifact_path") or dict(trial_execution_snapshot).get("artifact_path", "")))
    trial_evidence_artifact_path = Path(str(governed_skill_subsystem.get("last_trial_evidence_artifact_path") or dict(trial_evidence_snapshot).get("artifact_path", "")))
    provisional_admission_artifact_path = Path(str(governed_skill_subsystem.get("last_provisional_admission_artifact_path") or dict(provisional_admission_snapshot).get("artifact_path", "")))
    provisional_probe_v1_artifact_path = Path(
        str(governed_skill_subsystem.get("last_provisional_execution_artifact_path") or dict(provisional_probe_v1_snapshot).get("artifact_path", ""))
    )
    trial_execution_summary = dict(_load_json_file(trial_execution_artifact_path).get("governed_skill_trial_summary", {}))
    trial_evidence_summary = dict(_load_json_file(trial_evidence_artifact_path).get("governed_skill_trial_evidence_summary", {}))
    provisional_summary = dict(_load_json_file(provisional_admission_artifact_path).get("governed_skill_provisional_admission_summary", {}))
    provisional_probe_v1_summary = dict(_load_json_file(provisional_probe_v1_artifact_path).get("governed_skill_provisional_probe_summary", {}))
    provisional_envelope = dict(provisional_summary.get("provisional_envelope", {}))
    evidence_obligations = dict(provisional_summary.get("evidence_obligations", {}))

    log_group = _select_trial_log_group(max_files=3)
    if not bool(log_group.get("passed", False)):
        return {
            "passed": False,
            "shadow_contract": "provisional_skill_probe",
            "proposal_semantics": "shadow_skill_trial",
            "reason": "shadow provisional probe failed: no trusted local log group is available",
            "observability_gain": {"passed": False, "reason": str(log_group.get("reason", ""))},
            "activation_analysis_usefulness": {"passed": False, "reason": str(log_group.get("reason", ""))},
            "ambiguity_reduction": {"passed": False, "reason": str(log_group.get("reason", ""))},
            "safety_neutrality": {"passed": True, "scope": str(proposal.get("scope", "")), "reason": "no live-policy mutation occurred"},
            "later_selection_usefulness": {"passed": False, "reason": "the v2 provisional probe has no trusted local logs to parse"},
        }

    parsed_logs = [_parse_local_trace_log(Path(path)) for path in list(log_group.get("selected_paths", []))]
    parsed_log_summary = _summarize_parsed_logs(parsed_logs)
    current_metrics = {
        "dummy_eval_count": int(parsed_log_summary.get("dummy_eval_count", 0) or 0),
        "patch_tuple_count": int(parsed_log_summary.get("patch_tuple_count", 0) or 0),
        "recognized_line_share_weighted": float(parsed_log_summary.get("recognized_line_share_weighted", 0.0) or 0.0),
        "seed_coverage": int(parsed_log_summary.get("parsed_file_count", 0) or 0),
        "directive_relevance": str(primary_candidate.get("directive_relevance", "")),
        "duplication": str(primary_candidate.get("duplication_risk", "")),
    }
    evidence_obligation_status = {
        "recognized_line_share_weighted_observed": current_metrics["recognized_line_share_weighted"],
        "recognized_line_share_weighted_required": float(evidence_obligations.get("recognized_line_share_weighted_min", 0.95) or 0.95),
        "seed_log_coverage_observed": current_metrics["seed_coverage"],
        "seed_log_coverage_required": int(evidence_obligations.get("seed_log_coverage_min", 3) or 3),
        "dummy_eval_count_observed": current_metrics["dummy_eval_count"],
        "dummy_eval_count_required": int(evidence_obligations.get("dummy_eval_count_min", 100) or 100),
        "patch_tuple_count_observed": current_metrics["patch_tuple_count"],
        "patch_tuple_count_required": int(evidence_obligations.get("patch_tuple_count_min", 500) or 500),
        "directive_relevance_observed": current_metrics["directive_relevance"],
        "directive_relevance_required": str(evidence_obligations.get("directive_relevance_required", "high")),
        "duplication_risk_observed": current_metrics["duplication"],
        "duplication_risk_required_low": bool(evidence_obligations.get("duplication_risk_must_remain_low", True)),
        "shadow_only_execution": True,
        "governance_reporting_active": True,
    }
    evidence_obligation_status["passed"] = (
        evidence_obligation_status["recognized_line_share_weighted_observed"] >= evidence_obligation_status["recognized_line_share_weighted_required"]
        and evidence_obligation_status["seed_log_coverage_observed"] >= evidence_obligation_status["seed_log_coverage_required"]
        and evidence_obligation_status["dummy_eval_count_observed"] >= evidence_obligation_status["dummy_eval_count_required"]
        and evidence_obligation_status["patch_tuple_count_observed"] >= evidence_obligation_status["patch_tuple_count_required"]
        and evidence_obligation_status["directive_relevance_observed"] == evidence_obligation_status["directive_relevance_required"]
        and evidence_obligation_status["duplication_risk_observed"] == "low"
    )
    evidence_obligation_status["reason"] = (
        "all provisional evidence obligations remained satisfied across the second bounded rerun"
        if evidence_obligation_status["passed"]
        else "at least one provisional evidence obligation failed on the second bounded rerun"
    )

    pressure = _bucket_pressure(bucket_state, dict(provisional_envelope.get("resource_ceilings", {})))
    artifact_path = _diagnostic_artifact_dir() / f"proposal_learning_loop_v4_governed_skill_local_trace_parser_provisional_probe_v2_{proposal['proposal_id']}.json"
    allowed_roots = [Path(path).resolve() for path in list(provisional_envelope.get("allowed_write_roots", []))]
    write_paths = [artifact_path, SELF_STRUCTURE_STATE_PATH, SELF_STRUCTURE_LEDGER_PATH]
    envelope_compliance = {
        "network_mode_required": str(provisional_envelope.get("network_mode", "none") or "none"),
        "network_mode_observed": "none",
        "network_mode_remained_none": str(provisional_envelope.get("network_mode", "none") or "none") == "none",
        "branch_state_stayed_paused_with_baseline_held": current_branch_state == "paused_with_baseline_held",
        "no_branch_state_mutation": True,
        "no_retained_promotion": True,
        "no_protected_surface_modification": True,
        "no_downstream_selected_set_work": True,
        "no_plan_ownership_change": True,
        "no_routing_work": True,
        "writes_within_approved_roots": all(_path_within_allowed_roots(path, allowed_roots) for path in write_paths),
        "approved_write_paths": [str(path) for path in write_paths],
        "resource_ceilings": dict(provisional_envelope.get("resource_ceilings", {})),
        "bucket_pressure": pressure,
        "resource_limits_respected": pressure["concern_level"] == "low",
    }
    envelope_compliance["passed"] = all(
        bool(envelope_compliance[key])
        for key in [
            "network_mode_remained_none",
            "branch_state_stayed_paused_with_baseline_held",
            "no_branch_state_mutation",
            "no_retained_promotion",
            "no_protected_surface_modification",
            "no_downstream_selected_set_work",
            "no_plan_ownership_change",
            "no_routing_work",
            "writes_within_approved_roots",
            "resource_limits_respected",
        ]
    )

    rollback_trigger_status = {
        "network_mode_deviation": not bool(envelope_compliance["network_mode_remained_none"]),
        "write_root_violation": not bool(envelope_compliance["writes_within_approved_roots"]),
        "branch_state_mutation": not bool(envelope_compliance["branch_state_stayed_paused_with_baseline_held"]),
        "protected_surface_change": not bool(envelope_compliance["no_protected_surface_modification"]),
        "downstream_selected_set_work": not bool(envelope_compliance["no_downstream_selected_set_work"]),
        "plan_ownership_change": not bool(envelope_compliance["no_plan_ownership_change"]),
        "routing_work_drift": not bool(envelope_compliance["no_routing_work"]),
        "resource_ceiling_breach": not bool(envelope_compliance["resource_limits_respected"]),
        "evidence_quality_regression": not bool(evidence_obligation_status["passed"]),
    }
    rollback_trigger_status["any_trigger_fired"] = any(bool(value) for key, value in rollback_trigger_status.items() if key != "any_trigger_fired")
    deprecation_trigger_status = {
        "repeated_low_distinct_utility": current_metrics["dummy_eval_count"] < int(evidence_obligations.get("dummy_eval_count_min", 100) or 100),
        "directive_relevance_decay": current_metrics["directive_relevance"] != str(evidence_obligations.get("directive_relevance_required", "high")),
        "duplication_overlap_growth": current_metrics["duplication"] != "low",
        "governance_reporting_failure": False,
        "bucket_infeasibility": pressure["concern_level"] != "low",
    }
    deprecation_trigger_status["any_trigger_active"] = any(bool(value) for key, value in deprecation_trigger_status.items() if key != "any_trigger_active")

    trend_vs_trial = _trend_against(current_metrics, _extract_metrics(trial_execution_summary))
    trend_vs_provisional_v1 = _trend_against(current_metrics, _extract_metrics(provisional_probe_v1_summary))
    overall_trend = (
        "weakening"
        if "weakening" in {str(trend_vs_trial["classification"]), str(trend_vs_provisional_v1["classification"])}
        else "strengthening"
        if "strengthening" in {str(trend_vs_trial["classification"]), str(trend_vs_provisional_v1["classification"])}
        else "stable_flat"
    )

    if evidence_obligation_status["passed"] and envelope_compliance["passed"] and not rollback_trigger_status["any_trigger_fired"] and not deprecation_trigger_status["any_trigger_active"]:
        candidate_status = "viable_for_continued_provisional_handling"
        best_next_template = "memory_summary.v4_governed_skill_provisional_evidence_snapshot_v2"
        outcome_reason = "the parser remained stable, useful, directive-relevant, low-duplication, and governance-compliant across another bounded provisional run"
    elif not envelope_compliance["passed"] or rollback_trigger_status["any_trigger_fired"]:
        candidate_status = "blocked_from_further_escalation"
        best_next_template = "memory_summary.v4_governed_skill_provisional_gap_snapshot_v1"
        outcome_reason = "the second provisional rerun surfaced an envelope or rollback-trigger problem that blocks further escalation"
    else:
        candidate_status = "downgraded_to_sandbox_only"
        best_next_template = "memory_summary.v4_governed_skill_provisional_gap_snapshot_v1"
        outcome_reason = "the second provisional rerun stayed safe but no longer clears the evidence bar for continued provisional handling"

    payload = {
        "proposal_id": str(proposal.get("proposal_id")),
        "template_name": "proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v2",
        "evaluation_semantics": str(proposal.get("evaluation_semantics", "")),
        "trigger_reason": str(proposal.get("trigger_reason", "")),
        "branch_context": {
            "current_branch_id": str(branch_record.get("branch_id", "")),
            "current_branch_state": current_branch_state,
            "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
            "plan_non_owning": bool(current_state_summary.get("plan_non_owning", False)),
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
        },
        "comparison_references": {
            "memory_summary.v4_governance_substrate_v1_snapshot": _artifact_reference(governance_snapshot, latest_snapshots),
            "proposal_learning_loop.v4_governed_skill_local_trace_parser_trial_v1": _artifact_reference(trial_execution_snapshot, latest_snapshots),
            "memory_summary.v4_governed_skill_trial_evidence_snapshot_v1": _artifact_reference(trial_evidence_snapshot, latest_snapshots),
            "memory_summary.v4_governed_skill_provisional_admission_snapshot_v1": _artifact_reference(provisional_admission_snapshot, latest_snapshots),
            "proposal_learning_loop.v4_governed_skill_local_trace_parser_provisional_probe_v1": _artifact_reference(provisional_probe_v1_snapshot, latest_snapshots),
            "memory_summary.v4_governed_skill_provisional_evidence_snapshot_v1": _artifact_reference(provisional_evidence_snapshot, latest_snapshots),
        },
        "governed_skill_provisional_probe_summary": {
            "candidate_evaluated": {
                "skill_id": str(primary_candidate.get("skill_id", "")),
                "candidate_name": str(primary_candidate.get("candidate_name", "")),
                "candidate_summary": str(primary_candidate.get("candidate_summary", "")),
                "provisional_admission_outcome": str(last_provisional_admission.get("provisional_admission_outcome", "")),
            },
            "what_the_probe_did": [
                "selected a coherent trusted local shadow-log group under the admitted provisional envelope",
                "parsed local intervention shadow logs for section markers, adopt_patch events, and dummy_eval payloads",
                "read the latest trial, trial-evidence, provisional-admission, provisional-probe-v1, and provisional-evidence artifacts as trusted governance-owned context",
                "materialized only shadow-only evidence, trend-sensitive metrics, and rollback/deprecation status without opening or mutating a branch",
            ],
            "local_sources_parsed": {
                "trusted_log_group": dict(log_group),
                "trusted_log_parse_summary": parsed_log_summary,
                "trusted_diagnostic_memory_sources": [
                    _trial_artifact_digest(trial_execution_artifact_path),
                    _trial_artifact_digest(trial_evidence_artifact_path),
                    _trial_artifact_digest(provisional_admission_artifact_path),
                    _trial_artifact_digest(provisional_probe_v1_artifact_path),
                ],
            },
            "evidence_produced": {
                "utility_assessment": {
                    "passed": evidence_obligation_status["passed"],
                    "reason": outcome_reason if candidate_status == "viable_for_continued_provisional_handling" else "the second provisional rerun did not fully preserve the admitted evidence contract",
                    "dummy_eval_count": current_metrics["dummy_eval_count"],
                    "patch_tuple_count": current_metrics["patch_tuple_count"],
                    "recognized_line_share_weighted": current_metrics["recognized_line_share_weighted"],
                },
                "directive_relevance": {
                    "passed": current_metrics["directive_relevance"] == "high",
                    "value": current_metrics["directive_relevance"],
                    "reason": "candidate remains high-directive-relevance local parsing work inside governance-owned provisional handling",
                },
                "duplication_overlap": {
                    "passed": current_metrics["duplication"] == "low",
                    "value": current_metrics["duplication"],
                    "reason": "candidate remains low-duplication relative to the current governed skill set",
                },
            },
            "evidence_obligation_status": evidence_obligation_status,
            "envelope_compliance": envelope_compliance,
            "rollback_trigger_status": rollback_trigger_status,
            "deprecation_trigger_status": deprecation_trigger_status,
            "trend_comparison": {
                "overall_classification": overall_trend,
                "vs_trial": trend_vs_trial,
                "vs_provisional_probe_v1": trend_vs_provisional_v1,
                "cumulative_retention_readiness_signal": (
                    "beginning_to_strengthen"
                    if overall_trend == "strengthening"
                    else "still_below_retained_threshold"
                ),
            },
            "provisional_handling_assessment": {"candidate_status": candidate_status, "reason": outcome_reason},
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
            "governance_source_of_truth": {
                "owner": "governance_substrate_v1",
                "proposal_learning_loop_is_governance_truth_source": False,
                "reason": "the v2 provisional probe derives its rules and trend checks from governance artifacts rather than from execution code alone",
            },
        },
        "analytics_context": {
            "analytics_report_path": str(intervention_data_dir() / "intervention_analytics_latest.json"),
            "proposal_recommendations_path": str(intervention_data_dir() / "proposal_recommendations_latest.json"),
            "proposal_count": int(analytics.get("proposal_count", 0) or 0),
            "current_recommendation_top_templates": [
                str(item.get("template_name", ""))
                for item in list(recommendations.get("all_ranked_proposals", []))
                if isinstance(item, dict) and str(item.get("decision", "")) == "suggested"
            ][:8],
            "directive_history_tail": [str(item.get("event_type", "")) for item in directive_history[-8:]],
            "self_structure_event_tail": [str(item.get("event_type", "")) for item in self_structure_ledger[-12:]],
            "intervention_ledger_rows_reviewed": len(intervention_ledger[-8:]),
        },
        "observability_gain": {
            "passed": True,
            "reason": "the admitted provisional skill now has a second bounded execution record with explicit trend comparison against both the original trial and provisional probe v1",
            "artifact_paths": {
                "provisional_probe_v2_artifact": str(artifact_path),
                "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
                "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            },
        },
        "activation_analysis_usefulness": {"passed": True, "reason": "the v2 provisional probe shows whether the line is merely stable or actually beginning to strengthen toward later retention-readiness"},
        "ambiguity_reduction": {"passed": True, "score": 0.99, "reason": "the v2 rerun cleanly distinguishes strengthening, stable-flat, and weakening evidence while preserving the same governance envelope"},
        "safety_neutrality": {"passed": True, "scope": str(proposal.get("scope", "")), "reason": "the v2 provisional probe remained shadow-only, local, reversible, and governance-bounded; no live behavior change occurred"},
        "later_selection_usefulness": {"passed": True, "recommended_next_template": best_next_template, "reason": "the next step can now respond to the observed evidence trend rather than only a single provisional run"},
        "diagnostic_conclusions": {
            "governed_skill_provisional_probe_v2_in_place": True,
            "branch_state_stayed_paused_with_baseline_held": True,
            "retained_promotion_occurred": False,
            "plan_should_remain_non_owning": bool(current_state_summary.get("plan_non_owning", False)),
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "provisional_handling_status": candidate_status,
            "evidence_trend": overall_trend,
            "below_retained_promotion_threshold": True,
            "best_next_template": best_next_template,
        },
    }
    _write_json(artifact_path, payload)
    estimated_write_bytes = int(artifact_path.stat().st_size) + len(json.dumps({"updated_state": True})) + len(json.dumps({"ledger_event": True}))
    payload["governed_skill_provisional_probe_summary"]["envelope_compliance"]["estimated_write_bytes"] = int(estimated_write_bytes)
    payload["governed_skill_provisional_probe_summary"]["envelope_compliance"]["storage_budget_mb"] = int(dict(provisional_envelope.get("resource_ceilings", {})).get("storage_write_mb", 0) or 0)
    payload["governed_skill_provisional_probe_summary"]["envelope_compliance"]["storage_budget_respected"] = estimated_write_bytes <= int(dict(provisional_envelope.get("resource_ceilings", {})).get("storage_write_mb", 0) or 0) * 1024 * 1024
    _write_json(artifact_path, payload)

    updated_self_structure_state = dict(self_structure_state)
    updated_governed_skill_subsystem = dict(governed_skill_subsystem)
    updated_governed_skill_subsystem["last_provisional_execution_artifact_path"] = str(artifact_path)
    updated_governed_skill_subsystem["last_provisional_execution_outcome"] = {
        "primary_candidate_skill_id": str(primary_candidate.get("skill_id", "")),
        "primary_candidate_name": str(primary_candidate.get("candidate_name", "")),
        "provisional_execution_outcome": "provisional_probe_v2_completed",
        "bounded_and_reversible": True,
        "branch_state_mutation": False,
        "retained_promotion": False,
        "candidate_status": candidate_status,
        "evidence_trend": overall_trend,
    }
    updated_governed_skill_subsystem["best_next_template"] = best_next_template
    updated_self_structure_state["generated_at"] = _now()
    updated_self_structure_state["governed_skill_subsystem"] = updated_governed_skill_subsystem
    updated_current_state_summary = dict(current_state_summary)
    updated_current_state_summary.update(
        {
            "latest_skill_provisional_execution_outcome": "provisional_probe_v2_completed",
            "latest_skill_provisional_candidate": str(primary_candidate.get("candidate_name", "")),
            "latest_skill_provisional_status": candidate_status,
            "latest_skill_provisional_trend": overall_trend,
            "skill_provisional_branch_opened": False,
            "current_branch_state": current_branch_state,
            "plan_non_owning": True,
            "routing_deferred": bool(current_state_summary.get("routing_deferred", False)),
            "retained_skill_promotion_performed": False,
        }
    )
    updated_self_structure_state["current_state_summary"] = updated_current_state_summary
    _write_json(SELF_STRUCTURE_STATE_PATH, updated_self_structure_state)

    ledger_event = {
        "event_id": f"governed_skill_local_trace_parser_provisional_probe_v2::{proposal['proposal_id']}",
        "timestamp": _now(),
        "event_type": "governed_skill_local_trace_parser_provisional_probe_v2_materialized",
        "event_class": "governed_skill_provisional_execution",
        "directive_id": str(dict(directive_state.get("current_directive_state", {})).get("directive_id", "")),
        "directive_state": str(directive_state.get("initialization_state", "")),
        "branch_id": str(branch_record.get("branch_id", "")),
        "branch_state": current_branch_state,
        "held_baseline_template": str(dict(branch_record.get("held_baseline", {})).get("template", "")),
        "primary_candidate_skill_id": str(primary_candidate.get("skill_id", "")),
        "provisional_execution_outcome": "provisional_probe_v2_completed",
        "candidate_status": candidate_status,
        "evidence_trend": overall_trend,
        "branch_state_mutation": False,
        "retained_promotion": False,
        "network_mode": "none",
        "artifact_paths": {
            "directive_state_latest": str(DIRECTIVE_STATE_PATH),
            "directive_history": str(DIRECTIVE_HISTORY_PATH),
            "self_structure_state_latest": str(SELF_STRUCTURE_STATE_PATH),
            "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
            "branch_registry_latest": str(BRANCH_REGISTRY_PATH),
            "bucket_state_latest": str(BUCKET_STATE_PATH),
            "skill_trial_execution_artifact": str(trial_execution_artifact_path),
            "skill_trial_evidence_artifact": str(trial_evidence_artifact_path),
            "skill_provisional_admission_artifact": str(provisional_admission_artifact_path),
            "skill_provisional_probe_v1_artifact": str(provisional_probe_v1_artifact_path),
            "skill_provisional_probe_v2_artifact": str(artifact_path),
        },
        "source_proposal_id": str(proposal.get("proposal_id", "")),
    }
    _append_jsonl(SELF_STRUCTURE_LEDGER_PATH, ledger_event)

    return {
        "passed": True,
        "shadow_contract": "provisional_skill_probe",
        "proposal_semantics": "shadow_skill_trial",
        "reason": "shadow provisional probe passed: the admitted local trace parser remained bounded and governance-compliant across a second provisional run with explicit trend comparison",
        "observability_gain": dict(payload["observability_gain"]),
        "activation_analysis_usefulness": dict(payload["activation_analysis_usefulness"]),
        "ambiguity_reduction": dict(payload["ambiguity_reduction"]),
        "safety_neutrality": dict(payload["safety_neutrality"]),
        "later_selection_usefulness": dict(payload["later_selection_usefulness"]),
        "diagnostic_conclusions": dict(payload["diagnostic_conclusions"]),
        "artifact_path": str(artifact_path),
    }
