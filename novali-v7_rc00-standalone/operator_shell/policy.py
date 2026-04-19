from __future__ import annotations

import hashlib
import logging
import json
import os
import sys
import uuid
import urllib.parse
from pathlib import Path
from typing import Any

from .common import (
    OPERATOR_CONTEXT_ENV,
    OPERATOR_ROLE_RUNTIME,
    OperatorPolicyMutationRefusedError,
)
from .envelope import (
    build_default_operator_runtime_envelope_spec,
    operator_runtime_launch_plan_latest_path,
    operator_runtime_envelope_spec_path,
    probe_runtime_backend_capabilities,
    validate_operator_runtime_envelope_spec,
)


RUNTIME_CONSTRAINTS_SCHEMA_NAME = "OperatorRuntimeConstraints"
RUNTIME_CONSTRAINTS_SCHEMA_VERSION = "operator_runtime_constraints_v1"
TRUSTED_SOURCE_BINDINGS_SCHEMA_NAME = "TrustedSourceBindings"
TRUSTED_SOURCE_BINDINGS_SCHEMA_VERSION = "trusted_source_bindings_v1"
TRUSTED_SOURCE_SECRETS_SCHEMA_NAME = "TrustedSourceSecretsLocal"
TRUSTED_SOURCE_SECRETS_SCHEMA_VERSION = "trusted_source_secrets_local_v1"
TRUSTED_SOURCE_CREDENTIAL_STATUS_SCHEMA_NAME = "TrustedSourceCredentialStatus"
TRUSTED_SOURCE_CREDENTIAL_STATUS_SCHEMA_VERSION = "trusted_source_credential_status_v1"
TRUSTED_SOURCE_PROVIDER_STATUS_SCHEMA_NAME = "TrustedSourceProviderStatus"
TRUSTED_SOURCE_PROVIDER_STATUS_SCHEMA_VERSION = "trusted_source_provider_status_v1"
TRUSTED_SOURCE_OPERATOR_POLICY_SCHEMA_NAME = "TrustedSourceOperatorPolicy"
TRUSTED_SOURCE_OPERATOR_POLICY_SCHEMA_VERSION = "trusted_source_operator_policy_v1"
TRUSTED_SOURCE_OPERATOR_AGGRESSIVENESS_POLICY_SCHEMA_NAME = (
    "TrustedSourceOperatorAggressivenessPolicy"
)
TRUSTED_SOURCE_OPERATOR_AGGRESSIVENESS_POLICY_SCHEMA_VERSION = (
    "trusted_source_operator_aggressiveness_policy_v1"
)
TRUSTED_SOURCE_OPERATOR_BUDGET_POLICY_SCHEMA_NAME = "TrustedSourceOperatorBudgetPolicy"
TRUSTED_SOURCE_OPERATOR_BUDGET_POLICY_SCHEMA_VERSION = (
    "trusted_source_operator_budget_policy_v1"
)
TRUSTED_SOURCE_OPERATOR_RETRY_POLICY_SCHEMA_NAME = "TrustedSourceOperatorRetryPolicy"
TRUSTED_SOURCE_OPERATOR_RETRY_POLICY_SCHEMA_VERSION = (
    "trusted_source_operator_retry_policy_v1"
)
TRUSTED_SOURCE_OPERATOR_ESCALATION_THRESHOLDS_SCHEMA_NAME = (
    "TrustedSourceOperatorEscalationThresholds"
)
TRUSTED_SOURCE_OPERATOR_ESCALATION_THRESHOLDS_SCHEMA_VERSION = (
    "trusted_source_operator_escalation_thresholds_v1"
)
EFFECTIVE_OPERATOR_SESSION_SCHEMA_NAME = "EffectiveOperatorSession"
EFFECTIVE_OPERATOR_SESSION_SCHEMA_VERSION = "effective_operator_session_v1"
OPERATOR_LAUNCH_EVENT_SCHEMA_NAME = "OperatorLaunchEvent"
OPERATOR_LAUNCH_EVENT_SCHEMA_VERSION = "operator_launch_event_v1"
OPERATOR_RUN_PRESET_SCHEMA_NAME = "OperatorRunPreset"
OPERATOR_RUN_PRESET_SCHEMA_VERSION = "operator_run_preset_v1"
OPERATOR_SESSION_STATE_SCHEMA_NAME = "OperatorSessionState"
OPERATOR_SESSION_STATE_SCHEMA_VERSION = "operator_session_state_v1"
OPERATOR_RESUME_SUMMARY_SCHEMA_NAME = "OperatorResumeSummary"
OPERATOR_RESUME_SUMMARY_SCHEMA_VERSION = "operator_resume_summary_v1"
OPERATOR_SESSION_CONTINUITY_SCHEMA_NAME = "OperatorSessionContinuity"
OPERATOR_SESSION_CONTINUITY_SCHEMA_VERSION = "operator_session_continuity_v1"
OPERATOR_CURRENT_SESSION_SUMMARY_SCHEMA_NAME = "OperatorCurrentSessionSummary"
OPERATOR_CURRENT_SESSION_SUMMARY_SCHEMA_VERSION = "operator_current_session_summary_v1"
OPERATOR_NEXT_ACTION_SUMMARY_SCHEMA_NAME = "OperatorNextActionSummary"
OPERATOR_NEXT_ACTION_SUMMARY_SCHEMA_VERSION = "operator_next_action_summary_v1"
OPERATOR_RESUME_POLICY_SUMMARY_SCHEMA_NAME = "OperatorResumePolicySummary"
OPERATOR_RESUME_POLICY_SUMMARY_SCHEMA_VERSION = "operator_resume_policy_summary_v1"
OPERATOR_REVIEW_QUEUE_SCHEMA_NAME = "OperatorReviewQueue"
OPERATOR_REVIEW_QUEUE_SCHEMA_VERSION = "operator_review_queue_v1"
OPERATOR_INTERVENTION_SUMMARY_SCHEMA_NAME = "OperatorInterventionSummary"
OPERATOR_INTERVENTION_SUMMARY_SCHEMA_VERSION = "operator_intervention_summary_v1"
OPERATOR_PENDING_DECISIONS_SCHEMA_NAME = "OperatorPendingDecisions"
LOGGER = logging.getLogger(__name__)
_SEEN_JSON_LOAD_WARNINGS: set[str] = set()
OPERATOR_PENDING_DECISIONS_SCHEMA_VERSION = "operator_pending_decisions_v1"
OPERATOR_REVIEW_REASON_SCHEMA_NAME = "OperatorReviewReason"
OPERATOR_REVIEW_REASON_SCHEMA_VERSION = "operator_review_reason_v1"
OPERATOR_INTERVENTION_OPTIONS_SCHEMA_NAME = "OperatorInterventionOptions"
OPERATOR_INTERVENTION_OPTIONS_SCHEMA_VERSION = "operator_intervention_options_v1"
OPERATOR_REVIEW_DECISION_SCHEMA_NAME = "OperatorReviewDecision"
OPERATOR_REVIEW_DECISION_SCHEMA_VERSION = "operator_review_decision_v1"
OPERATOR_REVIEW_ACTION_EXECUTION_SCHEMA_NAME = "OperatorReviewActionExecution"
OPERATOR_REVIEW_ACTION_EXECUTION_SCHEMA_VERSION = (
    "operator_review_action_execution_v1"
)
OPERATOR_REVIEW_RESOLUTION_SCHEMA_NAME = "OperatorReviewResolution"
OPERATOR_REVIEW_RESOLUTION_SCHEMA_VERSION = "operator_review_resolution_v1"
CONTROLLER_DELEGATION_CONTRACT_SCHEMA_NAME = "ControllerDelegationContract"
CONTROLLER_DELEGATION_CONTRACT_SCHEMA_VERSION = "controller_delegation_contract_v1"
CONTROLLER_CHILD_REGISTRY_SCHEMA_NAME = "ControllerChildRegistry"
CONTROLLER_CHILD_REGISTRY_SCHEMA_VERSION = "controller_child_registry_v1"
CONTROLLER_RESOURCE_LEASE_SCHEMA_NAME = "ControllerResourceLease"
CONTROLLER_RESOURCE_LEASE_SCHEMA_VERSION = "controller_resource_lease_v1"
CONTROLLER_DELEGATION_STATE_SCHEMA_NAME = "ControllerDelegationState"
CONTROLLER_DELEGATION_STATE_SCHEMA_VERSION = "controller_delegation_state_v1"
CHILD_AUTHORITY_SCOPE_SCHEMA_NAME = "ChildAuthorityScope"
CHILD_AUTHORITY_SCOPE_SCHEMA_VERSION = "child_authority_scope_v1"
CHILD_STOP_CONDITION_SCHEMA_NAME = "ChildStopCondition"
CHILD_STOP_CONDITION_SCHEMA_VERSION = "child_stop_condition_v1"
CHILD_RETURN_CONTRACT_SCHEMA_NAME = "ChildReturnContract"
CHILD_RETURN_CONTRACT_SCHEMA_VERSION = "child_return_contract_v1"
VERIFIER_CHECKLIST_SCHEMA_NAME = "VerifierChecklist"
VERIFIER_CHECKLIST_SCHEMA_VERSION = "verifier_checklist_v1"
VERIFIER_ADOPTION_READINESS_SCHEMA_NAME = "VerifierAdoptionReadiness"
VERIFIER_ADOPTION_READINESS_SCHEMA_VERSION = "verifier_adoption_readiness_v1"
VERIFIER_INTEGRITY_SUMMARY_SCHEMA_NAME = "VerifierIntegritySummary"
VERIFIER_INTEGRITY_SUMMARY_SCHEMA_VERSION = "verifier_integrity_summary_v1"
CHILD_BUDGET_STATE_SCHEMA_NAME = "ChildBudgetState"
CHILD_BUDGET_STATE_SCHEMA_VERSION = "child_budget_state_v1"
CHILD_TERMINATION_SUMMARY_SCHEMA_NAME = "ChildTerminationSummary"
CHILD_TERMINATION_SUMMARY_SCHEMA_VERSION = "child_termination_summary_v1"
CONTROLLER_CHILD_TASK_ASSIGNMENT_SCHEMA_NAME = "ControllerChildTaskAssignment"
CONTROLLER_CHILD_TASK_ASSIGNMENT_SCHEMA_VERSION = "controller_child_task_assignment_v1"
CHILD_TASK_RESULT_SCHEMA_NAME = "ChildTaskResult"
CHILD_TASK_RESULT_SCHEMA_VERSION = "child_task_result_v1"
CHILD_ARTIFACT_BUNDLE_SCHEMA_NAME = "ChildArtifactBundle"
CHILD_ARTIFACT_BUNDLE_SCHEMA_VERSION = "child_artifact_bundle_v1"
CONTROLLER_CHILD_RETURN_SUMMARY_SCHEMA_NAME = "ControllerChildReturnSummary"
CONTROLLER_CHILD_RETURN_SUMMARY_SCHEMA_VERSION = "controller_child_return_summary_v1"
CONTROLLER_CHILD_ADOPTION_DECISION_SCHEMA_NAME = "ControllerChildAdoptionDecision"
CONTROLLER_CHILD_ADOPTION_DECISION_SCHEMA_VERSION = (
    "controller_child_adoption_decision_v1"
)
CONTROLLER_CHILD_REVIEW_SCHEMA_NAME = "ControllerChildReview"
CONTROLLER_CHILD_REVIEW_SCHEMA_VERSION = "controller_child_review_v1"
CONTROLLER_DELEGATION_DECISION_SCHEMA_NAME = "ControllerDelegationDecision"
CONTROLLER_DELEGATION_DECISION_SCHEMA_VERSION = "controller_delegation_decision_v1"
CONTROLLER_CHILD_ADOPTION_SUMMARY_SCHEMA_NAME = "ControllerChildAdoptionSummary"
CONTROLLER_CHILD_ADOPTION_SUMMARY_SCHEMA_VERSION = (
    "controller_child_adoption_summary_v1"
)
CONTROLLER_LIBRARIAN_MISSION_IMPROVEMENT_SCHEMA_NAME = (
    "ControllerLibrarianMissionImprovement"
)
CONTROLLER_LIBRARIAN_MISSION_IMPROVEMENT_SCHEMA_VERSION = (
    "controller_librarian_mission_improvement_v1"
)
CONTROLLER_VERIFIER_MISSION_IMPROVEMENT_SCHEMA_NAME = (
    "ControllerVerifierMissionImprovement"
)
CONTROLLER_VERIFIER_MISSION_IMPROVEMENT_SCHEMA_VERSION = (
    "controller_verifier_mission_improvement_v1"
)
CONTROLLER_SEQUENTIAL_DELEGATION_WORKFLOW_SCHEMA_NAME = (
    "ControllerSequentialDelegationWorkflow"
)
CONTROLLER_SEQUENTIAL_DELEGATION_WORKFLOW_SCHEMA_VERSION = (
    "controller_sequential_delegation_workflow_v1"
)
CONTROLLER_MISSION_DELEGATION_PLAN_SCHEMA_NAME = "ControllerMissionDelegationPlan"
CONTROLLER_MISSION_DELEGATION_PLAN_SCHEMA_VERSION = (
    "controller_mission_delegation_plan_v1"
)
CONTROLLER_CHILD_ADMISSIBILITY_SCHEMA_NAME = "ControllerChildAdmissibility"
CONTROLLER_CHILD_ADMISSIBILITY_SCHEMA_VERSION = (
    "controller_child_admissibility_v1"
)
CONTROLLER_BLOCKED_DELEGATION_OPTIONS_SCHEMA_NAME = (
    "ControllerBlockedDelegationOptions"
)
CONTROLLER_BLOCKED_DELEGATION_OPTIONS_SCHEMA_VERSION = (
    "controller_blocked_delegation_options_v1"
)
CONTROLLER_TYPED_HANDOFF_CONTRACT_SCHEMA_NAME = "ControllerTypedHandoffContract"
CONTROLLER_TYPED_HANDOFF_CONTRACT_SCHEMA_VERSION = (
    "controller_typed_handoff_contract_v1"
)
CONTROLLER_DELEGATION_OUTCOME_SCHEMA_NAME = "ControllerDelegationOutcome"
CONTROLLER_DELEGATION_OUTCOME_SCHEMA_VERSION = (
    "controller_delegation_outcome_v1"
)
CONTROLLER_DELEGATION_PATH_HISTORY_SCHEMA_NAME = "ControllerDelegationPathHistory"
CONTROLLER_DELEGATION_PATH_HISTORY_SCHEMA_VERSION = (
    "controller_delegation_path_history_v1"
)
CONTROLLER_PATH_SELECTION_EVIDENCE_SCHEMA_NAME = "ControllerPathSelectionEvidence"
CONTROLLER_PATH_SELECTION_EVIDENCE_SCHEMA_VERSION = (
    "controller_path_selection_evidence_v1"
)
CONTROLLER_RECOMMENDATION_SUPPORT_SCHEMA_NAME = "ControllerRecommendationSupport"
CONTROLLER_RECOMMENDATION_SUPPORT_SCHEMA_VERSION = (
    "controller_recommendation_support_v1"
)
CONTROLLER_RECOMMENDATION_AUDIT_SCHEMA_NAME = "ControllerRecommendationAudit"
CONTROLLER_RECOMMENDATION_AUDIT_SCHEMA_VERSION = (
    "controller_recommendation_audit_v1"
)
CONTROLLER_RECOMMENDATION_AUDIT_HISTORY_SCHEMA_NAME = (
    "ControllerRecommendationAuditHistory"
)
CONTROLLER_RECOMMENDATION_AUDIT_HISTORY_SCHEMA_VERSION = (
    "controller_recommendation_audit_history_v1"
)
CONTROLLER_RECOMMENDATION_CALIBRATION_SUMMARY_SCHEMA_NAME = (
    "ControllerRecommendationCalibrationSummary"
)
CONTROLLER_RECOMMENDATION_CALIBRATION_SUMMARY_SCHEMA_VERSION = (
    "controller_recommendation_calibration_summary_v1"
)
CONTROLLER_RECOMMENDATION_WINDOW_SCHEMA_NAME = "ControllerRecommendationWindow"
CONTROLLER_RECOMMENDATION_WINDOW_SCHEMA_VERSION = (
    "controller_recommendation_window_v1"
)
CONTROLLER_RECOMMENDATION_STABILITY_SCHEMA_NAME = (
    "ControllerRecommendationStability"
)
CONTROLLER_RECOMMENDATION_STABILITY_SCHEMA_VERSION = (
    "controller_recommendation_stability_v1"
)
CONTROLLER_RECOMMENDATION_STABILITY_HISTORY_SCHEMA_NAME = (
    "ControllerRecommendationStabilityHistory"
)
CONTROLLER_RECOMMENDATION_STABILITY_HISTORY_SCHEMA_VERSION = (
    "controller_recommendation_stability_history_v1"
)
CONTROLLER_RECOMMENDATION_GOVERNANCE_SCHEMA_NAME = (
    "ControllerRecommendationGovernance"
)
CONTROLLER_RECOMMENDATION_GOVERNANCE_SCHEMA_VERSION = (
    "controller_recommendation_governance_v1"
)
CONTROLLER_RECOMMENDATION_OVERRIDE_SCHEMA_NAME = (
    "ControllerRecommendationOverride"
)
CONTROLLER_RECOMMENDATION_OVERRIDE_SCHEMA_VERSION = (
    "controller_recommendation_override_v1"
)
CONTROLLER_RECOMMENDATION_OVERRIDE_HISTORY_SCHEMA_NAME = (
    "ControllerRecommendationOverrideHistory"
)
CONTROLLER_RECOMMENDATION_OVERRIDE_HISTORY_SCHEMA_VERSION = (
    "controller_recommendation_override_history_v1"
)
CONTROLLER_INTERVENTION_AUDIT_SCHEMA_NAME = "ControllerInterventionAudit"
CONTROLLER_INTERVENTION_AUDIT_SCHEMA_VERSION = (
    "controller_intervention_audit_v1"
)
CONTROLLER_INTERVENTION_AUDIT_HISTORY_SCHEMA_NAME = (
    "ControllerInterventionAuditHistory"
)
CONTROLLER_INTERVENTION_AUDIT_HISTORY_SCHEMA_VERSION = (
    "controller_intervention_audit_history_v1"
)
CONTROLLER_INTERVENTION_CALIBRATION_SUMMARY_SCHEMA_NAME = (
    "ControllerInterventionCalibrationSummary"
)
CONTROLLER_INTERVENTION_CALIBRATION_SUMMARY_SCHEMA_VERSION = (
    "controller_intervention_calibration_summary_v1"
)
CONTROLLER_INTERVENTION_PRUDENCE_SCHEMA_NAME = "ControllerInterventionPrudence"
CONTROLLER_INTERVENTION_PRUDENCE_SCHEMA_VERSION = (
    "controller_intervention_prudence_v1"
)
CONTROLLER_INTERVENTION_PRUDENCE_HISTORY_SCHEMA_NAME = (
    "ControllerInterventionPrudenceHistory"
)
CONTROLLER_INTERVENTION_PRUDENCE_HISTORY_SCHEMA_VERSION = (
    "controller_intervention_prudence_history_v1"
)
CONTROLLER_RECOMMENDATION_TRUST_SIGNAL_SCHEMA_NAME = (
    "ControllerRecommendationTrustSignal"
)
CONTROLLER_RECOMMENDATION_TRUST_SIGNAL_SCHEMA_VERSION = (
    "controller_recommendation_trust_signal_v1"
)
CONTROLLER_GOVERNANCE_SUMMARY_SCHEMA_NAME = "ControllerGovernanceSummary"
CONTROLLER_GOVERNANCE_SUMMARY_SCHEMA_VERSION = (
    "controller_governance_summary_v1"
)
CONTROLLER_GOVERNANCE_SUMMARY_HISTORY_SCHEMA_NAME = (
    "ControllerGovernanceSummaryHistory"
)
CONTROLLER_GOVERNANCE_SUMMARY_HISTORY_SCHEMA_VERSION = (
    "controller_governance_summary_history_v1"
)
CONTROLLER_RECOMMENDATION_STATE_SUMMARY_SCHEMA_NAME = (
    "ControllerRecommendationStateSummary"
)
CONTROLLER_RECOMMENDATION_STATE_SUMMARY_SCHEMA_VERSION = (
    "controller_recommendation_state_summary_v1"
)
CONTROLLER_GOVERNANCE_TREND_SCHEMA_NAME = "ControllerGovernanceTrend"
CONTROLLER_GOVERNANCE_TREND_SCHEMA_VERSION = "controller_governance_trend_v1"
CONTROLLER_GOVERNANCE_TREND_HISTORY_SCHEMA_NAME = (
    "ControllerGovernanceTrendHistory"
)
CONTROLLER_GOVERNANCE_TREND_HISTORY_SCHEMA_VERSION = (
    "controller_governance_trend_history_v1"
)
CONTROLLER_TEMPORAL_DRIFT_SUMMARY_SCHEMA_NAME = (
    "ControllerTemporalDriftSummary"
)
CONTROLLER_TEMPORAL_DRIFT_SUMMARY_SCHEMA_VERSION = (
    "controller_temporal_drift_summary_v1"
)
CONTROLLER_OPERATOR_GUIDANCE_SCHEMA_NAME = "ControllerOperatorGuidance"
CONTROLLER_OPERATOR_GUIDANCE_SCHEMA_VERSION = (
    "controller_operator_guidance_v1"
)
CONTROLLER_OPERATOR_GUIDANCE_HISTORY_SCHEMA_NAME = (
    "ControllerOperatorGuidanceHistory"
)
CONTROLLER_OPERATOR_GUIDANCE_HISTORY_SCHEMA_VERSION = (
    "controller_operator_guidance_history_v1"
)
CONTROLLER_ACTION_GUIDANCE_SUMMARY_SCHEMA_NAME = (
    "ControllerActionGuidanceSummary"
)
CONTROLLER_ACTION_GUIDANCE_SUMMARY_SCHEMA_VERSION = (
    "controller_action_guidance_summary_v1"
)
CONTROLLER_ACTION_READINESS_SCHEMA_NAME = "ControllerActionReadiness"
CONTROLLER_ACTION_READINESS_SCHEMA_VERSION = (
    "controller_action_readiness_v1"
)
CONTROLLER_ACTION_READINESS_HISTORY_SCHEMA_NAME = (
    "ControllerActionReadinessHistory"
)
CONTROLLER_ACTION_READINESS_HISTORY_SCHEMA_VERSION = (
    "controller_action_readiness_history_v1"
)
CONTROLLER_GUIDED_HANDOFF_SUMMARY_SCHEMA_NAME = (
    "ControllerGuidedHandoffSummary"
)
CONTROLLER_GUIDED_HANDOFF_SUMMARY_SCHEMA_VERSION = (
    "controller_guided_handoff_summary_v1"
)
CONTROLLER_OPERATOR_FLOW_SCHEMA_NAME = "ControllerOperatorFlow"
CONTROLLER_OPERATOR_FLOW_SCHEMA_VERSION = "controller_operator_flow_v1"
CONTROLLER_OPERATOR_FLOW_HISTORY_SCHEMA_NAME = "ControllerOperatorFlowHistory"
CONTROLLER_OPERATOR_FLOW_HISTORY_SCHEMA_VERSION = (
    "controller_operator_flow_history_v1"
)
CONTROLLER_DEMO_READINESS_SUMMARY_SCHEMA_NAME = (
    "ControllerDemoReadinessSummary"
)
CONTROLLER_DEMO_READINESS_SUMMARY_SCHEMA_VERSION = (
    "controller_demo_readiness_summary_v1"
)
CONTROLLER_DEMO_SCENARIO_SCHEMA_NAME = "ControllerDemoScenario"
CONTROLLER_DEMO_SCENARIO_SCHEMA_VERSION = "controller_demo_scenario_v1"
CONTROLLER_DEMO_SCENARIO_HISTORY_SCHEMA_NAME = (
    "ControllerDemoScenarioHistory"
)
CONTROLLER_DEMO_SCENARIO_HISTORY_SCHEMA_VERSION = (
    "controller_demo_scenario_history_v1"
)
CONTROLLER_DEMO_RUN_READINESS_SCHEMA_NAME = "ControllerDemoRunReadiness"
CONTROLLER_DEMO_RUN_READINESS_SCHEMA_VERSION = (
    "controller_demo_run_readiness_v1"
)
CONTROLLER_DEMO_OPERATOR_WALKTHROUGH_SCHEMA_NAME = (
    "ControllerDemoOperatorWalkthrough"
)
CONTROLLER_DEMO_OPERATOR_WALKTHROUGH_SCHEMA_VERSION = (
    "controller_demo_operator_walkthrough_v1"
)
CONTROLLER_DEMO_SUCCESS_RUBRIC_SCHEMA_NAME = "ControllerDemoSuccessRubric"
CONTROLLER_DEMO_SUCCESS_RUBRIC_SCHEMA_VERSION = (
    "controller_demo_success_rubric_v1"
)
CONTROLLER_DEMO_EXECUTION_SCHEMA_NAME = "ControllerDemoExecution"
CONTROLLER_DEMO_EXECUTION_SCHEMA_VERSION = "controller_demo_execution_v1"
CONTROLLER_DEMO_EXECUTION_HISTORY_SCHEMA_NAME = (
    "ControllerDemoExecutionHistory"
)
CONTROLLER_DEMO_EXECUTION_HISTORY_SCHEMA_VERSION = (
    "controller_demo_execution_history_v1"
)
CONTROLLER_DEMO_RESULT_SUMMARY_SCHEMA_NAME = "ControllerDemoResultSummary"
CONTROLLER_DEMO_RESULT_SUMMARY_SCHEMA_VERSION = (
    "controller_demo_result_summary_v1"
)
CONTROLLER_DEMO_OUTPUT_INVENTORY_SCHEMA_NAME = "ControllerDemoOutputInventory"
CONTROLLER_DEMO_OUTPUT_INVENTORY_SCHEMA_VERSION = (
    "controller_demo_output_inventory_v1"
)
CONTROLLER_DEMO_EVIDENCE_TRAIL_SCHEMA_NAME = "ControllerDemoEvidenceTrail"
CONTROLLER_DEMO_EVIDENCE_TRAIL_SCHEMA_VERSION = (
    "controller_demo_evidence_trail_v1"
)
CONTROLLER_DEMO_OUTPUT_COMPLETION_SCHEMA_NAME = "ControllerDemoOutputCompletion"
CONTROLLER_DEMO_OUTPUT_COMPLETION_SCHEMA_VERSION = (
    "controller_demo_output_completion_v1"
)
CONTROLLER_DEMO_OUTPUT_COMPLETION_HISTORY_SCHEMA_NAME = (
    "ControllerDemoOutputCompletionHistory"
)
CONTROLLER_DEMO_OUTPUT_COMPLETION_HISTORY_SCHEMA_VERSION = (
    "controller_demo_output_completion_history_v1"
)
CONTROLLER_DEMO_REVIEWABLE_ARTIFACTS_SCHEMA_NAME = (
    "ControllerDemoReviewableArtifacts"
)
CONTROLLER_DEMO_REVIEWABLE_ARTIFACTS_SCHEMA_VERSION = (
    "controller_demo_reviewable_artifacts_v1"
)
CONTROLLER_DEMO_COMPLETION_SUMMARY_SCHEMA_NAME = "ControllerDemoCompletionSummary"
CONTROLLER_DEMO_COMPLETION_SUMMARY_SCHEMA_VERSION = (
    "controller_demo_completion_summary_v1"
)
CONTROLLER_TRUSTED_DEMO_SCENARIO_SCHEMA_NAME = "ControllerTrustedDemoScenario"
CONTROLLER_TRUSTED_DEMO_SCENARIO_SCHEMA_VERSION = (
    "controller_trusted_demo_scenario_v1"
)
CONTROLLER_TRUSTED_DEMO_SCENARIO_HISTORY_SCHEMA_NAME = (
    "ControllerTrustedDemoScenarioHistory"
)
CONTROLLER_TRUSTED_DEMO_SCENARIO_HISTORY_SCHEMA_VERSION = (
    "controller_trusted_demo_scenario_history_v1"
)
CONTROLLER_TRUSTED_DEMO_DIRECTIVE_SCHEMA_NAME = "ControllerTrustedDemoDirective"
CONTROLLER_TRUSTED_DEMO_DIRECTIVE_SCHEMA_VERSION = (
    "controller_trusted_demo_directive_v1"
)
CONTROLLER_TRUSTED_DEMO_SUCCESS_RUBRIC_SCHEMA_NAME = (
    "ControllerTrustedDemoSuccessRubric"
)
CONTROLLER_TRUSTED_DEMO_SUCCESS_RUBRIC_SCHEMA_VERSION = (
    "controller_trusted_demo_success_rubric_v1"
)
CONTROLLER_TRUSTED_DEMO_SKILL_TARGET_SCHEMA_NAME = (
    "ControllerTrustedDemoSkillTarget"
)
CONTROLLER_TRUSTED_DEMO_SKILL_TARGET_SCHEMA_VERSION = (
    "controller_trusted_demo_skill_target_v1"
)
CONTROLLER_TRUSTED_DEMO_SELECTION_RATIONALE_SCHEMA_NAME = (
    "ControllerTrustedDemoSelectionRationale"
)
CONTROLLER_TRUSTED_DEMO_SELECTION_RATIONALE_SCHEMA_VERSION = (
    "controller_trusted_demo_selection_rationale_v1"
)
CONTROLLER_TRUSTED_DEMO_LOCAL_FIRST_ANALYSIS_SCHEMA_NAME = (
    "ControllerTrustedDemoLocalFirstAnalysis"
)
CONTROLLER_TRUSTED_DEMO_LOCAL_FIRST_ANALYSIS_SCHEMA_VERSION = (
    "controller_trusted_demo_local_first_analysis_v1"
)
CONTROLLER_TRUSTED_DEMO_KNOWLEDGE_GAP_SCHEMA_NAME = (
    "ControllerTrustedDemoKnowledgeGap"
)
CONTROLLER_TRUSTED_DEMO_KNOWLEDGE_GAP_SCHEMA_VERSION = (
    "controller_trusted_demo_knowledge_gap_v1"
)
CONTROLLER_TRUSTED_DEMO_KNOWLEDGE_GAP_HISTORY_SCHEMA_NAME = (
    "ControllerTrustedDemoKnowledgeGapHistory"
)
CONTROLLER_TRUSTED_DEMO_KNOWLEDGE_GAP_HISTORY_SCHEMA_VERSION = (
    "controller_trusted_demo_knowledge_gap_history_v1"
)
CONTROLLER_TRUSTED_DEMO_REQUEST_SCHEMA_NAME = "ControllerTrustedDemoRequest"
CONTROLLER_TRUSTED_DEMO_REQUEST_SCHEMA_VERSION = (
    "controller_trusted_demo_request_v1"
)
CONTROLLER_TRUSTED_DEMO_REQUEST_HISTORY_SCHEMA_NAME = (
    "ControllerTrustedDemoRequestHistory"
)
CONTROLLER_TRUSTED_DEMO_REQUEST_HISTORY_SCHEMA_VERSION = (
    "controller_trusted_demo_request_history_v1"
)
CONTROLLER_TRUSTED_DEMO_RESPONSE_SUMMARY_SCHEMA_NAME = (
    "ControllerTrustedDemoResponseSummary"
)
CONTROLLER_TRUSTED_DEMO_RESPONSE_SUMMARY_SCHEMA_VERSION = (
    "controller_trusted_demo_response_summary_v1"
)
CONTROLLER_TRUSTED_DEMO_INCORPORATION_SCHEMA_NAME = (
    "ControllerTrustedDemoIncorporation"
)
CONTROLLER_TRUSTED_DEMO_INCORPORATION_SCHEMA_VERSION = (
    "controller_trusted_demo_incorporation_v1"
)
CONTROLLER_TRUSTED_DEMO_GROWTH_ARTIFACT_SCHEMA_NAME = (
    "ControllerTrustedDemoGrowthArtifact"
)
CONTROLLER_TRUSTED_DEMO_GROWTH_ARTIFACT_SCHEMA_VERSION = (
    "controller_trusted_demo_growth_artifact_v1"
)
CONTROLLER_TRUSTED_DEMO_GROWTH_ARTIFACT_HISTORY_SCHEMA_NAME = (
    "ControllerTrustedDemoGrowthArtifactHistory"
)
CONTROLLER_TRUSTED_DEMO_GROWTH_ARTIFACT_HISTORY_SCHEMA_VERSION = (
    "controller_trusted_demo_growth_artifact_history_v1"
)
CONTROLLER_TRUSTED_DEMO_DELTA_SUMMARY_SCHEMA_NAME = (
    "ControllerTrustedDemoDeltaSummary"
)
CONTROLLER_TRUSTED_DEMO_DELTA_SUMMARY_SCHEMA_VERSION = (
    "controller_trusted_demo_delta_summary_v1"
)
CONTROLLER_TRUSTED_LIVE_CONNECTIVITY_SCHEMA_NAME = (
    "ControllerTrustedLiveConnectivity"
)
CONTROLLER_TRUSTED_LIVE_CONNECTIVITY_SCHEMA_VERSION = (
    "controller_trusted_live_connectivity_v1"
)
CONTROLLER_TRUSTED_LIVE_CONNECTIVITY_HISTORY_SCHEMA_NAME = (
    "ControllerTrustedLiveConnectivityHistory"
)
CONTROLLER_TRUSTED_LIVE_CONNECTIVITY_HISTORY_SCHEMA_VERSION = (
    "controller_trusted_live_connectivity_history_v1"
)
CONTROLLER_TRUSTED_LIVE_REQUEST_SCHEMA_NAME = "ControllerTrustedLiveRequest"
CONTROLLER_TRUSTED_LIVE_REQUEST_SCHEMA_VERSION = (
    "controller_trusted_live_request_v1"
)
CONTROLLER_TRUSTED_LIVE_RESPONSE_SUMMARY_SCHEMA_NAME = (
    "ControllerTrustedLiveResponseSummary"
)
CONTROLLER_TRUSTED_LIVE_RESPONSE_SUMMARY_SCHEMA_VERSION = (
    "controller_trusted_live_response_summary_v1"
)
CONTROLLER_TRUSTED_LIVE_EVIDENCE_RECEIPT_SCHEMA_NAME = (
    "ControllerTrustedLiveEvidenceReceipt"
)
CONTROLLER_TRUSTED_LIVE_EVIDENCE_RECEIPT_SCHEMA_VERSION = (
    "controller_trusted_live_evidence_receipt_v1"
)
CONTROLLER_TRUSTED_LIVE_VALIDATION_SUMMARY_SCHEMA_NAME = (
    "ControllerTrustedLiveValidationSummary"
)
CONTROLLER_TRUSTED_LIVE_VALIDATION_SUMMARY_SCHEMA_VERSION = (
    "controller_trusted_live_validation_summary_v1"
)
CONTROLLER_TRUSTED_DEMO_LIVE_REQUEST_SCHEMA_NAME = (
    "ControllerTrustedDemoLiveRequest"
)
CONTROLLER_TRUSTED_DEMO_LIVE_REQUEST_SCHEMA_VERSION = (
    "controller_trusted_demo_live_request_v1"
)
CONTROLLER_TRUSTED_DEMO_LIVE_REQUEST_HISTORY_SCHEMA_NAME = (
    "ControllerTrustedDemoLiveRequestHistory"
)
CONTROLLER_TRUSTED_DEMO_LIVE_REQUEST_HISTORY_SCHEMA_VERSION = (
    "controller_trusted_demo_live_request_history_v1"
)
CONTROLLER_TRUSTED_DEMO_LIVE_RESPONSE_SUMMARY_SCHEMA_NAME = (
    "ControllerTrustedDemoLiveResponseSummary"
)
CONTROLLER_TRUSTED_DEMO_LIVE_RESPONSE_SUMMARY_SCHEMA_VERSION = (
    "controller_trusted_demo_live_response_summary_v1"
)
CONTROLLER_TRUSTED_DEMO_LIVE_EVIDENCE_RECEIPT_SCHEMA_NAME = (
    "ControllerTrustedDemoLiveEvidenceReceipt"
)
CONTROLLER_TRUSTED_DEMO_LIVE_EVIDENCE_RECEIPT_SCHEMA_VERSION = (
    "controller_trusted_demo_live_evidence_receipt_v1"
)
CONTROLLER_TRUSTED_DEMO_LIVE_INCORPORATION_SCHEMA_NAME = (
    "ControllerTrustedDemoLiveIncorporation"
)
CONTROLLER_TRUSTED_DEMO_LIVE_INCORPORATION_SCHEMA_VERSION = (
    "controller_trusted_demo_live_incorporation_v1"
)
CONTROLLER_TRUSTED_DEMO_GROWTH_ARTIFACT_UPDATE_SCHEMA_NAME = (
    "ControllerTrustedDemoGrowthArtifactUpdate"
)
CONTROLLER_TRUSTED_DEMO_GROWTH_ARTIFACT_UPDATE_SCHEMA_VERSION = (
    "controller_trusted_demo_growth_artifact_update_v1"
)
CONTROLLER_TRUSTED_DEMO_GROWTH_ARTIFACT_UPDATE_HISTORY_SCHEMA_NAME = (
    "ControllerTrustedDemoGrowthArtifactUpdateHistory"
)
CONTROLLER_TRUSTED_DEMO_GROWTH_ARTIFACT_UPDATE_HISTORY_SCHEMA_VERSION = (
    "controller_trusted_demo_growth_artifact_update_history_v1"
)
CONTROLLER_TRUSTED_DEMO_BEFORE_AFTER_DELTA_SCHEMA_NAME = (
    "ControllerTrustedDemoBeforeAfterDelta"
)
CONTROLLER_TRUSTED_DEMO_BEFORE_AFTER_DELTA_SCHEMA_VERSION = (
    "controller_trusted_demo_before_after_delta_v1"
)
CONTROLLER_DEMO_STORYLINE_SCHEMA_NAME = "ControllerDemoStoryline"
CONTROLLER_DEMO_STORYLINE_SCHEMA_VERSION = "controller_demo_storyline_v1"
CONTROLLER_DEMO_STORYLINE_HISTORY_SCHEMA_NAME = (
    "ControllerDemoStorylineHistory"
)
CONTROLLER_DEMO_STORYLINE_HISTORY_SCHEMA_VERSION = (
    "controller_demo_storyline_history_v1"
)
CONTROLLER_DEMO_PRESENTATION_SUMMARY_SCHEMA_NAME = (
    "ControllerDemoPresentationSummary"
)
CONTROLLER_DEMO_PRESENTATION_SUMMARY_SCHEMA_VERSION = (
    "controller_demo_presentation_summary_v1"
)
CONTROLLER_DEMO_NARRATION_GUIDE_SCHEMA_NAME = "ControllerDemoNarrationGuide"
CONTROLLER_DEMO_NARRATION_GUIDE_SCHEMA_VERSION = (
    "controller_demo_narration_guide_v1"
)
CONTROLLER_DEMO_REVIEW_READINESS_SCHEMA_NAME = "ControllerDemoReviewReadiness"
CONTROLLER_DEMO_REVIEW_READINESS_SCHEMA_VERSION = (
    "controller_demo_review_readiness_v1"
)
CONTROLLER_DEMO_RUNBOOK_SCHEMA_NAME = "ControllerDemoRunbook"
CONTROLLER_DEMO_RUNBOOK_SCHEMA_VERSION = "controller_demo_runbook_v1"
CONTROLLER_DEMO_RUNBOOK_HISTORY_SCHEMA_NAME = "ControllerDemoRunbookHistory"
CONTROLLER_DEMO_RUNBOOK_HISTORY_SCHEMA_VERSION = (
    "controller_demo_runbook_history_v1"
)
CONTROLLER_DEMO_FACILITATOR_CHECKLIST_SCHEMA_NAME = (
    "ControllerDemoFacilitatorChecklist"
)
CONTROLLER_DEMO_FACILITATOR_CHECKLIST_SCHEMA_VERSION = (
    "controller_demo_facilitator_checklist_v1"
)
CONTROLLER_DEMO_CHECKPOINT_SUMMARY_SCHEMA_NAME = (
    "ControllerDemoCheckpointSummary"
)
CONTROLLER_DEMO_CHECKPOINT_SUMMARY_SCHEMA_VERSION = (
    "controller_demo_checkpoint_summary_v1"
)
CONTROLLER_DEMO_ACCEPTANCE_RUBRIC_SCHEMA_NAME = (
    "ControllerDemoAcceptanceRubric"
)
CONTROLLER_DEMO_ACCEPTANCE_RUBRIC_SCHEMA_VERSION = (
    "controller_demo_acceptance_rubric_v1"
)
CONTROLLER_DEMO_PACKAGED_COMPLETENESS_SCHEMA_NAME = (
    "ControllerDemoPackagedCompleteness"
)
CONTROLLER_DEMO_PACKAGED_COMPLETENESS_SCHEMA_VERSION = (
    "controller_demo_packaged_completeness_v1"
)
CONTROLLER_DEMO_PACKAGED_COMPLETENESS_HISTORY_SCHEMA_NAME = (
    "ControllerDemoPackagedCompletenessHistory"
)
CONTROLLER_DEMO_PACKAGED_COMPLETENESS_HISTORY_SCHEMA_VERSION = (
    "controller_demo_packaged_completeness_history_v1"
)
CONTROLLER_DEMO_PACKAGED_ARTIFACT_INVENTORY_SCHEMA_NAME = (
    "ControllerDemoPackagedArtifactInventory"
)
CONTROLLER_DEMO_PACKAGED_ARTIFACT_INVENTORY_SCHEMA_VERSION = (
    "controller_demo_packaged_artifact_inventory_v1"
)
CONTROLLER_DEMO_PACKAGED_CHECKPOINT_CLOSURE_SCHEMA_NAME = (
    "ControllerDemoPackagedCheckpointClosure"
)
CONTROLLER_DEMO_PACKAGED_CHECKPOINT_CLOSURE_SCHEMA_VERSION = (
    "controller_demo_packaged_checkpoint_closure_v1"
)
CONTROLLER_DEMO_PACKAGED_RUBRIC_JUSTIFICATION_SCHEMA_NAME = (
    "ControllerDemoPackagedRubricJustification"
)
CONTROLLER_DEMO_PACKAGED_RUBRIC_JUSTIFICATION_SCHEMA_VERSION = (
    "controller_demo_packaged_rubric_justification_v1"
)
CONTROLLER_DEMO_PRESENTER_HANDOFF_SCHEMA_NAME = (
    "ControllerDemoPresenterHandoff"
)
CONTROLLER_DEMO_PRESENTER_HANDOFF_SCHEMA_VERSION = (
    "controller_demo_presenter_handoff_v1"
)
CONTROLLER_DEMO_PRESENTER_HANDOFF_HISTORY_SCHEMA_NAME = (
    "ControllerDemoPresenterHandoffHistory"
)
CONTROLLER_DEMO_PRESENTER_HANDOFF_HISTORY_SCHEMA_VERSION = (
    "controller_demo_presenter_handoff_history_v1"
)
CONTROLLER_DEMO_QUICKSTART_SHEET_SCHEMA_NAME = (
    "ControllerDemoQuickstartSheet"
)
CONTROLLER_DEMO_QUICKSTART_SHEET_SCHEMA_VERSION = (
    "controller_demo_quickstart_sheet_v1"
)
CONTROLLER_DEMO_AUDIENCE_SUMMARY_SCHEMA_NAME = (
    "ControllerDemoAudienceSummary"
)
CONTROLLER_DEMO_AUDIENCE_SUMMARY_SCHEMA_VERSION = (
    "controller_demo_audience_summary_v1"
)
CONTROLLER_DEMO_PRE_DEMO_SANITY_SCHEMA_NAME = (
    "ControllerDemoPreDemoSanity"
)
CONTROLLER_DEMO_PRE_DEMO_SANITY_SCHEMA_VERSION = (
    "controller_demo_pre_demo_sanity_v1"
)
CONTROLLER_DEMO_POST_DEMO_REVIEW_SCHEMA_NAME = (
    "ControllerDemoPostDemoReview"
)
CONTROLLER_DEMO_POST_DEMO_REVIEW_SCHEMA_VERSION = (
    "controller_demo_post_demo_review_v1"
)
CONTROLLER_DEMO_SHORT_FORM_SCHEMA_NAME = "ControllerDemoShortForm"
CONTROLLER_DEMO_SHORT_FORM_SCHEMA_VERSION = "controller_demo_short_form_v1"
CONTROLLER_DEMO_SHORT_FORM_HISTORY_SCHEMA_NAME = (
    "ControllerDemoShortFormHistory"
)
CONTROLLER_DEMO_SHORT_FORM_HISTORY_SCHEMA_VERSION = (
    "controller_demo_short_form_history_v1"
)
CONTROLLER_DEMO_FULL_WALKTHROUGH_SCHEMA_NAME = (
    "ControllerDemoFullWalkthrough"
)
CONTROLLER_DEMO_FULL_WALKTHROUGH_SCHEMA_VERSION = (
    "controller_demo_full_walkthrough_v1"
)
CONTROLLER_DEMO_MUST_SHOW_CHECKPOINTS_SCHEMA_NAME = (
    "ControllerDemoMustShowCheckpoints"
)
CONTROLLER_DEMO_MUST_SHOW_CHECKPOINTS_SCHEMA_VERSION = (
    "controller_demo_must_show_checkpoints_v1"
)
CONTROLLER_DEMO_AUDIENCE_MODE_OPTIMIZATION_SCHEMA_NAME = (
    "ControllerDemoAudienceModeOptimization"
)
CONTROLLER_DEMO_AUDIENCE_MODE_OPTIMIZATION_SCHEMA_VERSION = (
    "controller_demo_audience_mode_optimization_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_SCHEMA_NAME = "ControllerRealWorkBenchmark"
CONTROLLER_REAL_WORK_BENCHMARK_SCHEMA_VERSION = (
    "controller_real_work_benchmark_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_HISTORY_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkHistory"
)
CONTROLLER_REAL_WORK_BENCHMARK_HISTORY_SCHEMA_VERSION = (
    "controller_real_work_benchmark_history_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_DIRECTIVE_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkDirective"
)
CONTROLLER_REAL_WORK_BENCHMARK_DIRECTIVE_SCHEMA_VERSION = (
    "controller_real_work_benchmark_directive_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_OUTPUT_CONTRACT_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkOutputContract"
)
CONTROLLER_REAL_WORK_BENCHMARK_OUTPUT_CONTRACT_SCHEMA_VERSION = (
    "controller_real_work_benchmark_output_contract_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_SUCCESS_RUBRIC_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkSuccessRubric"
)
CONTROLLER_REAL_WORK_BENCHMARK_SUCCESS_RUBRIC_SCHEMA_VERSION = (
    "controller_real_work_benchmark_success_rubric_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_OPERATOR_VALUE_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkOperatorValue"
)
CONTROLLER_REAL_WORK_BENCHMARK_OPERATOR_VALUE_SCHEMA_VERSION = (
    "controller_real_work_benchmark_operator_value_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_SELECTION_RATIONALE_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkSelectionRationale"
)
CONTROLLER_REAL_WORK_BENCHMARK_SELECTION_RATIONALE_SCHEMA_VERSION = (
    "controller_real_work_benchmark_selection_rationale_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_EXECUTION_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkExecution"
)
CONTROLLER_REAL_WORK_BENCHMARK_EXECUTION_SCHEMA_VERSION = (
    "controller_real_work_benchmark_execution_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_EXECUTION_HISTORY_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkExecutionHistory"
)
CONTROLLER_REAL_WORK_BENCHMARK_EXECUTION_HISTORY_SCHEMA_VERSION = (
    "controller_real_work_benchmark_execution_history_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_RESULT_SUMMARY_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkResultSummary"
)
CONTROLLER_REAL_WORK_BENCHMARK_RESULT_SUMMARY_SCHEMA_VERSION = (
    "controller_real_work_benchmark_result_summary_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_OUTPUT_INVENTORY_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkOutputInventory"
)
CONTROLLER_REAL_WORK_BENCHMARK_OUTPUT_INVENTORY_SCHEMA_VERSION = (
    "controller_real_work_benchmark_output_inventory_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_RUBRIC_RESULT_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkRubricResult"
)
CONTROLLER_REAL_WORK_BENCHMARK_RUBRIC_RESULT_SCHEMA_VERSION = (
    "controller_real_work_benchmark_rubric_result_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_CLOSURE_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkClosure"
)
CONTROLLER_REAL_WORK_BENCHMARK_CLOSURE_SCHEMA_VERSION = (
    "controller_real_work_benchmark_closure_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_CLOSURE_HISTORY_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkClosureHistory"
)
CONTROLLER_REAL_WORK_BENCHMARK_CLOSURE_HISTORY_SCHEMA_VERSION = (
    "controller_real_work_benchmark_closure_history_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_REPEATABILITY_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkRepeatability"
)
CONTROLLER_REAL_WORK_BENCHMARK_REPEATABILITY_SCHEMA_VERSION = (
    "controller_real_work_benchmark_repeatability_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_REPEATABILITY_HISTORY_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkRepeatabilityHistory"
)
CONTROLLER_REAL_WORK_BENCHMARK_REPEATABILITY_HISTORY_SCHEMA_VERSION = (
    "controller_real_work_benchmark_repeatability_history_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_PROMOTION_READINESS_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkPromotionReadiness"
)
CONTROLLER_REAL_WORK_BENCHMARK_PROMOTION_READINESS_SCHEMA_VERSION = (
    "controller_real_work_benchmark_promotion_readiness_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_UNRESOLVED_BUNDLE_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkUnresolvedBundle"
)
CONTROLLER_REAL_WORK_BENCHMARK_UNRESOLVED_BUNDLE_SCHEMA_VERSION = (
    "controller_real_work_benchmark_unresolved_bundle_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_DELTA_FROM_RC46_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkDeltaFromRc46"
)
CONTROLLER_REAL_WORK_BENCHMARK_DELTA_FROM_RC46_SCHEMA_VERSION = (
    "controller_real_work_benchmark_delta_from_rc46_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_DECISION_PACKET_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkDecisionPacket"
)
CONTROLLER_REAL_WORK_BENCHMARK_DECISION_PACKET_SCHEMA_VERSION = (
    "controller_real_work_benchmark_decision_packet_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_DECISION_PACKET_HISTORY_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkDecisionPacketHistory"
)
CONTROLLER_REAL_WORK_BENCHMARK_DECISION_PACKET_HISTORY_SCHEMA_VERSION = (
    "controller_real_work_benchmark_decision_packet_history_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_PROMOTION_DECISION_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkPromotionDecision"
)
CONTROLLER_REAL_WORK_BENCHMARK_PROMOTION_DECISION_SCHEMA_VERSION = (
    "controller_real_work_benchmark_promotion_decision_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_REVIEW_GATE_PACKET_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkReviewGatePacket"
)
CONTROLLER_REAL_WORK_BENCHMARK_REVIEW_GATE_PACKET_SCHEMA_VERSION = (
    "controller_real_work_benchmark_review_gate_packet_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_FINAL_BLOCKER_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkFinalBlocker"
)
CONTROLLER_REAL_WORK_BENCHMARK_FINAL_BLOCKER_SCHEMA_VERSION = (
    "controller_real_work_benchmark_final_blocker_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_DECISION_RATIONALE_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkDecisionRationale"
)
CONTROLLER_REAL_WORK_BENCHMARK_DECISION_RATIONALE_SCHEMA_VERSION = (
    "controller_real_work_benchmark_decision_rationale_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_NEXT_ACTION_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkNextAction"
)
CONTROLLER_REAL_WORK_BENCHMARK_NEXT_ACTION_SCHEMA_VERSION = (
    "controller_real_work_benchmark_next_action_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_REVIEW_PACKET_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkReviewPacket"
)
CONTROLLER_REAL_WORK_BENCHMARK_REVIEW_PACKET_SCHEMA_VERSION = (
    "controller_real_work_benchmark_review_packet_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_REVIEW_PACKET_HISTORY_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkReviewPacketHistory"
)
CONTROLLER_REAL_WORK_BENCHMARK_REVIEW_PACKET_HISTORY_SCHEMA_VERSION = (
    "controller_real_work_benchmark_review_packet_history_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_OPERATOR_REVIEW_DECISION_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkOperatorReviewDecision"
)
CONTROLLER_REAL_WORK_BENCHMARK_OPERATOR_REVIEW_DECISION_SCHEMA_VERSION = (
    "controller_real_work_benchmark_operator_review_decision_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_PROMOTION_OUTCOME_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkPromotionOutcome"
)
CONTROLLER_REAL_WORK_BENCHMARK_PROMOTION_OUTCOME_SCHEMA_VERSION = (
    "controller_real_work_benchmark_promotion_outcome_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_OPERATOR_CONFIRMATION_STATE_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkOperatorConfirmationState"
)
CONTROLLER_REAL_WORK_BENCHMARK_OPERATOR_CONFIRMATION_STATE_SCHEMA_VERSION = (
    "controller_real_work_benchmark_operator_confirmation_state_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_REVIEW_EVIDENCE_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkReviewEvidence"
)
CONTROLLER_REAL_WORK_BENCHMARK_REVIEW_EVIDENCE_SCHEMA_VERSION = (
    "controller_real_work_benchmark_review_evidence_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_REVIEW_CHECKLIST_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkReviewChecklist"
)
CONTROLLER_REAL_WORK_BENCHMARK_REVIEW_CHECKLIST_SCHEMA_VERSION = (
    "controller_real_work_benchmark_review_checklist_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_REVIEW_CONFIRMATION_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkReviewConfirmation"
)
CONTROLLER_REAL_WORK_BENCHMARK_REVIEW_CONFIRMATION_SCHEMA_VERSION = (
    "controller_real_work_benchmark_review_confirmation_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_REVIEW_CONFIRMATION_HISTORY_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkReviewConfirmationHistory"
)
CONTROLLER_REAL_WORK_BENCHMARK_REVIEW_CONFIRMATION_HISTORY_SCHEMA_VERSION = (
    "controller_real_work_benchmark_review_confirmation_history_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_REVIEW_DECISION_SOURCE_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkReviewDecisionSource"
)
CONTROLLER_REAL_WORK_BENCHMARK_REVIEW_DECISION_SOURCE_SCHEMA_VERSION = (
    "controller_real_work_benchmark_review_decision_source_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_PROMOTION_OUTCOME_CONFIRMED_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkPromotionOutcomeConfirmed"
)
CONTROLLER_REAL_WORK_BENCHMARK_PROMOTION_OUTCOME_CONFIRMED_SCHEMA_VERSION = (
    "controller_real_work_benchmark_promotion_outcome_confirmed_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_REVIEW_RESOLUTION_SUMMARY_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkReviewResolutionSummary"
)
CONTROLLER_REAL_WORK_BENCHMARK_REVIEW_RESOLUTION_SUMMARY_SCHEMA_VERSION = (
    "controller_real_work_benchmark_review_resolution_summary_v1"
)
CONTROLLER_REAL_WORK_BENCHMARK_CONFIRMATION_GAP_SCHEMA_NAME = (
    "ControllerRealWorkBenchmarkConfirmationGap"
)
CONTROLLER_REAL_WORK_BENCHMARK_CONFIRMATION_GAP_SCHEMA_VERSION = (
    "controller_real_work_benchmark_confirmation_gap_v1"
)

SUPPORTED_SOURCE_KINDS = {
    "local_path",
    "local_bundle",
    "network_api",
}
SUPPORTED_CREDENTIAL_STRATEGIES = {
    "none",
    "env_var",
    "local_secret_store",
}
EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION = "bootstrap_only_initialization"
EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING = "bounded_active_workspace_coding"
SUPPORTED_EXECUTION_PROFILES = {
    EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION,
    EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING,
}
GOVERNED_EXECUTION_MODE_SINGLE_CYCLE = "single_cycle"
GOVERNED_EXECUTION_MODE_MULTI_CYCLE = "multi_cycle"
SUPPORTED_GOVERNED_EXECUTION_MODES = {
    GOVERNED_EXECUTION_MODE_SINGLE_CYCLE,
    GOVERNED_EXECUTION_MODE_MULTI_CYCLE,
}
DEFAULT_GOVERNED_EXECUTION_MAX_CYCLES_SINGLE = 1
DEFAULT_GOVERNED_EXECUTION_MAX_CYCLES_MULTI = 2
MAX_GOVERNED_EXECUTION_CYCLES_PER_INVOCATION = 4
ACTIVE_WORKSPACE_ROOT_NAME = "novali-active_workspace"
ACTIVE_WORKSPACE_LAYOUT_DIRECTORIES = (
    "src",
    "tests",
    "docs",
    "artifacts",
    "plans",
)
TRUSTED_SOURCE_OPERATOR_ALLOWED_AGGRESSIVENESS_POSTURES = {
    "conservative",
    "normal_bounded",
    "permissive_bounded",
}
TRUSTED_SOURCE_OPERATOR_ALLOWED_EXTERNAL_REQUERY_MODES = {
    "constrained",
    "enabled",
    "disabled",
    "review_first",
}
OPERATOR_RUN_PRESET_LONG_RUN_LOW_TOUCH = "long_run_low_touch"
OPERATOR_RUN_PRESET_FOCUSED_TIGHTER_CONTROL = "focused_tighter_control"
OPERATOR_RUN_PRESET_CUSTOM_MANUAL = "custom_manual_policy"
SUPPORTED_OPERATOR_RUN_PRESET_IDS = {
    OPERATOR_RUN_PRESET_LONG_RUN_LOW_TOUCH,
    OPERATOR_RUN_PRESET_FOCUSED_TIGHTER_CONTROL,
}
DEFAULT_OPERATOR_RUN_PRESET_ID = OPERATOR_RUN_PRESET_LONG_RUN_LOW_TOUCH


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def _stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _session_payload_without_hashes(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in dict(payload).items()
        if key != "frozen_hashes"
    }


def default_operator_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        root = Path(local_app_data) / "NOVALI" / "operator_state"
    else:
        root = Path.home() / ".novali_operator"
    root.mkdir(parents=True, exist_ok=True)
    return root


def operator_runtime_constraints_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "operator_runtime_constraints_latest.json"


def trusted_source_bindings_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "trusted_source_bindings_latest.json"


def trusted_source_secrets_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "trusted_source_secrets.local.json"


def trusted_source_credential_status_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "trusted_source_credential_status_latest.json"


def trusted_source_provider_status_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "trusted_source_provider_status_latest.json"


def trusted_source_handshake_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "trusted_source_handshake_latest.json"


def trusted_source_session_contract_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "trusted_source_session_contract_latest.json"


def trusted_source_request_contract_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "trusted_source_request_contract_latest.json"


def trusted_source_response_template_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "trusted_source_response_template_latest.json"


def trusted_source_operator_policy_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "trusted_source_operator_policy_latest.json"


def trusted_source_aggressiveness_policy_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "trusted_source_aggressiveness_policy_latest.json"


def trusted_source_escalation_thresholds_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "trusted_source_escalation_thresholds_latest.json"


def trusted_source_budget_policy_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "trusted_source_budget_policy_latest.json"


def trusted_source_retry_policy_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "trusted_source_retry_policy_latest.json"


def operator_run_preset_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "operator_run_preset_latest.json"


def operator_session_state_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "operator_session_state_latest.json"


def operator_resume_summary_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "operator_resume_summary_latest.json"


def operator_session_continuity_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "operator_session_continuity_latest.json"


def operator_current_session_summary_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "operator_current_session_summary_latest.json"


def operator_next_action_summary_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "operator_next_action_summary_latest.json"


def operator_resume_policy_summary_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "operator_resume_policy_summary_latest.json"


def operator_review_queue_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "operator_review_queue_latest.json"


def operator_intervention_summary_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "operator_intervention_summary_latest.json"


def operator_pending_decisions_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "operator_pending_decisions_latest.json"


def operator_review_reason_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "operator_review_reason_latest.json"


def operator_intervention_options_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "operator_intervention_options_latest.json"


def operator_review_decision_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "operator_review_decision_latest.json"


def operator_review_action_execution_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "operator_review_action_execution_latest.json"


def operator_review_resolution_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "operator_review_resolution_latest.json"


def controller_delegation_contract_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_delegation_contract_latest.json"


def controller_child_registry_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_child_registry_latest.json"


def controller_resource_lease_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_resource_lease_latest.json"


def controller_delegation_state_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_delegation_state_latest.json"


def child_authority_scope_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "child_authority_scope_latest.json"


def child_stop_condition_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "child_stop_condition_latest.json"


def child_return_contract_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "child_return_contract_latest.json"


def verifier_checklist_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "verifier_checklist_latest.json"


def verifier_adoption_readiness_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "verifier_adoption_readiness_latest.json"


def verifier_integrity_summary_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "verifier_integrity_summary_latest.json"


def child_budget_state_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "child_budget_state_latest.json"


def child_termination_summary_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "child_termination_summary_latest.json"


def controller_child_task_assignment_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_child_task_assignment_latest.json"


def child_task_result_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "child_task_result_latest.json"


def child_artifact_bundle_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "child_artifact_bundle_latest.json"


def controller_child_return_summary_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_child_return_summary_latest.json"


def controller_child_adoption_decision_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_child_adoption_decision_latest.json"


def controller_child_review_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_child_review_latest.json"


def controller_delegation_decision_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_delegation_decision_latest.json"


def controller_child_adoption_summary_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_child_adoption_summary_latest.json"


def controller_librarian_mission_improvement_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_librarian_mission_improvement_latest.json"


def controller_verifier_mission_improvement_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_verifier_mission_improvement_latest.json"


def controller_sequential_delegation_workflow_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_sequential_delegation_workflow_latest.json"


def controller_mission_delegation_plan_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_mission_delegation_plan_latest.json"


def controller_child_admissibility_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_child_admissibility_latest.json"


def controller_blocked_delegation_options_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_blocked_delegation_options_latest.json"


def controller_typed_handoff_contract_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_typed_handoff_contract_latest.json"


def controller_delegation_outcome_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_delegation_outcome_latest.json"


def controller_delegation_path_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_delegation_path_history_latest.json"


def controller_path_selection_evidence_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_path_selection_evidence_latest.json"


def controller_recommendation_support_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_recommendation_support_latest.json"


def controller_recommendation_audit_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_recommendation_audit_latest.json"


def controller_recommendation_audit_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_recommendation_audit_history_latest.json"


def controller_recommendation_calibration_summary_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_recommendation_calibration_summary_latest.json"


def controller_recommendation_window_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_recommendation_window_latest.json"


def controller_recommendation_stability_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_recommendation_stability_latest.json"


def controller_recommendation_stability_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_recommendation_stability_history_latest.json"


def controller_recommendation_governance_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_recommendation_governance_latest.json"


def controller_recommendation_override_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_recommendation_override_latest.json"


def controller_recommendation_override_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_recommendation_override_history_latest.json"


def controller_intervention_audit_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_intervention_audit_latest.json"


def controller_intervention_audit_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_intervention_audit_history_latest.json"


def controller_intervention_calibration_summary_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_intervention_calibration_summary_latest.json"


def controller_intervention_prudence_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_intervention_prudence_latest.json"


def controller_intervention_prudence_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_intervention_prudence_history_latest.json"


def controller_recommendation_trust_signal_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_recommendation_trust_signal_latest.json"


def controller_governance_summary_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_governance_summary_latest.json"


def controller_governance_summary_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_governance_summary_history_latest.json"


def controller_recommendation_state_summary_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_recommendation_state_summary_latest.json"


def controller_governance_trend_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_governance_trend_latest.json"


def controller_governance_trend_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_governance_trend_history_latest.json"


def controller_temporal_drift_summary_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_temporal_drift_summary_latest.json"


def controller_operator_guidance_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_operator_guidance_latest.json"


def controller_operator_guidance_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_operator_guidance_history_latest.json"


def controller_action_guidance_summary_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_action_guidance_summary_latest.json"


def controller_action_readiness_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_action_readiness_latest.json"


def controller_action_readiness_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_action_readiness_history_latest.json"


def controller_guided_handoff_summary_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_guided_handoff_summary_latest.json"


def controller_operator_flow_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_operator_flow_latest.json"


def controller_operator_flow_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_operator_flow_history_latest.json"


def controller_demo_readiness_summary_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_readiness_summary_latest.json"


def controller_demo_scenario_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_scenario_latest.json"


def controller_demo_scenario_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_scenario_history_latest.json"


def controller_demo_run_readiness_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_run_readiness_latest.json"


def controller_demo_operator_walkthrough_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_operator_walkthrough_latest.json"


def controller_demo_success_rubric_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_success_rubric_latest.json"


def controller_demo_execution_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_execution_latest.json"


def controller_demo_execution_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_execution_history_latest.json"


def controller_demo_result_summary_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_result_summary_latest.json"


def controller_demo_output_inventory_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_output_inventory_latest.json"


def controller_demo_evidence_trail_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_evidence_trail_latest.json"


def controller_demo_output_completion_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_output_completion_latest.json"


def controller_demo_output_completion_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_output_completion_history_latest.json"


def controller_demo_reviewable_artifacts_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_reviewable_artifacts_latest.json"


def controller_demo_completion_summary_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_completion_summary_latest.json"


def controller_trusted_demo_scenario_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_demo_scenario_latest.json"


def controller_trusted_demo_scenario_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_demo_scenario_history_latest.json"


def controller_trusted_demo_directive_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_demo_directive_latest.json"


def controller_trusted_demo_success_rubric_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_demo_success_rubric_latest.json"


def controller_trusted_demo_skill_target_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_demo_skill_target_latest.json"


def controller_trusted_demo_selection_rationale_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_demo_selection_rationale_latest.json"


def controller_trusted_demo_local_first_analysis_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_demo_local_first_analysis_latest.json"


def controller_trusted_demo_knowledge_gap_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_demo_knowledge_gap_latest.json"


def controller_trusted_demo_knowledge_gap_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_demo_knowledge_gap_history_latest.json"


def controller_trusted_demo_request_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_demo_request_latest.json"


def controller_trusted_demo_request_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_demo_request_history_latest.json"


def controller_trusted_demo_response_summary_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_demo_response_summary_latest.json"


def controller_trusted_demo_incorporation_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_demo_incorporation_latest.json"


def controller_trusted_demo_growth_artifact_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_demo_growth_artifact_latest.json"


def controller_trusted_demo_growth_artifact_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_demo_growth_artifact_history_latest.json"


def controller_trusted_demo_delta_summary_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_demo_delta_summary_latest.json"


def controller_trusted_live_connectivity_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_live_connectivity_latest.json"


def controller_trusted_live_connectivity_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_live_connectivity_history_latest.json"


def controller_trusted_live_request_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_live_request_latest.json"


def controller_trusted_live_response_summary_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_live_response_summary_latest.json"


def controller_trusted_live_evidence_receipt_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_live_evidence_receipt_latest.json"


def controller_trusted_live_validation_summary_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_live_validation_summary_latest.json"


def controller_trusted_demo_live_request_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_demo_live_request_latest.json"


def controller_trusted_demo_live_request_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_demo_live_request_history_latest.json"


def controller_trusted_demo_live_response_summary_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_demo_live_response_summary_latest.json"


def controller_trusted_demo_live_evidence_receipt_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_demo_live_evidence_receipt_latest.json"


def controller_trusted_demo_live_incorporation_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_demo_live_incorporation_latest.json"


def controller_trusted_demo_growth_artifact_update_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_demo_growth_artifact_update_latest.json"


def controller_trusted_demo_growth_artifact_update_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_demo_growth_artifact_update_history_latest.json"


def controller_trusted_demo_before_after_delta_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_trusted_demo_before_after_delta_latest.json"


def controller_demo_storyline_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_storyline_latest.json"


def controller_demo_storyline_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_storyline_history_latest.json"


def controller_demo_presentation_summary_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_presentation_summary_latest.json"


def controller_demo_narration_guide_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_narration_guide_latest.json"


def controller_demo_review_readiness_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_review_readiness_latest.json"


def controller_demo_runbook_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_runbook_latest.json"


def controller_demo_runbook_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_runbook_history_latest.json"


def controller_demo_facilitator_checklist_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_facilitator_checklist_latest.json"


def controller_demo_checkpoint_summary_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_checkpoint_summary_latest.json"


def controller_demo_acceptance_rubric_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_acceptance_rubric_latest.json"


def controller_demo_packaged_completeness_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_packaged_completeness_latest.json"


def controller_demo_packaged_completeness_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_packaged_completeness_history_latest.json"


def controller_demo_packaged_artifact_inventory_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_packaged_artifact_inventory_latest.json"


def controller_demo_packaged_checkpoint_closure_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_packaged_checkpoint_closure_latest.json"


def controller_demo_packaged_rubric_justification_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_packaged_rubric_justification_latest.json"


def controller_demo_presenter_handoff_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_presenter_handoff_latest.json"


def controller_demo_presenter_handoff_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_presenter_handoff_history_latest.json"


def controller_demo_quickstart_sheet_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_quickstart_sheet_latest.json"


def controller_demo_audience_summary_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_audience_summary_latest.json"


def controller_demo_pre_demo_sanity_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_pre_demo_sanity_latest.json"


def controller_demo_post_demo_review_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_post_demo_review_latest.json"


def controller_demo_short_form_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_short_form_latest.json"


def controller_demo_short_form_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_short_form_history_latest.json"


def controller_demo_full_walkthrough_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_full_walkthrough_latest.json"


def controller_demo_must_show_checkpoints_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_must_show_checkpoints_latest.json"


def controller_demo_audience_mode_optimization_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_demo_audience_mode_optimization_latest.json"


def controller_real_work_benchmark_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_latest.json"


def controller_real_work_benchmark_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_history_latest.json"


def controller_real_work_benchmark_directive_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_directive_latest.json"


def controller_real_work_benchmark_output_contract_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_output_contract_latest.json"


def controller_real_work_benchmark_success_rubric_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_success_rubric_latest.json"


def controller_real_work_benchmark_operator_value_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_operator_value_latest.json"


def controller_real_work_benchmark_selection_rationale_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_selection_rationale_latest.json"


def controller_real_work_benchmark_execution_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_execution_latest.json"


def controller_real_work_benchmark_execution_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_execution_history_latest.json"


def controller_real_work_benchmark_result_summary_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_result_summary_latest.json"


def controller_real_work_benchmark_output_inventory_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_output_inventory_latest.json"


def controller_real_work_benchmark_rubric_result_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_rubric_result_latest.json"


def controller_real_work_benchmark_closure_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_closure_latest.json"


def controller_real_work_benchmark_closure_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_closure_history_latest.json"


def controller_real_work_benchmark_repeatability_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_repeatability_latest.json"


def controller_real_work_benchmark_repeatability_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_repeatability_history_latest.json"


def controller_real_work_benchmark_promotion_readiness_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_promotion_readiness_latest.json"


def controller_real_work_benchmark_unresolved_bundle_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_unresolved_bundle_latest.json"


def controller_real_work_benchmark_delta_from_rc46_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_delta_from_rc46_latest.json"


def controller_real_work_benchmark_decision_packet_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_decision_packet_latest.json"


def controller_real_work_benchmark_decision_packet_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_decision_packet_history_latest.json"


def controller_real_work_benchmark_promotion_decision_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_promotion_decision_latest.json"


def controller_real_work_benchmark_review_gate_packet_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_review_gate_packet_latest.json"


def controller_real_work_benchmark_final_blocker_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_final_blocker_latest.json"


def controller_real_work_benchmark_decision_rationale_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_decision_rationale_latest.json"


def controller_real_work_benchmark_next_action_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_next_action_latest.json"


def controller_real_work_benchmark_review_packet_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_review_packet_latest.json"


def controller_real_work_benchmark_review_packet_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_review_packet_history_latest.json"


def controller_real_work_benchmark_operator_review_decision_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_operator_review_decision_latest.json"


def controller_real_work_benchmark_promotion_outcome_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_promotion_outcome_latest.json"


def controller_real_work_benchmark_operator_confirmation_state_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return (
        base / "controller_real_work_benchmark_operator_confirmation_state_latest.json"
    )


def controller_real_work_benchmark_review_evidence_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_review_evidence_latest.json"


def controller_real_work_benchmark_review_checklist_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_review_checklist_latest.json"


def controller_real_work_benchmark_review_confirmation_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_review_confirmation_latest.json"


def controller_real_work_benchmark_review_confirmation_history_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return (
        base / "controller_real_work_benchmark_review_confirmation_history_latest.json"
    )


def controller_real_work_benchmark_review_decision_source_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_review_decision_source_latest.json"


def controller_real_work_benchmark_promotion_outcome_confirmed_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return (
        base / "controller_real_work_benchmark_promotion_outcome_confirmed_latest.json"
    )


def controller_real_work_benchmark_review_resolution_summary_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return (
        base / "controller_real_work_benchmark_review_resolution_summary_latest.json"
    )


def controller_real_work_benchmark_confirmation_gap_path(
    root: str | Path | None = None,
) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "controller_real_work_benchmark_confirmation_gap_latest.json"


def effective_operator_session_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "effective_operator_session_latest.json"


def operator_launch_event_ledger_path(root: str | Path | None = None) -> Path:
    base = default_operator_root() if root is None else Path(root)
    base.mkdir(parents=True, exist_ok=True)
    return base / "operator_launch_events.jsonl"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    trimmed = raw_text.strip()
    if not trimmed:
        warning_key = f"{str(path.resolve())}::blank"
        if warning_key not in _SEEN_JSON_LOAD_WARNINGS:
            LOGGER.warning(
                "Treating blank JSON artifact as uninitialized operator state: %s",
                path,
            )
            _SEEN_JSON_LOAD_WARNINGS.add(warning_key)
        return {}
    try:
        payload = json.loads(trimmed)
    except json.JSONDecodeError as exc:
        warning_key = f"{str(path.resolve())}::decode"
        if warning_key not in _SEEN_JSON_LOAD_WARNINGS:
            LOGGER.warning(
                "Treating malformed JSON artifact as degraded operator state: %s (%s)",
                path,
                exc,
            )
            _SEEN_JSON_LOAD_WARNINGS.add(warning_key)
        return {}
    return payload if isinstance(payload, dict) else {}


def _json_artifact_requires_default(path: Path) -> bool:
    if not path.exists():
        return True
    try:
        raw_text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return True
    if not raw_text.strip():
        return True
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return True
    return not isinstance(payload, dict)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_stable_json(payload), encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("", encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _require_operator_mutation_rights() -> None:
    if os.environ.get(OPERATOR_CONTEXT_ENV, "").strip().lower() == OPERATOR_ROLE_RUNTIME:
        raise OperatorPolicyMutationRefusedError(
            "operator-owned policy cannot be mutated from runtime context",
            constraint_id="operator_policy_mutation_lock",
            enforcement_class="hard_enforced",
        )


def _normalize_path(value: Any) -> str:
    if value in {None, ""}:
        return ""
    try:
        return str(Path(str(value)).resolve())
    except OSError:
        return str(value)


def _normalize_endpoint_base(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urllib.parse.urlsplit(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return text
    normalized_path = parsed.path.rstrip("/") or ""
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, normalized_path, "", ""))


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _coerce_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    return default


def _is_under_path(candidate: Path, root: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def default_runtime_state_root(package_root: str | Path | None = None) -> Path:
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    candidate = package_root_path / "runtime_data" / "state"
    return candidate if candidate.parent.exists() else package_root_path / "data"


def default_runtime_logs_root(package_root: str | Path | None = None) -> Path:
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    candidate = package_root_path / "runtime_data" / "logs"
    return candidate if candidate.parent.exists() else package_root_path / "logs"


def default_generated_output_root(package_root: str | Path | None = None) -> Path:
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    candidate = package_root_path / "runtime_data" / "generated"
    return candidate if candidate.parent.exists() else package_root_path / "data" / "generated"


def active_workspace_base_root(package_root: str | Path | None = None) -> Path:
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    return package_root_path / ACTIVE_WORKSPACE_ROOT_NAME


def sanitize_workspace_id(value: Any, *, fallback: str = "workspace_default") -> str:
    text = str(value or "").strip()
    token = "".join(
        character if character.isalnum() or character in {"-", "_", "."} else "_"
        for character in text
    ).strip("._-")
    return token or fallback


def active_workspace_root(
    package_root: str | Path | None = None,
    *,
    workspace_id: Any,
) -> Path:
    return active_workspace_base_root(package_root) / sanitize_workspace_id(
        workspace_id,
        fallback="workspace_default",
    )


def protected_runtime_root_hints(
    package_root: str | Path | None = None,
    *,
    operator_root: str | Path | None = None,
) -> list[str]:
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    operator_root_path = default_operator_root() if operator_root is None else Path(operator_root)
    rows = [
        package_root_path / "main.py",
        package_root_path / "theory" / "nined_core.py",
        package_root_path / "directive_inputs",
        default_runtime_state_root(package_root_path),
        operator_root_path,
    ]
    unique: list[str] = []
    seen: set[str] = set()
    for item in rows:
        normalized = _normalize_path(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


def ensure_active_workspace_layout(
    package_root: str | Path | None = None,
    *,
    workspace_id: Any,
) -> dict[str, Any]:
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    base_root = active_workspace_base_root(package_root_path)
    base_root.mkdir(parents=True, exist_ok=True)
    clean_workspace_id = sanitize_workspace_id(workspace_id, fallback="workspace_default")
    workspace_root = base_root / clean_workspace_id
    workspace_root.mkdir(parents=True, exist_ok=True)
    layout_paths: dict[str, str] = {}
    for directory_name in ACTIVE_WORKSPACE_LAYOUT_DIRECTORIES:
        target = workspace_root / directory_name
        target.mkdir(parents=True, exist_ok=True)
        layout_paths[directory_name] = _normalize_path(target)
    generated_output_root = default_generated_output_root(package_root_path)
    generated_output_root.mkdir(parents=True, exist_ok=True)
    log_root = default_runtime_logs_root(package_root_path)
    log_root.mkdir(parents=True, exist_ok=True)
    return {
        "workspace_base_root": _normalize_path(base_root),
        "workspace_id": clean_workspace_id,
        "workspace_root": _normalize_path(workspace_root),
        "working_directory": layout_paths.get("src", _normalize_path(workspace_root)),
        "layout_directories": list(ACTIVE_WORKSPACE_LAYOUT_DIRECTORIES),
        "layout_paths": layout_paths,
        "generated_output_root": _normalize_path(generated_output_root),
        "log_root": _normalize_path(log_root),
    }


def build_runtime_constraints_for_profile(
    package_root: str | Path | None = None,
    *,
    operator_root: str | Path | None = None,
    execution_profile: str = EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION,
    workspace_id: Any = "",
    governed_execution_mode: str = GOVERNED_EXECUTION_MODE_SINGLE_CYCLE,
    max_cycles_per_invocation: Any = None,
    max_total_cycles: Any = None,
) -> dict[str, Any]:
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    operator_root_path = default_operator_root() if operator_root is None else Path(operator_root)
    profile_name = str(execution_profile or EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION).strip()
    if profile_name not in SUPPORTED_EXECUTION_PROFILES:
        profile_name = EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION
    controller_mode = str(governed_execution_mode or GOVERNED_EXECUTION_MODE_SINGLE_CYCLE).strip()
    if controller_mode not in SUPPORTED_GOVERNED_EXECUTION_MODES:
        controller_mode = GOVERNED_EXECUTION_MODE_SINGLE_CYCLE
    controller_cap = (
        DEFAULT_GOVERNED_EXECUTION_MAX_CYCLES_SINGLE
        if controller_mode == GOVERNED_EXECUTION_MODE_SINGLE_CYCLE
        else DEFAULT_GOVERNED_EXECUTION_MAX_CYCLES_MULTI
    )
    if max_cycles_per_invocation not in {None, ""}:
        try:
            controller_cap = int(max_cycles_per_invocation)
        except (TypeError, ValueError):
            controller_cap = (
                DEFAULT_GOVERNED_EXECUTION_MAX_CYCLES_SINGLE
                if controller_mode == GOVERNED_EXECUTION_MODE_SINGLE_CYCLE
                else DEFAULT_GOVERNED_EXECUTION_MAX_CYCLES_MULTI
            )
    total_cycle_cap = (
        DEFAULT_GOVERNED_EXECUTION_MAX_CYCLES_SINGLE
        if controller_mode == GOVERNED_EXECUTION_MODE_SINGLE_CYCLE
        else DEFAULT_GOVERNED_EXECUTION_MAX_CYCLES_MULTI
    )
    if max_total_cycles not in {None, ""}:
        try:
            total_cycle_cap = int(max_total_cycles)
        except (TypeError, ValueError):
            total_cycle_cap = (
                DEFAULT_GOVERNED_EXECUTION_MAX_CYCLES_SINGLE
                if controller_mode == GOVERNED_EXECUTION_MODE_SINGLE_CYCLE
                else DEFAULT_GOVERNED_EXECUTION_MAX_CYCLES_MULTI
            )

    state_root = default_runtime_state_root(package_root_path)
    state_root.mkdir(parents=True, exist_ok=True)
    log_root = default_runtime_logs_root(package_root_path)
    log_root.mkdir(parents=True, exist_ok=True)
    generated_output_root = default_generated_output_root(package_root_path)
    generated_output_root.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema_name": RUNTIME_CONSTRAINTS_SCHEMA_NAME,
        "schema_version": RUNTIME_CONSTRAINTS_SCHEMA_VERSION,
        "generated_at": _now(),
        "required_for_launch": True,
        "execution_profile": profile_name,
        "governed_execution": {
            "mode": controller_mode,
            "max_cycles_per_invocation": controller_cap,
            "max_total_cycles": total_cycle_cap,
        },
        "workspace_policy": {
            "workspace_base_root": _normalize_path(active_workspace_base_root(package_root_path)),
            "workspace_id": "",
            "workspace_root": "",
            "working_directory": "",
            "layout_directories": list(ACTIVE_WORKSPACE_LAYOUT_DIRECTORIES),
            "layout_paths": {},
            "generated_output_root": _normalize_path(generated_output_root),
            "log_root": _normalize_path(log_root),
            "protected_root_hints": protected_runtime_root_hints(
                package_root_path,
                operator_root=operator_root_path,
            ),
        },
        "constraints": {
            "max_memory_mb": 2048,
            "max_python_threads": 8,
            "max_child_processes": 0,
            "subprocess_mode": "disabled",
            "working_directory": _normalize_path(package_root_path),
            "allowed_write_roots": [
                _normalize_path(state_root),
                _normalize_path(log_root),
            ],
            "session_time_limit_seconds": 600,
            "cpu_utilization_cap_pct": None,
            "network_egress_mode": "unsupported",
            "request_rate_limit_per_minute": None,
        },
    }

    if profile_name == EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING:
        workspace_layout = ensure_active_workspace_layout(
            package_root_path,
            workspace_id=workspace_id,
        )
        payload["workspace_policy"] = {
            **dict(payload.get("workspace_policy", {})),
            **workspace_layout,
            "protected_root_hints": protected_runtime_root_hints(
                package_root_path,
                operator_root=operator_root_path,
            ),
        }
        payload["constraints"]["working_directory"] = str(workspace_layout["working_directory"])
        payload["constraints"]["allowed_write_roots"] = [
            str(workspace_layout["workspace_root"]),
            str(workspace_layout["generated_output_root"]),
            str(workspace_layout["log_root"]),
        ]
    return payload


def build_default_runtime_constraints(package_root: str | Path | None = None) -> dict[str, Any]:
    return build_runtime_constraints_for_profile(
        package_root,
        execution_profile=EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION,
    )


def build_default_trusted_source_bindings(package_root: str | Path | None = None) -> dict[str, Any]:
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    novali_v5_root = package_root_path.parent / "novali-v5"
    novali_v4_root = package_root_path.parent / "novali-v4"
    knowledge_pack_root = package_root_path / "trusted_sources" / "knowledge_packs"
    return {
        "schema_name": TRUSTED_SOURCE_BINDINGS_SCHEMA_NAME,
        "schema_version": TRUSTED_SOURCE_BINDINGS_SCHEMA_VERSION,
        "generated_at": _now(),
        "bindings": [
            {
                "source_id": "local_repo:novali-v5",
                "source_kind": "local_path",
                "enabled": novali_v5_root.exists(),
                "credential_strategy": "none",
                "credential_ref": "",
                "path_hint": _normalize_path(novali_v5_root),
            },
            {
                "source_id": "local_artifacts:novali-v5/data",
                "source_kind": "local_path",
                "enabled": (novali_v5_root / "data").exists(),
                "credential_strategy": "none",
                "credential_ref": "",
                "path_hint": _normalize_path(novali_v5_root / "data"),
            },
            {
                "source_id": "local_logs:logs",
                "source_kind": "local_path",
                "enabled": True,
                "credential_strategy": "none",
                "credential_ref": "",
                "path_hint": _normalize_path(package_root_path / "logs"),
            },
            {
                "source_id": "local_repo:novali-v4",
                "source_kind": "local_path",
                "enabled": novali_v4_root.exists(),
                "credential_strategy": "none",
                "credential_ref": "",
                "path_hint": _normalize_path(novali_v4_root),
            },
            {
                "source_id": "local_artifacts:novali-v4/data",
                "source_kind": "local_path",
                "enabled": (novali_v4_root / "data").exists(),
                "credential_strategy": "none",
                "credential_ref": "",
                "path_hint": _normalize_path(novali_v4_root / "data"),
            },
            {
                "source_id": "trusted_benchmark_pack_v1",
                "source_kind": "local_bundle",
                "enabled": True,
                "credential_strategy": "none",
                "credential_ref": "",
                "path_hint": _normalize_path(package_root_path / "benchmarks" / "trusted_benchmark_pack_v1"),
            },
            {
                "source_id": "internal_knowledge_pack:successor_completion_v1",
                "source_kind": "local_bundle",
                "enabled": True,
                "credential_strategy": "none",
                "credential_ref": "",
                "path_hint": _normalize_path(
                    knowledge_pack_root / "successor_completion_knowledge_pack_v1.json"
                ),
            },
            {
                "source_id": "internal_knowledge_pack:workspace_continuation_v1",
                "source_kind": "local_bundle",
                "enabled": True,
                "credential_strategy": "none",
                "credential_ref": "",
                "path_hint": _normalize_path(
                    knowledge_pack_root / "workspace_continuation_knowledge_pack_v1.json"
                ),
            },
            {
                "source_id": "internal_knowledge_pack:successor_promotion_review_v1",
                "source_kind": "local_bundle",
                "enabled": True,
                "credential_strategy": "none",
                "credential_ref": "",
                "path_hint": _normalize_path(
                    knowledge_pack_root / "successor_promotion_review_knowledge_pack_v1.json"
                ),
            },
            {
                "source_id": "openai_api",
                "source_kind": "network_api",
                "enabled": False,
                "credential_strategy": "env_var",
                "credential_ref": "OPENAI_API_KEY",
                "endpoint_base": "https://api.openai.com/v1",
                "path_hint": "",
            },
        ],
    }


def build_default_trusted_source_secrets() -> dict[str, Any]:
    return {
        "schema_name": TRUSTED_SOURCE_SECRETS_SCHEMA_NAME,
        "schema_version": TRUSTED_SOURCE_SECRETS_SCHEMA_VERSION,
        "generated_at": _now(),
        "secrets_by_source": {},
    }


def build_default_trusted_source_operator_policy() -> dict[str, Any]:
    return {
        "schema_name": TRUSTED_SOURCE_OPERATOR_POLICY_SCHEMA_NAME,
        "schema_version": TRUSTED_SOURCE_OPERATOR_POLICY_SCHEMA_VERSION,
        "generated_at": _now(),
        "policy_state": "operator_configured_trusted_source_governance",
        "policy_scope": "operator_session",
        "aggressiveness_posture": "normal_bounded",
        "external_requery_mode": "constrained",
        "prefer_indexed_reuse_strongly": True,
        "max_external_requests_per_mission": 1,
        "max_retries_per_gap": 1,
        "operator_review_after_external_requests": 1,
        "operator_review_after_retry_attempts": 1,
        "provider_policy_scope": "session_binding_defaults",
        "active_provider_ids": ["openai_api"],
        "governance_authority_note": (
            "trusted-source operator policy constrains bounded evidence acquisition only "
            "and never replaces directive-first or protected-surface authority"
        ),
    }


def _operator_run_preset_payload(
    preset_id: str,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    normalized_preset_id = str(preset_id or DEFAULT_OPERATOR_RUN_PRESET_ID).strip()
    if normalized_preset_id == OPERATOR_RUN_PRESET_FOCUSED_TIGHTER_CONTROL:
        preset_label = "Focused / tighter-control"
        preset_state = "operator_run_preset_focused_tighter_control"
        intent_summary = (
            "Tighter bounded run posture for narrower work. Review gates appear sooner, "
            "indexed reuse is preferred strongly, and governed execution defaults to one cycle."
        )
        policy_defaults = {
            "aggressiveness_posture": "conservative",
            "external_requery_mode": "review_first",
            "prefer_indexed_reuse_strongly": True,
            "max_external_requests_per_mission": 1,
            "max_retries_per_gap": 0,
            "operator_review_after_external_requests": 0,
            "operator_review_after_retry_attempts": 0,
        }
        governed_runtime_defaults = {
            "execution_profile": EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING,
            "governed_execution_mode": GOVERNED_EXECUTION_MODE_SINGLE_CYCLE,
            "max_cycles_per_invocation": 1,
            "max_total_cycles": 1,
        }
        long_run_ready = False
        review_gate_posture = "review_early"
        low_touch_after_initialization = False
        default_selected = False
    else:
        normalized_preset_id = OPERATOR_RUN_PRESET_LONG_RUN_LOW_TOUCH
        preset_label = "Long-run / low-touch"
        preset_state = "operator_run_preset_long_run_low_touch"
        intent_summary = (
            "Evidence-backed default for bounded multi-cycle successor work after initialization. "
            "It keeps reuse-first governance, bounded review gates, and a practical multi-cycle run posture."
        )
        policy_defaults = {
            "aggressiveness_posture": "normal_bounded",
            "external_requery_mode": "constrained",
            "prefer_indexed_reuse_strongly": True,
            "max_external_requests_per_mission": 1,
            "max_retries_per_gap": 1,
            "operator_review_after_external_requests": 1,
            "operator_review_after_retry_attempts": 1,
        }
        governed_runtime_defaults = {
            "execution_profile": EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING,
            "governed_execution_mode": GOVERNED_EXECUTION_MODE_MULTI_CYCLE,
            "max_cycles_per_invocation": 2,
            "max_total_cycles": 3,
        }
        long_run_ready = True
        review_gate_posture = "review_after_threshold_crossed"
        low_touch_after_initialization = True
        default_selected = True
    return {
        "schema_name": OPERATOR_RUN_PRESET_SCHEMA_NAME,
        "schema_version": OPERATOR_RUN_PRESET_SCHEMA_VERSION,
        "generated_at": str(generated_at or "").strip() or _now(),
        "preset_id": normalized_preset_id,
        "preset_label": preset_label,
        "preset_state": preset_state,
        "preset_scope": "operator_session_defaults",
        "default_selected": default_selected,
        "long_run_ready": long_run_ready,
        "low_touch_after_initialization": low_touch_after_initialization,
        "review_gate_posture": review_gate_posture,
        "intent_summary": intent_summary,
        "advanced_controls_route": "/settings",
        "bootstrap_runtime_defaults": {
            "execution_profile": EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION,
            "governed_execution_mode": GOVERNED_EXECUTION_MODE_SINGLE_CYCLE,
            "max_cycles_per_invocation": 1,
            "max_total_cycles": 1,
        },
        "governed_runtime_defaults": governed_runtime_defaults,
        "effective_trusted_source_policy": dict(policy_defaults),
        "governance_authority_note": (
            "operator presets adjust bounded evidence-acquisition posture and recommended run shape "
            "only; they do not replace directive-first authority or protected-surface rules"
        ),
    }


def build_default_operator_run_preset() -> dict[str, Any]:
    return _operator_run_preset_payload(DEFAULT_OPERATOR_RUN_PRESET_ID)


def build_operator_run_preset(preset_id: str) -> dict[str, Any]:
    normalized_preset_id = str(preset_id or DEFAULT_OPERATOR_RUN_PRESET_ID).strip()
    if normalized_preset_id not in SUPPORTED_OPERATOR_RUN_PRESET_IDS:
        normalized_preset_id = DEFAULT_OPERATOR_RUN_PRESET_ID
    return _operator_run_preset_payload(normalized_preset_id)


def _operator_run_preset_matches_policy(
    preset_payload: dict[str, Any],
    *,
    operator_policy_payload: dict[str, Any],
) -> bool:
    expected = dict(preset_payload.get("effective_trusted_source_policy", {}))
    return (
        str(operator_policy_payload.get("aggressiveness_posture", "")).strip()
        == str(expected.get("aggressiveness_posture", "")).strip()
        and str(operator_policy_payload.get("external_requery_mode", "")).strip()
        == str(expected.get("external_requery_mode", "")).strip()
        and bool(operator_policy_payload.get("prefer_indexed_reuse_strongly", False))
        == bool(expected.get("prefer_indexed_reuse_strongly", False))
        and int(operator_policy_payload.get("max_external_requests_per_mission", 0) or 0)
        == int(expected.get("max_external_requests_per_mission", 0) or 0)
        and int(operator_policy_payload.get("max_retries_per_gap", 0) or 0)
        == int(expected.get("max_retries_per_gap", 0) or 0)
        and int(operator_policy_payload.get("operator_review_after_external_requests", 0) or 0)
        == int(expected.get("operator_review_after_external_requests", 0) or 0)
        and int(operator_policy_payload.get("operator_review_after_retry_attempts", 0) or 0)
        == int(expected.get("operator_review_after_retry_attempts", 0) or 0)
    )


def _custom_operator_run_preset_payload(
    *,
    operator_policy_payload: dict[str, Any],
    runtime_payload: dict[str, Any],
) -> dict[str, Any]:
    governed_execution = dict(runtime_payload.get("governed_execution", {}))
    return {
        "schema_name": OPERATOR_RUN_PRESET_SCHEMA_NAME,
        "schema_version": OPERATOR_RUN_PRESET_SCHEMA_VERSION,
        "generated_at": _now(),
        "preset_id": OPERATOR_RUN_PRESET_CUSTOM_MANUAL,
        "preset_label": "Custom / manually tuned",
        "preset_state": "operator_run_preset_custom_manual_policy",
        "preset_scope": "operator_session_defaults",
        "default_selected": False,
        "long_run_ready": bool(
            str(governed_execution.get("mode", "")).strip()
            == GOVERNED_EXECUTION_MODE_MULTI_CYCLE
        ),
        "low_touch_after_initialization": False,
        "review_gate_posture": str(
            operator_policy_payload.get("operator_review_threshold_state", "")
        ).strip()
        or "custom_thresholds",
        "intent_summary": (
            "Current advanced controls differ from the packaged presets. The saved runtime and "
            "trusted-source governance values remain authoritative for this operator session."
        ),
        "advanced_controls_route": "/settings",
        "bootstrap_runtime_defaults": {
            "execution_profile": EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION,
            "governed_execution_mode": GOVERNED_EXECUTION_MODE_SINGLE_CYCLE,
            "max_cycles_per_invocation": 1,
        },
        "governed_runtime_defaults": {
            "execution_profile": str(
                runtime_payload.get(
                    "execution_profile",
                    EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING,
                )
            ).strip()
            or EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING,
            "governed_execution_mode": str(
                governed_execution.get(
                    "mode",
                    GOVERNED_EXECUTION_MODE_SINGLE_CYCLE,
                )
            ).strip()
            or GOVERNED_EXECUTION_MODE_SINGLE_CYCLE,
            "max_cycles_per_invocation": int(
                governed_execution.get("max_cycles_per_invocation", 1) or 1
            ),
        },
        "effective_trusted_source_policy": {
            "aggressiveness_posture": str(
                operator_policy_payload.get("aggressiveness_posture", "normal_bounded")
            ).strip()
            or "normal_bounded",
            "external_requery_mode": str(
                operator_policy_payload.get("external_requery_mode", "constrained")
            ).strip()
            or "constrained",
            "prefer_indexed_reuse_strongly": bool(
                operator_policy_payload.get("prefer_indexed_reuse_strongly", True)
            ),
            "max_external_requests_per_mission": int(
                operator_policy_payload.get("max_external_requests_per_mission", 1) or 0
            ),
            "max_retries_per_gap": int(
                operator_policy_payload.get("max_retries_per_gap", 1) or 0
            ),
            "operator_review_after_external_requests": int(
                operator_policy_payload.get(
                    "operator_review_after_external_requests",
                    1,
                )
                or 0
            ),
            "operator_review_after_retry_attempts": int(
                operator_policy_payload.get(
                    "operator_review_after_retry_attempts",
                    1,
                )
                or 0
            ),
        },
        "governance_authority_note": (
            "custom operator tuning still constrains bounded evidence use only and never replaces "
            "directive-first or protected-surface authority"
        ),
    }


def _trusted_source_operator_policy_views(
    payload: dict[str, Any],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    posture = str(payload.get("aggressiveness_posture", "")).strip().lower()
    if posture not in TRUSTED_SOURCE_OPERATOR_ALLOWED_AGGRESSIVENESS_POSTURES:
        posture = "normal_bounded"
    external_requery_mode = str(payload.get("external_requery_mode", "")).strip().lower()
    if external_requery_mode not in TRUSTED_SOURCE_OPERATOR_ALLOWED_EXTERNAL_REQUERY_MODES:
        external_requery_mode = "constrained"
    prefer_indexed_reuse_strongly = _coerce_bool(
        payload.get("prefer_indexed_reuse_strongly", True),
        default=True,
    )
    max_external_requests_per_mission = _bounded_int(
        payload.get("max_external_requests_per_mission", 1),
        default=1,
        minimum=0,
        maximum=4,
    )
    max_retries_per_gap = _bounded_int(
        payload.get("max_retries_per_gap", 1),
        default=1,
        minimum=0,
        maximum=3,
    )
    operator_review_after_external_requests = _bounded_int(
        payload.get(
            "operator_review_after_external_requests",
            max_external_requests_per_mission,
        ),
        default=max_external_requests_per_mission,
        minimum=0,
        maximum=4,
    )
    operator_review_after_retry_attempts = _bounded_int(
        payload.get("operator_review_after_retry_attempts", max_retries_per_gap),
        default=max_retries_per_gap,
        minimum=0,
        maximum=3,
    )
    if external_requery_mode == "disabled":
        max_external_requests_per_mission = 0
    if external_requery_mode == "review_first":
        operator_review_after_external_requests = 0
    aggressiveness_state = (
        "low_aggression"
        if posture == "conservative" or external_requery_mode == "review_first"
        else "normal_aggression"
    )
    policy_state = {
        "conservative": "operator_policy_conservative_bounded",
        "normal_bounded": "operator_policy_normal_bounded",
        "permissive_bounded": "operator_policy_permissive_bounded",
    }.get(posture, "operator_policy_normal_bounded")
    if external_requery_mode == "disabled":
        policy_state = "operator_policy_external_requery_disabled"
    elif external_requery_mode == "review_first":
        policy_state = "operator_policy_review_before_external"
    budget_policy_state = {
        "conservative": "operator_budget_policy_conservative",
        "normal_bounded": "operator_budget_policy_normal_bounded",
        "permissive_bounded": "operator_budget_policy_permissive_bounded",
    }.get(posture, "operator_budget_policy_normal_bounded")
    retry_policy_state = {
        "conservative": "operator_retry_policy_low_ceiling",
        "normal_bounded": "operator_retry_policy_bounded",
        "permissive_bounded": "operator_retry_policy_permissive_bounded",
    }.get(posture, "operator_retry_policy_bounded")
    operator_review_threshold_state = (
        "review_first"
        if external_requery_mode == "review_first"
        else (
            "review_early"
            if operator_review_after_external_requests == 0
            or operator_review_after_retry_attempts == 0
            else "review_after_threshold_crossed"
        )
    )
    active_provider_ids = [
        str(item).strip()
        for item in list(payload.get("active_provider_ids", ["openai_api"]))
        if str(item).strip()
    ] or ["openai_api"]
    normalized_policy = {
        "schema_name": TRUSTED_SOURCE_OPERATOR_POLICY_SCHEMA_NAME,
        "schema_version": TRUSTED_SOURCE_OPERATOR_POLICY_SCHEMA_VERSION,
        "generated_at": str(payload.get("generated_at", "")) or _now(),
        "policy_state": policy_state,
        "policy_scope": "operator_session",
        "aggressiveness_posture": posture,
        "aggressiveness_state": aggressiveness_state,
        "external_requery_mode": external_requery_mode,
        "external_requery_enabled": external_requery_mode in {"enabled", "constrained"},
        "prefer_indexed_reuse_strongly": prefer_indexed_reuse_strongly,
        "max_external_requests_per_mission": max_external_requests_per_mission,
        "max_retries_per_gap": max_retries_per_gap,
        "operator_review_after_external_requests": operator_review_after_external_requests,
        "operator_review_after_retry_attempts": operator_review_after_retry_attempts,
        "operator_review_threshold_state": operator_review_threshold_state,
        "provider_policy_scope": "session_binding_defaults",
        "active_provider_ids": active_provider_ids,
        "governance_authority_note": (
            "trusted-source operator policy constrains bounded evidence acquisition only "
            "and never replaces directive-first or protected-surface authority"
        ),
    }
    aggressiveness_policy = {
        "schema_name": TRUSTED_SOURCE_OPERATOR_AGGRESSIVENESS_POLICY_SCHEMA_NAME,
        "schema_version": TRUSTED_SOURCE_OPERATOR_AGGRESSIVENESS_POLICY_SCHEMA_VERSION,
        "generated_at": str(payload.get("generated_at", "")) or _now(),
        "aggressiveness_state": aggressiveness_state,
        "aggressiveness_posture": posture,
        "prefer_local_only_when_sufficient": True,
        "prefer_indexed_reuse_when_sufficient": True,
        "prefer_indexed_reuse_strongly": prefer_indexed_reuse_strongly,
        "external_requery_requires_explicit_justification": True,
        "operator_review_preferred_over_aggressive_escalation": True,
    }
    budget_policy = {
        "schema_name": TRUSTED_SOURCE_OPERATOR_BUDGET_POLICY_SCHEMA_NAME,
        "schema_version": TRUSTED_SOURCE_OPERATOR_BUDGET_POLICY_SCHEMA_VERSION,
        "generated_at": str(payload.get("generated_at", "")) or _now(),
        "budget_policy_state": budget_policy_state,
        "max_external_requests_per_mission": max_external_requests_per_mission,
        "prefer_local_only_when_sufficient": True,
        "prefer_indexed_reuse_when_sufficient": True,
        "prefer_indexed_reuse_strongly": prefer_indexed_reuse_strongly,
        "external_request_budget_unit": "bounded_external_request",
        "operator_review_after_external_requests": operator_review_after_external_requests,
        "external_requery_mode": external_requery_mode,
    }
    retry_policy = {
        "schema_name": TRUSTED_SOURCE_OPERATOR_RETRY_POLICY_SCHEMA_NAME,
        "schema_version": TRUSTED_SOURCE_OPERATOR_RETRY_POLICY_SCHEMA_VERSION,
        "generated_at": str(payload.get("generated_at", "")) or _now(),
        "retry_policy_state": retry_policy_state,
        "max_retries_per_gap": max_retries_per_gap,
        "operator_review_after_retry_attempts": operator_review_after_retry_attempts,
        "retry_requires_explicit_transient_or_value_justification": True,
        "retry_block_requires_operator_review": True,
    }
    escalation_thresholds = {
        "schema_name": TRUSTED_SOURCE_OPERATOR_ESCALATION_THRESHOLDS_SCHEMA_NAME,
        "schema_version": TRUSTED_SOURCE_OPERATOR_ESCALATION_THRESHOLDS_SCHEMA_VERSION,
        "generated_at": str(payload.get("generated_at", "")) or _now(),
        "operator_review_threshold_state": operator_review_threshold_state,
        "external_requery_mode": external_requery_mode,
        "max_external_requeries_per_cycle": 1,
        "max_external_requests_per_mission": max_external_requests_per_mission,
        "max_retries_per_gap": max_retries_per_gap,
        "operator_review_after_external_requests": operator_review_after_external_requests,
        "operator_review_after_retry_attempts": operator_review_after_retry_attempts,
        "trusted_source_authority_boundary": "evidence_only_not_governance_authority",
    }
    return (
        normalized_policy,
        aggressiveness_policy,
        budget_policy,
        retry_policy,
        escalation_thresholds,
    )


def initialize_operator_policy_files(
    *,
    root: str | Path | None = None,
    package_root: str | Path | None = None,
) -> dict[str, str]:
    _require_operator_mutation_rights()
    constraints_path = operator_runtime_constraints_path(root)
    envelope_path = operator_runtime_envelope_spec_path(root)
    bindings_path = trusted_source_bindings_path(root)
    secrets_path = trusted_source_secrets_path(root)
    trusted_source_operator_policy_file = trusted_source_operator_policy_path(root)
    run_preset_file = operator_run_preset_path(root)
    if _json_artifact_requires_default(constraints_path):
        _write_json(constraints_path, build_default_runtime_constraints(package_root))
    if _json_artifact_requires_default(envelope_path):
        _write_json(envelope_path, build_default_operator_runtime_envelope_spec(package_root))
    if _json_artifact_requires_default(bindings_path):
        _write_json(bindings_path, build_default_trusted_source_bindings(package_root))
    if _json_artifact_requires_default(secrets_path):
        _write_json(secrets_path, build_default_trusted_source_secrets())
    if _json_artifact_requires_default(trusted_source_operator_policy_file):
        (
            trusted_source_operator_policy_payload,
            aggressiveness_policy_payload,
            budget_policy_payload,
            retry_policy_payload,
            escalation_thresholds_payload,
        ) = _trusted_source_operator_policy_views(
            build_default_trusted_source_operator_policy()
        )
        _write_json(trusted_source_operator_policy_file, trusted_source_operator_policy_payload)
        _write_json(
            trusted_source_aggressiveness_policy_path(root),
            aggressiveness_policy_payload,
        )
        _write_json(trusted_source_budget_policy_path(root), budget_policy_payload)
        _write_json(trusted_source_retry_policy_path(root), retry_policy_payload)
        _write_json(
            trusted_source_escalation_thresholds_path(root),
            escalation_thresholds_payload,
        )
    if _json_artifact_requires_default(run_preset_file):
        preset_payload = infer_operator_run_preset(
            root=root,
            package_root=package_root,
        )
        _write_json(run_preset_file, preset_payload)
    return {
        "operator_runtime_constraints_path": str(constraints_path),
        "operator_runtime_envelope_spec_path": str(envelope_path),
        "trusted_source_bindings_path": str(bindings_path),
        "trusted_source_secrets_path": str(secrets_path),
        "trusted_source_credential_status_path": str(trusted_source_credential_status_path(root)),
        "trusted_source_provider_status_path": str(trusted_source_provider_status_path(root)),
        "trusted_source_handshake_path": str(trusted_source_handshake_path(root)),
        "trusted_source_session_contract_path": str(trusted_source_session_contract_path(root)),
        "trusted_source_request_contract_path": str(trusted_source_request_contract_path(root)),
        "trusted_source_response_template_path": str(trusted_source_response_template_path(root)),
        "trusted_source_operator_policy_path": str(trusted_source_operator_policy_file),
        "trusted_source_aggressiveness_policy_path": str(
            trusted_source_aggressiveness_policy_path(root)
        ),
        "trusted_source_budget_policy_path": str(trusted_source_budget_policy_path(root)),
        "trusted_source_retry_policy_path": str(trusted_source_retry_policy_path(root)),
        "trusted_source_escalation_thresholds_path": str(
            trusted_source_escalation_thresholds_path(root)
        ),
        "operator_run_preset_path": str(run_preset_file),
        "operator_session_state_path": str(operator_session_state_path(root)),
        "operator_resume_summary_path": str(operator_resume_summary_path(root)),
        "operator_session_continuity_path": str(operator_session_continuity_path(root)),
        "operator_current_session_summary_path": str(
            operator_current_session_summary_path(root)
        ),
        "operator_next_action_summary_path": str(
            operator_next_action_summary_path(root)
        ),
        "operator_resume_policy_summary_path": str(
            operator_resume_policy_summary_path(root)
        ),
        "operator_review_queue_path": str(operator_review_queue_path(root)),
        "operator_intervention_summary_path": str(
            operator_intervention_summary_path(root)
        ),
        "operator_pending_decisions_path": str(operator_pending_decisions_path(root)),
        "operator_review_reason_path": str(operator_review_reason_path(root)),
        "operator_intervention_options_path": str(
            operator_intervention_options_path(root)
        ),
        "operator_review_decision_path": str(operator_review_decision_path(root)),
        "operator_review_action_execution_path": str(
            operator_review_action_execution_path(root)
        ),
        "operator_review_resolution_path": str(operator_review_resolution_path(root)),
        "controller_delegation_contract_path": str(
            controller_delegation_contract_path(root)
        ),
        "controller_child_registry_path": str(controller_child_registry_path(root)),
        "controller_resource_lease_path": str(controller_resource_lease_path(root)),
        "controller_delegation_state_path": str(controller_delegation_state_path(root)),
        "child_authority_scope_path": str(child_authority_scope_path(root)),
        "child_stop_condition_path": str(child_stop_condition_path(root)),
        "child_return_contract_path": str(child_return_contract_path(root)),
        "verifier_checklist_path": str(verifier_checklist_path(root)),
        "verifier_adoption_readiness_path": str(
            verifier_adoption_readiness_path(root)
        ),
        "verifier_integrity_summary_path": str(
            verifier_integrity_summary_path(root)
        ),
        "child_budget_state_path": str(child_budget_state_path(root)),
        "child_termination_summary_path": str(child_termination_summary_path(root)),
        "controller_child_task_assignment_path": str(
            controller_child_task_assignment_path(root)
        ),
        "child_task_result_path": str(child_task_result_path(root)),
        "child_artifact_bundle_path": str(child_artifact_bundle_path(root)),
        "controller_child_return_summary_path": str(
            controller_child_return_summary_path(root)
        ),
        "controller_child_adoption_decision_path": str(
            controller_child_adoption_decision_path(root)
        ),
        "controller_child_review_path": str(controller_child_review_path(root)),
        "controller_delegation_decision_path": str(
            controller_delegation_decision_path(root)
        ),
        "controller_child_adoption_summary_path": str(
            controller_child_adoption_summary_path(root)
        ),
        "controller_librarian_mission_improvement_path": str(
            controller_librarian_mission_improvement_path(root)
        ),
        "controller_verifier_mission_improvement_path": str(
            controller_verifier_mission_improvement_path(root)
        ),
        "controller_sequential_delegation_workflow_path": str(
            controller_sequential_delegation_workflow_path(root)
        ),
        "controller_mission_delegation_plan_path": str(
            controller_mission_delegation_plan_path(root)
        ),
        "controller_child_admissibility_path": str(
            controller_child_admissibility_path(root)
        ),
        "controller_blocked_delegation_options_path": str(
            controller_blocked_delegation_options_path(root)
        ),
        "controller_typed_handoff_contract_path": str(
            controller_typed_handoff_contract_path(root)
        ),
        "controller_delegation_outcome_path": str(
            controller_delegation_outcome_path(root)
        ),
        "controller_delegation_path_history_path": str(
            controller_delegation_path_history_path(root)
        ),
        "controller_path_selection_evidence_path": str(
            controller_path_selection_evidence_path(root)
        ),
        "controller_recommendation_support_path": str(
            controller_recommendation_support_path(root)
        ),
        "controller_recommendation_audit_path": str(
            controller_recommendation_audit_path(root)
        ),
        "controller_recommendation_audit_history_path": str(
            controller_recommendation_audit_history_path(root)
        ),
        "controller_recommendation_calibration_summary_path": str(
            controller_recommendation_calibration_summary_path(root)
        ),
        "controller_recommendation_governance_path": str(
            controller_recommendation_governance_path(root)
        ),
        "controller_recommendation_override_path": str(
            controller_recommendation_override_path(root)
        ),
        "controller_recommendation_override_history_path": str(
            controller_recommendation_override_history_path(root)
        ),
        "controller_intervention_audit_path": str(
            controller_intervention_audit_path(root)
        ),
        "controller_intervention_audit_history_path": str(
            controller_intervention_audit_history_path(root)
        ),
        "controller_intervention_calibration_summary_path": str(
            controller_intervention_calibration_summary_path(root)
        ),
        "controller_intervention_prudence_path": str(
            controller_intervention_prudence_path(root)
        ),
        "controller_intervention_prudence_history_path": str(
            controller_intervention_prudence_history_path(root)
        ),
        "controller_recommendation_trust_signal_path": str(
            controller_recommendation_trust_signal_path(root)
        ),
        "controller_governance_summary_path": str(
            controller_governance_summary_path(root)
        ),
        "controller_governance_summary_history_path": str(
            controller_governance_summary_history_path(root)
        ),
        "controller_recommendation_state_summary_path": str(
            controller_recommendation_state_summary_path(root)
        ),
        "controller_governance_trend_path": str(
            controller_governance_trend_path(root)
        ),
        "controller_governance_trend_history_path": str(
            controller_governance_trend_history_path(root)
        ),
        "controller_temporal_drift_summary_path": str(
            controller_temporal_drift_summary_path(root)
        ),
        "controller_operator_guidance_path": str(
            controller_operator_guidance_path(root)
        ),
        "controller_operator_guidance_history_path": str(
            controller_operator_guidance_history_path(root)
        ),
        "controller_action_guidance_summary_path": str(
            controller_action_guidance_summary_path(root)
        ),
        "controller_action_readiness_path": str(
            controller_action_readiness_path(root)
        ),
        "controller_action_readiness_history_path": str(
            controller_action_readiness_history_path(root)
        ),
        "controller_guided_handoff_summary_path": str(
            controller_guided_handoff_summary_path(root)
        ),
        "controller_operator_flow_path": str(
            controller_operator_flow_path(root)
        ),
        "controller_operator_flow_history_path": str(
            controller_operator_flow_history_path(root)
        ),
        "controller_demo_readiness_summary_path": str(
            controller_demo_readiness_summary_path(root)
        ),
        "controller_demo_scenario_path": str(
            controller_demo_scenario_path(root)
        ),
        "controller_demo_scenario_history_path": str(
            controller_demo_scenario_history_path(root)
        ),
        "controller_demo_run_readiness_path": str(
            controller_demo_run_readiness_path(root)
        ),
        "controller_demo_operator_walkthrough_path": str(
            controller_demo_operator_walkthrough_path(root)
        ),
        "controller_demo_success_rubric_path": str(
            controller_demo_success_rubric_path(root)
        ),
        "controller_demo_execution_path": str(
            controller_demo_execution_path(root)
        ),
        "controller_demo_execution_history_path": str(
            controller_demo_execution_history_path(root)
        ),
        "controller_demo_result_summary_path": str(
            controller_demo_result_summary_path(root)
        ),
        "controller_demo_output_inventory_path": str(
            controller_demo_output_inventory_path(root)
        ),
        "controller_demo_evidence_trail_path": str(
            controller_demo_evidence_trail_path(root)
        ),
        "controller_demo_output_completion_path": str(
            controller_demo_output_completion_path(root)
        ),
        "controller_demo_output_completion_history_path": str(
            controller_demo_output_completion_history_path(root)
        ),
        "controller_demo_reviewable_artifacts_path": str(
            controller_demo_reviewable_artifacts_path(root)
        ),
        "controller_demo_completion_summary_path": str(
            controller_demo_completion_summary_path(root)
        ),
        "controller_trusted_demo_scenario_path": str(
            controller_trusted_demo_scenario_path(root)
        ),
        "controller_trusted_demo_scenario_history_path": str(
            controller_trusted_demo_scenario_history_path(root)
        ),
        "controller_trusted_demo_directive_path": str(
            controller_trusted_demo_directive_path(root)
        ),
        "controller_trusted_demo_success_rubric_path": str(
            controller_trusted_demo_success_rubric_path(root)
        ),
        "controller_trusted_demo_skill_target_path": str(
            controller_trusted_demo_skill_target_path(root)
        ),
        "controller_trusted_demo_selection_rationale_path": str(
            controller_trusted_demo_selection_rationale_path(root)
        ),
        "controller_trusted_demo_local_first_analysis_path": str(
            controller_trusted_demo_local_first_analysis_path(root)
        ),
        "controller_trusted_demo_knowledge_gap_path": str(
            controller_trusted_demo_knowledge_gap_path(root)
        ),
        "controller_trusted_demo_knowledge_gap_history_path": str(
            controller_trusted_demo_knowledge_gap_history_path(root)
        ),
        "controller_trusted_demo_request_path": str(
            controller_trusted_demo_request_path(root)
        ),
        "controller_trusted_demo_request_history_path": str(
            controller_trusted_demo_request_history_path(root)
        ),
        "controller_trusted_demo_response_summary_path": str(
            controller_trusted_demo_response_summary_path(root)
        ),
        "controller_trusted_demo_incorporation_path": str(
            controller_trusted_demo_incorporation_path(root)
        ),
        "controller_trusted_demo_growth_artifact_path": str(
            controller_trusted_demo_growth_artifact_path(root)
        ),
        "controller_trusted_demo_growth_artifact_history_path": str(
            controller_trusted_demo_growth_artifact_history_path(root)
        ),
        "controller_trusted_demo_delta_summary_path": str(
            controller_trusted_demo_delta_summary_path(root)
        ),
        "controller_trusted_live_connectivity_path": str(
            controller_trusted_live_connectivity_path(root)
        ),
        "controller_trusted_live_connectivity_history_path": str(
            controller_trusted_live_connectivity_history_path(root)
        ),
        "controller_trusted_live_request_path": str(
            controller_trusted_live_request_path(root)
        ),
        "controller_trusted_live_response_summary_path": str(
            controller_trusted_live_response_summary_path(root)
        ),
        "controller_trusted_live_evidence_receipt_path": str(
            controller_trusted_live_evidence_receipt_path(root)
        ),
        "controller_trusted_live_validation_summary_path": str(
            controller_trusted_live_validation_summary_path(root)
        ),
        "controller_trusted_demo_live_request_path": str(
            controller_trusted_demo_live_request_path(root)
        ),
        "controller_trusted_demo_live_request_history_path": str(
            controller_trusted_demo_live_request_history_path(root)
        ),
        "controller_trusted_demo_live_response_summary_path": str(
            controller_trusted_demo_live_response_summary_path(root)
        ),
        "controller_trusted_demo_live_evidence_receipt_path": str(
            controller_trusted_demo_live_evidence_receipt_path(root)
        ),
        "controller_trusted_demo_live_incorporation_path": str(
            controller_trusted_demo_live_incorporation_path(root)
        ),
        "controller_trusted_demo_growth_artifact_update_path": str(
            controller_trusted_demo_growth_artifact_update_path(root)
        ),
        "controller_trusted_demo_growth_artifact_update_history_path": str(
            controller_trusted_demo_growth_artifact_update_history_path(root)
        ),
        "controller_trusted_demo_before_after_delta_path": str(
            controller_trusted_demo_before_after_delta_path(root)
        ),
        "controller_recommendation_window_path": str(
            controller_recommendation_window_path(root)
        ),
        "controller_recommendation_stability_path": str(
            controller_recommendation_stability_path(root)
        ),
        "controller_recommendation_stability_history_path": str(
            controller_recommendation_stability_history_path(root)
        ),
    }


def load_runtime_constraints(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(operator_runtime_constraints_path(root))


def load_runtime_envelope_spec(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(operator_runtime_envelope_spec_path(root))


def load_runtime_constraints_or_default(
    *,
    root: str | Path | None = None,
    package_root: str | Path | None = None,
) -> dict[str, Any]:
    payload = load_runtime_constraints(root)
    return payload if payload else build_default_runtime_constraints(package_root)


def load_runtime_envelope_spec_or_default(
    *,
    root: str | Path | None = None,
    package_root: str | Path | None = None,
) -> dict[str, Any]:
    payload = load_runtime_envelope_spec(root)
    return payload if payload else build_default_operator_runtime_envelope_spec(package_root)


def load_trusted_source_bindings(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(trusted_source_bindings_path(root))


def load_trusted_source_bindings_or_default(
    *,
    root: str | Path | None = None,
    package_root: str | Path | None = None,
) -> dict[str, Any]:
    payload = load_trusted_source_bindings(root)
    return payload if payload else build_default_trusted_source_bindings(package_root)


def load_trusted_source_secrets(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(trusted_source_secrets_path(root))


def load_trusted_source_secrets_or_default(root: str | Path | None = None) -> dict[str, Any]:
    payload = load_trusted_source_secrets(root)
    return payload if payload else build_default_trusted_source_secrets()


def load_trusted_source_credential_status(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(trusted_source_credential_status_path(root))


def load_trusted_source_provider_status(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(trusted_source_provider_status_path(root))


def load_trusted_source_handshake(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(trusted_source_handshake_path(root))


def load_trusted_source_session_contract(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(trusted_source_session_contract_path(root))


def load_trusted_source_request_contract(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(trusted_source_request_contract_path(root))


def load_trusted_source_response_template(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(trusted_source_response_template_path(root))


def load_operator_run_preset(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(operator_run_preset_path(root))


def load_trusted_source_operator_policy(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(trusted_source_operator_policy_path(root))


def load_operator_session_state(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(operator_session_state_path(root))


def load_operator_resume_summary(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(operator_resume_summary_path(root))


def load_operator_session_continuity(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(operator_session_continuity_path(root))


def load_operator_current_session_summary(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(operator_current_session_summary_path(root))


def load_operator_next_action_summary(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(operator_next_action_summary_path(root))


def load_operator_resume_policy_summary(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(operator_resume_policy_summary_path(root))


def load_operator_review_queue(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(operator_review_queue_path(root))


def load_operator_intervention_summary(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(operator_intervention_summary_path(root))


def load_operator_pending_decisions(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(operator_pending_decisions_path(root))


def load_operator_review_reason(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(operator_review_reason_path(root))


def load_operator_intervention_options(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(operator_intervention_options_path(root))


def load_operator_review_decision(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(operator_review_decision_path(root))


def load_operator_review_action_execution(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(operator_review_action_execution_path(root))


def load_operator_review_resolution(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(operator_review_resolution_path(root))


def load_controller_delegation_contract(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_delegation_contract_path(root))


def load_controller_child_registry(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(controller_child_registry_path(root))


def load_controller_resource_lease(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(controller_resource_lease_path(root))


def load_controller_delegation_state(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(controller_delegation_state_path(root))


def load_child_authority_scope(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(child_authority_scope_path(root))


def load_child_stop_condition(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(child_stop_condition_path(root))


def load_child_return_contract(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(child_return_contract_path(root))


def load_verifier_checklist(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(verifier_checklist_path(root))


def load_verifier_adoption_readiness(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(verifier_adoption_readiness_path(root))


def load_verifier_integrity_summary(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(verifier_integrity_summary_path(root))


def load_child_budget_state(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(child_budget_state_path(root))


def load_child_termination_summary(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(child_termination_summary_path(root))


def load_controller_child_task_assignment(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_child_task_assignment_path(root))


def load_child_task_result(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(child_task_result_path(root))


def load_child_artifact_bundle(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(child_artifact_bundle_path(root))


def load_controller_child_return_summary(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_child_return_summary_path(root))


def load_controller_child_adoption_decision(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_child_adoption_decision_path(root))


def load_controller_child_review(root: str | Path | None = None) -> dict[str, Any]:
    return _load_json(controller_child_review_path(root))


def load_controller_delegation_decision(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_delegation_decision_path(root))


def load_controller_child_adoption_summary(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_child_adoption_summary_path(root))


def load_controller_librarian_mission_improvement(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_librarian_mission_improvement_path(root))


def load_controller_verifier_mission_improvement(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_verifier_mission_improvement_path(root))


def load_controller_sequential_delegation_workflow(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_sequential_delegation_workflow_path(root))


def load_controller_mission_delegation_plan(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_mission_delegation_plan_path(root))


def load_controller_child_admissibility(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_child_admissibility_path(root))


def load_controller_blocked_delegation_options(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_blocked_delegation_options_path(root))


def load_controller_typed_handoff_contract(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_typed_handoff_contract_path(root))


def load_controller_delegation_outcome(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_delegation_outcome_path(root))


def load_controller_delegation_path_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_delegation_path_history_path(root))


def load_controller_path_selection_evidence(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_path_selection_evidence_path(root))


def load_controller_recommendation_support(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_recommendation_support_path(root))


def load_controller_recommendation_audit(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_recommendation_audit_path(root))


def load_controller_recommendation_audit_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_recommendation_audit_history_path(root))


def load_controller_recommendation_calibration_summary(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_recommendation_calibration_summary_path(root))


def load_controller_recommendation_window(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_recommendation_window_path(root))


def load_controller_recommendation_stability(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_recommendation_stability_path(root))


def load_controller_recommendation_stability_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_recommendation_stability_history_path(root))


def load_controller_recommendation_governance(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_recommendation_governance_path(root))


def load_controller_recommendation_override(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_recommendation_override_path(root))


def load_controller_recommendation_override_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_recommendation_override_history_path(root))


def load_controller_intervention_audit(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_intervention_audit_path(root))


def load_controller_intervention_audit_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_intervention_audit_history_path(root))


def load_controller_intervention_calibration_summary(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_intervention_calibration_summary_path(root))


def load_controller_intervention_prudence(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_intervention_prudence_path(root))


def load_controller_intervention_prudence_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_intervention_prudence_history_path(root))


def load_controller_recommendation_trust_signal(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_recommendation_trust_signal_path(root))


def load_controller_governance_summary(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_governance_summary_path(root))


def load_controller_governance_summary_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_governance_summary_history_path(root))


def load_controller_recommendation_state_summary(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_recommendation_state_summary_path(root))


def load_controller_governance_trend(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_governance_trend_path(root))


def load_controller_governance_trend_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_governance_trend_history_path(root))


def load_controller_temporal_drift_summary(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_temporal_drift_summary_path(root))


def load_controller_operator_guidance(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_operator_guidance_path(root))


def load_controller_operator_guidance_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_operator_guidance_history_path(root))


def load_controller_action_guidance_summary(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_action_guidance_summary_path(root))


def load_controller_action_readiness(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_action_readiness_path(root))


def load_controller_action_readiness_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_action_readiness_history_path(root))


def load_controller_guided_handoff_summary(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_guided_handoff_summary_path(root))


def load_controller_operator_flow(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_operator_flow_path(root))


def load_controller_operator_flow_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_operator_flow_history_path(root))


def load_controller_demo_readiness_summary(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_readiness_summary_path(root))


def load_controller_demo_scenario(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_scenario_path(root))


def load_controller_demo_scenario_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_scenario_history_path(root))


def load_controller_demo_run_readiness(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_run_readiness_path(root))


def load_controller_demo_operator_walkthrough(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_operator_walkthrough_path(root))


def load_controller_demo_success_rubric(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_success_rubric_path(root))


def load_controller_demo_execution(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_execution_path(root))


def load_controller_demo_execution_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_execution_history_path(root))


def load_controller_demo_result_summary(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_result_summary_path(root))


def load_controller_demo_output_inventory(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_output_inventory_path(root))


def load_controller_demo_evidence_trail(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_evidence_trail_path(root))


def load_controller_demo_output_completion(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_output_completion_path(root))


def load_controller_demo_output_completion_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_output_completion_history_path(root))


def load_controller_demo_reviewable_artifacts(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_reviewable_artifacts_path(root))


def load_controller_demo_completion_summary(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_completion_summary_path(root))


def load_controller_trusted_demo_scenario(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_demo_scenario_path(root))


def load_controller_trusted_demo_scenario_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_demo_scenario_history_path(root))


def load_controller_trusted_demo_directive(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_demo_directive_path(root))


def load_controller_trusted_demo_success_rubric(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_demo_success_rubric_path(root))


def load_controller_trusted_demo_skill_target(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_demo_skill_target_path(root))


def load_controller_trusted_demo_selection_rationale(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_demo_selection_rationale_path(root))


def load_controller_trusted_demo_local_first_analysis(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_demo_local_first_analysis_path(root))


def load_controller_trusted_demo_knowledge_gap(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_demo_knowledge_gap_path(root))


def load_controller_trusted_demo_knowledge_gap_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_demo_knowledge_gap_history_path(root))


def load_controller_trusted_demo_request(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_demo_request_path(root))


def load_controller_trusted_demo_request_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_demo_request_history_path(root))


def load_controller_trusted_demo_response_summary(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_demo_response_summary_path(root))


def load_controller_trusted_demo_incorporation(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_demo_incorporation_path(root))


def load_controller_trusted_demo_growth_artifact(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_demo_growth_artifact_path(root))


def load_controller_trusted_demo_growth_artifact_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_demo_growth_artifact_history_path(root))


def load_controller_trusted_demo_delta_summary(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_demo_delta_summary_path(root))


def load_controller_trusted_live_connectivity(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_live_connectivity_path(root))


def load_controller_trusted_live_connectivity_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_live_connectivity_history_path(root))


def load_controller_trusted_live_request(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_live_request_path(root))


def load_controller_trusted_live_response_summary(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_live_response_summary_path(root))


def load_controller_trusted_live_evidence_receipt(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_live_evidence_receipt_path(root))


def load_controller_trusted_live_validation_summary(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_live_validation_summary_path(root))


def load_controller_trusted_demo_live_request(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_demo_live_request_path(root))


def load_controller_trusted_demo_live_request_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_demo_live_request_history_path(root))


def load_controller_trusted_demo_live_response_summary(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_demo_live_response_summary_path(root))


def load_controller_trusted_demo_live_evidence_receipt(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_demo_live_evidence_receipt_path(root))


def load_controller_trusted_demo_live_incorporation(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_demo_live_incorporation_path(root))


def load_controller_trusted_demo_growth_artifact_update(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_demo_growth_artifact_update_path(root))


def load_controller_trusted_demo_growth_artifact_update_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_demo_growth_artifact_update_history_path(root))


def load_controller_trusted_demo_before_after_delta(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_trusted_demo_before_after_delta_path(root))


def load_controller_demo_storyline(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_storyline_path(root))


def load_controller_demo_storyline_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_storyline_history_path(root))


def load_controller_demo_presentation_summary(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_presentation_summary_path(root))


def load_controller_demo_narration_guide(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_narration_guide_path(root))


def load_controller_demo_review_readiness(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_review_readiness_path(root))


def load_controller_demo_runbook(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_runbook_path(root))


def load_controller_demo_runbook_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_runbook_history_path(root))


def load_controller_demo_facilitator_checklist(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_facilitator_checklist_path(root))


def load_controller_demo_checkpoint_summary(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_checkpoint_summary_path(root))


def load_controller_demo_acceptance_rubric(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_acceptance_rubric_path(root))


def load_controller_demo_packaged_completeness(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_packaged_completeness_path(root))


def load_controller_demo_packaged_completeness_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_packaged_completeness_history_path(root))


def load_controller_demo_packaged_artifact_inventory(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_packaged_artifact_inventory_path(root))


def load_controller_demo_packaged_checkpoint_closure(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_packaged_checkpoint_closure_path(root))


def load_controller_demo_packaged_rubric_justification(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_packaged_rubric_justification_path(root))


def load_controller_demo_presenter_handoff(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_presenter_handoff_path(root))


def load_controller_demo_presenter_handoff_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_presenter_handoff_history_path(root))


def load_controller_demo_quickstart_sheet(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_quickstart_sheet_path(root))


def load_controller_demo_audience_summary(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_audience_summary_path(root))


def load_controller_demo_pre_demo_sanity(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_pre_demo_sanity_path(root))


def load_controller_demo_post_demo_review(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_post_demo_review_path(root))


def load_controller_demo_short_form(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_short_form_path(root))


def load_controller_demo_short_form_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_short_form_history_path(root))


def load_controller_demo_full_walkthrough(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_full_walkthrough_path(root))


def load_controller_demo_must_show_checkpoints(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_must_show_checkpoints_path(root))


def load_controller_demo_audience_mode_optimization(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_demo_audience_mode_optimization_path(root))


def load_controller_real_work_benchmark(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_path(root))


def load_controller_real_work_benchmark_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_history_path(root))


def load_controller_real_work_benchmark_directive(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_directive_path(root))


def load_controller_real_work_benchmark_output_contract(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_output_contract_path(root))


def load_controller_real_work_benchmark_success_rubric(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_success_rubric_path(root))


def load_controller_real_work_benchmark_operator_value(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_operator_value_path(root))


def load_controller_real_work_benchmark_selection_rationale(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_selection_rationale_path(root))


def load_controller_real_work_benchmark_execution(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_execution_path(root))


def load_controller_real_work_benchmark_execution_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_execution_history_path(root))


def load_controller_real_work_benchmark_result_summary(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_result_summary_path(root))


def load_controller_real_work_benchmark_output_inventory(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_output_inventory_path(root))


def load_controller_real_work_benchmark_rubric_result(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_rubric_result_path(root))


def load_controller_real_work_benchmark_closure(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_closure_path(root))


def load_controller_real_work_benchmark_closure_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_closure_history_path(root))


def load_controller_real_work_benchmark_repeatability(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_repeatability_path(root))


def load_controller_real_work_benchmark_repeatability_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_repeatability_history_path(root))


def load_controller_real_work_benchmark_promotion_readiness(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_promotion_readiness_path(root))


def load_controller_real_work_benchmark_unresolved_bundle(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_unresolved_bundle_path(root))


def load_controller_real_work_benchmark_delta_from_rc46(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_delta_from_rc46_path(root))


def load_controller_real_work_benchmark_decision_packet(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_decision_packet_path(root))


def load_controller_real_work_benchmark_decision_packet_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_decision_packet_history_path(root))


def load_controller_real_work_benchmark_promotion_decision(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_promotion_decision_path(root))


def load_controller_real_work_benchmark_review_gate_packet(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_review_gate_packet_path(root))


def load_controller_real_work_benchmark_final_blocker(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_final_blocker_path(root))


def load_controller_real_work_benchmark_decision_rationale(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_decision_rationale_path(root))


def load_controller_real_work_benchmark_next_action(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_next_action_path(root))


def load_controller_real_work_benchmark_review_packet(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_review_packet_path(root))


def load_controller_real_work_benchmark_review_packet_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_review_packet_history_path(root))


def load_controller_real_work_benchmark_operator_review_decision(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_operator_review_decision_path(root))


def load_controller_real_work_benchmark_promotion_outcome(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_promotion_outcome_path(root))


def load_controller_real_work_benchmark_operator_confirmation_state(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(
        controller_real_work_benchmark_operator_confirmation_state_path(root)
    )


def load_controller_real_work_benchmark_review_evidence(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_review_evidence_path(root))


def load_controller_real_work_benchmark_review_checklist(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_review_checklist_path(root))


def load_controller_real_work_benchmark_review_confirmation(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_review_confirmation_path(root))


def load_controller_real_work_benchmark_review_confirmation_history(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(
        controller_real_work_benchmark_review_confirmation_history_path(root)
    )


def load_controller_real_work_benchmark_review_decision_source(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_review_decision_source_path(root))


def load_controller_real_work_benchmark_promotion_outcome_confirmed(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(
        controller_real_work_benchmark_promotion_outcome_confirmed_path(root)
    )


def load_controller_real_work_benchmark_review_resolution_summary(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(
        controller_real_work_benchmark_review_resolution_summary_path(root)
    )


def load_controller_real_work_benchmark_confirmation_gap(
    root: str | Path | None = None,
) -> dict[str, Any]:
    return _load_json(controller_real_work_benchmark_confirmation_gap_path(root))


def load_trusted_source_operator_policy_or_default(
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:
    payload = load_trusted_source_operator_policy(root)
    return (
        _trusted_source_operator_policy_views(payload)[0]
        if payload
        else _trusted_source_operator_policy_views(
            build_default_trusted_source_operator_policy()
        )[0]
    )


def infer_operator_run_preset(
    *,
    root: str | Path | None = None,
    package_root: str | Path | None = None,
) -> dict[str, Any]:
    operator_policy_payload = load_trusted_source_operator_policy_or_default(root=root)
    runtime_payload = load_runtime_constraints_or_default(root=root, package_root=package_root)
    for preset_id in (
        OPERATOR_RUN_PRESET_LONG_RUN_LOW_TOUCH,
        OPERATOR_RUN_PRESET_FOCUSED_TIGHTER_CONTROL,
    ):
        preset_payload = build_operator_run_preset(preset_id)
        if _operator_run_preset_matches_policy(
            preset_payload,
            operator_policy_payload=operator_policy_payload,
        ):
            return preset_payload
    return _custom_operator_run_preset_payload(
        operator_policy_payload=operator_policy_payload,
        runtime_payload=runtime_payload,
    )


def load_operator_run_preset_or_default(
    *,
    root: str | Path | None = None,
    package_root: str | Path | None = None,
) -> dict[str, Any]:
    payload = load_operator_run_preset(root)
    if payload:
        return payload
    return infer_operator_run_preset(root=root, package_root=package_root)


def save_runtime_constraints(payload: dict[str, Any], *, root: str | Path | None = None) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(operator_runtime_constraints_path(root), payload)


def save_runtime_envelope_spec(payload: dict[str, Any], *, root: str | Path | None = None) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(operator_runtime_envelope_spec_path(root), payload)


def save_trusted_source_bindings(payload: dict[str, Any], *, root: str | Path | None = None) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(trusted_source_bindings_path(root), payload)


def save_trusted_source_secrets(payload: dict[str, Any], *, root: str | Path | None = None) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(trusted_source_secrets_path(root), payload)


def save_trusted_source_credential_status(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(trusted_source_credential_status_path(root), payload)


def save_trusted_source_provider_status(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(trusted_source_provider_status_path(root), payload)


def save_trusted_source_handshake(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(trusted_source_handshake_path(root), payload)


def save_trusted_source_session_contract(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(trusted_source_session_contract_path(root), payload)


def save_trusted_source_request_contract(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(trusted_source_request_contract_path(root), payload)


def save_trusted_source_response_template(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(trusted_source_response_template_path(root), payload)


def save_operator_session_state(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(operator_session_state_path(root), payload)


def save_operator_resume_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(operator_resume_summary_path(root), payload)


def save_operator_session_continuity(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(operator_session_continuity_path(root), payload)


def save_operator_current_session_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(operator_current_session_summary_path(root), payload)


def save_operator_next_action_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(operator_next_action_summary_path(root), payload)


def save_operator_resume_policy_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(operator_resume_policy_summary_path(root), payload)


def save_operator_review_queue(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(operator_review_queue_path(root), payload)


def save_operator_intervention_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(operator_intervention_summary_path(root), payload)


def save_operator_pending_decisions(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(operator_pending_decisions_path(root), payload)


def save_operator_review_reason(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(operator_review_reason_path(root), payload)


def save_operator_intervention_options(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(operator_intervention_options_path(root), payload)


def save_operator_review_decision(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(operator_review_decision_path(root), payload)


def save_operator_review_action_execution(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(operator_review_action_execution_path(root), payload)


def save_operator_review_resolution(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(operator_review_resolution_path(root), payload)


def save_controller_delegation_contract(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_delegation_contract_path(root), payload)


def save_controller_child_registry(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_child_registry_path(root), payload)


def save_controller_resource_lease(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_resource_lease_path(root), payload)


def save_controller_delegation_state(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_delegation_state_path(root), payload)


def save_child_authority_scope(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(child_authority_scope_path(root), payload)


def save_child_stop_condition(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(child_stop_condition_path(root), payload)


def save_child_return_contract(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(child_return_contract_path(root), payload)


def save_verifier_checklist(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(verifier_checklist_path(root), payload)


def save_verifier_adoption_readiness(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(verifier_adoption_readiness_path(root), payload)


def save_verifier_integrity_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(verifier_integrity_summary_path(root), payload)


def save_child_budget_state(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(child_budget_state_path(root), payload)


def save_child_termination_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(child_termination_summary_path(root), payload)


def save_controller_child_task_assignment(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_child_task_assignment_path(root), payload)


def save_child_task_result(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(child_task_result_path(root), payload)


def save_child_artifact_bundle(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(child_artifact_bundle_path(root), payload)


def save_controller_child_return_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_child_return_summary_path(root), payload)


def save_controller_child_adoption_decision(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_child_adoption_decision_path(root), payload)


def save_controller_child_review(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_child_review_path(root), payload)


def save_controller_delegation_decision(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_delegation_decision_path(root), payload)


def save_controller_child_adoption_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_child_adoption_summary_path(root), payload)


def save_controller_librarian_mission_improvement(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_librarian_mission_improvement_path(root), payload)


def save_controller_verifier_mission_improvement(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_verifier_mission_improvement_path(root), payload)


def save_controller_sequential_delegation_workflow(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_sequential_delegation_workflow_path(root), payload)


def save_controller_mission_delegation_plan(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_mission_delegation_plan_path(root), payload)


def save_controller_child_admissibility(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_child_admissibility_path(root), payload)


def save_controller_blocked_delegation_options(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_blocked_delegation_options_path(root), payload)


def save_controller_typed_handoff_contract(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_typed_handoff_contract_path(root), payload)


def save_controller_delegation_outcome(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_delegation_outcome_path(root), payload)


def save_controller_delegation_path_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_delegation_path_history_path(root), payload)


def save_controller_path_selection_evidence(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_path_selection_evidence_path(root), payload)


def save_controller_recommendation_support(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_recommendation_support_path(root), payload)


def save_controller_recommendation_audit(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_recommendation_audit_path(root), payload)


def save_controller_recommendation_audit_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_recommendation_audit_history_path(root), payload)


def save_controller_recommendation_calibration_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_recommendation_calibration_summary_path(root), payload)


def save_controller_recommendation_window(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_recommendation_window_path(root), payload)


def save_controller_recommendation_stability(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_recommendation_stability_path(root), payload)


def save_controller_recommendation_stability_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_recommendation_stability_history_path(root), payload)


def save_controller_recommendation_governance(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_recommendation_governance_path(root), payload)


def save_controller_recommendation_override(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_recommendation_override_path(root), payload)


def save_controller_recommendation_override_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_recommendation_override_history_path(root), payload)


def save_controller_intervention_audit(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_intervention_audit_path(root), payload)


def save_controller_intervention_audit_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_intervention_audit_history_path(root), payload)


def save_controller_intervention_calibration_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_intervention_calibration_summary_path(root), payload)


def save_controller_intervention_prudence(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_intervention_prudence_path(root), payload)


def save_controller_intervention_prudence_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_intervention_prudence_history_path(root), payload)


def save_controller_recommendation_trust_signal(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_recommendation_trust_signal_path(root), payload)


def save_controller_governance_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_governance_summary_path(root), payload)


def save_controller_governance_summary_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_governance_summary_history_path(root), payload)


def save_controller_recommendation_state_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_recommendation_state_summary_path(root), payload)


def save_controller_governance_trend(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_governance_trend_path(root), payload)


def save_controller_governance_trend_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_governance_trend_history_path(root), payload)


def save_controller_temporal_drift_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_temporal_drift_summary_path(root), payload)


def save_controller_operator_guidance(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_operator_guidance_path(root), payload)


def save_controller_operator_guidance_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_operator_guidance_history_path(root), payload)


def save_controller_action_guidance_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_action_guidance_summary_path(root), payload)


def save_controller_action_readiness(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_action_readiness_path(root), payload)


def save_controller_action_readiness_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_action_readiness_history_path(root), payload)


def save_controller_guided_handoff_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_guided_handoff_summary_path(root), payload)


def save_controller_operator_flow(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_operator_flow_path(root), payload)


def save_controller_operator_flow_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_operator_flow_history_path(root), payload)


def save_controller_demo_readiness_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_readiness_summary_path(root), payload)


def save_controller_demo_scenario(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_scenario_path(root), payload)


def save_controller_demo_scenario_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_scenario_history_path(root), payload)


def save_controller_demo_run_readiness(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_run_readiness_path(root), payload)


def save_controller_demo_operator_walkthrough(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_operator_walkthrough_path(root), payload)


def save_controller_demo_success_rubric(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_success_rubric_path(root), payload)


def save_controller_demo_execution(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_execution_path(root), payload)


def save_controller_demo_execution_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_execution_history_path(root), payload)


def save_controller_demo_result_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_result_summary_path(root), payload)


def save_controller_demo_output_inventory(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_output_inventory_path(root), payload)


def save_controller_demo_evidence_trail(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_evidence_trail_path(root), payload)


def save_controller_demo_output_completion(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_output_completion_path(root), payload)


def save_controller_demo_output_completion_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_output_completion_history_path(root), payload)


def save_controller_demo_reviewable_artifacts(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_reviewable_artifacts_path(root), payload)


def save_controller_demo_completion_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_completion_summary_path(root), payload)


def save_controller_trusted_demo_scenario(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_demo_scenario_path(root), payload)


def save_controller_trusted_demo_scenario_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_demo_scenario_history_path(root), payload)


def save_controller_trusted_demo_directive(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_demo_directive_path(root), payload)


def save_controller_trusted_demo_success_rubric(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_demo_success_rubric_path(root), payload)


def save_controller_trusted_demo_skill_target(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_demo_skill_target_path(root), payload)


def save_controller_trusted_demo_selection_rationale(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_demo_selection_rationale_path(root), payload)


def save_controller_trusted_demo_local_first_analysis(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_demo_local_first_analysis_path(root), payload)


def save_controller_trusted_demo_knowledge_gap(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_demo_knowledge_gap_path(root), payload)


def save_controller_trusted_demo_knowledge_gap_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_demo_knowledge_gap_history_path(root), payload)


def save_controller_trusted_demo_request(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_demo_request_path(root), payload)


def save_controller_trusted_demo_request_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_demo_request_history_path(root), payload)


def save_controller_trusted_demo_response_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_demo_response_summary_path(root), payload)


def save_controller_trusted_demo_incorporation(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_demo_incorporation_path(root), payload)


def save_controller_trusted_demo_growth_artifact(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_demo_growth_artifact_path(root), payload)


def save_controller_trusted_demo_growth_artifact_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_demo_growth_artifact_history_path(root), payload)


def save_controller_trusted_demo_delta_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_demo_delta_summary_path(root), payload)


def save_controller_trusted_live_connectivity(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_live_connectivity_path(root), payload)


def save_controller_trusted_live_connectivity_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_live_connectivity_history_path(root), payload)


def save_controller_trusted_live_request(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_live_request_path(root), payload)


def save_controller_trusted_live_response_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_live_response_summary_path(root), payload)


def save_controller_trusted_live_evidence_receipt(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_live_evidence_receipt_path(root), payload)


def save_controller_trusted_live_validation_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_live_validation_summary_path(root), payload)


def save_controller_trusted_demo_live_request(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_demo_live_request_path(root), payload)


def save_controller_trusted_demo_live_request_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_demo_live_request_history_path(root), payload)


def save_controller_trusted_demo_live_response_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_demo_live_response_summary_path(root), payload)


def save_controller_trusted_demo_live_evidence_receipt(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_demo_live_evidence_receipt_path(root), payload)


def save_controller_trusted_demo_live_incorporation(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_demo_live_incorporation_path(root), payload)


def save_controller_trusted_demo_growth_artifact_update(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_demo_growth_artifact_update_path(root), payload)


def save_controller_trusted_demo_growth_artifact_update_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_demo_growth_artifact_update_history_path(root), payload)


def save_controller_trusted_demo_before_after_delta(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_trusted_demo_before_after_delta_path(root), payload)


def save_controller_demo_storyline(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_storyline_path(root), payload)


def save_controller_demo_storyline_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_storyline_history_path(root), payload)


def save_controller_demo_presentation_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_presentation_summary_path(root), payload)


def save_controller_demo_narration_guide(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_narration_guide_path(root), payload)


def save_controller_demo_review_readiness(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_review_readiness_path(root), payload)


def save_controller_demo_runbook(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_runbook_path(root), payload)


def save_controller_demo_runbook_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_runbook_history_path(root), payload)


def save_controller_demo_facilitator_checklist(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_facilitator_checklist_path(root), payload)


def save_controller_demo_checkpoint_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_checkpoint_summary_path(root), payload)


def save_controller_demo_acceptance_rubric(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_acceptance_rubric_path(root), payload)


def save_controller_demo_packaged_completeness(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_packaged_completeness_path(root), payload)


def save_controller_demo_packaged_completeness_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_packaged_completeness_history_path(root), payload)


def save_controller_demo_packaged_artifact_inventory(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_packaged_artifact_inventory_path(root), payload)


def save_controller_demo_packaged_checkpoint_closure(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_packaged_checkpoint_closure_path(root), payload)


def save_controller_demo_packaged_rubric_justification(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_packaged_rubric_justification_path(root), payload)


def save_controller_demo_presenter_handoff(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_presenter_handoff_path(root), payload)


def save_controller_demo_presenter_handoff_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_presenter_handoff_history_path(root), payload)


def save_controller_demo_quickstart_sheet(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_quickstart_sheet_path(root), payload)


def save_controller_demo_audience_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_audience_summary_path(root), payload)


def save_controller_demo_pre_demo_sanity(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_pre_demo_sanity_path(root), payload)


def save_controller_demo_post_demo_review(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_post_demo_review_path(root), payload)


def save_controller_demo_short_form(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_short_form_path(root), payload)


def save_controller_demo_short_form_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_short_form_history_path(root), payload)


def save_controller_demo_full_walkthrough(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_full_walkthrough_path(root), payload)


def save_controller_demo_must_show_checkpoints(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_must_show_checkpoints_path(root), payload)


def save_controller_demo_audience_mode_optimization(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_demo_audience_mode_optimization_path(root), payload)


def save_controller_real_work_benchmark(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_path(root), payload)


def save_controller_real_work_benchmark_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_history_path(root), payload)


def save_controller_real_work_benchmark_directive(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_directive_path(root), payload)


def save_controller_real_work_benchmark_output_contract(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_output_contract_path(root), payload)


def save_controller_real_work_benchmark_success_rubric(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_success_rubric_path(root), payload)


def save_controller_real_work_benchmark_operator_value(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_operator_value_path(root), payload)


def save_controller_real_work_benchmark_selection_rationale(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_selection_rationale_path(root), payload)


def save_controller_real_work_benchmark_execution(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_execution_path(root), payload)


def save_controller_real_work_benchmark_execution_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_execution_history_path(root), payload)


def save_controller_real_work_benchmark_result_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_result_summary_path(root), payload)


def save_controller_real_work_benchmark_output_inventory(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_output_inventory_path(root), payload)


def save_controller_real_work_benchmark_rubric_result(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_rubric_result_path(root), payload)


def save_controller_real_work_benchmark_closure(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_closure_path(root), payload)


def save_controller_real_work_benchmark_closure_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_closure_history_path(root), payload)


def save_controller_real_work_benchmark_repeatability(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_repeatability_path(root), payload)


def save_controller_real_work_benchmark_repeatability_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_repeatability_history_path(root), payload)


def save_controller_real_work_benchmark_promotion_readiness(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_promotion_readiness_path(root), payload)


def save_controller_real_work_benchmark_unresolved_bundle(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_unresolved_bundle_path(root), payload)


def save_controller_real_work_benchmark_delta_from_rc46(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_delta_from_rc46_path(root), payload)


def save_controller_real_work_benchmark_decision_packet(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_decision_packet_path(root), payload)


def save_controller_real_work_benchmark_decision_packet_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(
        controller_real_work_benchmark_decision_packet_history_path(root), payload
    )


def save_controller_real_work_benchmark_promotion_decision(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_promotion_decision_path(root), payload)


def save_controller_real_work_benchmark_review_gate_packet(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(
        controller_real_work_benchmark_review_gate_packet_path(root), payload
    )


def save_controller_real_work_benchmark_final_blocker(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_final_blocker_path(root), payload)


def save_controller_real_work_benchmark_decision_rationale(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_decision_rationale_path(root), payload)


def save_controller_real_work_benchmark_next_action(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_next_action_path(root), payload)


def save_controller_real_work_benchmark_review_packet(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_review_packet_path(root), payload)


def save_controller_real_work_benchmark_review_packet_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_review_packet_history_path(root), payload)


def save_controller_real_work_benchmark_operator_review_decision(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(
        controller_real_work_benchmark_operator_review_decision_path(root), payload
    )


def save_controller_real_work_benchmark_promotion_outcome(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_promotion_outcome_path(root), payload)


def save_controller_real_work_benchmark_operator_confirmation_state(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(
        controller_real_work_benchmark_operator_confirmation_state_path(root), payload
    )


def save_controller_real_work_benchmark_review_evidence(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_review_evidence_path(root), payload)


def save_controller_real_work_benchmark_review_checklist(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_review_checklist_path(root), payload)


def save_controller_real_work_benchmark_review_confirmation(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_review_confirmation_path(root), payload)


def save_controller_real_work_benchmark_review_confirmation_history(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(
        controller_real_work_benchmark_review_confirmation_history_path(root), payload
    )


def save_controller_real_work_benchmark_review_decision_source(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(
        controller_real_work_benchmark_review_decision_source_path(root), payload
    )


def save_controller_real_work_benchmark_promotion_outcome_confirmed(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(
        controller_real_work_benchmark_promotion_outcome_confirmed_path(root), payload
    )


def save_controller_real_work_benchmark_review_resolution_summary(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(
        controller_real_work_benchmark_review_resolution_summary_path(root), payload
    )


def save_controller_real_work_benchmark_confirmation_gap(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    _require_operator_mutation_rights()
    payload = dict(payload)
    payload["generated_at"] = _now()
    _write_json(controller_real_work_benchmark_confirmation_gap_path(root), payload)


def save_trusted_source_operator_policy(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:
    _require_operator_mutation_rights()
    (
        normalized_policy,
        aggressiveness_policy_payload,
        budget_policy_payload,
        retry_policy_payload,
        escalation_thresholds_payload,
    ) = _trusted_source_operator_policy_views(dict(payload))
    _write_json(trusted_source_operator_policy_path(root), normalized_policy)
    _write_json(
        trusted_source_aggressiveness_policy_path(root),
        aggressiveness_policy_payload,
    )
    _write_json(trusted_source_budget_policy_path(root), budget_policy_payload)
    _write_json(trusted_source_retry_policy_path(root), retry_policy_payload)
    _write_json(
        trusted_source_escalation_thresholds_path(root),
        escalation_thresholds_payload,
    )
    return normalized_policy


def save_operator_run_preset(
    preset_id: str,
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:
    _require_operator_mutation_rights()
    payload = build_operator_run_preset(preset_id)
    _write_json(operator_run_preset_path(root), payload)
    return payload


def reconcile_operator_run_preset(
    *,
    root: str | Path | None = None,
    package_root: str | Path | None = None,
) -> dict[str, Any]:
    _require_operator_mutation_rights()
    payload = infer_operator_run_preset(root=root, package_root=package_root)
    _write_json(operator_run_preset_path(root), payload)
    return payload


def validate_runtime_constraints(
    payload: dict[str, Any],
    *,
    package_root: str | Path | None = None,
    operator_root: str | Path | None = None,
) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    operator_root_path = default_operator_root() if operator_root is None else Path(operator_root)
    errors: list[str] = []
    if str(payload.get("schema_name", "")) != RUNTIME_CONSTRAINTS_SCHEMA_NAME:
        errors.append(f"schema_name must be {RUNTIME_CONSTRAINTS_SCHEMA_NAME}")
    if str(payload.get("schema_version", "")) != RUNTIME_CONSTRAINTS_SCHEMA_VERSION:
        errors.append(f"schema_version must be {RUNTIME_CONSTRAINTS_SCHEMA_VERSION}")

    constraints = dict(payload.get("constraints", {}))
    execution_profile = str(
        payload.get("execution_profile", EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION)
    ).strip() or EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION
    if execution_profile not in SUPPORTED_EXECUTION_PROFILES:
        errors.append(
            "execution_profile must be one of "
            + ", ".join(sorted(SUPPORTED_EXECUTION_PROFILES))
        )
    governed_execution = dict(payload.get("governed_execution", {}))
    governed_execution_mode = str(
        governed_execution.get("mode", GOVERNED_EXECUTION_MODE_SINGLE_CYCLE)
    ).strip() or GOVERNED_EXECUTION_MODE_SINGLE_CYCLE
    if governed_execution_mode not in SUPPORTED_GOVERNED_EXECUTION_MODES:
        errors.append(
            "governed_execution.mode must be one of "
            + ", ".join(sorted(SUPPORTED_GOVERNED_EXECUTION_MODES))
        )
        governed_execution_mode = GOVERNED_EXECUTION_MODE_SINGLE_CYCLE

    raw_max_cycles_per_invocation = governed_execution.get("max_cycles_per_invocation", None)
    max_cycles_per_invocation: int | None
    if raw_max_cycles_per_invocation in {None, ""}:
        max_cycles_per_invocation = None
    else:
        try:
            max_cycles_per_invocation = int(raw_max_cycles_per_invocation)
        except (TypeError, ValueError):
            errors.append("governed_execution.max_cycles_per_invocation must be an integer or null")
            max_cycles_per_invocation = None
    if max_cycles_per_invocation is not None and max_cycles_per_invocation <= 0:
        errors.append("governed_execution.max_cycles_per_invocation must be >= 1")
        max_cycles_per_invocation = None
    if governed_execution_mode == GOVERNED_EXECUTION_MODE_SINGLE_CYCLE:
        if max_cycles_per_invocation not in {None, DEFAULT_GOVERNED_EXECUTION_MAX_CYCLES_SINGLE}:
            errors.append("governed_execution.max_cycles_per_invocation must be 1 in single_cycle mode")
        normalized_max_cycles_per_invocation = DEFAULT_GOVERNED_EXECUTION_MAX_CYCLES_SINGLE
    else:
        normalized_max_cycles_per_invocation = (
            DEFAULT_GOVERNED_EXECUTION_MAX_CYCLES_MULTI
            if max_cycles_per_invocation is None
            else max_cycles_per_invocation
        )
        if normalized_max_cycles_per_invocation < 2:
            errors.append("governed_execution.max_cycles_per_invocation must be >= 2 in multi_cycle mode")
        if normalized_max_cycles_per_invocation > MAX_GOVERNED_EXECUTION_CYCLES_PER_INVOCATION:
            errors.append(
                "governed_execution.max_cycles_per_invocation must be <= "
                f"{MAX_GOVERNED_EXECUTION_CYCLES_PER_INVOCATION}"
            )
    raw_max_total_cycles = governed_execution.get("max_total_cycles", None)
    max_total_cycles: int | None
    if raw_max_total_cycles in {None, ""}:
        max_total_cycles = None
    else:
        try:
            max_total_cycles = int(raw_max_total_cycles)
        except (TypeError, ValueError):
            errors.append("governed_execution.max_total_cycles must be an integer or null")
            max_total_cycles = None
    if max_total_cycles is not None and max_total_cycles <= 0:
        errors.append("governed_execution.max_total_cycles must be >= 1")
        max_total_cycles = None
    if governed_execution_mode == GOVERNED_EXECUTION_MODE_SINGLE_CYCLE:
        if max_total_cycles not in {None, DEFAULT_GOVERNED_EXECUTION_MAX_CYCLES_SINGLE}:
            errors.append("governed_execution.max_total_cycles must be 1 in single_cycle mode")
        normalized_max_total_cycles = DEFAULT_GOVERNED_EXECUTION_MAX_CYCLES_SINGLE
    else:
        normalized_max_total_cycles = (
            DEFAULT_GOVERNED_EXECUTION_MAX_CYCLES_MULTI
            if max_total_cycles is None
            else max_total_cycles
        )
    workspace_policy = dict(payload.get("workspace_policy", {}))
    required_keys = {
        "max_memory_mb",
        "max_python_threads",
        "max_child_processes",
        "subprocess_mode",
        "working_directory",
        "allowed_write_roots",
        "session_time_limit_seconds",
    }
    missing = sorted(required_keys - set(constraints.keys()))
    if missing:
        errors.append(f"missing runtime constraint fields: {', '.join(missing)}")

    def _positive_int(name: str) -> int | None:
        value = constraints.get(name)
        if value in {None, ""}:
            return None
        try:
            coerced = int(value)
        except (TypeError, ValueError):
            errors.append(f"{name} must be an integer or null")
            return None
        if coerced < 0:
            errors.append(f"{name} must be >= 0")
        return coerced

    max_memory_mb = _positive_int("max_memory_mb")
    max_python_threads = _positive_int("max_python_threads")
    max_child_processes = _positive_int("max_child_processes")
    session_time_limit_seconds = _positive_int("session_time_limit_seconds")

    subprocess_mode = str(constraints.get("subprocess_mode", "disabled"))
    if subprocess_mode not in {"disabled", "bounded", "allow"}:
        errors.append("subprocess_mode must be one of disabled, bounded, allow")
    if subprocess_mode == "disabled" and (max_child_processes or 0) != 0:
        errors.append("max_child_processes must be 0 when subprocess_mode is disabled")
    if subprocess_mode == "bounded" and (max_child_processes or 0) <= 0:
        errors.append("max_child_processes must be > 0 when subprocess_mode is bounded")

    working_directory = Path(str(constraints.get("working_directory", "")))
    if not str(working_directory).strip():
        errors.append("working_directory must not be empty")
    elif not working_directory.exists():
        errors.append("working_directory must exist")

    allowed_write_roots = [Path(str(item)) for item in list(constraints.get("allowed_write_roots", []))]
    if not allowed_write_roots:
        errors.append("allowed_write_roots must not be empty")
    normalized_roots: list[str] = []
    seen_roots: set[str] = set()
    for root in allowed_write_roots:
        normalized_root = _normalize_path(root)
        if not normalized_root:
            errors.append("allowed_write_roots must not contain empty entries")
            continue
        if normalized_root in seen_roots:
            continue
        seen_roots.add(normalized_root)
        normalized_roots.append(normalized_root)
        if not root.exists():
            errors.append(f"allowed_write_root does not exist: {root}")
        if _is_under_path(Path(normalized_root), operator_root_path) or _is_under_path(operator_root_path, Path(normalized_root)):
            errors.append("allowed_write_roots must not include or contain the operator policy root")

    cpu_utilization_cap_pct = constraints.get("cpu_utilization_cap_pct")
    request_rate_limit_per_minute = constraints.get("request_rate_limit_per_minute")
    network_egress_mode = str(constraints.get("network_egress_mode", "unsupported"))

    normalized_workspace_policy = {
        "workspace_base_root": _normalize_path(active_workspace_base_root(package_root_path)),
        "workspace_id": "",
        "workspace_root": "",
        "working_directory": "",
        "layout_directories": list(ACTIVE_WORKSPACE_LAYOUT_DIRECTORIES),
        "layout_paths": {},
        "generated_output_root": _normalize_path(default_generated_output_root(package_root_path)),
        "log_root": _normalize_path(default_runtime_logs_root(package_root_path)),
        "protected_root_hints": protected_runtime_root_hints(
            package_root_path,
            operator_root=operator_root_path,
        ),
    }

    if execution_profile == EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING:
        raw_workspace_id = str(
            workspace_policy.get("workspace_id", payload.get("workspace_id", ""))
        ).strip()
        if not raw_workspace_id:
            errors.append("workspace_policy.workspace_id is required for bounded_active_workspace_coding")
        workspace_layout = ensure_active_workspace_layout(
            package_root_path,
            workspace_id=raw_workspace_id or "workspace_default",
        )
        normalized_workspace_policy = {
            **normalized_workspace_policy,
            **workspace_layout,
            "protected_root_hints": protected_runtime_root_hints(
                package_root_path,
                operator_root=operator_root_path,
            ),
        }
        expected_working_directory = str(normalized_workspace_policy["working_directory"])
        if _normalize_path(working_directory) != expected_working_directory:
            errors.append(
                "working_directory must match the bounded active workspace execution profile"
            )
        expected_allowed_write_roots = [
            str(normalized_workspace_policy["workspace_root"]),
            str(normalized_workspace_policy["generated_output_root"]),
            str(normalized_workspace_policy["log_root"]),
        ]
        if set(normalized_roots) != set(expected_allowed_write_roots):
            errors.append(
                "allowed_write_roots must match the bounded active workspace execution profile"
            )
        normalized_roots = expected_allowed_write_roots
        working_directory = Path(expected_working_directory)
    else:
        normalized_workspace_policy["workspace_id"] = str(workspace_policy.get("workspace_id", "")).strip()

    normalized = {
        "schema_name": RUNTIME_CONSTRAINTS_SCHEMA_NAME,
        "schema_version": RUNTIME_CONSTRAINTS_SCHEMA_VERSION,
        "generated_at": str(payload.get("generated_at", "")) or _now(),
        "required_for_launch": bool(payload.get("required_for_launch", True)),
        "execution_profile": execution_profile,
        "governed_execution": {
            "mode": governed_execution_mode,
            "max_cycles_per_invocation": normalized_max_cycles_per_invocation,
            "max_total_cycles": normalized_max_total_cycles,
        },
        "workspace_policy": normalized_workspace_policy,
        "constraints": {
            "max_memory_mb": max_memory_mb,
            "max_python_threads": max_python_threads,
            "max_child_processes": max_child_processes,
            "subprocess_mode": subprocess_mode,
            "working_directory": _normalize_path(working_directory),
            "allowed_write_roots": normalized_roots,
            "session_time_limit_seconds": session_time_limit_seconds,
            "cpu_utilization_cap_pct": cpu_utilization_cap_pct,
            "network_egress_mode": network_egress_mode,
            "request_rate_limit_per_minute": request_rate_limit_per_minute,
        },
    }

    enforcement = {
        "max_memory_mb": {
            "enforcement_class": "watchdog_enforced" if sys.platform.startswith("win") else "unsupported_on_this_platform",
            "reason": (
                "Windows launcher polls child working-set memory and terminates on violation"
                if sys.platform.startswith("win")
                else "memory watchdog backend is only implemented for Windows in this slice"
            ),
            "requested_value": max_memory_mb,
        },
        "max_python_threads": {
            "enforcement_class": "hard_enforced",
            "reason": "Python thread starts are intercepted inside the runtime guard",
            "requested_value": max_python_threads,
        },
        "max_child_processes": {
            "enforcement_class": "hard_enforced",
            "reason": "Python subprocess and multiprocessing starts are intercepted inside the runtime guard",
            "requested_value": max_child_processes,
        },
        "subprocess_mode": {
            "enforcement_class": "hard_enforced",
            "reason": "Python subprocess spawning APIs are blocked or bounded inside the runtime guard",
            "requested_value": subprocess_mode,
        },
        "working_directory": {
            "enforcement_class": "hard_enforced",
            "reason": "launcher sets the child working directory and the runtime guard blocks cwd escapes",
            "requested_value": _normalize_path(working_directory),
        },
        "allowed_write_roots": {
            "enforcement_class": "hard_enforced",
            "reason": "runtime guard blocks normal Python mutation calls outside operator-approved write roots",
            "requested_value": normalized_roots,
        },
        "session_time_limit_seconds": {
            "enforcement_class": "watchdog_enforced",
            "reason": "launcher terminates the child process when the session time budget is exceeded",
            "requested_value": session_time_limit_seconds,
        },
        "cpu_utilization_cap_pct": {
            "enforcement_class": "unsupported_on_this_platform",
            "reason": "no conservative CPU throttling claim is made in this first operator slice",
            "requested_value": cpu_utilization_cap_pct,
        },
        "network_egress_mode": {
            "enforcement_class": "unsupported_on_this_platform",
            "reason": "no network egress sandbox is claimed in this first operator slice",
            "requested_value": network_egress_mode,
        },
        "request_rate_limit_per_minute": {
            "enforcement_class": "unsupported_on_this_platform",
            "reason": "request-rate ceilings are not claimed in this first operator slice",
            "requested_value": request_rate_limit_per_minute,
        },
        "execution_profile": {
            "enforcement_class": "hard_enforced",
            "reason": "operator-selected execution profile freezes the working directory and writable-root policy before launch",
            "requested_value": execution_profile,
        },
        "governed_execution_mode": {
            "enforcement_class": "hard_enforced",
            "reason": "operator-selected governed execution mode is frozen before launch and cannot be widened by runtime code",
            "requested_value": governed_execution_mode,
        },
        "max_cycles_per_invocation": {
            "enforcement_class": "hard_enforced",
            "reason": "operator-selected governed execution cycle cap is frozen before launch and prevents hidden infinite looping",
            "requested_value": normalized_max_cycles_per_invocation,
        },
        "max_total_cycles": {
            "enforcement_class": "hard_enforced",
            "reason": "operator-selected total governed continuation budget is frozen before launch and bounds restart-safe continuation across invocations",
            "requested_value": normalized_max_total_cycles,
        },
        "active_workspace_root": {
            "enforcement_class": (
                "hard_enforced"
                if execution_profile == EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING
                else "not_requested"
            ),
            "reason": (
                "bounded coding runs are restricted to the explicit active workspace plus approved generated-output roots"
                if execution_profile == EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING
                else "bootstrap-only initialization does not require an active coding workspace"
            ),
            "requested_value": str(normalized_workspace_policy.get("workspace_root", "")),
        },
    }
    return errors, normalized, enforcement


def validate_trusted_source_bindings(
    payload: dict[str, Any],
    *,
    secrets_payload: dict[str, Any] | None = None,
) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    errors: list[str] = []
    if str(payload.get("schema_name", "")) != TRUSTED_SOURCE_BINDINGS_SCHEMA_NAME:
        errors.append(f"schema_name must be {TRUSTED_SOURCE_BINDINGS_SCHEMA_NAME}")
    if str(payload.get("schema_version", "")) != TRUSTED_SOURCE_BINDINGS_SCHEMA_VERSION:
        errors.append(f"schema_version must be {TRUSTED_SOURCE_BINDINGS_SCHEMA_VERSION}")

    raw_bindings = list(payload.get("bindings", []))
    if not raw_bindings:
        errors.append("trusted source bindings must contain at least one binding")

    secrets_by_source = dict(dict(secrets_payload or {}).get("secrets_by_source", {}))
    normalized_bindings: list[dict[str, Any]] = []
    availability_rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for index, item in enumerate(raw_bindings):
        binding = dict(item)
        source_id = str(binding.get("source_id", "")).strip()
        source_kind = str(binding.get("source_kind", "")).strip()
        enabled = bool(binding.get("enabled", False))
        credential_strategy = str(binding.get("credential_strategy", "none")).strip() or "none"
        credential_ref = str(binding.get("credential_ref", "")).strip()
        endpoint_base = _normalize_endpoint_base(
            binding.get(
                "endpoint_base",
                "https://api.openai.com/v1" if source_id == "openai_api" else "",
            )
        )
        path_hint = _normalize_path(binding.get("path_hint", ""))

        if not source_id:
            errors.append(f"binding[{index}] source_id is required")
            source_id = f"binding_{index}"
        if source_id in seen_ids:
            errors.append(f"duplicate trusted source binding: {source_id}")
        seen_ids.add(source_id)

        if source_kind not in SUPPORTED_SOURCE_KINDS:
            errors.append(f"{source_id}: source_kind must be one of {sorted(SUPPORTED_SOURCE_KINDS)}")
        if credential_strategy not in SUPPORTED_CREDENTIAL_STRATEGIES:
            errors.append(
                f"{source_id}: credential_strategy must be one of {sorted(SUPPORTED_CREDENTIAL_STRATEGIES)}"
            )
        if any(key in binding for key in {"credential_value", "secret", "api_key", "access_token"}):
            errors.append(f"{source_id}: raw secrets must not appear in trusted_source_bindings_latest.json")

        resolved_secret_value, resolved_secret_source = resolve_trusted_source_secret(
            binding,
            secrets_payload={"secrets_by_source": secrets_by_source},
        )
        env_credential_present = bool(
            credential_strategy == "env_var" and str(resolved_secret_value).strip()
        )
        local_secret_key = credential_ref or source_id
        local_secret_present = bool(
            credential_strategy == "local_secret_store" and str(resolved_secret_value).strip()
        )
        path_exists = bool(path_hint and Path(path_hint).exists())

        ready_for_launch = False
        availability_class = "disabled"
        availability_reason = "source is disabled"
        if enabled:
            if source_kind in {"local_path", "local_bundle"}:
                ready_for_launch = path_exists
                availability_class = "ready" if ready_for_launch else "missing_path"
                availability_reason = (
                    "local trusted source path is present"
                    if ready_for_launch
                    else "local trusted source path is missing"
                )
                if not path_hint:
                    errors.append(f"{source_id}: path_hint is required for local trusted sources")
            elif source_kind == "network_api":
                if not endpoint_base:
                    errors.append(f"{source_id}: endpoint_base is required for network_api bindings")
                if credential_strategy == "none":
                    errors.append(f"{source_id}: enabled network_api bindings require a credential strategy")
                    availability_class = "missing_credential"
                    availability_reason = "enabled network API source has no credential strategy"
                elif credential_strategy == "env_var":
                    ready_for_launch = bool(endpoint_base) and env_credential_present
                    availability_class = "ready" if ready_for_launch else "missing_credential"
                    availability_reason = (
                        "required environment credential is present and endpoint base is configured"
                        if ready_for_launch
                        else (
                            "required environment credential is missing"
                            if not env_credential_present
                            else "network API endpoint base is missing"
                        )
                    )
                    if not credential_ref:
                        errors.append(f"{source_id}: credential_ref is required for env_var strategy")
                elif credential_strategy == "local_secret_store":
                    ready_for_launch = bool(endpoint_base) and local_secret_present
                    availability_class = "ready" if ready_for_launch else "missing_credential"
                    availability_reason = (
                        "required local secret is present and endpoint base is configured"
                        if ready_for_launch
                        else (
                            "required local secret is missing"
                            if not local_secret_present
                            else "network API endpoint base is missing"
                        )
                    )

        normalized_bindings.append(
            {
                "source_id": source_id,
                "source_kind": source_kind,
                "enabled": enabled,
                "credential_strategy": credential_strategy,
                "credential_ref": credential_ref,
                "endpoint_base": endpoint_base,
                "path_hint": path_hint,
            }
        )
        availability_rows.append(
            {
                "source_id": source_id,
                "source_kind": source_kind,
                "enabled": enabled,
                "credential_strategy": credential_strategy,
                "credential_ref": credential_ref,
                "endpoint_base": endpoint_base,
                "path_hint": path_hint,
                "path_exists": path_exists,
                "env_credential_present": env_credential_present,
                "local_secret_present": local_secret_present,
                "resolved_secret_source": resolved_secret_source,
                "ready_for_launch": ready_for_launch,
                "availability_class": availability_class,
                "availability_reason": availability_reason,
            }
        )

    normalized = {
        "schema_name": TRUSTED_SOURCE_BINDINGS_SCHEMA_NAME,
        "schema_version": TRUSTED_SOURCE_BINDINGS_SCHEMA_VERSION,
        "generated_at": str(payload.get("generated_at", "")) or _now(),
        "bindings": normalized_bindings,
    }
    availability = {
        "checked_at": _now(),
        "sources": availability_rows,
        "summary": {
            "ready_count": sum(1 for item in availability_rows if item["ready_for_launch"]),
            "enabled_count": sum(1 for item in availability_rows if item["enabled"]),
            "disabled_count": sum(1 for item in availability_rows if not item["enabled"]),
            "missing_path_count": sum(1 for item in availability_rows if item["availability_class"] == "missing_path"),
            "missing_credential_count": sum(
                1 for item in availability_rows if item["availability_class"] == "missing_credential"
            ),
        },
    }
    return errors, normalized, availability


def summarize_trusted_source_availability(availability: dict[str, Any]) -> dict[str, Any]:
    rows = list(availability.get("sources", []))
    return {
        "ready_sources": [item["source_id"] for item in rows if item.get("ready_for_launch")],
        "attention_required_sources": [
            item["source_id"]
            for item in rows
            if item.get("enabled") and not item.get("ready_for_launch")
        ],
        "disabled_sources": [item["source_id"] for item in rows if not item.get("enabled")],
        "summary": dict(availability.get("summary", {})),
    }


def resolve_trusted_source_secret(
    binding: dict[str, Any],
    *,
    secrets_payload: dict[str, Any] | None = None,
) -> tuple[str, str]:
    binding = dict(binding)
    strategy = str(binding.get("credential_strategy", "none")).strip() or "none"
    credential_ref = str(binding.get("credential_ref", "")).strip()
    source_id = str(binding.get("source_id", "")).strip()
    if strategy == "none":
        return "", "no_secret_required"
    if strategy == "env_var":
        if not credential_ref:
            return "", "missing_credential_ref"
        return str(os.environ.get(credential_ref, "")), "environment_variable"
    if strategy == "local_secret_store":
        secrets_by_source = dict(dict(secrets_payload or {}).get("secrets_by_source", {}))
        secret_key = credential_ref or source_id
        return str(secrets_by_source.get(secret_key, "")), "local_secret_store"
    return "", "unsupported_strategy"


def validate_effective_operator_session(
    payload: dict[str, Any],
    *,
    operator_root: str | Path | None = None,
    package_root: str | Path | None = None,
) -> list[str]:
    errors: list[str] = []
    if str(payload.get("schema_name", "")) != EFFECTIVE_OPERATOR_SESSION_SCHEMA_NAME:
        errors.append(f"schema_name must be {EFFECTIVE_OPERATOR_SESSION_SCHEMA_NAME}")
    if str(payload.get("schema_version", "")) != EFFECTIVE_OPERATOR_SESSION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {EFFECTIVE_OPERATOR_SESSION_SCHEMA_VERSION}")

    required_fields = [
        "session_id",
        "created_at",
        "operator_policy_root",
        "package_root",
        "runtime_event_log_path",
        "effective_runtime_constraints",
        "runtime_constraint_enforcement",
        "operator_runtime_envelope_spec",
        "effective_runtime_envelope",
        "trusted_source_bindings",
        "trusted_source_availability",
        "frozen_hashes",
    ]
    for field_name in required_fields:
        if not payload.get(field_name):
            errors.append(f"effective session is missing required field: {field_name}")
    if errors:
        return errors

    if operator_root is not None and _normalize_path(payload.get("operator_policy_root", "")) != _normalize_path(operator_root):
        errors.append("effective session operator_policy_root does not match the expected operator root")
    if package_root is not None and _normalize_path(payload.get("package_root", "")) != _normalize_path(package_root):
        errors.append("effective session package_root does not match the expected package root")

    mutation_lock = dict(payload.get("operator_runtime_mutation_lock", {}))
    if not bool(mutation_lock.get("enabled", False)):
        errors.append("effective session must enable operator_runtime_mutation_lock")

    frozen_hashes = dict(payload.get("frozen_hashes", {}))
    expected_session_hash = str(frozen_hashes.get("session_payload_sha256", ""))
    actual_session_hash = _stable_hash(_session_payload_without_hashes(payload))
    if expected_session_hash != actual_session_hash:
        errors.append("effective session payload hash does not match its frozen session hash")

    runtime_constraints = dict(payload.get("effective_runtime_constraints", {}))
    expected_runtime_hash = str(frozen_hashes.get("runtime_constraints_sha256", ""))
    if expected_runtime_hash != _stable_hash(runtime_constraints):
        errors.append("effective runtime constraints hash does not match the frozen session hash")

    runtime_envelope_spec = dict(payload.get("operator_runtime_envelope_spec", {}))
    expected_runtime_envelope_hash = str(frozen_hashes.get("runtime_envelope_spec_sha256", ""))
    if expected_runtime_envelope_hash != _stable_hash(runtime_envelope_spec):
        errors.append("operator runtime envelope spec hash does not match the frozen session hash")

    effective_runtime_envelope = dict(payload.get("effective_runtime_envelope", {}))
    expected_effective_envelope_hash = str(frozen_hashes.get("effective_runtime_envelope_sha256", ""))
    if expected_effective_envelope_hash != _stable_hash(effective_runtime_envelope):
        errors.append("effective runtime envelope hash does not match the frozen session hash")

    trusted_source_bindings = dict(payload.get("trusted_source_bindings", {}))
    expected_bindings_hash = str(frozen_hashes.get("trusted_source_bindings_sha256", ""))
    if expected_bindings_hash != _stable_hash(trusted_source_bindings):
        errors.append("trusted source bindings hash does not match the frozen session hash")
    trusted_source_operator_policy = dict(
        payload.get("trusted_source_operator_policy", {})
    )
    expected_operator_policy_hash = str(
        frozen_hashes.get("trusted_source_operator_policy_sha256", "")
    )
    if trusted_source_operator_policy:
        if expected_operator_policy_hash != _stable_hash(trusted_source_operator_policy):
            errors.append(
                "trusted source operator policy hash does not match the frozen session hash"
            )

    runtime_errors, _, _ = validate_runtime_constraints(
        runtime_constraints,
        package_root=package_root,
        operator_root=operator_root,
    )
    if runtime_errors:
        errors.append("effective runtime constraints are internally invalid")
        errors.extend([f"runtime_constraints::{item}" for item in runtime_errors])

    binding_errors, _, _ = validate_trusted_source_bindings(
        trusted_source_bindings,
        secrets_payload={"secrets_by_source": {}},
    )
    if binding_errors:
        errors.append("effective trusted source bindings are internally invalid")
        errors.extend([f"trusted_source_bindings::{item}" for item in binding_errors])

    envelope_errors, _, _ = validate_operator_runtime_envelope_spec(
        runtime_envelope_spec,
        runtime_constraints=runtime_constraints,
        trusted_source_bindings=trusted_source_bindings,
        enforce_backend_availability=False,
    )
    if envelope_errors:
        errors.append("effective operator runtime envelope is internally invalid")
        errors.extend([f"runtime_envelope::{item}" for item in envelope_errors])
    return errors


def load_effective_operator_session_from_file(path: str | Path) -> dict[str, Any]:
    return _load_json(Path(path))


def load_last_operator_launch_event(root: str | Path | None = None) -> dict[str, Any]:
    path = operator_launch_event_ledger_path(root)
    try:
        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except FileNotFoundError:
        return {}
    for line in reversed(lines):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return {}


def _default_runtime_event_log_path(
    *,
    normalized_constraints: dict[str, Any],
    package_root: Path,
    session_id: str,
) -> Path:
    workspace_policy = dict(normalized_constraints.get("workspace_policy", {}))
    preferred_log_root = Path(
        str(workspace_policy.get("log_root", default_runtime_logs_root(package_root)))
    )
    if preferred_log_root.exists():
        return preferred_log_root / "runtime_events" / f"{session_id}.jsonl"
    allowed_roots = [
        Path(item)
        for item in list(dict(normalized_constraints.get("constraints", {})).get("allowed_write_roots", []))
    ]
    for root in allowed_roots:
        if root.exists():
            return root / "runtime_events" / f"{session_id}.jsonl"
    return package_root / "logs" / "runtime_events" / f"{session_id}.jsonl"


def validate_existing_resume_session(
    *,
    root: str | Path | None = None,
    package_root: str | Path | None = None,
) -> tuple[dict[str, Any], list[str]]:
    session_path = effective_operator_session_path(root)
    existing_session = load_effective_operator_session_from_file(session_path)
    if not existing_session:
        return {}, ["resume requires an existing frozen operator session snapshot"]
    errors = validate_effective_operator_session(
        existing_session,
        operator_root=root,
        package_root=package_root,
    )
    return existing_session, errors


def freeze_effective_operator_session(
    *,
    root: str | Path | None = None,
    package_root: str | Path | None = None,
    directive_file: str | Path | None = None,
    clarification_file: str | Path | None = None,
    state_root: str | Path | None = None,
    entry_script: str | Path | None = None,
    runtime_args: list[str] | None = None,
    launch_kind: str = "bootstrap_only",
) -> tuple[dict[str, Any], list[str]]:
    operator_root = default_operator_root() if root is None else Path(root)
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    if directive_file is None:
        _, resume_errors = validate_existing_resume_session(
            root=operator_root,
            package_root=package_root_path,
        )
        if resume_errors:
            return {}, resume_errors

    runtime_constraints_payload = load_runtime_constraints(root)
    runtime_envelope_payload = load_runtime_envelope_spec(root)
    trusted_source_bindings_payload = load_trusted_source_bindings(root)
    trusted_source_operator_policy_payload = load_trusted_source_operator_policy_or_default(
        root=root
    )
    trusted_source_secrets_payload = load_trusted_source_secrets_or_default(root)

    errors: list[str] = []
    if not runtime_constraints_payload:
        errors.append("operator runtime constraints file is missing")
    if not runtime_envelope_payload:
        errors.append("operator runtime envelope spec file is missing")
    if not trusted_source_bindings_payload:
        errors.append("trusted source bindings file is missing")
    if errors:
        return {}, errors

    runtime_errors, normalized_constraints, enforcement = validate_runtime_constraints(
        runtime_constraints_payload,
        package_root=package_root_path,
        operator_root=operator_root,
    )
    bindings_errors, normalized_bindings, availability = validate_trusted_source_bindings(
        trusted_source_bindings_payload,
        secrets_payload=trusted_source_secrets_payload,
    )
    envelope_errors, normalized_envelope, effective_envelope = validate_operator_runtime_envelope_spec(
        runtime_envelope_payload,
        runtime_constraints=normalized_constraints,
        trusted_source_bindings=normalized_bindings,
    )
    errors.extend(runtime_errors)
    errors.extend(bindings_errors)
    errors.extend(envelope_errors)

    execution_profile = str(
        normalized_constraints.get(
            "execution_profile",
            EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION,
        )
    ).strip() or EXECUTION_PROFILE_BOOTSTRAP_ONLY_INITIALIZATION
    workspace_policy = dict(normalized_constraints.get("workspace_policy", {}))
    workspace_id = str(workspace_policy.get("workspace_id", "")).strip()
    workspace_root = str(workspace_policy.get("workspace_root", "")).strip()
    allowed_write_roots = list(
        dict(normalized_constraints.get("constraints", {})).get("allowed_write_roots", [])
    )

    if str(launch_kind).strip() == "governed_execution":
        if execution_profile != EXECUTION_PROFILE_BOUNDED_ACTIVE_WORKSPACE_CODING:
            errors.append(
                "governed_execution requires a coding-capable saved runtime policy; "
                f"current execution_profile is {execution_profile or '<missing>'}"
            )
        if not workspace_id or not workspace_root:
            errors.append(
                "governed_execution requires workspace_id and workspace_root to be materialized "
                "from the saved bounded coding profile"
            )
        elif not any(
            _is_under_path(Path(workspace_root), Path(root_item))
            for root_item in allowed_write_roots
        ):
            errors.append(
                "governed_execution requires the active workspace root to be inside an "
                "operator-approved writable root"
            )

    normalized_state_root = _normalize_path(state_root)
    if directive_file is not None and normalized_state_root:
        if allowed_write_roots and not any(
            _is_under_path(Path(normalized_state_root), Path(root_item))
            for root_item in allowed_write_roots
        ):
            errors.append(
                "fresh bootstrap requires state_root to be inside an operator-approved writable root; "
                "use bootstrap_only initialization first or select a profile that includes the state root"
            )

    if bool(runtime_constraints_payload.get("required_for_launch", True)):
        for item in list(availability.get("sources", [])):
            if item.get("enabled") and not item.get("ready_for_launch"):
                errors.append(
                    f"trusted source binding is enabled but not ready: {item.get('source_id')} ({item.get('availability_reason')})"
                )

    if errors:
        return {}, errors

    session_id = f"operator_session::{uuid.uuid4()}"
    runtime_event_log = _default_runtime_event_log_path(
        normalized_constraints=normalized_constraints,
        package_root=package_root_path,
        session_id=session_id.replace("::", "_"),
    )
    runtime_event_log.parent.mkdir(parents=True, exist_ok=True)
    session = {
        "schema_name": EFFECTIVE_OPERATOR_SESSION_SCHEMA_NAME,
        "schema_version": EFFECTIVE_OPERATOR_SESSION_SCHEMA_VERSION,
        "created_at": _now(),
        "session_id": session_id,
        "operator_policy_root": _normalize_path(operator_root),
        "package_root": _normalize_path(package_root_path),
        "state_root": _normalize_path(state_root),
        "directive_file": _normalize_path(directive_file),
        "clarification_file": _normalize_path(clarification_file),
        "entry_script": _normalize_path(entry_script),
        "launch_kind": str(launch_kind),
        "execution_profile": str(normalized_constraints.get("execution_profile", "")),
        "workspace_policy": dict(normalized_constraints.get("workspace_policy", {})),
        "runtime_args": [str(item) for item in list(runtime_args or [])],
        "runtime_event_log_path": _normalize_path(runtime_event_log),
        "effective_runtime_constraints": normalized_constraints,
        "runtime_constraint_enforcement": enforcement,
        "operator_runtime_envelope_spec": normalized_envelope,
        "effective_runtime_envelope": effective_envelope,
        "trusted_source_bindings": normalized_bindings,
        "trusted_source_operator_policy": trusted_source_operator_policy_payload,
        "trusted_source_availability": availability,
        "trusted_source_summary": summarize_trusted_source_availability(availability),
        "operator_runtime_mutation_lock": {
            "enabled": True,
            "lock_owner": "operator_shell",
            "reason": "runtime sessions may read effective constraints but may not mutate operator-owned policy",
        },
        "frozen_hashes": {
            "runtime_constraints_sha256": _stable_hash(normalized_constraints),
            "runtime_envelope_spec_sha256": _stable_hash(normalized_envelope),
            "effective_runtime_envelope_sha256": _stable_hash(effective_envelope),
            "trusted_source_bindings_sha256": _stable_hash(normalized_bindings),
            "trusted_source_operator_policy_sha256": _stable_hash(
                trusted_source_operator_policy_payload
            ),
            "session_payload_sha256": "",
        },
    }
    session["frozen_hashes"]["session_payload_sha256"] = _stable_hash(
        {key: value for key, value in session.items() if key != "frozen_hashes"}
    )
    _write_json(effective_operator_session_path(root), session)
    return session, []


def record_operator_launch_event(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> None:
    ledger_row = {
        "schema_name": OPERATOR_LAUNCH_EVENT_SCHEMA_NAME,
        "schema_version": OPERATOR_LAUNCH_EVENT_SCHEMA_VERSION,
        **dict(payload),
    }
    _append_jsonl(operator_launch_event_ledger_path(root), ledger_row)


def read_operator_status_snapshot(
    *,
    root: str | Path | None = None,
    package_root: str | Path | None = None,
) -> dict[str, Any]:
    package_root_path = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    runtime_payload = load_runtime_constraints(root)
    runtime_envelope_payload = load_runtime_envelope_spec(root)
    bindings_payload = load_trusted_source_bindings(root)
    secrets_payload = load_trusted_source_secrets_or_default(root)
    credential_status_payload = load_trusted_source_credential_status(root)
    provider_status_payload = load_trusted_source_provider_status(root)
    handshake_payload = load_trusted_source_handshake(root)
    session_contract_payload = load_trusted_source_session_contract(root)
    request_contract_payload = load_trusted_source_request_contract(root)
    response_template_payload = load_trusted_source_response_template(root)
    operator_run_preset_payload = load_operator_run_preset_or_default(
        root=root,
        package_root=package_root_path,
    )
    trusted_source_operator_policy_payload = load_trusted_source_operator_policy_or_default(
        root=root
    )
    trusted_source_aggressiveness_policy_payload = _load_json(
        trusted_source_aggressiveness_policy_path(root)
    )
    trusted_source_budget_policy_payload = _load_json(
        trusted_source_budget_policy_path(root)
    )
    trusted_source_retry_policy_payload = _load_json(
        trusted_source_retry_policy_path(root)
    )
    trusted_source_escalation_thresholds_payload = _load_json(
        trusted_source_escalation_thresholds_path(root)
    )

    runtime_errors, normalized_constraints, enforcement = validate_runtime_constraints(
        runtime_payload if runtime_payload else build_default_runtime_constraints(package_root_path),
        package_root=package_root_path,
        operator_root=root,
    )
    binding_errors, normalized_bindings, availability = validate_trusted_source_bindings(
        bindings_payload if bindings_payload else build_default_trusted_source_bindings(package_root_path),
        secrets_payload=secrets_payload,
    )
    backend_probe = probe_runtime_backend_capabilities()
    envelope_errors, normalized_envelope, effective_envelope = validate_operator_runtime_envelope_spec(
        runtime_envelope_payload if runtime_envelope_payload else build_default_operator_runtime_envelope_spec(package_root_path),
        runtime_constraints=normalized_constraints,
        trusted_source_bindings=normalized_bindings,
        backend_probe=backend_probe,
    )
    if not runtime_envelope_payload:
        envelope_errors = ["operator runtime envelope spec file is missing", *list(envelope_errors)]
    session = load_effective_operator_session_from_file(effective_operator_session_path(root))
    session_errors = validate_effective_operator_session(
        session,
        operator_root=root,
        package_root=package_root_path,
    ) if session else ["no frozen operator session has been materialized yet"]
    last_launch_event = load_last_operator_launch_event(root)
    latest_launch_plan_path = operator_runtime_launch_plan_latest_path(root)
    latest_launch_plan = _load_json(latest_launch_plan_path)
    controller_delegation_contract_payload = load_controller_delegation_contract(root)
    controller_child_registry_payload = load_controller_child_registry(root)
    controller_resource_lease_payload = load_controller_resource_lease(root)
    controller_delegation_state_payload = load_controller_delegation_state(root)
    child_authority_scope_payload = load_child_authority_scope(root)
    child_stop_condition_payload = load_child_stop_condition(root)
    child_return_contract_payload = load_child_return_contract(root)
    verifier_checklist_payload = load_verifier_checklist(root)
    verifier_adoption_readiness_payload = load_verifier_adoption_readiness(root)
    verifier_integrity_summary_payload = load_verifier_integrity_summary(root)
    child_budget_state_payload = load_child_budget_state(root)
    child_termination_summary_payload = load_child_termination_summary(root)
    controller_child_task_assignment_payload = load_controller_child_task_assignment(root)
    child_task_result_payload = load_child_task_result(root)
    child_artifact_bundle_payload = load_child_artifact_bundle(root)
    controller_child_return_summary_payload = load_controller_child_return_summary(root)
    controller_child_adoption_decision_payload = load_controller_child_adoption_decision(root)
    controller_child_review_payload = load_controller_child_review(root)
    controller_delegation_decision_payload = load_controller_delegation_decision(root)
    controller_child_adoption_summary_payload = load_controller_child_adoption_summary(
        root
    )
    controller_librarian_mission_improvement_payload = (
        load_controller_librarian_mission_improvement(root)
    )
    controller_verifier_mission_improvement_payload = (
        load_controller_verifier_mission_improvement(root)
    )
    controller_sequential_delegation_workflow_payload = (
        load_controller_sequential_delegation_workflow(root)
    )
    controller_mission_delegation_plan_payload = (
        load_controller_mission_delegation_plan(root)
    )
    controller_child_admissibility_payload = load_controller_child_admissibility(root)
    controller_blocked_delegation_options_payload = (
        load_controller_blocked_delegation_options(root)
    )
    controller_typed_handoff_contract_payload = (
        load_controller_typed_handoff_contract(root)
    )
    controller_delegation_outcome_payload = load_controller_delegation_outcome(root)
    controller_delegation_path_history_payload = (
        load_controller_delegation_path_history(root)
    )
    controller_path_selection_evidence_payload = (
        load_controller_path_selection_evidence(root)
    )
    controller_recommendation_support_payload = (
        load_controller_recommendation_support(root)
    )
    controller_recommendation_audit_payload = (
        load_controller_recommendation_audit(root)
    )
    controller_recommendation_audit_history_payload = (
        load_controller_recommendation_audit_history(root)
    )
    controller_recommendation_calibration_summary_payload = (
        load_controller_recommendation_calibration_summary(root)
    )
    controller_recommendation_window_payload = (
        load_controller_recommendation_window(root)
    )
    controller_recommendation_stability_payload = (
        load_controller_recommendation_stability(root)
    )
    controller_recommendation_stability_history_payload = (
        load_controller_recommendation_stability_history(root)
    )
    controller_recommendation_governance_payload = (
        load_controller_recommendation_governance(root)
    )
    controller_recommendation_override_payload = (
        load_controller_recommendation_override(root)
    )
    controller_recommendation_override_history_payload = (
        load_controller_recommendation_override_history(root)
    )
    controller_intervention_audit_payload = load_controller_intervention_audit(root)
    controller_intervention_audit_history_payload = (
        load_controller_intervention_audit_history(root)
    )
    controller_intervention_calibration_summary_payload = (
        load_controller_intervention_calibration_summary(root)
    )
    controller_intervention_prudence_payload = (
        load_controller_intervention_prudence(root)
    )
    controller_intervention_prudence_history_payload = (
        load_controller_intervention_prudence_history(root)
    )
    controller_recommendation_trust_signal_payload = (
        load_controller_recommendation_trust_signal(root)
    )
    controller_governance_summary_payload = load_controller_governance_summary(root)
    controller_governance_summary_history_payload = (
        load_controller_governance_summary_history(root)
    )
    controller_recommendation_state_summary_payload = (
        load_controller_recommendation_state_summary(root)
    )
    controller_governance_trend_payload = load_controller_governance_trend(root)
    controller_governance_trend_history_payload = (
        load_controller_governance_trend_history(root)
    )
    controller_temporal_drift_summary_payload = (
        load_controller_temporal_drift_summary(root)
    )
    controller_operator_guidance_payload = load_controller_operator_guidance(root)
    controller_operator_guidance_history_payload = (
        load_controller_operator_guidance_history(root)
    )
    controller_action_guidance_summary_payload = (
        load_controller_action_guidance_summary(root)
    )
    controller_action_readiness_payload = load_controller_action_readiness(root)
    controller_action_readiness_history_payload = (
        load_controller_action_readiness_history(root)
    )
    controller_guided_handoff_summary_payload = (
        load_controller_guided_handoff_summary(root)
    )
    controller_operator_flow_payload = load_controller_operator_flow(root)
    controller_operator_flow_history_payload = (
        load_controller_operator_flow_history(root)
    )
    controller_demo_readiness_summary_payload = (
        load_controller_demo_readiness_summary(root)
    )
    controller_demo_scenario_payload = load_controller_demo_scenario(root)
    controller_demo_scenario_history_payload = (
        load_controller_demo_scenario_history(root)
    )
    controller_demo_run_readiness_payload = (
        load_controller_demo_run_readiness(root)
    )
    controller_demo_operator_walkthrough_payload = (
        load_controller_demo_operator_walkthrough(root)
    )
    controller_demo_success_rubric_payload = (
        load_controller_demo_success_rubric(root)
    )
    controller_demo_execution_payload = load_controller_demo_execution(root)
    controller_demo_execution_history_payload = (
        load_controller_demo_execution_history(root)
    )
    controller_demo_result_summary_payload = (
        load_controller_demo_result_summary(root)
    )
    controller_demo_output_inventory_payload = (
        load_controller_demo_output_inventory(root)
    )
    controller_demo_evidence_trail_payload = (
        load_controller_demo_evidence_trail(root)
    )
    controller_demo_output_completion_payload = (
        load_controller_demo_output_completion(root)
    )
    controller_demo_output_completion_history_payload = (
        load_controller_demo_output_completion_history(root)
    )
    controller_demo_reviewable_artifacts_payload = (
        load_controller_demo_reviewable_artifacts(root)
    )
    controller_demo_completion_summary_payload = (
        load_controller_demo_completion_summary(root)
    )
    controller_trusted_demo_scenario_payload = (
        load_controller_trusted_demo_scenario(root)
    )
    controller_trusted_demo_scenario_history_payload = (
        load_controller_trusted_demo_scenario_history(root)
    )
    controller_trusted_demo_directive_payload = (
        load_controller_trusted_demo_directive(root)
    )
    controller_trusted_demo_success_rubric_payload = (
        load_controller_trusted_demo_success_rubric(root)
    )
    controller_trusted_demo_skill_target_payload = (
        load_controller_trusted_demo_skill_target(root)
    )
    controller_trusted_demo_selection_rationale_payload = (
        load_controller_trusted_demo_selection_rationale(root)
    )
    controller_trusted_demo_local_first_analysis_payload = (
        load_controller_trusted_demo_local_first_analysis(root)
    )
    controller_trusted_demo_knowledge_gap_payload = (
        load_controller_trusted_demo_knowledge_gap(root)
    )
    controller_trusted_demo_knowledge_gap_history_payload = (
        load_controller_trusted_demo_knowledge_gap_history(root)
    )
    controller_trusted_demo_request_payload = (
        load_controller_trusted_demo_request(root)
    )
    controller_trusted_demo_request_history_payload = (
        load_controller_trusted_demo_request_history(root)
    )
    controller_trusted_demo_response_summary_payload = (
        load_controller_trusted_demo_response_summary(root)
    )
    controller_trusted_demo_incorporation_payload = (
        load_controller_trusted_demo_incorporation(root)
    )
    controller_trusted_demo_growth_artifact_payload = (
        load_controller_trusted_demo_growth_artifact(root)
    )
    controller_trusted_demo_growth_artifact_history_payload = (
        load_controller_trusted_demo_growth_artifact_history(root)
    )
    controller_trusted_demo_delta_summary_payload = (
        load_controller_trusted_demo_delta_summary(root)
    )
    controller_trusted_live_connectivity_payload = (
        load_controller_trusted_live_connectivity(root)
    )
    controller_trusted_live_connectivity_history_payload = (
        load_controller_trusted_live_connectivity_history(root)
    )
    controller_trusted_live_request_payload = (
        load_controller_trusted_live_request(root)
    )
    controller_trusted_live_response_summary_payload = (
        load_controller_trusted_live_response_summary(root)
    )
    controller_trusted_live_evidence_receipt_payload = (
        load_controller_trusted_live_evidence_receipt(root)
    )
    controller_trusted_live_validation_summary_payload = (
        load_controller_trusted_live_validation_summary(root)
    )
    controller_trusted_demo_live_request_payload = (
        load_controller_trusted_demo_live_request(root)
    )
    controller_trusted_demo_live_request_history_payload = (
        load_controller_trusted_demo_live_request_history(root)
    )
    controller_trusted_demo_live_response_summary_payload = (
        load_controller_trusted_demo_live_response_summary(root)
    )
    controller_trusted_demo_live_evidence_receipt_payload = (
        load_controller_trusted_demo_live_evidence_receipt(root)
    )
    controller_trusted_demo_live_incorporation_payload = (
        load_controller_trusted_demo_live_incorporation(root)
    )
    controller_trusted_demo_growth_artifact_update_payload = (
        load_controller_trusted_demo_growth_artifact_update(root)
    )
    controller_trusted_demo_growth_artifact_update_history_payload = (
        load_controller_trusted_demo_growth_artifact_update_history(root)
    )
    controller_trusted_demo_before_after_delta_payload = (
        load_controller_trusted_demo_before_after_delta(root)
    )
    controller_demo_storyline_payload = load_controller_demo_storyline(root)
    controller_demo_storyline_history_payload = (
        load_controller_demo_storyline_history(root)
    )
    controller_demo_presentation_summary_payload = (
        load_controller_demo_presentation_summary(root)
    )
    controller_demo_narration_guide_payload = (
        load_controller_demo_narration_guide(root)
    )
    controller_demo_review_readiness_payload = (
        load_controller_demo_review_readiness(root)
    )
    controller_demo_runbook_payload = load_controller_demo_runbook(root)
    controller_demo_runbook_history_payload = (
        load_controller_demo_runbook_history(root)
    )
    controller_demo_facilitator_checklist_payload = (
        load_controller_demo_facilitator_checklist(root)
    )
    controller_demo_checkpoint_summary_payload = (
        load_controller_demo_checkpoint_summary(root)
    )
    controller_demo_acceptance_rubric_payload = (
        load_controller_demo_acceptance_rubric(root)
    )
    controller_demo_packaged_completeness_payload = (
        load_controller_demo_packaged_completeness(root)
    )
    controller_demo_packaged_completeness_history_payload = (
        load_controller_demo_packaged_completeness_history(root)
    )
    controller_demo_packaged_artifact_inventory_payload = (
        load_controller_demo_packaged_artifact_inventory(root)
    )
    controller_demo_packaged_checkpoint_closure_payload = (
        load_controller_demo_packaged_checkpoint_closure(root)
    )
    controller_demo_packaged_rubric_justification_payload = (
        load_controller_demo_packaged_rubric_justification(root)
    )
    controller_demo_presenter_handoff_payload = (
        load_controller_demo_presenter_handoff(root)
    )
    controller_demo_presenter_handoff_history_payload = (
        load_controller_demo_presenter_handoff_history(root)
    )
    controller_demo_quickstart_sheet_payload = (
        load_controller_demo_quickstart_sheet(root)
    )
    controller_demo_audience_summary_payload = (
        load_controller_demo_audience_summary(root)
    )
    controller_demo_pre_demo_sanity_payload = (
        load_controller_demo_pre_demo_sanity(root)
    )
    controller_demo_post_demo_review_payload = (
        load_controller_demo_post_demo_review(root)
    )
    controller_demo_short_form_payload = load_controller_demo_short_form(root)
    controller_demo_short_form_history_payload = (
        load_controller_demo_short_form_history(root)
    )
    controller_demo_full_walkthrough_payload = (
        load_controller_demo_full_walkthrough(root)
    )
    controller_demo_must_show_checkpoints_payload = (
        load_controller_demo_must_show_checkpoints(root)
    )
    controller_demo_audience_mode_optimization_payload = (
        load_controller_demo_audience_mode_optimization(root)
    )
    controller_real_work_benchmark_payload = load_controller_real_work_benchmark(root)
    controller_real_work_benchmark_history_payload = (
        load_controller_real_work_benchmark_history(root)
    )
    controller_real_work_benchmark_directive_payload = (
        load_controller_real_work_benchmark_directive(root)
    )
    controller_real_work_benchmark_output_contract_payload = (
        load_controller_real_work_benchmark_output_contract(root)
    )
    controller_real_work_benchmark_success_rubric_payload = (
        load_controller_real_work_benchmark_success_rubric(root)
    )
    controller_real_work_benchmark_operator_value_payload = (
        load_controller_real_work_benchmark_operator_value(root)
    )
    controller_real_work_benchmark_selection_rationale_payload = (
        load_controller_real_work_benchmark_selection_rationale(root)
    )
    controller_real_work_benchmark_execution_payload = (
        load_controller_real_work_benchmark_execution(root)
    )
    controller_real_work_benchmark_execution_history_payload = (
        load_controller_real_work_benchmark_execution_history(root)
    )
    controller_real_work_benchmark_result_summary_payload = (
        load_controller_real_work_benchmark_result_summary(root)
    )
    controller_real_work_benchmark_output_inventory_payload = (
        load_controller_real_work_benchmark_output_inventory(root)
    )
    controller_real_work_benchmark_rubric_result_payload = (
        load_controller_real_work_benchmark_rubric_result(root)
    )
    controller_real_work_benchmark_closure_payload = (
        load_controller_real_work_benchmark_closure(root)
    )
    controller_real_work_benchmark_closure_history_payload = (
        load_controller_real_work_benchmark_closure_history(root)
    )
    controller_real_work_benchmark_repeatability_payload = (
        load_controller_real_work_benchmark_repeatability(root)
    )
    controller_real_work_benchmark_repeatability_history_payload = (
        load_controller_real_work_benchmark_repeatability_history(root)
    )
    controller_real_work_benchmark_promotion_readiness_payload = (
        load_controller_real_work_benchmark_promotion_readiness(root)
    )
    controller_real_work_benchmark_unresolved_bundle_payload = (
        load_controller_real_work_benchmark_unresolved_bundle(root)
    )
    controller_real_work_benchmark_delta_from_rc46_payload = (
        load_controller_real_work_benchmark_delta_from_rc46(root)
    )
    controller_real_work_benchmark_decision_packet_payload = (
        load_controller_real_work_benchmark_decision_packet(root)
    )
    controller_real_work_benchmark_decision_packet_history_payload = (
        load_controller_real_work_benchmark_decision_packet_history(root)
    )
    controller_real_work_benchmark_promotion_decision_payload = (
        load_controller_real_work_benchmark_promotion_decision(root)
    )
    controller_real_work_benchmark_review_gate_packet_payload = (
        load_controller_real_work_benchmark_review_gate_packet(root)
    )
    controller_real_work_benchmark_final_blocker_payload = (
        load_controller_real_work_benchmark_final_blocker(root)
    )
    controller_real_work_benchmark_decision_rationale_payload = (
        load_controller_real_work_benchmark_decision_rationale(root)
    )
    controller_real_work_benchmark_next_action_payload = (
        load_controller_real_work_benchmark_next_action(root)
    )
    controller_real_work_benchmark_review_packet_payload = (
        load_controller_real_work_benchmark_review_packet(root)
    )
    controller_real_work_benchmark_review_packet_history_payload = (
        load_controller_real_work_benchmark_review_packet_history(root)
    )
    controller_real_work_benchmark_operator_review_decision_payload = (
        load_controller_real_work_benchmark_operator_review_decision(root)
    )
    controller_real_work_benchmark_promotion_outcome_payload = (
        load_controller_real_work_benchmark_promotion_outcome(root)
    )
    controller_real_work_benchmark_operator_confirmation_state_payload = (
        load_controller_real_work_benchmark_operator_confirmation_state(root)
    )
    controller_real_work_benchmark_review_evidence_payload = (
        load_controller_real_work_benchmark_review_evidence(root)
    )
    controller_real_work_benchmark_review_checklist_payload = (
        load_controller_real_work_benchmark_review_checklist(root)
    )
    controller_real_work_benchmark_review_confirmation_payload = (
        load_controller_real_work_benchmark_review_confirmation(root)
    )
    controller_real_work_benchmark_review_confirmation_history_payload = (
        load_controller_real_work_benchmark_review_confirmation_history(root)
    )
    controller_real_work_benchmark_review_decision_source_payload = (
        load_controller_real_work_benchmark_review_decision_source(root)
    )
    controller_real_work_benchmark_promotion_outcome_confirmed_payload = (
        load_controller_real_work_benchmark_promotion_outcome_confirmed(root)
    )
    controller_real_work_benchmark_review_resolution_summary_payload = (
        load_controller_real_work_benchmark_review_resolution_summary(root)
    )
    controller_real_work_benchmark_confirmation_gap_payload = (
        load_controller_real_work_benchmark_confirmation_gap(root)
    )
    secret_binding_rows = []
    for binding in list(normalized_bindings.get("bindings", [])):
        secret_value, secret_source = resolve_trusted_source_secret(binding, secrets_payload=secrets_payload)
        secret_binding_rows.append(
            {
                "source_id": str(binding.get("source_id", "")),
                "credential_strategy": str(binding.get("credential_strategy", "")),
                "credential_ref": str(binding.get("credential_ref", "")),
                "secret_source": secret_source,
                "secret_present": bool(str(secret_value).strip()),
            }
        )
    return {
        "operator_root": _normalize_path(default_operator_root() if root is None else Path(root)),
        "runtime_constraints_path": str(operator_runtime_constraints_path(root)),
        "runtime_envelope_spec_path": str(operator_runtime_envelope_spec_path(root)),
        "trusted_source_bindings_path": str(trusted_source_bindings_path(root)),
        "trusted_source_secrets_path": str(trusted_source_secrets_path(root)),
        "trusted_source_credential_status_path": str(trusted_source_credential_status_path(root)),
        "trusted_source_provider_status_path": str(trusted_source_provider_status_path(root)),
        "trusted_source_handshake_path": str(trusted_source_handshake_path(root)),
        "trusted_source_session_contract_path": str(trusted_source_session_contract_path(root)),
        "trusted_source_request_contract_path": str(trusted_source_request_contract_path(root)),
        "trusted_source_response_template_path": str(trusted_source_response_template_path(root)),
        "trusted_source_operator_policy_path": str(
            trusted_source_operator_policy_path(root)
        ),
        "trusted_source_aggressiveness_policy_path": str(
            trusted_source_aggressiveness_policy_path(root)
        ),
        "trusted_source_budget_policy_path": str(trusted_source_budget_policy_path(root)),
        "trusted_source_retry_policy_path": str(trusted_source_retry_policy_path(root)),
        "trusted_source_escalation_thresholds_path": str(
            trusted_source_escalation_thresholds_path(root)
        ),
        "operator_run_preset_path": str(operator_run_preset_path(root)),
        "operator_session_state_path": str(operator_session_state_path(root)),
        "operator_resume_summary_path": str(operator_resume_summary_path(root)),
        "operator_session_continuity_path": str(operator_session_continuity_path(root)),
        "operator_current_session_summary_path": str(
            operator_current_session_summary_path(root)
        ),
        "operator_next_action_summary_path": str(
            operator_next_action_summary_path(root)
        ),
        "operator_resume_policy_summary_path": str(
            operator_resume_policy_summary_path(root)
        ),
        "operator_review_queue_path": str(operator_review_queue_path(root)),
        "operator_intervention_summary_path": str(
            operator_intervention_summary_path(root)
        ),
        "operator_pending_decisions_path": str(operator_pending_decisions_path(root)),
        "operator_review_reason_path": str(operator_review_reason_path(root)),
        "operator_intervention_options_path": str(
            operator_intervention_options_path(root)
        ),
        "operator_review_decision_path": str(operator_review_decision_path(root)),
        "operator_review_action_execution_path": str(
            operator_review_action_execution_path(root)
        ),
        "operator_review_resolution_path": str(operator_review_resolution_path(root)),
        "controller_delegation_contract_path": str(
            controller_delegation_contract_path(root)
        ),
        "controller_child_registry_path": str(controller_child_registry_path(root)),
        "controller_resource_lease_path": str(controller_resource_lease_path(root)),
        "controller_delegation_state_path": str(controller_delegation_state_path(root)),
        "child_authority_scope_path": str(child_authority_scope_path(root)),
        "child_stop_condition_path": str(child_stop_condition_path(root)),
        "child_return_contract_path": str(child_return_contract_path(root)),
        "verifier_checklist_path": str(verifier_checklist_path(root)),
        "verifier_adoption_readiness_path": str(
            verifier_adoption_readiness_path(root)
        ),
        "verifier_integrity_summary_path": str(
            verifier_integrity_summary_path(root)
        ),
        "child_budget_state_path": str(child_budget_state_path(root)),
        "child_termination_summary_path": str(child_termination_summary_path(root)),
        "controller_child_task_assignment_path": str(
            controller_child_task_assignment_path(root)
        ),
        "child_task_result_path": str(child_task_result_path(root)),
        "child_artifact_bundle_path": str(child_artifact_bundle_path(root)),
        "controller_child_return_summary_path": str(
            controller_child_return_summary_path(root)
        ),
        "controller_child_adoption_decision_path": str(
            controller_child_adoption_decision_path(root)
        ),
        "controller_child_review_path": str(controller_child_review_path(root)),
        "controller_delegation_decision_path": str(
            controller_delegation_decision_path(root)
        ),
        "controller_child_adoption_summary_path": str(
            controller_child_adoption_summary_path(root)
        ),
        "controller_librarian_mission_improvement_path": str(
            controller_librarian_mission_improvement_path(root)
        ),
        "controller_verifier_mission_improvement_path": str(
            controller_verifier_mission_improvement_path(root)
        ),
        "controller_sequential_delegation_workflow_path": str(
            controller_sequential_delegation_workflow_path(root)
        ),
        "controller_mission_delegation_plan_path": str(
            controller_mission_delegation_plan_path(root)
        ),
        "controller_child_admissibility_path": str(
            controller_child_admissibility_path(root)
        ),
        "controller_blocked_delegation_options_path": str(
            controller_blocked_delegation_options_path(root)
        ),
        "controller_typed_handoff_contract_path": str(
            controller_typed_handoff_contract_path(root)
        ),
        "controller_delegation_outcome_path": str(
            controller_delegation_outcome_path(root)
        ),
        "controller_delegation_path_history_path": str(
            controller_delegation_path_history_path(root)
        ),
        "controller_path_selection_evidence_path": str(
            controller_path_selection_evidence_path(root)
        ),
        "controller_recommendation_support_path": str(
            controller_recommendation_support_path(root)
        ),
        "controller_recommendation_audit_path": str(
            controller_recommendation_audit_path(root)
        ),
        "controller_recommendation_audit_history_path": str(
            controller_recommendation_audit_history_path(root)
        ),
        "controller_recommendation_calibration_summary_path": str(
            controller_recommendation_calibration_summary_path(root)
        ),
        "controller_recommendation_window_path": str(
            controller_recommendation_window_path(root)
        ),
        "controller_recommendation_stability_path": str(
            controller_recommendation_stability_path(root)
        ),
        "controller_recommendation_stability_history_path": str(
            controller_recommendation_stability_history_path(root)
        ),
        "controller_recommendation_governance_path": str(
            controller_recommendation_governance_path(root)
        ),
        "controller_recommendation_override_path": str(
            controller_recommendation_override_path(root)
        ),
        "controller_recommendation_override_history_path": str(
            controller_recommendation_override_history_path(root)
        ),
        "controller_intervention_audit_path": str(
            controller_intervention_audit_path(root)
        ),
        "controller_intervention_audit_history_path": str(
            controller_intervention_audit_history_path(root)
        ),
        "controller_intervention_calibration_summary_path": str(
            controller_intervention_calibration_summary_path(root)
        ),
        "controller_intervention_prudence_path": str(
            controller_intervention_prudence_path(root)
        ),
        "controller_intervention_prudence_history_path": str(
            controller_intervention_prudence_history_path(root)
        ),
        "controller_recommendation_trust_signal_path": str(
            controller_recommendation_trust_signal_path(root)
        ),
        "controller_governance_summary_path": str(
            controller_governance_summary_path(root)
        ),
        "controller_governance_summary_history_path": str(
            controller_governance_summary_history_path(root)
        ),
        "controller_recommendation_state_summary_path": str(
            controller_recommendation_state_summary_path(root)
        ),
        "controller_governance_trend_path": str(
            controller_governance_trend_path(root)
        ),
        "controller_governance_trend_history_path": str(
            controller_governance_trend_history_path(root)
        ),
        "controller_temporal_drift_summary_path": str(
            controller_temporal_drift_summary_path(root)
        ),
        "controller_operator_guidance_path": str(
            controller_operator_guidance_path(root)
        ),
        "controller_operator_guidance_history_path": str(
            controller_operator_guidance_history_path(root)
        ),
        "controller_action_guidance_summary_path": str(
            controller_action_guidance_summary_path(root)
        ),
        "controller_action_readiness_path": str(
            controller_action_readiness_path(root)
        ),
        "controller_action_readiness_history_path": str(
            controller_action_readiness_history_path(root)
        ),
        "controller_guided_handoff_summary_path": str(
            controller_guided_handoff_summary_path(root)
        ),
        "controller_operator_flow_path": str(
            controller_operator_flow_path(root)
        ),
        "controller_operator_flow_history_path": str(
            controller_operator_flow_history_path(root)
        ),
        "controller_demo_readiness_summary_path": str(
            controller_demo_readiness_summary_path(root)
        ),
        "controller_demo_scenario_path": str(
            controller_demo_scenario_path(root)
        ),
        "controller_demo_scenario_history_path": str(
            controller_demo_scenario_history_path(root)
        ),
        "controller_demo_run_readiness_path": str(
            controller_demo_run_readiness_path(root)
        ),
        "controller_demo_operator_walkthrough_path": str(
            controller_demo_operator_walkthrough_path(root)
        ),
        "controller_demo_success_rubric_path": str(
            controller_demo_success_rubric_path(root)
        ),
        "controller_demo_execution_path": str(
            controller_demo_execution_path(root)
        ),
        "controller_demo_execution_history_path": str(
            controller_demo_execution_history_path(root)
        ),
        "controller_demo_result_summary_path": str(
            controller_demo_result_summary_path(root)
        ),
        "controller_demo_output_inventory_path": str(
            controller_demo_output_inventory_path(root)
        ),
        "controller_demo_evidence_trail_path": str(
            controller_demo_evidence_trail_path(root)
        ),
        "controller_demo_output_completion_path": str(
            controller_demo_output_completion_path(root)
        ),
        "controller_demo_output_completion_history_path": str(
            controller_demo_output_completion_history_path(root)
        ),
        "controller_demo_reviewable_artifacts_path": str(
            controller_demo_reviewable_artifacts_path(root)
        ),
        "controller_demo_completion_summary_path": str(
            controller_demo_completion_summary_path(root)
        ),
        "controller_trusted_demo_scenario_path": str(
            controller_trusted_demo_scenario_path(root)
        ),
        "controller_trusted_demo_scenario_history_path": str(
            controller_trusted_demo_scenario_history_path(root)
        ),
        "controller_trusted_demo_directive_path": str(
            controller_trusted_demo_directive_path(root)
        ),
        "controller_trusted_demo_success_rubric_path": str(
            controller_trusted_demo_success_rubric_path(root)
        ),
        "controller_trusted_demo_skill_target_path": str(
            controller_trusted_demo_skill_target_path(root)
        ),
        "controller_trusted_demo_selection_rationale_path": str(
            controller_trusted_demo_selection_rationale_path(root)
        ),
        "controller_trusted_demo_local_first_analysis_path": str(
            controller_trusted_demo_local_first_analysis_path(root)
        ),
        "controller_trusted_demo_knowledge_gap_path": str(
            controller_trusted_demo_knowledge_gap_path(root)
        ),
        "controller_trusted_demo_knowledge_gap_history_path": str(
            controller_trusted_demo_knowledge_gap_history_path(root)
        ),
        "controller_trusted_demo_request_path": str(
            controller_trusted_demo_request_path(root)
        ),
        "controller_trusted_demo_request_history_path": str(
            controller_trusted_demo_request_history_path(root)
        ),
        "controller_trusted_demo_response_summary_path": str(
            controller_trusted_demo_response_summary_path(root)
        ),
        "controller_trusted_demo_incorporation_path": str(
            controller_trusted_demo_incorporation_path(root)
        ),
        "controller_trusted_demo_growth_artifact_path": str(
            controller_trusted_demo_growth_artifact_path(root)
        ),
        "controller_trusted_demo_growth_artifact_history_path": str(
            controller_trusted_demo_growth_artifact_history_path(root)
        ),
        "controller_trusted_demo_delta_summary_path": str(
            controller_trusted_demo_delta_summary_path(root)
        ),
        "controller_trusted_live_connectivity_path": str(
            controller_trusted_live_connectivity_path(root)
        ),
        "controller_trusted_live_connectivity_history_path": str(
            controller_trusted_live_connectivity_history_path(root)
        ),
        "controller_trusted_live_request_path": str(
            controller_trusted_live_request_path(root)
        ),
        "controller_trusted_live_response_summary_path": str(
            controller_trusted_live_response_summary_path(root)
        ),
        "controller_trusted_live_evidence_receipt_path": str(
            controller_trusted_live_evidence_receipt_path(root)
        ),
        "controller_trusted_live_validation_summary_path": str(
            controller_trusted_live_validation_summary_path(root)
        ),
        "controller_trusted_demo_live_request_path": str(
            controller_trusted_demo_live_request_path(root)
        ),
        "controller_trusted_demo_live_request_history_path": str(
            controller_trusted_demo_live_request_history_path(root)
        ),
        "controller_trusted_demo_live_response_summary_path": str(
            controller_trusted_demo_live_response_summary_path(root)
        ),
        "controller_trusted_demo_live_evidence_receipt_path": str(
            controller_trusted_demo_live_evidence_receipt_path(root)
        ),
        "controller_trusted_demo_live_incorporation_path": str(
            controller_trusted_demo_live_incorporation_path(root)
        ),
        "controller_trusted_demo_growth_artifact_update_path": str(
            controller_trusted_demo_growth_artifact_update_path(root)
        ),
        "controller_trusted_demo_growth_artifact_update_history_path": str(
            controller_trusted_demo_growth_artifact_update_history_path(root)
        ),
        "controller_trusted_demo_before_after_delta_path": str(
            controller_trusted_demo_before_after_delta_path(root)
        ),
        "controller_demo_storyline_path": str(controller_demo_storyline_path(root)),
        "controller_demo_storyline_history_path": str(
            controller_demo_storyline_history_path(root)
        ),
        "controller_demo_presentation_summary_path": str(
            controller_demo_presentation_summary_path(root)
        ),
        "controller_demo_narration_guide_path": str(
            controller_demo_narration_guide_path(root)
        ),
        "controller_demo_review_readiness_path": str(
            controller_demo_review_readiness_path(root)
        ),
        "controller_demo_runbook_path": str(controller_demo_runbook_path(root)),
        "controller_demo_runbook_history_path": str(
            controller_demo_runbook_history_path(root)
        ),
        "controller_demo_facilitator_checklist_path": str(
            controller_demo_facilitator_checklist_path(root)
        ),
        "controller_demo_checkpoint_summary_path": str(
            controller_demo_checkpoint_summary_path(root)
        ),
        "controller_demo_acceptance_rubric_path": str(
            controller_demo_acceptance_rubric_path(root)
        ),
        "controller_demo_packaged_completeness_path": str(
            controller_demo_packaged_completeness_path(root)
        ),
        "controller_demo_packaged_completeness_history_path": str(
            controller_demo_packaged_completeness_history_path(root)
        ),
        "controller_demo_packaged_artifact_inventory_path": str(
            controller_demo_packaged_artifact_inventory_path(root)
        ),
        "controller_demo_packaged_checkpoint_closure_path": str(
            controller_demo_packaged_checkpoint_closure_path(root)
        ),
        "controller_demo_packaged_rubric_justification_path": str(
            controller_demo_packaged_rubric_justification_path(root)
        ),
        "controller_demo_presenter_handoff_path": str(
            controller_demo_presenter_handoff_path(root)
        ),
        "controller_demo_presenter_handoff_history_path": str(
            controller_demo_presenter_handoff_history_path(root)
        ),
        "controller_demo_quickstart_sheet_path": str(
            controller_demo_quickstart_sheet_path(root)
        ),
        "controller_demo_audience_summary_path": str(
            controller_demo_audience_summary_path(root)
        ),
        "controller_demo_pre_demo_sanity_path": str(
            controller_demo_pre_demo_sanity_path(root)
        ),
        "controller_demo_post_demo_review_path": str(
            controller_demo_post_demo_review_path(root)
        ),
        "controller_demo_short_form_path": str(
            controller_demo_short_form_path(root)
        ),
        "controller_demo_short_form_history_path": str(
            controller_demo_short_form_history_path(root)
        ),
        "controller_demo_full_walkthrough_path": str(
            controller_demo_full_walkthrough_path(root)
        ),
        "controller_demo_must_show_checkpoints_path": str(
            controller_demo_must_show_checkpoints_path(root)
        ),
        "controller_demo_audience_mode_optimization_path": str(
            controller_demo_audience_mode_optimization_path(root)
        ),
        "controller_real_work_benchmark_path": str(
            controller_real_work_benchmark_path(root)
        ),
        "controller_real_work_benchmark_history_path": str(
            controller_real_work_benchmark_history_path(root)
        ),
        "controller_real_work_benchmark_directive_path": str(
            controller_real_work_benchmark_directive_path(root)
        ),
        "controller_real_work_benchmark_output_contract_path": str(
            controller_real_work_benchmark_output_contract_path(root)
        ),
        "controller_real_work_benchmark_success_rubric_path": str(
            controller_real_work_benchmark_success_rubric_path(root)
        ),
        "controller_real_work_benchmark_operator_value_path": str(
            controller_real_work_benchmark_operator_value_path(root)
        ),
        "controller_real_work_benchmark_selection_rationale_path": str(
            controller_real_work_benchmark_selection_rationale_path(root)
        ),
        "controller_real_work_benchmark_execution_path": str(
            controller_real_work_benchmark_execution_path(root)
        ),
        "controller_real_work_benchmark_execution_history_path": str(
            controller_real_work_benchmark_execution_history_path(root)
        ),
        "controller_real_work_benchmark_result_summary_path": str(
            controller_real_work_benchmark_result_summary_path(root)
        ),
        "controller_real_work_benchmark_output_inventory_path": str(
            controller_real_work_benchmark_output_inventory_path(root)
        ),
        "controller_real_work_benchmark_rubric_result_path": str(
            controller_real_work_benchmark_rubric_result_path(root)
        ),
        "controller_real_work_benchmark_closure_path": str(
            controller_real_work_benchmark_closure_path(root)
        ),
        "controller_real_work_benchmark_closure_history_path": str(
            controller_real_work_benchmark_closure_history_path(root)
        ),
        "controller_real_work_benchmark_repeatability_path": str(
            controller_real_work_benchmark_repeatability_path(root)
        ),
        "controller_real_work_benchmark_repeatability_history_path": str(
            controller_real_work_benchmark_repeatability_history_path(root)
        ),
        "controller_real_work_benchmark_promotion_readiness_path": str(
            controller_real_work_benchmark_promotion_readiness_path(root)
        ),
        "controller_real_work_benchmark_unresolved_bundle_path": str(
            controller_real_work_benchmark_unresolved_bundle_path(root)
        ),
        "controller_real_work_benchmark_delta_from_rc46_path": str(
            controller_real_work_benchmark_delta_from_rc46_path(root)
        ),
        "controller_real_work_benchmark_decision_packet_path": str(
            controller_real_work_benchmark_decision_packet_path(root)
        ),
        "controller_real_work_benchmark_decision_packet_history_path": str(
            controller_real_work_benchmark_decision_packet_history_path(root)
        ),
        "controller_real_work_benchmark_promotion_decision_path": str(
            controller_real_work_benchmark_promotion_decision_path(root)
        ),
        "controller_real_work_benchmark_review_gate_packet_path": str(
            controller_real_work_benchmark_review_gate_packet_path(root)
        ),
        "controller_real_work_benchmark_final_blocker_path": str(
            controller_real_work_benchmark_final_blocker_path(root)
        ),
        "controller_real_work_benchmark_decision_rationale_path": str(
            controller_real_work_benchmark_decision_rationale_path(root)
        ),
        "controller_real_work_benchmark_next_action_path": str(
            controller_real_work_benchmark_next_action_path(root)
        ),
        "controller_real_work_benchmark_review_packet_path": str(
            controller_real_work_benchmark_review_packet_path(root)
        ),
        "controller_real_work_benchmark_review_packet_history_path": str(
            controller_real_work_benchmark_review_packet_history_path(root)
        ),
        "controller_real_work_benchmark_operator_review_decision_path": str(
            controller_real_work_benchmark_operator_review_decision_path(root)
        ),
        "controller_real_work_benchmark_promotion_outcome_path": str(
            controller_real_work_benchmark_promotion_outcome_path(root)
        ),
        "controller_real_work_benchmark_operator_confirmation_state_path": str(
            controller_real_work_benchmark_operator_confirmation_state_path(root)
        ),
        "controller_real_work_benchmark_review_evidence_path": str(
            controller_real_work_benchmark_review_evidence_path(root)
        ),
        "controller_real_work_benchmark_review_checklist_path": str(
            controller_real_work_benchmark_review_checklist_path(root)
        ),
        "controller_real_work_benchmark_review_confirmation_path": str(
            controller_real_work_benchmark_review_confirmation_path(root)
        ),
        "controller_real_work_benchmark_review_confirmation_history_path": str(
            controller_real_work_benchmark_review_confirmation_history_path(root)
        ),
        "controller_real_work_benchmark_review_decision_source_path": str(
            controller_real_work_benchmark_review_decision_source_path(root)
        ),
        "controller_real_work_benchmark_promotion_outcome_confirmed_path": str(
            controller_real_work_benchmark_promotion_outcome_confirmed_path(root)
        ),
        "controller_real_work_benchmark_review_resolution_summary_path": str(
            controller_real_work_benchmark_review_resolution_summary_path(root)
        ),
        "controller_real_work_benchmark_confirmation_gap_path": str(
            controller_real_work_benchmark_confirmation_gap_path(root)
        ),
        "effective_operator_session_path": str(effective_operator_session_path(root)),
        "operator_launch_event_ledger_path": str(operator_launch_event_ledger_path(root)),
        "operator_runtime_launch_plan_path": str(latest_launch_plan_path),
        "runtime_constraints_valid": len(runtime_errors) == 0,
        "runtime_constraints_errors": runtime_errors,
        "runtime_constraints": normalized_constraints,
        "runtime_constraint_enforcement": enforcement,
        "execution_profile": str(normalized_constraints.get("execution_profile", "")),
        "governed_execution_policy": dict(normalized_constraints.get("governed_execution", {})),
        "workspace_policy": dict(normalized_constraints.get("workspace_policy", {})),
        "runtime_envelope_spec_valid": len(envelope_errors) == 0,
        "runtime_envelope_spec_errors": envelope_errors,
        "runtime_envelope_spec": normalized_envelope,
        "effective_runtime_envelope": effective_envelope,
        "runtime_backend_probe": backend_probe,
        "trusted_source_bindings_valid": len(binding_errors) == 0,
        "trusted_source_binding_errors": binding_errors,
        "trusted_source_bindings": normalized_bindings,
        "trusted_source_availability": availability,
        "trusted_source_summary": summarize_trusted_source_availability(availability),
        "trusted_source_secret_summary": {
            "bindings": secret_binding_rows,
        },
        "trusted_source_credential_status": credential_status_payload,
        "trusted_source_provider_status": provider_status_payload,
        "trusted_source_handshake": handshake_payload,
        "trusted_source_session_contract": session_contract_payload,
        "trusted_source_request_contract": request_contract_payload,
        "trusted_source_response_template": response_template_payload,
        "operator_run_preset": operator_run_preset_payload,
        "trusted_source_operator_policy": trusted_source_operator_policy_payload,
        "trusted_source_aggressiveness_policy": (
            trusted_source_aggressiveness_policy_payload
            or _trusted_source_operator_policy_views(trusted_source_operator_policy_payload)[1]
        ),
        "trusted_source_budget_policy": (
            trusted_source_budget_policy_payload
            or _trusted_source_operator_policy_views(trusted_source_operator_policy_payload)[2]
        ),
        "trusted_source_retry_policy": (
            trusted_source_retry_policy_payload
            or _trusted_source_operator_policy_views(trusted_source_operator_policy_payload)[3]
        ),
        "trusted_source_escalation_thresholds": (
            trusted_source_escalation_thresholds_payload
            or _trusted_source_operator_policy_views(trusted_source_operator_policy_payload)[4]
        ),
        "operator_session_state": load_operator_session_state(root),
        "operator_resume_summary": load_operator_resume_summary(root),
        "operator_session_continuity": load_operator_session_continuity(root),
        "operator_current_session_summary": load_operator_current_session_summary(root),
        "operator_next_action_summary": load_operator_next_action_summary(root),
        "operator_resume_policy_summary": load_operator_resume_policy_summary(root),
        "operator_review_queue": load_operator_review_queue(root),
        "operator_intervention_summary": load_operator_intervention_summary(root),
        "operator_pending_decisions": load_operator_pending_decisions(root),
        "operator_review_reason": load_operator_review_reason(root),
        "operator_intervention_options": load_operator_intervention_options(root),
        "operator_review_decision": load_operator_review_decision(root),
        "operator_review_action_execution": load_operator_review_action_execution(root),
        "operator_review_resolution": load_operator_review_resolution(root),
        "controller_delegation_contract": controller_delegation_contract_payload,
        "controller_child_registry": controller_child_registry_payload,
        "controller_resource_lease": controller_resource_lease_payload,
        "controller_delegation_state": controller_delegation_state_payload,
        "child_authority_scope": child_authority_scope_payload,
        "child_stop_condition": child_stop_condition_payload,
        "child_return_contract": child_return_contract_payload,
        "verifier_checklist": verifier_checklist_payload,
        "verifier_adoption_readiness": verifier_adoption_readiness_payload,
        "verifier_integrity_summary": verifier_integrity_summary_payload,
        "child_budget_state": child_budget_state_payload,
        "child_termination_summary": child_termination_summary_payload,
        "controller_child_task_assignment": controller_child_task_assignment_payload,
        "child_task_result": child_task_result_payload,
        "child_artifact_bundle": child_artifact_bundle_payload,
        "controller_child_return_summary": controller_child_return_summary_payload,
        "controller_child_adoption_decision": controller_child_adoption_decision_payload,
        "controller_child_review": controller_child_review_payload,
        "controller_delegation_decision": controller_delegation_decision_payload,
        "controller_child_adoption_summary": (
            controller_child_adoption_summary_payload
        ),
        "controller_librarian_mission_improvement": (
            controller_librarian_mission_improvement_payload
        ),
        "controller_verifier_mission_improvement": (
            controller_verifier_mission_improvement_payload
        ),
        "controller_sequential_delegation_workflow": (
            controller_sequential_delegation_workflow_payload
        ),
        "controller_mission_delegation_plan": (
            controller_mission_delegation_plan_payload
        ),
        "controller_child_admissibility": controller_child_admissibility_payload,
        "controller_blocked_delegation_options": (
            controller_blocked_delegation_options_payload
        ),
        "controller_typed_handoff_contract": (
            controller_typed_handoff_contract_payload
        ),
        "controller_delegation_outcome": controller_delegation_outcome_payload,
        "controller_delegation_path_history": (
            controller_delegation_path_history_payload
        ),
        "controller_path_selection_evidence": (
            controller_path_selection_evidence_payload
        ),
        "controller_recommendation_support": (
            controller_recommendation_support_payload
        ),
        "controller_recommendation_audit": controller_recommendation_audit_payload,
        "controller_recommendation_audit_history": (
            controller_recommendation_audit_history_payload
        ),
        "controller_recommendation_calibration_summary": (
            controller_recommendation_calibration_summary_payload
        ),
        "controller_recommendation_window": (
            controller_recommendation_window_payload
        ),
        "controller_recommendation_stability": (
            controller_recommendation_stability_payload
        ),
        "controller_recommendation_stability_history": (
            controller_recommendation_stability_history_payload
        ),
        "controller_recommendation_governance": (
            controller_recommendation_governance_payload
        ),
        "controller_recommendation_override": (
            controller_recommendation_override_payload
        ),
        "controller_recommendation_override_history": (
            controller_recommendation_override_history_payload
        ),
        "controller_intervention_audit": controller_intervention_audit_payload,
        "controller_intervention_audit_history": (
            controller_intervention_audit_history_payload
        ),
        "controller_intervention_calibration_summary": (
            controller_intervention_calibration_summary_payload
        ),
        "controller_intervention_prudence": controller_intervention_prudence_payload,
        "controller_intervention_prudence_history": (
            controller_intervention_prudence_history_payload
        ),
        "controller_recommendation_trust_signal": (
            controller_recommendation_trust_signal_payload
        ),
        "controller_governance_summary": controller_governance_summary_payload,
        "controller_governance_summary_history": (
            controller_governance_summary_history_payload
        ),
        "controller_recommendation_state_summary": (
            controller_recommendation_state_summary_payload
        ),
        "controller_governance_trend": controller_governance_trend_payload,
        "controller_governance_trend_history": (
            controller_governance_trend_history_payload
        ),
        "controller_temporal_drift_summary": (
            controller_temporal_drift_summary_payload
        ),
        "controller_operator_guidance": controller_operator_guidance_payload,
        "controller_operator_guidance_history": (
            controller_operator_guidance_history_payload
        ),
        "controller_action_guidance_summary": (
            controller_action_guidance_summary_payload
        ),
        "controller_action_readiness": controller_action_readiness_payload,
        "controller_action_readiness_history": (
            controller_action_readiness_history_payload
        ),
        "controller_guided_handoff_summary": (
            controller_guided_handoff_summary_payload
        ),
        "controller_operator_flow": controller_operator_flow_payload,
        "controller_operator_flow_history": (
            controller_operator_flow_history_payload
        ),
        "controller_demo_readiness_summary": (
            controller_demo_readiness_summary_payload
        ),
        "controller_demo_scenario": controller_demo_scenario_payload,
        "controller_demo_scenario_history": (
            controller_demo_scenario_history_payload
        ),
        "controller_demo_run_readiness": (
            controller_demo_run_readiness_payload
        ),
        "controller_demo_operator_walkthrough": (
            controller_demo_operator_walkthrough_payload
        ),
        "controller_demo_success_rubric": (
            controller_demo_success_rubric_payload
        ),
        "controller_demo_execution": controller_demo_execution_payload,
        "controller_demo_execution_history": (
            controller_demo_execution_history_payload
        ),
        "controller_demo_result_summary": (
            controller_demo_result_summary_payload
        ),
        "controller_demo_output_inventory": (
            controller_demo_output_inventory_payload
        ),
        "controller_demo_evidence_trail": (
            controller_demo_evidence_trail_payload
        ),
        "controller_demo_output_completion": (
            controller_demo_output_completion_payload
        ),
        "controller_demo_output_completion_history": (
            controller_demo_output_completion_history_payload
        ),
        "controller_demo_reviewable_artifacts": (
            controller_demo_reviewable_artifacts_payload
        ),
        "controller_demo_completion_summary": (
            controller_demo_completion_summary_payload
        ),
        "controller_trusted_demo_scenario": (
            controller_trusted_demo_scenario_payload
        ),
        "controller_trusted_demo_scenario_history": (
            controller_trusted_demo_scenario_history_payload
        ),
        "controller_trusted_demo_directive": (
            controller_trusted_demo_directive_payload
        ),
        "controller_trusted_demo_success_rubric": (
            controller_trusted_demo_success_rubric_payload
        ),
        "controller_trusted_demo_skill_target": (
            controller_trusted_demo_skill_target_payload
        ),
        "controller_trusted_demo_selection_rationale": (
            controller_trusted_demo_selection_rationale_payload
        ),
        "controller_trusted_demo_local_first_analysis": (
            controller_trusted_demo_local_first_analysis_payload
        ),
        "controller_trusted_demo_knowledge_gap": (
            controller_trusted_demo_knowledge_gap_payload
        ),
        "controller_trusted_demo_knowledge_gap_history": (
            controller_trusted_demo_knowledge_gap_history_payload
        ),
        "controller_trusted_demo_request": (
            controller_trusted_demo_request_payload
        ),
        "controller_trusted_demo_request_history": (
            controller_trusted_demo_request_history_payload
        ),
        "controller_trusted_demo_response_summary": (
            controller_trusted_demo_response_summary_payload
        ),
        "controller_trusted_demo_incorporation": (
            controller_trusted_demo_incorporation_payload
        ),
        "controller_trusted_demo_growth_artifact": (
            controller_trusted_demo_growth_artifact_payload
        ),
        "controller_trusted_demo_growth_artifact_history": (
            controller_trusted_demo_growth_artifact_history_payload
        ),
        "controller_trusted_demo_delta_summary": (
            controller_trusted_demo_delta_summary_payload
        ),
        "controller_trusted_live_connectivity": (
            controller_trusted_live_connectivity_payload
        ),
        "controller_trusted_live_connectivity_history": (
            controller_trusted_live_connectivity_history_payload
        ),
        "controller_trusted_live_request": controller_trusted_live_request_payload,
        "controller_trusted_live_response_summary": (
            controller_trusted_live_response_summary_payload
        ),
        "controller_trusted_live_evidence_receipt": (
            controller_trusted_live_evidence_receipt_payload
        ),
        "controller_trusted_live_validation_summary": (
            controller_trusted_live_validation_summary_payload
        ),
        "controller_trusted_demo_live_request": (
            controller_trusted_demo_live_request_payload
        ),
        "controller_trusted_demo_live_request_history": (
            controller_trusted_demo_live_request_history_payload
        ),
        "controller_trusted_demo_live_response_summary": (
            controller_trusted_demo_live_response_summary_payload
        ),
        "controller_trusted_demo_live_evidence_receipt": (
            controller_trusted_demo_live_evidence_receipt_payload
        ),
        "controller_trusted_demo_live_incorporation": (
            controller_trusted_demo_live_incorporation_payload
        ),
        "controller_trusted_demo_growth_artifact_update": (
            controller_trusted_demo_growth_artifact_update_payload
        ),
        "controller_trusted_demo_growth_artifact_update_history": (
            controller_trusted_demo_growth_artifact_update_history_payload
        ),
        "controller_trusted_demo_before_after_delta": (
            controller_trusted_demo_before_after_delta_payload
        ),
        "controller_demo_storyline": controller_demo_storyline_payload,
        "controller_demo_storyline_history": (
            controller_demo_storyline_history_payload
        ),
        "controller_demo_presentation_summary": (
            controller_demo_presentation_summary_payload
        ),
        "controller_demo_narration_guide": (
            controller_demo_narration_guide_payload
        ),
        "controller_demo_review_readiness": (
            controller_demo_review_readiness_payload
        ),
        "controller_demo_runbook": controller_demo_runbook_payload,
        "controller_demo_runbook_history": (
            controller_demo_runbook_history_payload
        ),
        "controller_demo_facilitator_checklist": (
            controller_demo_facilitator_checklist_payload
        ),
        "controller_demo_checkpoint_summary": (
            controller_demo_checkpoint_summary_payload
        ),
        "controller_demo_acceptance_rubric": (
            controller_demo_acceptance_rubric_payload
        ),
        "controller_demo_packaged_completeness": (
            controller_demo_packaged_completeness_payload
        ),
        "controller_demo_packaged_completeness_history": (
            controller_demo_packaged_completeness_history_payload
        ),
        "controller_demo_packaged_artifact_inventory": (
            controller_demo_packaged_artifact_inventory_payload
        ),
        "controller_demo_packaged_checkpoint_closure": (
            controller_demo_packaged_checkpoint_closure_payload
        ),
        "controller_demo_packaged_rubric_justification": (
            controller_demo_packaged_rubric_justification_payload
        ),
        "controller_demo_presenter_handoff": (
            controller_demo_presenter_handoff_payload
        ),
        "controller_demo_presenter_handoff_history": (
            controller_demo_presenter_handoff_history_payload
        ),
        "controller_demo_quickstart_sheet": (
            controller_demo_quickstart_sheet_payload
        ),
        "controller_demo_audience_summary": (
            controller_demo_audience_summary_payload
        ),
        "controller_demo_pre_demo_sanity": (
            controller_demo_pre_demo_sanity_payload
        ),
        "controller_demo_post_demo_review": (
            controller_demo_post_demo_review_payload
        ),
        "controller_demo_short_form": controller_demo_short_form_payload,
        "controller_demo_short_form_history": (
            controller_demo_short_form_history_payload
        ),
        "controller_demo_full_walkthrough": (
            controller_demo_full_walkthrough_payload
        ),
        "controller_demo_must_show_checkpoints": (
            controller_demo_must_show_checkpoints_payload
        ),
        "controller_demo_audience_mode_optimization": (
            controller_demo_audience_mode_optimization_payload
        ),
        "controller_real_work_benchmark": controller_real_work_benchmark_payload,
        "controller_real_work_benchmark_history": (
            controller_real_work_benchmark_history_payload
        ),
        "controller_real_work_benchmark_directive": (
            controller_real_work_benchmark_directive_payload
        ),
        "controller_real_work_benchmark_output_contract": (
            controller_real_work_benchmark_output_contract_payload
        ),
        "controller_real_work_benchmark_success_rubric": (
            controller_real_work_benchmark_success_rubric_payload
        ),
        "controller_real_work_benchmark_operator_value": (
            controller_real_work_benchmark_operator_value_payload
        ),
        "controller_real_work_benchmark_selection_rationale": (
            controller_real_work_benchmark_selection_rationale_payload
        ),
        "controller_real_work_benchmark_execution": (
            controller_real_work_benchmark_execution_payload
        ),
        "controller_real_work_benchmark_execution_history": (
            controller_real_work_benchmark_execution_history_payload
        ),
        "controller_real_work_benchmark_result_summary": (
            controller_real_work_benchmark_result_summary_payload
        ),
        "controller_real_work_benchmark_output_inventory": (
            controller_real_work_benchmark_output_inventory_payload
        ),
        "controller_real_work_benchmark_rubric_result": (
            controller_real_work_benchmark_rubric_result_payload
        ),
        "controller_real_work_benchmark_closure": (
            controller_real_work_benchmark_closure_payload
        ),
        "controller_real_work_benchmark_closure_history": (
            controller_real_work_benchmark_closure_history_payload
        ),
        "controller_real_work_benchmark_repeatability": (
            controller_real_work_benchmark_repeatability_payload
        ),
        "controller_real_work_benchmark_repeatability_history": (
            controller_real_work_benchmark_repeatability_history_payload
        ),
        "controller_real_work_benchmark_promotion_readiness": (
            controller_real_work_benchmark_promotion_readiness_payload
        ),
        "controller_real_work_benchmark_unresolved_bundle": (
            controller_real_work_benchmark_unresolved_bundle_payload
        ),
        "controller_real_work_benchmark_delta_from_rc46": (
            controller_real_work_benchmark_delta_from_rc46_payload
        ),
        "controller_real_work_benchmark_decision_packet": (
            controller_real_work_benchmark_decision_packet_payload
        ),
        "controller_real_work_benchmark_decision_packet_history": (
            controller_real_work_benchmark_decision_packet_history_payload
        ),
        "controller_real_work_benchmark_promotion_decision": (
            controller_real_work_benchmark_promotion_decision_payload
        ),
        "controller_real_work_benchmark_review_gate_packet": (
            controller_real_work_benchmark_review_gate_packet_payload
        ),
        "controller_real_work_benchmark_final_blocker": (
            controller_real_work_benchmark_final_blocker_payload
        ),
        "controller_real_work_benchmark_decision_rationale": (
            controller_real_work_benchmark_decision_rationale_payload
        ),
        "controller_real_work_benchmark_next_action": (
            controller_real_work_benchmark_next_action_payload
        ),
        "controller_real_work_benchmark_review_packet": (
            controller_real_work_benchmark_review_packet_payload
        ),
        "controller_real_work_benchmark_review_packet_history": (
            controller_real_work_benchmark_review_packet_history_payload
        ),
        "controller_real_work_benchmark_operator_review_decision": (
            controller_real_work_benchmark_operator_review_decision_payload
        ),
        "controller_real_work_benchmark_promotion_outcome": (
            controller_real_work_benchmark_promotion_outcome_payload
        ),
        "controller_real_work_benchmark_operator_confirmation_state": (
            controller_real_work_benchmark_operator_confirmation_state_payload
        ),
        "controller_real_work_benchmark_review_evidence": (
            controller_real_work_benchmark_review_evidence_payload
        ),
        "controller_real_work_benchmark_review_checklist": (
            controller_real_work_benchmark_review_checklist_payload
        ),
        "controller_real_work_benchmark_review_confirmation": (
            controller_real_work_benchmark_review_confirmation_payload
        ),
        "controller_real_work_benchmark_review_confirmation_history": (
            controller_real_work_benchmark_review_confirmation_history_payload
        ),
        "controller_real_work_benchmark_review_decision_source": (
            controller_real_work_benchmark_review_decision_source_payload
        ),
        "controller_real_work_benchmark_promotion_outcome_confirmed": (
            controller_real_work_benchmark_promotion_outcome_confirmed_payload
        ),
        "controller_real_work_benchmark_review_resolution_summary": (
            controller_real_work_benchmark_review_resolution_summary_payload
        ),
        "controller_real_work_benchmark_confirmation_gap": (
            controller_real_work_benchmark_confirmation_gap_payload
        ),
        "effective_operator_session_valid": len(session_errors) == 0,
        "effective_operator_session_errors": session_errors,
        "effective_operator_session": session,
        "last_launch_event": last_launch_event,
        "last_launch_plan": latest_launch_plan,
    }
