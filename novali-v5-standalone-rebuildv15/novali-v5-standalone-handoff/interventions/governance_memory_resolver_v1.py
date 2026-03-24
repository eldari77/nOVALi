from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .governance_substrate_v1 import (
    BRANCH_REGISTRY_PATH,
    BUCKET_STATE_PATH,
    DIRECTIVE_HISTORY_PATH,
    DIRECTIVE_STATE_PATH,
    SELF_STRUCTURE_LEDGER_PATH,
    SELF_STRUCTURE_STATE_PATH,
    _now,
)
from .ledger import intervention_data_dir


VERSION_HANDOFF_STATUS_PATH = intervention_data_dir() / "version_handoff_status.json"
INTERVENTION_LEDGER_PATH = intervention_data_dir() / "intervention_ledger.jsonl"
INTERVENTION_ANALYTICS_PATH = intervention_data_dir() / "intervention_analytics_latest.json"
PROPOSAL_RECOMMENDATIONS_PATH = intervention_data_dir() / "proposal_recommendations_latest.json"
GOVERNANCE_MEMORY_AUTHORITY_PATH = intervention_data_dir() / "governance_memory_authority_latest.json"
GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH = intervention_data_dir() / "governance_memory_promotion_ledger.jsonl"
GOVERNANCE_REOPEN_INTAKE_LEDGER_PATH = intervention_data_dir() / "governance_reopen_intake_ledger.jsonl"
GOVERNANCE_REOPEN_SCREENING_LEDGER_PATH = intervention_data_dir() / "governance_reopen_screening_ledger.jsonl"
GOVERNANCE_REOPEN_REVIEW_LEDGER_PATH = intervention_data_dir() / "governance_reopen_review_ledger.jsonl"
GOVERNANCE_REOPEN_REVIEW_OUTCOME_LEDGER_PATH = intervention_data_dir() / "governance_reopen_review_outcome_ledger.jsonl"
GOVERNANCE_REOPEN_PROMOTION_HANDOFF_LEDGER_PATH = intervention_data_dir() / "governance_reopen_promotion_handoff_ledger.jsonl"
GOVERNANCE_REOPEN_PROMOTION_OUTCOME_LEDGER_PATH = intervention_data_dir() / "governance_reopen_promotion_outcome_ledger.jsonl"
GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_LEDGER_PATH = intervention_data_dir() / "governance_reopen_promotion_reconciliation_ledger.jsonl"
GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_ESCALATION_LEDGER_PATH = (
    intervention_data_dir() / "governance_reopen_promotion_reconciliation_escalation_ledger.jsonl"
)
GOVERNANCE_REOPEN_REMEDIATION_REVIEW_LEDGER_PATH = (
    intervention_data_dir() / "governance_reopen_remediation_review_ledger.jsonl"
)
GOVERNANCE_REOPEN_REMEDIATION_REVIEW_OUTCOME_LEDGER_PATH = (
    intervention_data_dir() / "governance_reopen_remediation_review_outcome_ledger.jsonl"
)
GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_HANDOFF_LEDGER_PATH = (
    intervention_data_dir() / "governance_reopen_rollback_or_repair_handoff_ledger.jsonl"
)
GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_OUTCOME_LEDGER_PATH = (
    intervention_data_dir() / "governance_reopen_rollback_or_repair_outcome_ledger.jsonl"
)
GOVERNANCE_REOPEN_MISMATCH_CASE_CLOSURE_LEDGER_PATH = (
    intervention_data_dir() / "governance_reopen_mismatch_case_closure_ledger.jsonl"
)
GOVERNANCE_REOPEN_CASE_REGISTRY_LEDGER_PATH = (
    intervention_data_dir() / "governance_reopen_case_registry_ledger.jsonl"
)
GOVERNANCE_REOPEN_CASE_TRIAGE_LEDGER_PATH = (
    intervention_data_dir() / "governance_reopen_case_triage_ledger.jsonl"
)
GOVERNANCE_REOPEN_CASE_QUEUE_LEDGER_PATH = (
    intervention_data_dir() / "governance_reopen_case_queue_ledger.jsonl"
)
GOVERNANCE_PORTFOLIO_BRIEF_LEDGER_PATH = (
    intervention_data_dir() / "governance_portfolio_brief_ledger.jsonl"
)

READ_CONTRACT_SCHEMA_NAME = "GovernanceMemoryReadContract"
READ_CONTRACT_SCHEMA_VERSION = "governance_memory_read_contract_v1"
RESOLVED_STATE_SCHEMA_NAME = "GovernanceMemoryResolvedCurrentState"
RESOLVED_STATE_SCHEMA_VERSION = "governance_memory_resolved_current_state_v1"


AUTHORITY_RESOLUTION_ORDER = [
    {
        "surface": "governance_memory_authority_latest",
        "precedence_rank": 1,
        "role": "canonical_current_state",
        "overlap_rule": "wins_on_current_state_overlap",
    },
    {
        "surface": "self_structure_state_latest",
        "precedence_rank": 2,
        "role": "compatibility_mirror_and_fallback",
        "overlap_rule": "used_only_when_canonical_field_is_missing_or_unreadable",
    },
    {
        "surface": "branch_registry_latest",
        "precedence_rank": 3,
        "role": "branch_posture_supporting_registry",
        "overlap_rule": "branch_support_only_never_overrides_present_canonical_fields",
    },
    {
        "surface": "directive_state_latest",
        "precedence_rank": 4,
        "role": "directive_context_supporting_registry",
        "overlap_rule": "directive_support_only_never_overrides_present_canonical_fields",
    },
    {
        "surface": "bucket_state_latest",
        "precedence_rank": 5,
        "role": "bucket_and_trust_supporting_registry",
        "overlap_rule": "bucket_support_only_never_overrides_present_canonical_fields",
    },
    {
        "surface": "version_handoff_status",
        "precedence_rank": 6,
        "role": "cross_version_reference_support",
        "overlap_rule": "support_only_never_overrides_present_canonical_fields",
    },
    {
        "surface": "binding_decision_artifacts",
        "precedence_rank": 7,
        "role": "decision_provenance_and_evidence_support",
        "overlap_rule": "evidence_only_never_overrides_current_state",
    },
    {
        "surface": "directive_history_and_ledgers",
        "precedence_rank": 8,
        "role": "historical_audit_only",
        "overlap_rule": "audit_only_never_overrides_current_state",
    },
    {
        "surface": "runtime_recommendation_surfaces",
        "precedence_rank": 9,
        "role": "observational_non_authoritative",
        "overlap_rule": "never_authoritative_without_explicit_governance_promotion",
    },
]


CANONICAL_FIELD_OWNERSHIP = {
    "active_branch": {
        "owner_surface": "governance_memory_authority_latest",
        "canonical_path": "authority_file_summary.active_branch",
        "fallback_paths": [
            "self_structure_state_latest.current_state_summary.active_working_version",
        ],
    },
    "frozen_fallback_reference_version": {
        "owner_surface": "governance_memory_authority_latest",
        "canonical_path": "authority_file_summary.frozen_fallback_reference_version",
        "fallback_paths": [
            "self_structure_state_latest.current_state_summary.frozen_fallback_reference_version",
        ],
    },
    "additional_reference_versions": {
        "owner_surface": "governance_memory_authority_latest",
        "canonical_path": "authority_file_summary.additional_reference_versions",
        "fallback_paths": [],
    },
    "current_branch_state": {
        "owner_surface": "governance_memory_authority_latest",
        "canonical_path": "authority_file_summary.current_branch_state",
        "fallback_paths": [
            "self_structure_state_latest.current_state_summary.current_branch_state",
            "branch_registry_latest.branches[0].state",
        ],
    },
    "held_baseline_template": {
        "owner_surface": "governance_memory_authority_latest",
        "canonical_path": "authority_file_summary.held_baseline_template",
        "fallback_paths": [
            "self_structure_state_latest.current_state_summary.held_baseline_template",
            "branch_registry_latest.branches[0].held_baseline.template",
        ],
    },
    "current_operating_stance": {
        "owner_surface": "governance_memory_authority_latest",
        "canonical_path": "authority_file_summary.current_operating_stance",
        "fallback_paths": [
            "self_structure_state_latest.current_state_summary.latest_current_operating_stance",
        ],
    },
    "routing_status": {
        "owner_surface": "governance_memory_authority_latest",
        "canonical_path": "authority_file_summary.routing_status",
        "fallback_paths": [
            "self_structure_state_latest.current_state_summary.routing_deferred",
        ],
    },
    "projection_safety_primary": {
        "owner_surface": "governance_memory_authority_latest",
        "canonical_path": "authority_file_summary.projection_safety_primary",
        "fallback_paths": [],
    },
    "plan_non_owning": {
        "owner_surface": "governance_memory_authority_latest",
        "canonical_path": "authority_file_summary.plan_non_owning",
        "fallback_paths": [
            "self_structure_state_latest.current_state_summary.plan_non_owning",
        ],
    },
    "governed_work_loop_status": {
        "owner_surface": "governance_memory_authority_latest",
        "canonical_path": "authority_file_summary.governed_work_loop_status",
        "fallback_paths": [
            "self_structure_state_latest.current_state_summary.latest_governed_work_loop_closeout_outcome",
        ],
    },
    "reopen_eligibility": {
        "owner_surface": "governance_memory_authority_latest",
        "canonical_path": "authority_file_summary.reopen_eligibility",
        "fallback_paths": [],
    },
    "capability_boundary_state": {
        "owner_surface": "governance_memory_authority_latest",
        "canonical_path": "capability_boundary_state",
        "fallback_paths": [],
    },
    "binding_decision_register": {
        "owner_surface": "governance_memory_authority_latest",
        "canonical_path": "binding_decision_register",
        "fallback_paths": [],
    },
    "selector_frontier_memory": {
        "owner_surface": "governance_memory_authority_latest",
        "canonical_path": "selector_frontier_memory",
        "fallback_paths": [
            "self_structure_state_latest.governance_memory_authority.selector_frontier_memory",
        ],
    },
    "swap_c_status": {
        "owner_surface": "governance_memory_authority_latest",
        "canonical_path": "authority_file_summary.swap_c_status",
        "fallback_paths": [
            "self_structure_state_latest.governance_memory_authority.swap_c_status",
            "version_handoff_status.carried_forward_baseline",
        ],
    },
    "authority_mutation_stage": {
        "owner_surface": "governance_memory_authority_latest",
        "canonical_path": "authority_mutation_stage",
        "fallback_paths": [],
    },
    "authority_candidate_record": {
        "owner_surface": "governance_memory_authority_latest",
        "canonical_path": "authority_candidate_record",
        "fallback_paths": [],
    },
    "authority_promotion_record": {
        "owner_surface": "governance_memory_authority_latest",
        "canonical_path": "authority_promotion_record",
        "fallback_paths": [],
    },
}


DERIVED_SUPPORTING_FIELD_OWNERSHIP = {
    "directive_id": {
        "owner_surface": "directive_state_latest",
        "path": "current_directive_state.directive_id",
    },
    "directive_activation_state": {
        "owner_surface": "directive_state_latest",
        "path": "initialization_state",
    },
    "bucket_id": {
        "owner_surface": "bucket_state_latest",
        "path": "current_bucket_state.bucket_id",
    },
    "trusted_sources": {
        "owner_surface": "bucket_state_latest",
        "path": "current_bucket_state.trusted_sources",
    },
    "write_roots": {
        "owner_surface": "bucket_state_latest",
        "path": "current_bucket_state.mount_policy.write_roots",
    },
    "read_roots": {
        "owner_surface": "bucket_state_latest",
        "path": "current_bucket_state.mount_policy.read_roots",
    },
    "branch_pause_rationale": {
        "owner_surface": "branch_registry_latest",
        "path": "branches[0].pause_rationale",
    },
    "branch_reopen_triggers": {
        "owner_surface": "branch_registry_latest",
        "path": "branches[0].reopen_triggers",
    },
    "authority_artifact_path": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_memory_authority_artifact_path",
    },
    "latest_reopen_intake_artifact_path": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_intake_artifact_path",
    },
    "latest_reopen_intake_state": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_intake_state",
    },
    "latest_reopen_screening_state": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_screening_state",
    },
    "latest_reopen_review_state": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_review_state",
    },
    "latest_reopen_screening_artifact_path": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_screening_artifact_path",
    },
    "latest_reopen_evidence_sufficiency_assessment": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_evidence_sufficiency_assessment",
    },
    "latest_reopen_review_artifact_path": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_review_artifact_path",
    },
    "latest_reopen_review_submission_state": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_review_submission_state",
    },
    "latest_reopen_review_outcome_state": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_review_outcome_state",
    },
    "latest_reopen_review_outcome_artifact_path": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_review_outcome_artifact_path",
    },
    "latest_reopen_promotion_handoff_state": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_promotion_handoff_state",
    },
    "latest_reopen_promotion_candidate_state": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_promotion_candidate_state",
    },
    "latest_reopen_promotion_handoff_artifact_path": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_promotion_handoff_artifact_path",
    },
    "latest_reopen_promotion_outcome_state": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_promotion_outcome_state",
    },
    "latest_reopen_promotion_outcome_artifact_path": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_promotion_outcome_artifact_path",
    },
    "latest_reopen_promotion_gate_actor": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_promotion_gate_actor",
    },
    "latest_reopen_promotion_reconciliation_state": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_reconciliation_state",
    },
    "latest_reopen_promotion_reconciliation_artifact_path": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_reconciliation_artifact_path",
    },
    "latest_reopen_rollback_reference_state": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_rollback_reference_state",
    },
    "latest_reopen_promotion_reconciliation_escalation_state": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_reconciliation_escalation_state",
    },
    "latest_reopen_promotion_reconciliation_escalation_artifact_path": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_reconciliation_escalation_artifact_path",
    },
    "latest_reopen_remediation_review_state": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_remediation_review_state",
    },
    "latest_reopen_remediation_review_artifact_path": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_remediation_review_artifact_path",
    },
    "latest_reopen_remediation_review_submission_state": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_remediation_review_submission_state",
    },
    "latest_reopen_remediation_review_outcome_state": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_remediation_review_outcome_state",
    },
    "latest_reopen_remediation_review_outcome_artifact_path": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_remediation_review_outcome_artifact_path",
    },
    "latest_reopen_remediation_follow_on_handoff_state": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_remediation_follow_on_handoff_state",
    },
    "latest_reopen_rollback_or_repair_handoff_state": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_rollback_or_repair_handoff_state",
    },
    "latest_reopen_rollback_or_repair_candidate_state": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_rollback_or_repair_candidate_state",
    },
    "latest_reopen_rollback_or_repair_handoff_artifact_path": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_rollback_or_repair_handoff_artifact_path",
    },
    "latest_reopen_rollback_or_repair_outcome_state": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_rollback_or_repair_outcome_state",
    },
    "latest_reopen_rollback_or_repair_outcome_artifact_path": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_rollback_or_repair_outcome_artifact_path",
    },
    "latest_reopen_rollback_or_repair_existing_path_actor": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_rollback_or_repair_existing_path_actor",
    },
    "latest_reopen_mismatch_case_closure_state": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_mismatch_case_closure_state",
    },
    "latest_reopen_mismatch_case_closure_artifact_path": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_mismatch_case_closure_artifact_path",
    },
    "latest_reopen_mismatch_case_follow_on_reconciliation_state": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_mismatch_case_follow_on_reconciliation_state",
    },
    "latest_reopen_case_registry_artifact_path": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_case_registry_artifact_path",
    },
    "latest_reopen_case_registry_total_case_count": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_case_registry_total_case_count",
    },
    "latest_reopen_case_registry_open_case_count": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_case_registry_open_case_count",
    },
    "latest_reopen_case_registry_pending_case_count": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_case_registry_pending_case_count",
    },
    "latest_reopen_case_registry_closed_case_count": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_case_registry_closed_case_count",
    },
    "latest_reopen_case_registry_stale_case_count": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_case_registry_stale_case_count",
    },
    "latest_reopen_case_triage_artifact_path": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_case_triage_artifact_path",
    },
    "latest_reopen_case_triage_total_case_count": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_case_triage_total_case_count",
    },
    "latest_reopen_case_triage_active_portfolio_case_count": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_case_triage_active_portfolio_case_count",
    },
    "latest_reopen_case_triage_attention_case_count": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_case_triage_attention_case_count",
    },
    "latest_reopen_case_triage_monitor_case_count": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_case_triage_monitor_case_count",
    },
    "latest_reopen_case_triage_follow_on_reconciliation_due_case_count": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_case_triage_follow_on_reconciliation_due_case_count",
    },
    "latest_reopen_case_triage_closed_no_action_case_count": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_case_triage_closed_no_action_case_count",
    },
    "latest_reopen_case_triage_stale_case_count": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_case_triage_stale_case_count",
    },
    "latest_reopen_case_queue_artifact_path": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_case_queue_artifact_path",
    },
    "latest_reopen_case_queue_total_case_count": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_case_queue_total_case_count",
    },
    "latest_reopen_case_queue_included_case_count": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_case_queue_included_case_count",
    },
    "latest_reopen_case_queue_attention_case_count": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_case_queue_attention_case_count",
    },
    "latest_reopen_case_queue_monitor_case_count": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_case_queue_monitor_case_count",
    },
    "latest_reopen_case_queue_follow_on_case_count": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_case_queue_follow_on_case_count",
    },
    "latest_reopen_case_queue_closed_excluded_case_count": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_case_queue_closed_excluded_case_count",
    },
    "latest_reopen_case_queue_stale_excluded_case_count": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_case_queue_stale_excluded_case_count",
    },
    "latest_reopen_case_queue_next_case_identifier": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_case_queue_next_case_identifier",
    },
    "latest_reopen_case_queue_next_queue_class": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_reopen_case_queue_next_queue_class",
    },
    "latest_governance_portfolio_brief_artifact_path": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_portfolio_brief_artifact_path",
    },
    "latest_governance_portfolio_brief_case_count": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_portfolio_brief_case_count",
    },
    "latest_governance_portfolio_brief_attention_case_count": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_portfolio_brief_attention_case_count",
    },
    "latest_governance_portfolio_brief_queue_included_case_count": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_portfolio_brief_queue_included_case_count",
    },
    "latest_governance_portfolio_brief_next_case_identifier": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_portfolio_brief_next_case_identifier",
    },
    "latest_governance_portfolio_brief_recommended_next_action_class": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_portfolio_brief_recommended_next_action_class",
    },
    "latest_governance_portfolio_brief_recommended_next_governance_action": {
        "owner_surface": "self_structure_state_latest",
        "path": "current_state_summary.latest_governance_portfolio_brief_recommended_next_governance_action",
    },
}


HISTORICAL_AUDIT_ONLY_SURFACES = {
    "directive_history": str(DIRECTIVE_HISTORY_PATH),
    "self_structure_ledger": str(SELF_STRUCTURE_LEDGER_PATH),
    "intervention_ledger": str(INTERVENTION_LEDGER_PATH),
    "governance_memory_promotion_ledger": str(GOVERNANCE_MEMORY_PROMOTION_LEDGER_PATH),
    "governance_reopen_intake_ledger": str(GOVERNANCE_REOPEN_INTAKE_LEDGER_PATH),
    "governance_reopen_screening_ledger": str(GOVERNANCE_REOPEN_SCREENING_LEDGER_PATH),
    "governance_reopen_review_ledger": str(GOVERNANCE_REOPEN_REVIEW_LEDGER_PATH),
    "governance_reopen_review_outcome_ledger": str(GOVERNANCE_REOPEN_REVIEW_OUTCOME_LEDGER_PATH),
    "governance_reopen_promotion_handoff_ledger": str(GOVERNANCE_REOPEN_PROMOTION_HANDOFF_LEDGER_PATH),
    "governance_reopen_promotion_outcome_ledger": str(GOVERNANCE_REOPEN_PROMOTION_OUTCOME_LEDGER_PATH),
    "governance_reopen_promotion_reconciliation_ledger": str(
        GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_LEDGER_PATH
    ),
    "governance_reopen_promotion_reconciliation_escalation_ledger": str(
        GOVERNANCE_REOPEN_PROMOTION_RECONCILIATION_ESCALATION_LEDGER_PATH
    ),
    "governance_reopen_remediation_review_ledger": str(
        GOVERNANCE_REOPEN_REMEDIATION_REVIEW_LEDGER_PATH
    ),
    "governance_reopen_remediation_review_outcome_ledger": str(
        GOVERNANCE_REOPEN_REMEDIATION_REVIEW_OUTCOME_LEDGER_PATH
    ),
    "governance_reopen_rollback_or_repair_handoff_ledger": str(
        GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_HANDOFF_LEDGER_PATH
    ),
    "governance_reopen_rollback_or_repair_outcome_ledger": str(
        GOVERNANCE_REOPEN_ROLLBACK_OR_REPAIR_OUTCOME_LEDGER_PATH
    ),
    "governance_reopen_mismatch_case_closure_ledger": str(
        GOVERNANCE_REOPEN_MISMATCH_CASE_CLOSURE_LEDGER_PATH
    ),
    "governance_reopen_case_registry_ledger": str(
        GOVERNANCE_REOPEN_CASE_REGISTRY_LEDGER_PATH
    ),
    "governance_reopen_case_triage_ledger": str(
        GOVERNANCE_REOPEN_CASE_TRIAGE_LEDGER_PATH
    ),
    "governance_reopen_case_queue_ledger": str(
        GOVERNANCE_REOPEN_CASE_QUEUE_LEDGER_PATH
    ),
    "governance_portfolio_brief_ledger": str(
        GOVERNANCE_PORTFOLIO_BRIEF_LEDGER_PATH
    ),
}


NON_AUTHORITATIVE_RUNTIME_SURFACES = {
    "proposal_recommendations_latest": str(PROPOSAL_RECOMMENDATIONS_PATH),
    "intervention_analytics_latest": str(INTERVENTION_ANALYTICS_PATH),
}


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")))
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        return {}


def _root_payloads(
    *,
    governance_memory_authority_override: dict[str, Any] | None = None,
    self_structure_state_override: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    return {
        "governance_memory_authority_latest": dict(governance_memory_authority_override or _load_json_file(GOVERNANCE_MEMORY_AUTHORITY_PATH)),
        "self_structure_state_latest": dict(self_structure_state_override or _load_json_file(SELF_STRUCTURE_STATE_PATH)),
        "branch_registry_latest": _load_json_file(BRANCH_REGISTRY_PATH),
        "directive_state_latest": _load_json_file(DIRECTIVE_STATE_PATH),
        "bucket_state_latest": _load_json_file(BUCKET_STATE_PATH),
        "version_handoff_status": _load_json_file(VERSION_HANDOFF_STATUS_PATH),
    }


def _parse_path(path: str) -> list[str]:
    tokens: list[str] = []
    current = []
    for char in str(path):
        if char == ".":
            if current:
                tokens.append("".join(current))
                current = []
            continue
        current.append(char)
    if current:
        tokens.append("".join(current))
    return tokens


def _get_path(payload: Any, path: str) -> Any:
    current: Any = payload
    for token in _parse_path(path):
        if "[" in token and token.endswith("]"):
            field, index_text = token[:-1].split("[", 1)
            if field:
                if not isinstance(current, dict):
                    return None
                current = current.get(field)
            if not isinstance(current, list):
                return None
            try:
                index = int(index_text)
            except ValueError:
                return None
            if index < 0 or index >= len(current):
                return None
            current = current[index]
            continue
        if not isinstance(current, dict):
            return None
        current = current.get(token)
        if current is None:
            return None
    return current


def _routing_fallback(value: Any) -> str:
    if isinstance(value, bool):
        return "routing_deferred" if value else "routing_not_deferred"
    return str(value or "")


def _resolve_field(field_name: str, payloads: dict[str, dict[str, Any]]) -> tuple[Any, str, bool]:
    spec = dict(CANONICAL_FIELD_OWNERSHIP.get(str(field_name), {}))
    owner_surface = str(spec.get("owner_surface", ""))
    canonical_path = str(spec.get("canonical_path", ""))
    if owner_surface and canonical_path:
        value = _get_path(payloads.get(owner_surface, {}), canonical_path)
        if value is not None:
            if field_name == "routing_status":
                return _routing_fallback(value), owner_surface, False
            return value, owner_surface, False
    for fallback_path in list(spec.get("fallback_paths", [])):
        fallback_text = str(fallback_path)
        if "." not in fallback_text:
            continue
        surface_name, nested_path = fallback_text.split(".", 1)
        value = _get_path(payloads.get(surface_name, {}), nested_path)
        if value is not None:
            if field_name == "routing_status":
                return _routing_fallback(value), surface_name, True
            return value, surface_name, True
    return None, "", False


def build_governance_memory_read_contract() -> dict[str, Any]:
    return {
        "schema_name": READ_CONTRACT_SCHEMA_NAME,
        "schema_version": READ_CONTRACT_SCHEMA_VERSION,
        "top_level_canonical_authority_file": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
        "top_level_canonical_authority_surface": "governance_memory_authority_latest",
        "resolution_order": list(AUTHORITY_RESOLUTION_ORDER),
        "overlap_resolution_rules": {
            "governance_memory_authority_latest_vs_self_structure_state_latest": (
                "governance_memory_authority_latest wins for current-state overlap; "
                "self_structure_state_latest is a compatibility mirror and fallback only"
            ),
            "self_structure_state_latest_vs_ledger_style_artifacts": (
                "self_structure_state_latest wins for current-state overlap; ledger-style artifacts are historical audit only"
            ),
            "binding_decision_artifacts_vs_runtime_recommendation_surfaces": (
                "binding decision artifacts provide evidence and provenance; runtime recommendations remain non-authoritative"
            ),
        },
        "canonical_field_ownership": dict(CANONICAL_FIELD_OWNERSHIP),
        "derived_supporting_field_ownership": dict(DERIVED_SUPPORTING_FIELD_OWNERSHIP),
        "historical_audit_only_surfaces": dict(HISTORICAL_AUDIT_ONLY_SURFACES),
        "non_authoritative_runtime_surfaces": dict(NON_AUTHORITATIVE_RUNTIME_SURFACES),
    }


def resolve_governance_memory_current_state(
    *,
    governance_memory_authority_override: dict[str, Any] | None = None,
    self_structure_state_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payloads = _root_payloads(
        governance_memory_authority_override=governance_memory_authority_override,
        self_structure_state_override=self_structure_state_override,
    )
    contract = build_governance_memory_read_contract()

    resolved_fields: dict[str, Any] = {}
    resolution_trace: dict[str, Any] = {}
    fallback_used = False
    for field_name in CANONICAL_FIELD_OWNERSHIP:
        value, source_surface, used_fallback = _resolve_field(field_name, payloads)
        resolved_fields[field_name] = value
        resolution_trace[field_name] = {
            "resolved_from_surface": source_surface,
            "used_fallback": bool(used_fallback),
        }
        fallback_used = fallback_used or bool(used_fallback)

    derived_support: dict[str, Any] = {}
    for field_name, spec in DERIVED_SUPPORTING_FIELD_OWNERSHIP.items():
        surface = str(spec.get("owner_surface", ""))
        path = str(spec.get("path", ""))
        derived_support[field_name] = {
            "value": _get_path(payloads.get(surface, {}), path),
            "resolved_from_surface": surface,
        }

    selector_frontier_memory = dict(resolved_fields.get("selector_frontier_memory") or {})
    blocked_residuals = dict(selector_frontier_memory.get("blocked_residuals") or {})
    binding_decisions = list(resolved_fields.get("binding_decision_register") or [])
    capability_boundary_state = dict(resolved_fields.get("capability_boundary_state") or {})
    reopen_eligibility = dict(resolved_fields.get("reopen_eligibility") or {})
    swap_c_status = dict(resolved_fields.get("swap_c_status") or {})
    authority_candidate_record = dict(resolved_fields.get("authority_candidate_record") or {})
    authority_promotion_record = dict(resolved_fields.get("authority_promotion_record") or {})

    return {
        "schema_name": RESOLVED_STATE_SCHEMA_NAME,
        "schema_version": RESOLVED_STATE_SCHEMA_VERSION,
        "read_contract_version": READ_CONTRACT_SCHEMA_VERSION,
        "resolved_at": _now(),
        "authority_source_file": str(GOVERNANCE_MEMORY_AUTHORITY_PATH),
        "authority_source_used": "governance_memory_authority_latest",
        "fallback_used": bool(fallback_used),
        "canonical_current_posture": {
            "active_branch": str(resolved_fields.get("active_branch", "")),
            "frozen_fallback_reference_version": str(
                resolved_fields.get("frozen_fallback_reference_version", "")
            ),
            "additional_reference_versions": [
                str(item) for item in list(resolved_fields.get("additional_reference_versions") or [])
            ],
            "current_branch_state": str(resolved_fields.get("current_branch_state", "")),
            "held_baseline_template": str(resolved_fields.get("held_baseline_template", "")),
            "current_operating_stance": str(resolved_fields.get("current_operating_stance", "")),
            "routing_status": str(resolved_fields.get("routing_status", "")),
            "projection_safety_primary": bool(resolved_fields.get("projection_safety_primary", False)),
            "plan_non_owning": bool(resolved_fields.get("plan_non_owning", False)),
            "governed_work_loop_status": str(resolved_fields.get("governed_work_loop_status", "")),
            "reopen_eligibility": reopen_eligibility,
        },
        "authority_mutation_state": {
            "current_stage": str(resolved_fields.get("authority_mutation_stage", "")),
            "candidate_record": authority_candidate_record,
            "promotion_record": authority_promotion_record,
        },
        "capability_boundaries": capability_boundary_state,
        "binding_decisions": {
            str(item.get("decision_id", "")): {
                "status": str(item.get("status", "")),
                "decision_class": str(item.get("decision_class", "")),
                "authority_source": str(item.get("authority_source", "")),
            }
            for item in binding_decisions
            if isinstance(item, dict) and str(item.get("decision_id", ""))
        },
        "selector_frontier_conclusions": {
            "final_selection_split_assessment": str(
                selector_frontier_memory.get("final_selection_split_assessment", "")
            ),
            "dominant_blocker": str(selector_frontier_memory.get("dominant_blocker", "")),
            "first_gate": str(selector_frontier_memory.get("first_gate", "")),
            "second_gate": str(selector_frontier_memory.get("second_gate", "")),
            "blocked_residuals": blocked_residuals,
        },
        "swap_c_status": swap_c_status,
        "supporting_context": derived_support,
        "resolution_trace": resolution_trace,
        "historical_audit_only_surfaces": dict(HISTORICAL_AUDIT_ONLY_SURFACES),
        "runtime_surfaces_authoritative": False,
    }
